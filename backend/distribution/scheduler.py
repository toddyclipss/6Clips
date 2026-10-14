# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Distribution Scheduler: bounded worker clock, injectable time, retry budgeting, and truth table transitions."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional, Tuple

from backend.distribution.account_boundary import AccountBoundaryManager
from backend.distribution.job_store import DistributionJobStore
from backend.distribution.models import (
    DistributionJob,
    DistributionStatus,
    PlatformAccount,
    PublishedReceiptV1,
)
from backend.distribution.transport import (
    DistributionTransportPort,
    ProductionLiveTransport,
    TransportError,
)

logger = logging.getLogger(__name__)


class TimeProvider:
    """Injectable time provider enabling deterministic test execution."""
    def __init__(self, fixed_time: Optional[datetime] = None):
        self._fixed_time = fixed_time

    def now(self) -> datetime:
        if self._fixed_time is not None:
            return self._fixed_time
        return datetime.now(timezone.utc)

    def set_time(self, t: datetime) -> None:
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        self._fixed_time = t

    def advance(self, delta: timedelta) -> None:
        current = self.now()
        self._fixed_time = current + delta


class DistributionScheduler:
    """Orchestrates job execution, retry budgeting, and state transitions."""

    def __init__(
        self,
        store: DistributionJobStore,
        transport: Optional[DistributionTransportPort] = None,
        time_provider: Optional[TimeProvider] = None,
        account_resolver: Optional[Callable[[str, str], Optional[PlatformAccount]]] = None,
    ):
        self.store = store
        self.transport = transport or ProductionLiveTransport()
        self.clock = time_provider or TimeProvider()
        self.account_resolver = account_resolver or self._default_account_resolver
        # Automatically recover any in-flight jobs on worker startup
        self.recover_in_flight_jobs()

    def recover_in_flight_jobs(self) -> int:
        """
        Durable restart recovery:
        Finds any jobs left in DISPATCHING state from a previous process crash/restart.
        Reconciles with confirmed receipts or marks as FAILED_RETRYABLE for idempotent recovery.
        """
        recovered_count = 0
        jobs = self.store.list_jobs()
        receipts = {r.job_id: r for r in self.store.list_receipts()}

        for job in jobs:
            if job.status == DistributionStatus.DISPATCHING:
                recovered_count += 1
                if job.job_id in receipts:
                    receipt = receipts[job.job_id]
                    job.status = DistributionStatus.PUBLISHED_VERIFIED
                    job.receipt_id = receipt.receipt_id
                    job.remote_post_id = receipt.remote_post_id
                    job.remote_post_url = receipt.remote_post_url
                    job.error_message = "Recovered verified published post following worker restart."
                else:
                    job.status = DistributionStatus.FAILED_RETRYABLE
                    job.error_code = "WORKER_RESTARTED_DURING_DISPATCH"
                    job.error_message = "Worker process terminated during dispatch; queued for idempotent retry."
                job.updated_at = self.clock.now().isoformat()
                self.store.save_job(job)
        return recovered_count

    def get_daemon_status(self) -> Dict[str, Any]:
        """
        Exposes accurate worker daemon status and explicit offline host limitation.
        """
        all_jobs = self.store.list_jobs()
        active = sum(
            1 for j in all_jobs
            if j.status in (DistributionStatus.SCHEDULED, DistributionStatus.READY_TO_SCHEDULE)
        )
        return {
            "daemon_active": True,
            "clock_now": self.clock.now().isoformat(),
            "scheduled_jobs_count": active,
            "offline_limitation_notice": (
                "ViralMint operates as a local application. Scheduled distribution jobs "
                "cannot publish when the host computer is turned off, asleep, or when the "
                "backend service is stopped. Queued jobs will be evaluated on the next daemon cycle."
            ),
        }

    @staticmethod
    def _default_account_resolver(account_id: str, platform: str) -> Optional[PlatformAccount]:
        """Default resolver returns a disconnected account structure."""
        return AccountBoundaryManager.evaluate_account_readiness(
            account_id=account_id,
            platform=platform,
            is_connected=False,
        )

    async def schedule_job(
        self,
        job: DistributionJob,
        account: PlatformAccount,
    ) -> DistributionJob:
        """Validate readiness and enqueue job for scheduled release."""
        # 0. Check idempotency: if job with matching idempotency key already exists, return it
        if job.idempotency_key:
            existing = self.store.get_job_by_idempotency_key(job.idempotency_key)
            if existing:
                logger.info("DistributionScheduler | Reusing existing job for idempotency key: %s", job.idempotency_key)
                return existing

        # 1. Enforce account can publish
        AccountBoundaryManager.assert_account_can_publish(account)

        now = self.clock.now()
        sched_dt = datetime.fromisoformat(job.scheduled_time_utc.replace("Z", "+00:00"))

        if sched_dt <= now:
            # Ready for immediate dispatch on next tick
            job.status = DistributionStatus.READY_TO_SCHEDULE
        else:
            job.status = DistributionStatus.SCHEDULED

        job.updated_at = now.isoformat()
        self.store.save_job(job)
        return job

    async def cancel_job(
        self,
        job_id: str,
        reason: str = "User cancelled",
        user_id: Optional[str] = None,
    ) -> DistributionJob:
        """
        Cancel a scheduled or pending job.
        Note: Canceling a scheduled job does NOT imply a remote post was deleted if already published.
        """
        job = self.store.get_job(job_id)
        if not job:
            raise ValueError(f"Job '{job_id}' not found.")

        if user_id and job.user_id != user_id and user_id != "admin":
            raise ValueError(f"Unauthorized: Job '{job_id}' belongs to another creator tenant.")

        if job.status == DistributionStatus.PUBLISHED_VERIFIED:
            raise ValueError("Cannot cancel a job that has already been verified published.")

        job.status = DistributionStatus.CANCELLED
        job.error_message = f"Cancelled: {reason}"
        job.updated_at = self.clock.now().isoformat()
        self.store.save_job(job)
        return job

    async def retry_job(
        self,
        job_id: str,
        user_id: Optional[str] = None,
    ) -> DistributionJob:
        """Retry a failed or blocked job if allowed."""
        job = self.store.get_job(job_id)
        if not job:
            raise ValueError(f"Job '{job_id}' not found.")

        if user_id and job.user_id != user_id and user_id != "admin":
            raise ValueError(f"Unauthorized: Job '{job_id}' belongs to another creator tenant.")

        if job.status not in (DistributionStatus.FAILED_RETRYABLE, DistributionStatus.BLOCKED, DistributionStatus.UNCERTAIN):
            raise ValueError(f"Job in state {job.status.value} cannot be manually retried.")

        job.status = DistributionStatus.READY_TO_SCHEDULE
        job.retry_count = 0
        job.error_code = None
        job.error_message = None
        job.updated_at = self.clock.now().isoformat()
        self.store.save_job(job)
        return job


    async def process_tick(self) -> Dict[str, Any]:
        """
        Single bounded clock tick:
        Evaluates scheduled jobs whose scheduled_time <= now and executes dispatch.
        """
        now = self.clock.now()
        now_iso = now.isoformat()

        all_jobs = self.store.list_jobs()
        due_jobs = []

        for j in all_jobs:
            if j.status in (
                DistributionStatus.READY_TO_SCHEDULE,
                DistributionStatus.SCHEDULED,
                DistributionStatus.FAILED_RETRYABLE,
            ):
                sched_dt = datetime.fromisoformat(j.scheduled_time_utc.replace("Z", "+00:00"))
                if sched_dt <= now:
                    due_jobs.append(j)

        results = {
            "tick_time": now_iso,
            "due_count": len(due_jobs),
            "dispatched": 0,
            "published": 0,
            "failed": 0,
        }

        for job in due_jobs:
            await self._dispatch_single_job(job)
            results["dispatched"] += 1
            if job.status == DistributionStatus.PUBLISHED_VERIFIED:
                results["published"] += 1
            elif job.status in (DistributionStatus.FAILED_RETRYABLE, DistributionStatus.BLOCKED):
                results["failed"] += 1

        return results

    async def _dispatch_single_job(self, job: DistributionJob) -> None:
        """Dispatch a single due job through the transport with error classification."""
        now = self.clock.now()

        # Re-check account readiness
        account = self.account_resolver(job.account_id, job.platform)
        if not account or not account.can_publish:
            job.status = DistributionStatus.BLOCKED
            job.error_code = "ACCOUNT_NOT_READY"
            job.error_message = (
                f"Account '{job.account_id}' is not in READY state (state: {account.state.value if account else 'UNKNOWN'})."
            )
            job.updated_at = now.isoformat()
            self.store.save_job(job)
            return

        # Transition to DISPATCHING
        job.status = DistributionStatus.DISPATCHING
        job.last_attempt_at = now.isoformat()
        job.updated_at = now.isoformat()
        self.store.save_job(job)

        try:
            # GT-28: Uncertain remote send reconciliation.
            # If a remote_post_id was already assigned during an earlier dispatch attempt,
            # query remote platform for verified receipt first before attempting duplicate re-upload.
            if job.remote_post_id:
                logger.info(
                    "Job %s has existing remote_post_id %s; verifying remote post before attempting re-dispatch (GT-28).",
                    job.job_id,
                    job.remote_post_id,
                )
                existing_rcpt = await self.transport.verify_post_receipt(job, account, job.remote_post_id)
                if existing_rcpt:
                    job.status = DistributionStatus.PUBLISHED_VERIFIED
                    job.receipt_id = existing_rcpt.receipt_id
                    self.store.save_receipt(existing_rcpt)
                    job.updated_at = self.clock.now().isoformat()
                    self.store.save_job(job)
                    return
                else:
                    # GT-28: Remote send status is UNCERTAIN. An upload was attempted and remote_post_id was assigned,
                    # but remote receipt verification is currently unconfirmed.
                    # Transition to UNCERTAIN to prevent duplicate remote upload and wait for provider resolution.
                    job.status = DistributionStatus.UNCERTAIN
                    job.error_code = "REMOTE_SEND_UNCERTAIN"
                    job.error_message = (
                        f"Remote post confirmation uncertain for post_id '{job.remote_post_id}'. "
                        "Awaiting provider receipt confirmation before retry to prevent duplicate posting (GT-28)."
                    )
                    job.updated_at = self.clock.now().isoformat()
                    self.store.save_job(job)
                    return

            success, post_id, post_url, err_msg = await self.transport.dispatch_post(job, account)
            if not success or not post_id:
                raise TransportError("DISPATCH_FAILED", err_msg or "Remote provider rejected upload", is_retryable=True)

            job.remote_post_id = post_id
            job.remote_post_url = post_url

            # Crucial truth table step: A local accepted call or HTTP 202 is NOT a remote published post.
            # Only verified provider receipt yields PUBLISHED_VERIFIED.
            receipt = await self.transport.verify_post_receipt(job, account, post_id)
            if receipt:
                job.status = DistributionStatus.PUBLISHED_VERIFIED
                job.receipt_id = receipt.receipt_id
                self.store.save_receipt(receipt)
            else:
                # Still in unverified/processing stage remotely
                logger.info("Job %s dispatched (post_id: %s) but not yet verified published.", job.job_id, post_id)
                # Keep in DISPATCHING or marked as waiting verification
                job.status = DistributionStatus.DISPATCHING
                job.error_message = "Upload acknowledged by platform; awaiting final post verification."

        except TransportError as te:
            logger.warning("Transport error for job %s: %s (retryable=%s)", job.job_id, te.message, te.is_retryable)
            self._handle_job_failure(job, te.code, te.message, te.is_retryable)
        except Exception as e:
            logger.exception("Unexpected error dispatching job %s: %s", job.job_id, e)
            self._handle_job_failure(job, "INTERNAL_ERROR", str(e), is_retryable=False)

        job.updated_at = self.clock.now().isoformat()
        self.store.save_job(job)

    def _handle_job_failure(
        self,
        job: DistributionJob,
        code: str,
        message: str,
        is_retryable: bool,
    ) -> None:
        """Classify failure and apply retry backoff budget."""
        job.error_code = code
        job.error_message = message

        if is_retryable and job.retry_count < job.max_retries:
            job.retry_count += 1
            job.status = DistributionStatus.FAILED_RETRYABLE
            job.error_category = "RETRYABLE"
            # Exponential backoff: 2^retry_count minutes
            delay_minutes = 2 ** job.retry_count
            next_sched = self.clock.now() + timedelta(minutes=delay_minutes)
            job.scheduled_time_utc = next_sched.isoformat()
        else:
            job.status = DistributionStatus.BLOCKED
            job.error_category = "FATAL"
