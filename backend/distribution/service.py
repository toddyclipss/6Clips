# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Distribution Service: high-level facade orchestrating approval, SEO, fan-out, and scheduling."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from backend.distribution.account_boundary import AccountBoundaryManager
from backend.distribution.eligibility import ReleaseEligibilityVerifier
from backend.distribution.job_store import DistributionJobStore
from backend.distribution.models import (
    ApprovalReceipt,
    DistributionJob,
    DistributionStatus,
    PlatformAccount,
    PlatformSEOMetadata,
    PublishedReceiptV1,
)
from backend.distribution.scheduler import DistributionScheduler, TimeProvider
from backend.distribution.seo_adapter import SEOAdapter
from backend.distribution.transport import DistributionTransportPort

logger = logging.getLogger(__name__)


class DistributionService:
    """Service facade for Phase 10 distribution workflows."""

    def __init__(
        self,
        store: Optional[DistributionJobStore] = None,
        transport: Optional[DistributionTransportPort] = None,
        time_provider: Optional[TimeProvider] = None,
    ):
        self.store = store or DistributionJobStore()
        self.time_provider = time_provider or TimeProvider()
        self.scheduler = DistributionScheduler(
            store=self.store,
            transport=transport,
            time_provider=self.time_provider,
        )

    def create_approval_receipt(
        self,
        output_id: str,
        project_id: str,
        project_revision: int,
        artifact_sha256: str,
        approved_by: str,
        consent_for_external_publish: bool = True,
        secret: str = "6clips-distribution-secret",
    ) -> ApprovalReceipt:
        """Create and sign an explicit, immutable editorial approval receipt."""
        receipt = ApprovalReceipt(
            output_id=output_id,
            project_id=project_id,
            project_revision=project_revision,
            artifact_sha256=artifact_sha256,
            approved_by=approved_by,
            approved_at_utc=self.time_provider.now().isoformat(),
            consent_for_external_publish=consent_for_external_publish,
        )
        receipt.signature = receipt.compute_signature(secret)
        return receipt

    def check_release_eligibility(
        self,
        file_path_str: str,
        expected_user_id: str,
        actual_user_id: str,
        current_project_revision: int,
        approval_receipt: Optional[ApprovalReceipt],
        permitted_uses: List[str],
        target_platform: str,
        technical_checks_status: str = "PASS",
        contract_checks_status: str = "PASS",
        secret: str = "6clips-distribution-secret",
    ) -> Dict[str, Any]:
        """Verify release eligibility before scheduling or distributing."""
        return ReleaseEligibilityVerifier.verify_eligibility(
            file_path_str=file_path_str,
            expected_user_id=expected_user_id,
            actual_user_id=actual_user_id,
            current_project_revision=current_project_revision,
            approval_receipt=approval_receipt,
            permitted_uses=permitted_uses,
            target_platform=target_platform,
            technical_checks_status=technical_checks_status,
            contract_checks_status=contract_checks_status,
            secret=secret,
        )

    async def schedule_distribution(
        self,
        output_id: str,
        project_id: str,
        project_revision: int,
        artifact_path: str,
        approval_receipt: ApprovalReceipt,
        platform: str,
        account: PlatformAccount,
        seo_metadata: PlatformSEOMetadata,
        scheduled_time_utc: str,
        user_id: str = "local",
        timezone_str: str = "UTC",
        permitted_uses: Optional[List[str]] = None,
    ) -> DistributionJob:
        """Schedule a single platform distribution job with full release verification."""
        # 1. Verify eligibility
        perms = permitted_uses or ["social_distribution", "platform_publish"]
        eligibility = self.check_release_eligibility(
            file_path_str=artifact_path,
            expected_user_id=user_id,
            actual_user_id=user_id,
            current_project_revision=project_revision,
            approval_receipt=approval_receipt,
            permitted_uses=perms,
            target_platform=platform,
        )

        # 2. Validate SEO metadata against platform constraints
        sanitized_seo = SEOAdapter.validate_metadata(seo_metadata)

        # 3. Create job
        job = DistributionJob(
            user_id=user_id,
            output_id=output_id,
            project_id=project_id,
            project_revision=project_revision,
            artifact_path=eligibility["artifact_path"],
            artifact_sha256=eligibility["artifact_sha256"],
            approval_receipt_id=approval_receipt.approval_id,
            platform=platform,
            account_id=account.account_id,
            seo_metadata=sanitized_seo,
            scheduled_time_utc=scheduled_time_utc,
            timezone=timezone_str,
        )

        # 4. Schedule via scheduler
        return await self.scheduler.schedule_job(job, account)

    async def schedule_multi_platform_fan_out(
        self,
        output_id: str,
        project_id: str,
        project_revision: int,
        artifact_path: str,
        approval_receipt: ApprovalReceipt,
        platform_configs: List[Dict[str, Any]],
        user_id: str = "local",
        permitted_uses: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Fan out an approved output to multiple platform distribution jobs.
        Isolates failures per platform so one failure does not prevent scheduling for other platforms.
        """
        created_jobs: List[DistributionJob] = []
        errors: List[Dict[str, Any]] = []

        for cfg in platform_configs:
            platform = cfg["platform"]
            account = cfg["account"]
            seo_metadata = cfg["seo_metadata"]
            scheduled_time = cfg.get("scheduled_time_utc", self.time_provider.now().isoformat())
            tz = cfg.get("timezone", "UTC")

            try:
                job = await self.schedule_distribution(
                    output_id=output_id,
                    project_id=project_id,
                    project_revision=project_revision,
                    artifact_path=artifact_path,
                    approval_receipt=approval_receipt,
                    platform=platform,
                    account=account,
                    seo_metadata=seo_metadata,
                    scheduled_time_utc=scheduled_time,
                    user_id=user_id,
                    timezone_str=tz,
                    permitted_uses=permitted_uses,
                )
                created_jobs.append(job)
            except Exception as e:
                logger.warning("Failed to schedule fan-out for %s: %s", platform, e)
                errors.append({"platform": platform, "error": str(e)})

        status = "COMPLETE" if not errors else ("PARTIAL" if created_jobs else "FAILED")
        return {
            "status": status,
            "jobs": created_jobs,
            "errors": errors,
            "total_requested": len(platform_configs),
            "total_scheduled": len(created_jobs),
        }

    def get_published_receipt(self, receipt_id: str) -> Optional[PublishedReceiptV1]:
        """Fetch confirmed publishing receipt for downstream consumers (e.g. Analytics Agent)."""
        return self.store.get_receipt(receipt_id)

    def list_published_receipts(self, project_id: Optional[str] = None) -> List[PublishedReceiptV1]:
        """List confirmed publishing receipts."""
        return self.store.list_receipts(project_id=project_id)

    def get_daemon_status(self) -> Dict[str, Any]:
        """Return daemon status and offline limitation warning."""
        return self.scheduler.get_daemon_status()

    def recover_in_flight_jobs(self) -> int:
        """Trigger worker restart recovery for any in-flight dispatching jobs."""
        return self.scheduler.recover_in_flight_jobs()
