# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
OAAS Queue Truth: Distinct lifecycle states, crash recovery, and offline host truth.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

from backend.oaas_provider_receipts.receipt_store import OAASReceiptStore, ProviderReceiptV2
from backend.oaas_provider_receipts.provider_client import ProviderDispatcher, ProviderDispatchResult

logger = logging.getLogger(__name__)


class PublishQueueState(str, Enum):
    """Accurate, non-conflated publishing states."""
    DRAFT = "DRAFT"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    PENDING_CREDENTIALS = "PENDING_CREDENTIALS"
    READY_TO_SCHEDULE = "READY_TO_SCHEDULE"
    SCHEDULED = "SCHEDULED"
    DISPATCHING = "DISPATCHING"
    PROVIDER_ACCEPTED = "PROVIDER_ACCEPTED"
    PUBLISHED_VERIFIED = "PUBLISHED_VERIFIED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


class JobLifecycleError(Exception):
    """Raised when an illegal state transition is attempted."""
    pass


class OAASPublishJob(BaseModel):
    """Durable publishing job representation."""
    job_id: str = Field(default_factory=lambda: f"job_{uuid4().hex[:12]}")
    project_id: str
    project_revision: int
    output_id: str
    artifact_path: str
    artifact_sha256: str
    approval_receipt_id: str
    approval_signature: str
    platform: str
    account_id: str
    title: str
    description: str = ""
    scheduled_time_utc: str
    state: PublishQueueState = PublishQueueState.DRAFT
    idempotency_key: str = Field(default_factory=lambda: f"idem_{uuid4().hex}")
    retry_count: int = 0
    max_retries: int = 3
    last_attempt_at_utc: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    receipt_id: Optional[str] = None
    created_at_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class OAASQueueManager:
    """Manages the lifecycle of publication jobs with truthful transitions and crash recovery."""

    def __init__(
        self,
        receipt_store: Optional[OAASReceiptStore] = None,
        dispatcher: Optional[ProviderDispatcher] = None,
    ):
        self.receipt_store = receipt_store or OAASReceiptStore()
        self.dispatcher = dispatcher or ProviderDispatcher()
        self._jobs: Dict[str, OAASPublishJob] = {}
        self._idempotency_index: Dict[str, str] = {}

    def get_daemon_status(self) -> Dict[str, Any]:
        """Truthful daemon status exposing local host limits."""
        queued = sum(
            1 for j in self._jobs.values()
            if j.state in (PublishQueueState.SCHEDULED, PublishQueueState.READY_TO_SCHEDULE)
        )
        return {
            "daemon_active": True,
            "current_utc": datetime.now(timezone.utc).isoformat(),
            "queued_jobs": queued,
            "verified_published": self.receipt_store.count_verified_receipts(),
            "offline_host_truth": (
                "ViralMint operates on the user's local machine. When the computer is asleep, "
                "powered off, or the application is closed, scheduled dispatches are paused. "
                "Any due jobs will be evaluated immediately upon the next application startup."
            ),
        }

    def create_job(
        self,
        project_id: str,
        project_revision: int,
        output_id: str,
        artifact_path: str,
        artifact_sha256: str,
        approval_receipt_id: str,
        approval_signature: str,
        platform: str,
        account_id: str,
        title: str,
        scheduled_time_utc: str,
        idempotency_key: Optional[str] = None,
    ) -> OAASPublishJob:
        idem = idempotency_key or f"idem_{uuid4().hex}"
        if idem in self._idempotency_index:
            existing_id = self._idempotency_index[idem]
            return self._jobs[existing_id]

        # Check credentials before setting READY_TO_SCHEDULE
        cred_status = self.dispatcher.get_credential_status(platform, account_id)
        if cred_status != "CONNECTED":
            initial_state = PublishQueueState.PENDING_CREDENTIALS
        else:
            initial_state = PublishQueueState.READY_TO_SCHEDULE

        job = OAASPublishJob(
            project_id=project_id,
            project_revision=project_revision,
            output_id=output_id,
            artifact_path=artifact_path,
            artifact_sha256=artifact_sha256,
            approval_receipt_id=approval_receipt_id,
            approval_signature=approval_signature,
            platform=platform,
            account_id=account_id,
            title=title,
            scheduled_time_utc=scheduled_time_utc,
            idempotency_key=idem,
            state=initial_state,
        )
        self._jobs[job.job_id] = job
        self._idempotency_index[idem] = job.job_id
        return job

    def recover_crash(self) -> int:
        """
        Idempotent wake/restart recovery:
        Reconciles any jobs that were left in DISPATCHING state during an unexpected restart.
        """
        recovered = 0
        for job in self._jobs.values():
            if job.state == PublishQueueState.DISPATCHING:
                recovered += 1
                receipt = self.receipt_store.get_receipt_by_job(job.job_id)
                if receipt:
                    job.state = PublishQueueState.PUBLISHED_VERIFIED
                    job.receipt_id = receipt.receipt_id
                    job.error_message = "Recovered verified publication after system restart."
                else:
                    job.state = PublishQueueState.FAILED_RETRYABLE
                    job.error_code = "PROCESS_RESTARTED_DURING_DISPATCH"
                    job.error_message = "Application process restarted while job was dispatching. Enqueued for safe retry."
                job.updated_at_utc = datetime.now(timezone.utc).isoformat()
        return recovered

    async def execute_job(self, job_id: str) -> OAASPublishJob:
        """Dispatch a single due job through the provider dispatcher."""
        job = self._jobs.get(job_id)
        if not job:
            raise JobLifecycleError(f"Job '{job_id}' not found.")

        if job.state not in (PublishQueueState.READY_TO_SCHEDULE, PublishQueueState.SCHEDULED, PublishQueueState.FAILED_RETRYABLE):
            raise JobLifecycleError(f"Job '{job_id}' is in state {job.state.value} and cannot be dispatched.")

        now_utc = datetime.now(timezone.utc).isoformat()
        job.state = PublishQueueState.DISPATCHING
        job.last_attempt_at_utc = now_utc
        job.updated_at_utc = now_utc

        result: ProviderDispatchResult = await self.dispatcher.dispatch(
            platform=job.platform,
            account_id=job.account_id,
            artifact_path=job.artifact_path,
            expected_artifact_sha256=job.artifact_sha256,
            title=job.title,
            description=job.description,
            idempotency_key=job.idempotency_key,
        )

        job.updated_at_utc = datetime.now(timezone.utc).isoformat()

        if result.success and result.status == "CONFIRMED":
            # Issue verified receipt
            receipt = ProviderReceiptV2(
                job_id=job.job_id,
                platform=job.platform,
                account_id=job.account_id,
                project_id=job.project_id,
                project_revision=job.project_revision,
                artifact_sha256=job.artifact_sha256,
                approval_signature=job.approval_signature,
                provider_post_id=result.provider_post_id or "",
                provider_post_url=result.provider_post_url or "",
                provider_timestamp_utc=result.provider_timestamp or now_utc,
                provider_metadata=result.raw_response,
            )
            self.receipt_store.register_receipt(receipt)
            job.state = PublishQueueState.PUBLISHED_VERIFIED
            job.receipt_id = receipt.receipt_id
            job.error_code = None
            job.error_message = None
        elif result.status == "PENDING_CREDENTIALS":
            job.state = PublishQueueState.PENDING_CREDENTIALS
            job.error_code = result.error_code
            job.error_message = result.error_message
        elif result.status == "BLOCKED":
            job.state = PublishQueueState.BLOCKED
            job.error_code = result.error_code
            job.error_message = result.error_message
        else:
            job.retry_count += 1
            if job.retry_count < job.max_retries:
                job.state = PublishQueueState.FAILED_RETRYABLE
            else:
                job.state = PublishQueueState.BLOCKED
            job.error_code = result.error_code or "DISPATCH_FAILED"
            job.error_message = result.error_message or "Remote dispatch failed."

        return job
