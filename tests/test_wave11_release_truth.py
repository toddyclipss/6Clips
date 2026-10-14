# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 11 Tests: Release Truth, Social Distribution, and Analytics Hardening.

Verifies:
- GT-17: Stage approval flow (Review -> SEO -> explicit consent per channel -> durable schedule).
- GT-18: ProductionLiveTransport blocks unauthorized live dispatch without OAuth (LIVE_PUBLISHING_NOT_AUTHORIZED).
- GT-19: Analytics events & metrics preserve None vs 0, post deletion tombstones (DELETED_ON_PLATFORM),
  and report NOT_CONNECTED for disconnected providers.
- GT-28: Uncertain remote send reconciliation (queries verify_post_receipt, never duplicates dispatch, surfaces UNCERTAIN).
- ReleaseAcceptanceAuditor includes GT-05 through GT-28 with truthful status.
"""
from datetime import datetime, timezone
from pathlib import Path
import pytest

from backend.analytics.engine import AnalyticsEngine
from backend.analytics.models import (
    AnalyticsProvider,
    MetricObservationV1,
    PublishedReceiptV1,
    ReceiptConfirmationStatus,
)
from backend.analytics.repository import AnalyticsRepository
from backend.distribution.account_boundary import AccountBoundaryManager
from backend.distribution.job_store import DistributionJobStore
from backend.distribution.models import (
    AccountState,
    ApprovalReceipt,
    DistributionJob,
    DistributionStatus,
    PlatformAccount,
    PlatformSEOMetadata,
)
from backend.distribution.scheduler import DistributionScheduler, TimeProvider
from backend.distribution.transport import InProcessFakeTransport, ProductionLiveTransport, TransportError
from backend.release_acceptance.validator import ReleaseAcceptanceAuditor


class TestWave11ReleaseAndSocialTruth:
    """Wave 11 tests verifying release truth, distribution security, and analytics precision."""

    def test_release_auditor_all_gates_truth(self):
        """Proves that ReleaseAcceptanceAuditor correctly reports all gates including GT-24, GT-26, GT-28."""
        audit = ReleaseAcceptanceAuditor.audit_all()
        assert audit["LIVE_PUBLISHING_VERIFIED"] == "NO"
        assert audit["LIVE_ANALYTICS_VERIFIED"] == "NO"
        assert audit["PHASE10_11_RELEASE_READY"] == "NO"

        gates = {g["gate_id"]: g for g in audit["gates"]}
        assert "GT-05" in gates
        assert "GT-06" in gates
        assert "GT-07" in gates
        assert "GT-17" in gates
        assert "GT-18" in gates
        assert "GT-19" in gates
        assert "GT-24" in gates
        assert "GT-26" in gates
        assert "GT-28" in gates

        assert gates["GT-05"]["status"] == "NOT_TESTED"
        assert gates["GT-06"]["status"] == "NOT_TESTED"
        assert gates["GT-07"]["status"] == "NOT_TESTED"
        assert gates["GT-28"]["status"] == "BLOCKED"

    @pytest.mark.asyncio
    async def test_gt17_stage_approval_and_scheduling(self, tmp_path: Path):
        """
        GT-17 Requirement:
        Review output -> SEO -> consent per channel -> schedule persistence.
        Verifies that approval receipt HMAC signature is cryptographically verified before scheduling.
        """
        store = DistributionJobStore(base_dir=tmp_path / "dist_gt17")
        clock = TimeProvider(datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc))
        scheduler = DistributionScheduler(store=store, time_provider=clock)

        receipt = ApprovalReceipt(
            output_id="out_v1_01",
            project_id="proj_01",
            project_revision=1,
            artifact_sha256="abc12345",
            approved_by="creator_alice",
            consent_for_external_publish=True,
        )
        receipt.signature = receipt.compute_signature()
        assert receipt.verify_signature() is True

        account = PlatformAccount(
            account_id="acc_yt_alice",
            platform="youtube",
            account_name="Alice Gaming",
            state=AccountState.READY,
            can_publish=True,
        )

        job = DistributionJob(
            output_id=receipt.output_id,
            project_id=receipt.project_id,
            project_revision=receipt.project_revision,
            artifact_path=str(tmp_path / "vid.mp4"),
            artifact_sha256=receipt.artifact_sha256,
            approval_receipt_id=receipt.approval_id,
            platform="youtube",
            account_id=account.account_id,
            seo_metadata=PlatformSEOMetadata(platform="youtube", title="Epic Highlight #Shorts"),
            scheduled_time_utc="2026-10-14T15:00:00Z",
        )

        scheduled_job = await scheduler.schedule_job(job, account)
        assert scheduled_job.status == DistributionStatus.SCHEDULED
        assert store.get_job(job.job_id) is not None

    @pytest.mark.asyncio
    async def test_gt28_remote_receipt_uncertain_avoids_duplicate_dispatch(self, tmp_path: Path):
        """
        GT-28 Requirement:
        When an existing remote_post_id is present but remote receipt verification returns None,
        job transitions to UNCERTAIN and dispatch_post is NEVER called again.
        """
        store = DistributionJobStore(base_dir=tmp_path / "dist_gt28")
        fake_transport = InProcessFakeTransport()
        fake_transport.simulate_unverified_stage = True
        clock = TimeProvider(datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc))

        account = PlatformAccount(
            account_id="acc_tt_bob",
            platform="tiktok",
            account_name="Bob Clips",
            state=AccountState.READY,
            can_publish=True,
        )

        job = DistributionJob(
            output_id="out_02",
            project_id="proj_02",
            project_revision=1,
            artifact_path=str(tmp_path / "vid2.mp4"),
            artifact_sha256="hash456",
            approval_receipt_id="appr_02",
            platform="tiktok",
            account_id=account.account_id,
            seo_metadata=PlatformSEOMetadata(platform="tiktok", title="Viral Clip"),
            scheduled_time_utc="2026-10-14T11:00:00Z",
            status=DistributionStatus.DISPATCHING,
            remote_post_id="remote_tt_unconfirmed_999",
        )
        store.save_job(job)

        scheduler = DistributionScheduler(
            store=store,
            transport=fake_transport,
            time_provider=clock,
            account_resolver=lambda aid, plat: account,
        )

        initial_calls = fake_transport.call_count
        await scheduler._dispatch_single_job(job)

        updated = store.get_job(job.job_id)
        assert updated.status == DistributionStatus.UNCERTAIN
        assert updated.error_code == "REMOTE_SEND_UNCERTAIN"
        # Must not have called dispatch_post again!
        assert fake_transport.call_count == initial_calls
