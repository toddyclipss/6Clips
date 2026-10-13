# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Distribution Transport Port and Adapters: enforces truth table and separates live vs test dispatch."""
from __future__ import annotations

import abc
import logging
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4
from datetime import datetime, timezone

from backend.distribution.models import (
    DistributionJob,
    PlatformAccount,
    PublishedReceiptV1,
)

logger = logging.getLogger(__name__)


class TransportError(Exception):
    """Raised when remote dispatch fails or transport is blocked."""
    def __init__(self, code: str, message: str, is_retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.is_retryable = is_retryable


class DistributionTransportPort(abc.ABC):
    """Abstract port for remote platform distribution dispatch."""

    @abc.abstractmethod
    async def dispatch_post(
        self,
        job: DistributionJob,
        account: PlatformAccount,
    ) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
        """
        Attempt publication to remote platform.
        Returns: (success, remote_post_id, remote_post_url, error_message)
        """
        pass

    @abc.abstractmethod
    async def verify_post_receipt(
        self,
        job: DistributionJob,
        account: PlatformAccount,
        remote_post_id: str,
    ) -> Optional[PublishedReceiptV1]:
        """
        Verify that remote platform has definitively committed the post.
        Returns PublishedReceiptV1 if confirmed, or None if unconfirmed.
        """
        pass


class ProductionLiveTransport(DistributionTransportPort):
    """
    Production transport enforcing truthful remote publication.
    In the current offline/disconnected configuration, live publishing is strictly blocked.
    Accurately reports LIVE_PUBLISHING_VERIFIED: NO and refuses unverified side effects.
    """

    async def dispatch_post(
        self,
        job: DistributionJob,
        account: PlatformAccount,
    ) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
        # Enforce account readiness and connectivity
        if not account.can_publish:
            raise TransportError(
                "ACCOUNT_NOT_READY",
                f"Cannot dispatch post: Account '{account.account_id}' for platform '{job.platform}' "
                f"is in state '{account.state.value}'. LIVE_PUBLISHING_VERIFIED: NO",
                is_retryable=False,
            )

        # Enforce that unauthorized live execution is blocked
        raise TransportError(
            "LIVE_PUBLISHING_NOT_AUTHORIZED",
            f"Live external publishing to {job.platform} is disabled by default in this environment. "
            f"Live OAuth credentials are not authorized for account '{account.account_id}'. "
            f"LIVE_PUBLISHING_VERIFIED: NO",
            is_retryable=False,
        )

    async def verify_post_receipt(
        self,
        job: DistributionJob,
        account: PlatformAccount,
        remote_post_id: str,
    ) -> Optional[PublishedReceiptV1]:
        # Production path strictly refuses fake receipts as proof of a real remote post
        if remote_post_id.startswith("fake_"):
            logger.warning(
                "ProductionLiveTransport | Rejected fake post ID in production: %s (LIVE_PUBLISHING_VERIFIED: NO)",
                remote_post_id,
            )
            return None
        return None



class InProcessFakeTransport(DistributionTransportPort):
    """
    Deterministic, in-process test transport for automated test execution.
    Allows simulating network timeouts, HTTP 202 unverified states, and verified receipts.
    """

    def __init__(self):
        self.dispatched_jobs: Dict[str, DistributionJob] = {}
        self.simulate_network_failure: bool = False
        self.simulate_unverified_stage: bool = False
        self.call_count: int = 0

    async def dispatch_post(
        self,
        job: DistributionJob,
        account: PlatformAccount,
    ) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
        self.call_count += 1
        if self.simulate_network_failure:
            raise TransportError(
                "SIMULATED_NETWORK_TIMEOUT",
                "Simulated connection reset or 503 Service Unavailable",
                is_retryable=True,
            )

        post_id = f"fake_{job.platform}_{uuid4().hex[:10]}"
        post_url = f"https://{job.platform}.com/post/{post_id}"
        self.dispatched_jobs[job.job_id] = job

        return True, post_id, post_url, None

    async def verify_post_receipt(
        self,
        job: DistributionJob,
        account: PlatformAccount,
        remote_post_id: str,
    ) -> Optional[PublishedReceiptV1]:
        if self.simulate_unverified_stage:
            # Emulates intermediate state where remote server accepted upload but has not finished encoding/confirming
            return None

        return PublishedReceiptV1(
            job_id=job.job_id,
            output_id=job.output_id,
            project_id=job.project_id,
            project_revision=job.project_revision,
            artifact_sha256=job.artifact_sha256,
            platform=job.platform,
            account_id=account.account_id,
            account_handle=account.handle,
            remote_post_id=remote_post_id,
            remote_post_url=f"https://{job.platform}.com/post/{remote_post_id}",
            published_at_utc=datetime.now(timezone.utc).isoformat(),
            verified_status="CONFIRMED",
            provenance={
                "transport": "InProcessFakeTransport",
                "environment": "test",
                "approval_receipt_id": job.approval_receipt_id,
            },
        )
