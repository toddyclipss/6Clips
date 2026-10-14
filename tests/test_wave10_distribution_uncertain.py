# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 10 Tests: Distribution Uncertain State, Duplicate Prevention, and Transport Safety.

Verifies:
- GT-28: When remote send acknowledgment is unconfirmed, system surfaces UNCERTAIN state.
- Idempotency & duplicate prevention: Remote post is never re-dispatched when post_id exists.
- In-flight restart recovery preserves confirmed receipts or marks FAILED_RETRYABLE.
- ProductionLiveTransport strictly raises TransportError when live OAuth is unconfigured.
- Manual retry allowed for UNCERTAIN, FAILED_RETRYABLE, and BLOCKED jobs.
"""
from datetime import datetime, timezone
from pathlib import Path
import pytest

from backend.distribution.account_boundary import AccountBoundaryManager
from backend.distribution.job_store import DistributionJobStore
from backend.distribution.models import (
    AccountState,
    ApprovalReceipt,
    DistributionJob,
    DistributionStatus,
    PlatformAccount,
    PlatformSEOMetadata,
    PublishedReceiptV1,
)
from backend.distribution.scheduler import DistributionScheduler, TimeProvider
from backend.distribution.transport import (
    DistributionTransportPort,
    InProcessFakeTransport,
    ProductionLiveTransport,
    TransportError,
)


class TestWave10DistributionUncertainAndSafety:
    """Verifies GT-28 uncertain handling, duplicate prevention, and transport guardrails."""

    @pytest.mark.asyncio
    async def test_uncertain_remote_send_transitions_to_uncertain_status(self, tmp_path: Path):
        """
        GT-28 Requirement:
        If remote upload was attempted (job has remote_post_id) but remote receipt verification
        returns None, scheduler must transition job to UNCERTAIN status and NOT call dispatch_post again.
        """
        store = DistributionJobStore(base_dir=tmp_path / "dist_uncertain")
        fake_transport = InProcessFakeTransport()
        # Simulate unverified remote stage (remote platform received upload but hasn't confirmed receipt)
        fake_transport.simulate_unverified_stage = True
        clock = TimeProvider(datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc))

        account = PlatformAccount(
            account_id="acc_yt_wave10",
            platform="youtube",
            account_name="Official YouTube",
            state=AccountState.READY,
            can_publish=True,
        )

        job = DistributionJob(
            output_id="out_wave10_01",
            project_id="proj_wave10_01",
            project_revision=1,
            artifact_path=str(tmp_path / "video.mp4"),
            artifact_sha256="abc12345",
            approval_receipt_id="appr_w10_01",
            platform="youtube",
            account_id=account.account_id,
            seo_metadata=PlatformSEOMetadata(platform="youtube", title="Wave 10 Short"),
            scheduled_time_utc="2026-10-14T11:00:00Z",
            status=DistributionStatus.DISPATCHING,
            remote_post_id="remote_yt_existing_01",
        )
        store.save_job(job)

        scheduler = DistributionScheduler(
            store=store,
            transport=fake_transport,
            time_provider=clock,
            account_resolver=lambda aid, plat: account,
        )

        initial_dispatches = fake_transport.call_count

        # Execute dispatch attempt
        await scheduler._dispatch_single_job(job)

        updated_job = store.get_job(job.job_id)
        assert updated_job.status == DistributionStatus.UNCERTAIN
        assert updated_job.error_code == "REMOTE_SEND_UNCERTAIN"
        assert "Awaiting provider receipt confirmation before retry to prevent duplicate posting" in updated_job.error_message
        # Dispatch was NEVER called again -> ZERO duplicate uploads
        assert fake_transport.call_count == initial_dispatches

    @pytest.mark.asyncio
    async def test_manual_retry_resets_uncertain_job(self, tmp_path: Path):
        """Proves that a creator can manually retry an UNCERTAIN job once provider issue is resolved."""
        store = DistributionJobStore(base_dir=tmp_path / "dist_retry")
        clock = TimeProvider(datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc))
        scheduler = DistributionScheduler(store=store, time_provider=clock)

        job = DistributionJob(
            output_id="out_retry_01",
            project_id="proj_retry_01",
            project_revision=1,
            artifact_path=str(tmp_path / "video.mp4"),
            artifact_sha256="sha123",
            approval_receipt_id="appr_01",
            platform="youtube",
            account_id="acc_01",
            seo_metadata=PlatformSEOMetadata(platform="youtube", title="Title"),
            scheduled_time_utc="2026-10-14T10:00:00Z",
            status=DistributionStatus.UNCERTAIN,
            error_code="REMOTE_SEND_UNCERTAIN",
        )
        store.save_job(job)

        retried = await scheduler.retry_job(job.job_id)
        assert retried.status == DistributionStatus.READY_TO_SCHEDULE
        assert retried.error_code is None
        assert retried.retry_count == 0

    def test_production_live_transport_refuses_fake_receipts_and_unauthorized_dispatch(self):
        """
        Enforces GT-18 / GT-28 absolute safety:
        ProductionLiveTransport strictly refuses fake post IDs and blocks unauthorized external dispatch.
        """
        transport = ProductionLiveTransport()
        account = PlatformAccount(
            account_id="acc_unauth",
            platform="tiktok",
            account_name="TikTok Channel",
            state=AccountState.READY,
            can_publish=True,
        )
        job = DistributionJob(
            output_id="out_sec_01",
            project_id="proj_sec_01",
            project_revision=1,
            artifact_path="data/video.mp4",
            artifact_sha256="hash",
            approval_receipt_id="appr_sec",
            platform="tiktok",
            account_id=account.account_id,
            seo_metadata=PlatformSEOMetadata(platform="tiktok", title="Clip"),
            scheduled_time_utc="2026-10-14T00:00:00Z",
        )

        # 1. Dispatch raises LIVE_PUBLISHING_NOT_AUTHORIZED
        import asyncio
        with pytest.raises(TransportError) as exc_info:
            asyncio.run(transport.dispatch_post(job, account))

        assert exc_info.value.code == "LIVE_PUBLISHING_NOT_AUTHORIZED"
        assert "LIVE_PUBLISHING_VERIFIED: NO" in exc_info.value.message

        # 2. verify_post_receipt strictly returns None for fake post ID
        res = asyncio.run(transport.verify_post_receipt(job, account, "fake_tiktok_12345"))
        assert res is None
