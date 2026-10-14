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
from backend.distribution.egress_audit import check_outbound_allowlist, record_egress_event

logger = logging.getLogger(__name__)

_PLATFORM_HOSTS: Dict[str, str] = {
    "youtube": "www.googleapis.com",
    "tiktok": "open.tiktokapis.com",
    "instagram": "graph.facebook.com",
    "x": "api.twitter.com",
}

_PLATFORM_PATHS: Dict[str, str] = {
    "youtube": "/upload/youtube/v3/videos",
    "tiktok": "/v2/post/publish/video/init/",
    "instagram": "/v19.0/{ig_user_id}/media",
    "x": "/2/tweets",
}


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
        target_host = _PLATFORM_HOSTS.get(job.platform.lower(), "unknown_platform")
        target_path = _PLATFORM_PATHS.get(job.platform.lower(), "/publish/post")

        # Check outbound allowlist
        if not check_outbound_allowlist(job.platform, target_host):
            record_egress_event(
                component="distribution",
                destination_host=target_host,
                sanitized_path=target_path,
                method="POST",
                endpoint_class="BLOCKED_WITH_REASON",
                trigger_authorization="ALLOWLIST_REJECTION",
                outcome_status="BLOCKED",
                correlation_id=job.job_id,
                callsite="ProductionLiveTransport.dispatch_post",
                extra_metadata={"error_code": "DESTINATION_HOST_NOT_ALLOWLISTED", "job_id": job.job_id, "platform": job.platform},
            )
            raise TransportError(
                "DESTINATION_HOST_NOT_ALLOWLISTED",
                f"Destination host '{target_host}' is not in the official outbound allowlist for platform '{job.platform}'.",
                is_retryable=False,
            )

        # Enforce account readiness and connectivity
        if not account.can_publish:
            record_egress_event(
                component="distribution",
                destination_host=target_host,
                sanitized_path=target_path,
                method="POST",
                endpoint_class="BLOCKED_WITH_REASON",
                trigger_authorization="DISCONNECTED_ACCOUNT",
                outcome_status="BLOCKED",
                correlation_id=job.job_id,
                callsite="ProductionLiveTransport.dispatch_post",
                extra_metadata={"error_code": "ACCOUNT_NOT_READY", "job_id": job.job_id, "platform": job.platform},
            )
            raise TransportError(
                "ACCOUNT_NOT_READY",
                f"Cannot dispatch post: Account '{account.account_id}' for platform '{job.platform}' "
                f"is in state '{account.state.value}'. LIVE_PUBLISHING_VERIFIED: NO",
                is_retryable=False,
            )

        # Enforce that unauthorized live execution is blocked
        record_egress_event(
            component="distribution",
            destination_host=target_host,
            sanitized_path=target_path,
            method="POST",
            endpoint_class="BLOCKED_WITH_REASON",
            trigger_authorization="UNAUTHORIZED_IDLE",
            outcome_status="BLOCKED",
            correlation_id=job.job_id,
            callsite="ProductionLiveTransport.dispatch_post",
            extra_metadata={"error_code": "LIVE_PUBLISHING_NOT_AUTHORIZED", "job_id": job.job_id, "platform": job.platform},
        )
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
        target_host = _PLATFORM_HOSTS.get(job.platform.lower(), "unknown_platform")
        target_path = f"/verify/{remote_post_id}"

        # Production path strictly refuses fake receipts as proof of a real remote post
        if remote_post_id.startswith("fake_"):
            logger.warning(
                "ProductionLiveTransport | Rejected fake post ID in production: %s (LIVE_PUBLISHING_VERIFIED: NO)",
                remote_post_id,
            )
            record_egress_event(
                component="distribution",
                destination_host=target_host,
                sanitized_path=target_path,
                method="GET",
                endpoint_class="BLOCKED_WITH_REASON",
                trigger_authorization="FAKE_RECEIPT_REJECTION",
                outcome_status="BLOCKED",
                correlation_id=job.job_id,
                callsite="ProductionLiveTransport.verify_post_receipt",
                extra_metadata={"error_code": "FAKE_RECEIPT_REJECTED", "job_id": job.job_id, "platform": job.platform},
            )
            return None

        record_egress_event(
            component="distribution",
            destination_host=target_host,
            sanitized_path=target_path,
            method="GET",
            endpoint_class="READ_ONLY_HEALTH_DISCOVERY",
            trigger_authorization="DISCONNECTED_SAFEGUARD",
            outcome_status="NOT_VERIFIED",
            correlation_id=job.job_id,
            callsite="ProductionLiveTransport.verify_post_receipt",
            extra_metadata={"job_id": job.job_id, "platform": job.platform},
        )
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
