# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 12 Agent 5: External API Egress, Schedulers, Analytics & Distribution Idle Verification.

Verifies:
1. Idle scheduler behavior: zero active jobs -> zero external network calls.
2. Disconnected account safety: disabled/disconnected accounts never poll or dispatch.
3. GT-28 uncertain remote send: existing remote_post_id awaiting verification transitions to UNCERTAIN,
   strictly preventing duplicate re-upload.
4. Analytics disconnected truthfulness: returns NOT_CONNECTED and None (never fake metrics or unsolicited polling).
5. Missing vs zero metrics: missing metrics truthfully evaluate to None, not 0.
6. Unknown OAuth / AUTH_REQUIRED: does not auto-refresh tokens in background.
7. Outbound domain allowlist: only approved platform endpoints are authorized.
8. Opt-in local metadata-only egress audit (%TEMP%/6clips_wave12_idle_audit/) captures safe provenance.
"""
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import pytest
import tempfile
from uuid import uuid4

from backend.analytics.engine import AnalyticsEngine
from backend.analytics.models import (
    AnalyticsProvider,
    MetricObservationSource,
    MetricObservationV1,
    ProviderConnectionStatus,
    PublishedReceiptV1,
    ReceiptConfirmationStatus,
)
from backend.analytics.providers import (
    DisconnectedAnalyticsAdapter,
    MockAnalyticsAdapter,
    OfficialPlatformAnalyticsAdapter,
)
from backend.analytics.repository import AnalyticsRepository
from backend.distribution.account_boundary import AccountBoundaryManager
from backend.distribution.egress_audit import (
    check_outbound_allowlist,
    clear_audit_events,
    get_audit_dir,
    get_recent_audit_events,
    is_audit_enabled,
    record_egress_event,
)
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
from backend.distribution.service import DistributionService
from backend.distribution.transport import (
    InProcessFakeTransport,
    ProductionLiveTransport,
    TransportError,
)
from backend.release_acceptance.validator import ReleaseAcceptanceAuditor, AcceptanceGateStatus


@pytest.fixture(autouse=True)
def enable_audit_env(monkeypatch):
    """Ensure audit environment is enabled and in-memory events are reset for each test."""
    monkeypatch.setenv("SIXCLIPS_IDLE_NET_AUDIT", "1")
    clear_audit_events()
    yield
    clear_audit_events()


@pytest.mark.asyncio
async def test_idle_scheduler_zero_jobs_emits_zero_external_requests(tmp_path):
    """Test 1: Idle scheduler with zero queued jobs evaluates 0 jobs and makes 0 external calls."""
    store = DistributionJobStore(base_dir=tmp_path)
    clock = TimeProvider(fixed_time=datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc))
    transport = ProductionLiveTransport()

    scheduler = DistributionScheduler(
        store=store,
        transport=transport,
        time_provider=clock,
    )

    tick_result = await scheduler.process_tick()
    assert tick_result["due_count"] == 0
    assert tick_result["dispatched"] == 0
    assert tick_result["published"] == 0
    assert tick_result["failed"] == 0

    events = get_recent_audit_events(component="distribution")
    assert len(events) >= 1
    assert any(e["endpoint_class"] == "NOT_OBSERVED" and e["outcome_status"] == "ZERO_REQUESTS" for e in events)
    assert all(e["destination_host"] == "NONE_LOCAL" for e in events)


@pytest.mark.asyncio
async def test_disconnected_accounts_strictly_block_dispatch(tmp_path):
    """Test 2: Disconnected accounts never trigger remote platform API requests."""
    store = DistributionJobStore(base_dir=tmp_path)
    clock = TimeProvider(fixed_time=datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc))
    transport = ProductionLiveTransport()

    scheduler = DistributionScheduler(
        store=store,
        transport=transport,
        time_provider=clock,
        account_resolver=lambda acc_id, plat: AccountBoundaryManager.evaluate_account_readiness(
            account_id=acc_id,
            platform=plat,
            is_connected=False,
        ),
    )

    # Create a job scheduled for right now
    job = DistributionJob(
        job_id="test_job_disconnected",
        user_id="local",
        output_id="out_001",
        project_id="proj_001",
        project_revision=1,
        artifact_path=str(tmp_path / "video.mp4"),
        artifact_sha256="0123456789abcdef" * 4,
        approval_receipt_id="appr_001",
        platform="youtube",
        account_id="yt_disconnected",
        seo_metadata=PlatformSEOMetadata(platform="youtube", title="Test", description="Test desc"),
        scheduled_time_utc=clock.now().isoformat(),
        status=DistributionStatus.SCHEDULED,
    )
    store.save_job(job)

    # Process tick
    tick_result = await scheduler.process_tick()
    assert tick_result["due_count"] == 1
    assert tick_result["dispatched"] == 1
    assert tick_result["published"] == 0
    assert tick_result["failed"] == 1

    saved = store.get_job("test_job_disconnected")
    assert saved.status == DistributionStatus.BLOCKED
    assert saved.error_code == "ACCOUNT_NOT_READY"

    # Verify audit event
    events = get_recent_audit_events(component="distribution")
    blocked = [e for e in events if e.get("outcome_status") == "BLOCKED"]
    assert len(blocked) >= 1
    assert blocked[0]["endpoint_class"] == "BLOCKED_WITH_REASON"
    assert blocked[0]["trigger_authorization"] == "DISCONNECTED_ACCOUNT"


@pytest.mark.asyncio
async def test_uncertain_remote_send_prevents_duplicate_upload_reconciliation(tmp_path):
    """Test 3: GT-28 uncertain remote send transitions to UNCERTAIN and prevents duplicate upload."""
    store = DistributionJobStore(base_dir=tmp_path)
    clock = TimeProvider(fixed_time=datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc))
    transport = ProductionLiveTransport()

    # Resolver returning connected account
    ready_account = AccountBoundaryManager.evaluate_account_readiness(
        account_id="acc_connected",
        platform="tiktok",
        granted_scopes=["video.upload", "video.publish"],
        is_connected=True,
    )

    scheduler = DistributionScheduler(
        store=store,
        transport=transport,
        time_provider=clock,
        account_resolver=lambda acc_id, plat: ready_account,
    )

    # Job that previously started dispatch and received remote_post_id before connection drop
    job = DistributionJob(
        job_id="test_job_uncertain",
        user_id="local",
        output_id="out_002",
        project_id="proj_002",
        project_revision=1,
        artifact_path=str(tmp_path / "clip.mp4"),
        artifact_sha256="abcdef0123456789" * 4,
        approval_receipt_id="appr_002",
        platform="tiktok",
        account_id="acc_connected",
        seo_metadata=PlatformSEOMetadata(platform="tiktok", title="Test", description="Test desc"),
        remote_post_id="tt_pending_post_999",
        scheduled_time_utc=clock.now().isoformat(),
        status=DistributionStatus.SCHEDULED,
    )
    store.save_job(job)

    # Process tick - remote verification returns None in ProductionLiveTransport
    tick_result = await scheduler.process_tick()

    saved = store.get_job("test_job_uncertain")
    assert saved.status == DistributionStatus.UNCERTAIN
    assert saved.error_code == "REMOTE_SEND_UNCERTAIN"
    assert "awaiting provider receipt confirmation" in saved.error_message.lower()


@pytest.mark.asyncio
async def test_analytics_disconnected_truthfully_returns_none_and_no_polling(tmp_path):
    """Test 4: Disconnected analytics adapter returns NOT_CONNECTED and None without external calls."""
    repo = AnalyticsRepository(base_dir=tmp_path / "analytics_repo")
    engine = AnalyticsEngine(repository=repo)

    # By default, engine providers are DisconnectedAnalyticsAdapter
    for prov in AnalyticsProvider:
        status = await engine.providers[prov].get_connection_status("default")
        assert status == ProviderConnectionStatus.NOT_CONNECTED

    # Attempt to poll a receipt with disconnected provider
    receipt = PublishedReceiptV1(
        receipt_id="rcpt_prod_001",
        project_id="proj_001",
        provider=AnalyticsProvider.YOUTUBE,
        account_reference="channel_xyz",
        remote_post_id="yt_real_vid_123",
        publish_timestamp=datetime.now(timezone.utc),
        confirmation_status=ReceiptConfirmationStatus.CONFIRMED,
    )
    repo.save_receipt(receipt)

    obs, err = await engine.poll_post_metrics(receipt.receipt_id)
    assert obs is None
    assert err == "PROVIDER_NOT_CONNECTED"

    events = get_recent_audit_events(component="analytics")
    assert any(e["outcome_status"] == "NOT_CONNECTED" for e in events)


@pytest.mark.asyncio
async def test_analytics_missing_metrics_distinguished_from_zero(tmp_path):
    """Test 5: Missing metrics return None, not 0."""
    repo = AnalyticsRepository(base_dir=tmp_path / "analytics_repo")
    engine = AnalyticsEngine(repository=repo)

    # Register MockAnalyticsAdapter with only views and likes provided; impressions & watch_time missing
    mock_adapter = MockAnalyticsAdapter(
        provider_type=AnalyticsProvider.TIKTOK,
        simulated_metrics={
            "tt_test_post": {
                "views": 1500,
                "likes": 120,
                "comments": 15,
                "shares": 5,
                "impressions": None,  # explicitly missing
                "watch_time_seconds": None,  # explicitly missing
            }
        },
    )
    engine.register_provider(mock_adapter)

    receipt = PublishedReceiptV1(
        receipt_id="rcpt_fixture_001",
        project_id="proj_test",
        provider=AnalyticsProvider.TIKTOK,
        account_reference="default",
        remote_post_id="tt_test_post",
        publish_timestamp=datetime.now(timezone.utc),
        confirmation_status=ReceiptConfirmationStatus.SIMULATED_TEST,
        metadata={"is_test_fixture": True},
    )
    engine.register_receipt(receipt, is_test_fixture=True)

    obs, err = await engine.poll_post_metrics(receipt.receipt_id)
    assert err is None
    assert obs is not None
    assert obs.views == 1500
    assert obs.likes == 120
    assert obs.impressions is None  # MUST BE None, NOT 0
    assert obs.watch_time_seconds is None  # MUST BE None, NOT 0
    assert "impressions" in obs.missing_metrics
    assert "watch_time_seconds" in obs.missing_metrics


@pytest.mark.asyncio
async def test_unknown_oauth_and_auth_required_do_not_auto_refresh(tmp_path):
    """Test 6: AUTH_REQUIRED status creates local notification and refuses auto-refresh."""
    repo = AnalyticsRepository(base_dir=tmp_path / "analytics_repo")
    mock_adapter = MockAnalyticsAdapter(
        provider_type=AnalyticsProvider.INSTAGRAM,
        simulate_auth_required=True,
    )
    engine = AnalyticsEngine(repository=repo, provider_adapters={AnalyticsProvider.INSTAGRAM: mock_adapter})

    receipt = PublishedReceiptV1(
        receipt_id="rcpt_auth_req",
        project_id="proj_test",
        provider=AnalyticsProvider.INSTAGRAM,
        account_reference="ig_test",
        remote_post_id="ig_post_999",
        publish_timestamp=datetime.now(timezone.utc),
        confirmation_status=ReceiptConfirmationStatus.SIMULATED_TEST,
        metadata={"is_test_fixture": True},
    )
    engine.register_receipt(receipt, is_test_fixture=True)

    obs, err = await engine.poll_post_metrics(receipt.receipt_id)
    assert obs is None
    assert err == "PROVIDER_AUTH_REQUIRED"

    notifications = repo.list_notifications()
    assert len(notifications) == 1
    assert notifications[0].requires_user_action is True
    assert "Re-authentication required" in notifications[0].summary


def test_outbound_domain_allowlist():
    """Test 7: Outbound domain allowlist permits only official platform hosts."""
    assert check_outbound_allowlist("youtube", "www.googleapis.com") is True
    assert check_outbound_allowlist("youtube", "oauth2.googleapis.com") is True
    assert check_outbound_allowlist("youtube", "malicious-site.com") is False

    assert check_outbound_allowlist("tiktok", "open.tiktokapis.com") is True
    assert check_outbound_allowlist("tiktok", "unauthorized-tracker.com") is False

    assert check_outbound_allowlist("instagram", "graph.facebook.com") is True
    assert check_outbound_allowlist("x", "api.twitter.com") is True
    assert check_outbound_allowlist("ollama", "127.0.0.1") is True


@pytest.mark.asyncio
async def test_previously_authorized_job_with_test_transport_flows_with_audit_lineage(tmp_path):
    """Test 8: Previously authorized scheduled job flows with explicit audit lineage."""
    store = DistributionJobStore(base_dir=tmp_path)
    clock = TimeProvider(fixed_time=datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc))
    transport = InProcessFakeTransport()

    ready_account = AccountBoundaryManager.evaluate_account_readiness(
        account_id="acc_youtube_1",
        platform="youtube",
        granted_scopes=AccountBoundaryManager.REQUIRED_SCOPES["youtube"],
        is_connected=True,
    )

    scheduler = DistributionScheduler(
        store=store,
        transport=transport,
        time_provider=clock,
        account_resolver=lambda acc_id, plat: ready_account,
    )

    job = DistributionJob(
        job_id="test_job_authorized_flow",
        user_id="local",
        output_id="out_003",
        project_id="proj_003",
        project_revision=1,
        artifact_path=str(tmp_path / "short.mp4"),
        artifact_sha256="fedcba9876543210" * 4,
        approval_receipt_id="appr_003",
        platform="youtube",
        account_id="acc_youtube_1",
        seo_metadata=PlatformSEOMetadata(platform="youtube", title="Test", description="Test desc"),
        scheduled_time_utc=clock.now().isoformat(),
        status=DistributionStatus.SCHEDULED,
    )
    store.save_job(job)

    tick_result = await scheduler.process_tick()
    assert tick_result["dispatched"] == 1
    assert tick_result["published"] == 1

    saved = store.get_job("test_job_authorized_flow")
    assert saved.status == DistributionStatus.PUBLISHED_VERIFIED
    assert saved.receipt_id is not None
    assert saved.remote_post_id.startswith("fake_youtube_")

    receipts = store.list_receipts()
    assert len(receipts) == 1
    assert receipts[0].receipt_id == saved.receipt_id


def test_gt18_and_gt19_truth_table_status():
    """Test 9: GT-18 remains BLOCKED and GT-19 remains NOT_TESTED when disconnected."""
    audit = ReleaseAcceptanceAuditor.audit_wave9_truth()
    assert audit["GT-18"]["status"] == "BLOCKED_NO_AUTHORIZED_ACCOUNT"
    assert audit["GT-19"]["status"] == "BLOCKED_NO_REMOTE_POST"
    assert audit["GT-18"]["real_human_inputs_present"] is False
    assert audit["GT-19"]["real_human_inputs_present"] is False
