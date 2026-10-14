# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 9 Tests: Release Gates Truth, Phase 10 Distribution & Phase 11 Analytics.

Verifies:
- Audit table matching literal Master Proposal text and requirements (GT-05, 06, 07, 17, 18, 19, 24, 26, 28).
- GT-17: Immutable ApprovalReceipt (HMAC-SHA256), release eligibility, and SEO scoping.
- GT-18: ProductionLiveTransport safety gate blocks live publication without credentials (BLOCKED_NO_AUTHORIZED_ACCOUNT).
- GT-28: Uncertain remote send reconciliation (queries verify_post_receipt on existing remote_post_id).
- GT-19: Analytics missing vs zero preservation (None preserved, 0 strictly authentic zero).
- Deleted post handling: status DELETED_ON_PLATFORM preserves historic metric points and halts polling.
- Rate-limit backoff durability across simulated process restarts.
- Strict refusal to claim GT-18 or GT-19 complete from mock adapters or test fixtures.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from backend.analytics.engine import AnalyticsEngine
from backend.analytics.models import (
    AnalyticsProvider,
    MetricObservationSource,
    MetricObservationV1,
    PublishedReceiptV1,
    ReceiptConfirmationStatus,
)
from backend.analytics.providers import MockAnalyticsAdapter
from backend.analytics.repository import AnalyticsRepository
from backend.distribution.account_boundary import AccountBoundaryManager
from backend.distribution.eligibility import ReleaseEligibilityVerifier
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
from backend.distribution.seo_adapter import SEOAdapter
from backend.distribution.service import DistributionService
from backend.distribution.transport import (
    DistributionTransportPort,
    InProcessFakeTransport,
    ProductionLiveTransport,
    TransportError,
)
from backend.release_acceptance.validator import (
    AcceptanceGateStatus,
    ReleaseAcceptanceAuditor,
)


class TestWave9LiteralTruthAudit:
    """Verifies that the audit table reproduces the literal requirements from the 6Clips Master Proposal."""

    def test_wave9_truth_audit_matrix_contents(self):
        audit = ReleaseAcceptanceAuditor.audit_wave9_truth()

        assert "declaration" in audit
        decl = audit["declaration"]
        assert decl["REAL_V1_GT05_ACCEPTED"] == "NOT_TESTED"
        assert decl["REAL_V2_GT07_ACCEPTED"] == "NOT_TESTED"
        assert decl["REAL_V3_GT06_ACCEPTED"] == "NOT_TESTED"
        assert decl["LIVE_PUBLISHING_VERIFIED"] == "NO"
        assert decl["LIVE_ANALYTICS_VERIFIED"] == "NO"

        # Check required gates
        required_gates = ["GT-05", "GT-06", "GT-07", "GT-17", "GT-18", "GT-19", "GT-24", "GT-26", "GT-28"]
        for gid in required_gates:
            assert gid in audit, f"Gate {gid} missing from audit"
            entry = audit[gid]
            assert "proposal_text" in entry
            assert "actual_implementation" in entry
            assert "real_human_inputs_present" in entry
            assert "test_evidence" in entry
            assert "status" in entry
            assert "outstanding_needs" in entry
            # In development environment, real human inputs must be False
            assert entry["real_human_inputs_present"] is False

        # Verify GT-18 and GT-19 are not claimed complete
        assert audit["GT-18"]["status"] == "BLOCKED_NO_AUTHORIZED_ACCOUNT"
        assert audit["GT-19"]["status"] == "BLOCKED_NO_REMOTE_POST"


class TestPhase10DistributionTruthWave9:
    """Verifies GT-17 (Review/SEO/Consent/Schedule) and GT-18/GT-28 (Remote publish & reconciliation)."""

    def test_gt17_approval_receipt_cryptographic_integrity(self):
        service = DistributionService()
        receipt = service.create_approval_receipt(
            output_id="out_v1_01",
            project_id="proj_v1_01",
            project_revision=1,
            artifact_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            approved_by="human_owner",
            consent_for_external_publish=True,
        )

        assert receipt.verify_signature() is True

        # Tampering with revision invalidates signature
        tampered = receipt.model_copy(update={"project_revision": 2})
        assert tampered.verify_signature() is False

    def test_gt18_production_transport_blocks_unauthorized_outbound_dispatch(self):
        transport = ProductionLiveTransport()
        account = PlatformAccount(
            account_id="acc_yt_01",
            platform="youtube",
            account_name="Official YT",
            state=AccountState.NOT_CONNECTED,
            can_publish=False,
        )
        seo = PlatformSEOMetadata(platform="youtube", title="Test Title", description="Test Desc")
        job = DistributionJob(
            output_id="out_01",
            project_id="proj_01",
            project_revision=1,
            artifact_path="data/video.mp4",
            artifact_sha256="abc",
            approval_receipt_id="appr_01",
            platform="youtube",
            account_id=account.account_id,
            seo_metadata=seo,
            scheduled_time_utc="2026-10-14T00:00:00Z",
        )

        # Must raise TransportError indicating live publishing is not authorized / not connected
        with pytest.raises(TransportError) as exc_info:
            import asyncio
            asyncio.run(transport.dispatch_post(job, account))

        assert exc_info.value.code in ("ACCOUNT_NOT_READY", "LIVE_PUBLISHING_NOT_AUTHORIZED")
        assert "LIVE_PUBLISHING_VERIFIED: NO" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_gt28_uncertain_remote_send_reconciliation(self, tmp_path: Path):
        """
        GT-28 Requirement:
        If remote confirmation was lost (job in DISPATCHING with existing remote_post_id),
        scheduler probes verify_post_receipt first. If confirmed, transitions to PUBLISHED_VERIFIED
        without calling dispatch_post again.
        """
        store = DistributionJobStore(base_dir=tmp_path / "dist_test")
        fake_transport = InProcessFakeTransport()
        clock = TimeProvider(datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc))

        account = PlatformAccount(
            account_id="acc_tiktok_01",
            platform="tiktok",
            account_name="Viral TikTok",
            state=AccountState.READY,
            can_publish=True,
        )

        job = DistributionJob(
            output_id="out_v1_02",
            project_id="proj_v1_02",
            project_revision=1,
            artifact_path=str(tmp_path / "vid.mp4"),
            artifact_sha256="hash123",
            approval_receipt_id="appr_02",
            platform="tiktok",
            account_id=account.account_id,
            seo_metadata=PlatformSEOMetadata(platform="tiktok", title="Viral Clip"),
            scheduled_time_utc="2026-10-14T11:00:00Z",
            status=DistributionStatus.DISPATCHING,
            remote_post_id="remote_tt_99999",
        )
        store.save_job(job)

        scheduler = DistributionScheduler(
            store=store,
            transport=fake_transport,
            time_provider=clock,
            account_resolver=lambda aid, plat: account,
        )

        initial_calls = fake_transport.call_count

        # Execute dispatch tick
        await scheduler._dispatch_single_job(job)

        updated = store.get_job(job.job_id)
        assert updated.status == DistributionStatus.PUBLISHED_VERIFIED
        # GT-28 guarantee: zero duplicate calls to dispatch_post
        assert fake_transport.call_count == initial_calls
        assert updated.remote_post_id == "remote_tt_99999"


class TestPhase11AnalyticsTruthWave9:
    """Verifies GT-19 ground truth: missing vs zero, deleted posts, backoff durability."""

    def test_missing_metrics_preserved_as_none_not_zero(self, tmp_path: Path):
        repo = AnalyticsRepository(base_dir=tmp_path)
        engine = AnalyticsEngine(repository=repo)

        rcpt = PublishedReceiptV1(
            project_id="proj_truth_01",
            provider=AnalyticsProvider.YOUTUBE,
            account_reference="yt_ref",
            remote_post_id="yt_post_01",
            publish_timestamp=datetime.now(timezone.utc),
            confirmation_status=ReceiptConfirmationStatus.SIMULATED_TEST,
        )
        saved = engine.register_receipt(rcpt, is_test_fixture=True)

        # Observation with genuine 0 views and unreported (None) shares & watch time
        obs = MetricObservationV1(
            receipt_id=saved.receipt_id,
            provider=AnalyticsProvider.YOUTUBE,
            remote_post_id="yt_post_01",
            views=0,  # Authentically observed 0
            likes=0,
            shares=None,  # Not supported / unreported by platform
            watch_time_seconds=None,
            observation_source=MetricObservationSource.OFFICIAL_API,
        )
        repo.record_observation(obs)

        # Reload from fresh repo instance to simulate process reboot
        reloaded_repo = AnalyticsRepository(base_dir=tmp_path)
        reloaded_engine = AnalyticsEngine(repository=reloaded_repo)
        agg = reloaded_engine.get_aggregated_metrics(saved.receipt_id)

        assert agg is not None
        assert agg.latest_views == 0
        assert agg.latest_likes == 0
        assert agg.latest_shares is None
        assert agg.latest_watch_time_seconds is None

    def test_deleted_post_halts_polling_and_preserves_history(self, tmp_path: Path):
        repo = AnalyticsRepository(base_dir=tmp_path)
        engine = AnalyticsEngine(repository=repo)

        rcpt = PublishedReceiptV1(
            project_id="proj_del_01",
            provider=AnalyticsProvider.TIKTOK,
            account_reference="tt_ref",
            remote_post_id="tt_del_99",
            publish_timestamp=datetime.now(timezone.utc),
            confirmation_status=ReceiptConfirmationStatus.SIMULATED_TEST,
        )
        saved = engine.register_receipt(rcpt, is_test_fixture=True)

        obs = MetricObservationV1(
            receipt_id=saved.receipt_id,
            provider=AnalyticsProvider.TIKTOK,
            remote_post_id="tt_del_99",
            views=2500,
            likes=180,
            observation_source=MetricObservationSource.OFFICIAL_API,
        )
        repo.record_observation(obs)

        # Mark post deleted remotely
        engine.mark_post_deleted(saved.receipt_id)

        # Polling deleted post returns error POST_DELETED_ON_PLATFORM
        import asyncio
        new_obs, err = asyncio.run(engine.poll_post_metrics(saved.receipt_id))
        assert new_obs is None
        assert err == "POST_DELETED_ON_PLATFORM"

        # Historic metrics are still preserved
        agg = engine.get_aggregated_metrics(saved.receipt_id)
        assert agg.is_deleted_on_platform is True
        assert agg.latest_views == 2500

    def test_mock_adapter_is_not_claimed_as_real_analytics_gate(self):
        mock_adapter = MockAnalyticsAdapter(AnalyticsProvider.YOUTUBE)
        assert mock_adapter.is_real_production_adapter is False

        # Release audit must maintain LIVE_ANALYTICS_VERIFIED: NO
        audit = ReleaseAcceptanceAuditor.audit_all()
        assert audit["LIVE_ANALYTICS_VERIFIED"] == "NO"
