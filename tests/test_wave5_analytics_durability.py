# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 5 Analytics Durability Test Suite:
- Restart recovery of receipts, observations, and notifications from isolated disk storage
- Strict rejection of fake_ receipts in production ingest
- Strict rejection of unconfirmed receipts (SCHEDULED, DISPATCHING, etc.)
- Distinction between observed zeroes and missing metrics (None != 0)
- Snapshot deduplication within the same sampling window
- Multi-tenant isolation (creator_id partitioned)
- Durable rate-limit backoff state recovery
- Creative feedback sample-size confidence guards and opt-in requirement
- Event notification outbox token safety and idempotency
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from backend.analytics.engine import AnalyticsEngine
from backend.analytics.feedback import CreativeFeedbackEngine
from backend.analytics.models import (
    AnalyticsEventType,
    AnalyticsEventNotification,
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


def test_analytics_durable_disk_persistence_and_restart_recovery(tmp_path: Path):
    """
    Verify that receipts, observations, and event notifications written to disk
    are fully hydrated when a new repository is initialized on the same directory.
    """
    repo1 = AnalyticsRepository(base_dir=tmp_path)

    # 1. Save receipt
    receipt = PublishedReceiptV1(
        receipt_id="rcpt-persist-1",
        project_id="proj-persist",
        output_video_id="out-vid-1",
        provider=AnalyticsProvider.YOUTUBE,
        account_reference="yt_channel_1",
        creator_id="alice",
        remote_post_id="post_yt_real_1",
        remote_post_url="https://youtube.com/watch?v=post_yt_real_1",
        publish_timestamp=datetime(2026, 10, 13, 10, 0, tzinfo=timezone.utc),
        confirmation_status=ReceiptConfirmationStatus.CONFIRMED,
    )
    repo1.save_receipt(receipt)

    # 2. Record observation
    obs = MetricObservationV1(
        observation_id="obs-persist-1",
        receipt_id="rcpt-persist-1",
        provider=AnalyticsProvider.YOUTUBE,
        observed_at=datetime(2026, 10, 13, 11, 0, tzinfo=timezone.utc),
        views=450,
        likes=35,
        comments=5,
        shares=None,  # Missing metric explicitly preserved as None
        missing_metrics=["shares", "saves"],
    )
    repo1.record_observation(obs)

    # 3. Record notification
    notif = AnalyticsEventNotification(
        event_id="evt-persist-1",
        event_type=AnalyticsEventType.METRICS_READY,
        receipt_id="rcpt-persist-1",
        provider=AnalyticsProvider.YOUTUBE,
        remote_post_id="post_yt_real_1",
        title="Metrics Updated",
        summary="Recorded 450 views",
    )
    repo1.record_notification(notif)

    # Verify files exist on disk
    assert (tmp_path / "receipts.json").exists()
    assert (tmp_path / "observations.json").exists()
    assert (tmp_path / "notifications.json").exists()

    # Restart: instantiate new repository pointing to same directory
    repo2 = AnalyticsRepository(base_dir=tmp_path)

    recovered_receipt = repo2.get_receipt("rcpt-persist-1")
    assert recovered_receipt is not None
    assert recovered_receipt.project_id == "proj-persist"
    assert recovered_receipt.creator_id == "alice"
    assert recovered_receipt.remote_post_id == "post_yt_real_1"

    recovered_obs = repo2.get_observations_for_receipt("rcpt-persist-1")
    assert len(recovered_obs) == 1
    assert recovered_obs[0].views == 450
    assert recovered_obs[0].likes == 35
    assert recovered_obs[0].shares is None
    assert "shares" in recovered_obs[0].missing_metrics

    recovered_notifs = repo2.list_notifications()
    assert len(recovered_notifs) == 1
    assert recovered_notifs[0].event_id == "evt-persist-1"


def test_analytics_rejects_fake_receipts_in_production(tmp_path: Path):
    """
    Verify that in production mode (is_test_fixture=False), receipts with fake_
    remote post IDs or receipt IDs are strictly rejected from ingestion.
    """
    repo = AnalyticsRepository(base_dir=tmp_path)
    engine = AnalyticsEngine(repository=repo)

    fake_receipt = PublishedReceiptV1(
        receipt_id="rcpt_prod_fake",
        project_id="proj-prod",
        provider=AnalyticsProvider.YOUTUBE,
        account_reference="channel_1",
        remote_post_id="fake_remote_post_999",
        publish_timestamp=datetime.now(timezone.utc),
        confirmation_status=ReceiptConfirmationStatus.CONFIRMED,
    )

    # Must raise ValueError in production ingest
    with pytest.raises(ValueError, match="Production analytics ingest strictly rejects unverified fake receipts."):
        engine.register_receipt(fake_receipt, is_test_fixture=False)


def test_analytics_rejects_unconfirmed_receipt_statuses(tmp_path: Path):
    """
    Verify that non-confirmed statuses (e.g. PENDING_VERIFICATION) cannot poll metrics.
    """
    repo = AnalyticsRepository(base_dir=tmp_path)
    engine = AnalyticsEngine(repository=repo)

    unconfirmed_receipt = PublishedReceiptV1(
        receipt_id="rcpt-unconfirmed-1",
        project_id="proj-unconfirmed",
        provider=AnalyticsProvider.TIKTOK,
        account_reference="tt_channel",
        remote_post_id="post_tt_123",
        publish_timestamp=datetime.now(timezone.utc),
        confirmation_status=ReceiptConfirmationStatus.PENDING_VERIFICATION,
        metadata={"is_test_fixture": True},
    )
    repo.save_receipt(unconfirmed_receipt)

    assert unconfirmed_receipt.is_eligible_for_polling() is False


def test_analytics_missing_vs_zero_metric_preservation(tmp_path: Path):
    """
    Verify that zero views (0) is strictly distinct from missing views (None).
    """
    repo = AnalyticsRepository(base_dir=tmp_path)
    engine = AnalyticsEngine(repository=repo)

    # Post A has 0 views observed
    receipt_a = PublishedReceiptV1(
        receipt_id="rcpt-views-zero",
        project_id="proj-a",
        provider=AnalyticsProvider.INSTAGRAM,
        account_reference="ig_user",
        remote_post_id="post_ig_zero",
        publish_timestamp=datetime.now(timezone.utc),
        confirmation_status=ReceiptConfirmationStatus.CONFIRMED,
        metadata={"is_test_fixture": True},
    )
    repo.save_receipt(receipt_a)

    obs_zero = MetricObservationV1(
        receipt_id="rcpt-views-zero",
        provider=AnalyticsProvider.INSTAGRAM,
        views=0,
        likes=0,
        missing_metrics=["watch_time_seconds"],
        is_test_fixture=True,
    )
    repo.record_observation(obs_zero)

    agg_zero = engine.get_aggregated_metrics("rcpt-views-zero")
    assert agg_zero.latest_views == 0
    assert agg_zero.engagement_rate is None  # Cannot divide by 0 views

    # Post B has views as None (unsupported or delayed by provider)
    receipt_b = PublishedReceiptV1(
        receipt_id="rcpt-views-missing",
        project_id="proj-b",
        provider=AnalyticsProvider.X,
        account_reference="x_user",
        remote_post_id="post_x_missing",
        publish_timestamp=datetime.now(timezone.utc),
        confirmation_status=ReceiptConfirmationStatus.CONFIRMED,
        metadata={"is_test_fixture": True},
    )
    repo.save_receipt(receipt_b)

    obs_missing = MetricObservationV1(
        receipt_id="rcpt-views-missing",
        provider=AnalyticsProvider.X,
        views=None,
        likes=12,
        missing_metrics=["views", "impressions"],
        is_test_fixture=True,
    )
    repo.record_observation(obs_missing)

    agg_missing = engine.get_aggregated_metrics("rcpt-views-missing")
    assert agg_missing.latest_views is None
    assert agg_missing.latest_likes == 12


@pytest.mark.asyncio
async def test_analytics_observation_deduplication(tmp_path: Path):
    """
    Verify that identical provider observations within 60s window are deduplicated.
    """
    repo = AnalyticsRepository(base_dir=tmp_path)
    mock_adapter = MockAnalyticsAdapter(
        provider_type=AnalyticsProvider.YOUTUBE,
        simulated_metrics={"views": 500, "likes": 25},
    )
    engine = AnalyticsEngine(repository=repo, provider_adapters={AnalyticsProvider.YOUTUBE: mock_adapter})

    receipt = PublishedReceiptV1(
        receipt_id="rcpt-dedup-1",
        project_id="proj-dedup",
        provider=AnalyticsProvider.YOUTUBE,
        account_reference="channel_dedup",
        remote_post_id="post_yt_dedup",
        publish_timestamp=datetime.now(timezone.utc),
        confirmation_status=ReceiptConfirmationStatus.SIMULATED_TEST,
        metadata={"is_test_fixture": True},
    )
    repo.save_receipt(receipt)

    obs1, err1 = await engine.poll_post_metrics("rcpt-dedup-1")
    assert err1 is None
    assert obs1 is not None

    # Immediate second poll with identical timestamp/hash
    obs2, err2 = await engine.poll_post_metrics("rcpt-dedup-1")
    assert err2 is None

    # Total recorded in repo must still be 1 (deduplicated)
    observations = repo.get_observations_for_receipt("rcpt-dedup-1")
    assert len(observations) == 1


def test_analytics_multi_tenant_isolation(tmp_path: Path):
    """
    Verify tenant isolation between Creator Alice and Creator Bob.
    """
    repo = AnalyticsRepository(base_dir=tmp_path)

    # Alice's receipt
    r_alice = PublishedReceiptV1(
        receipt_id="rcpt-alice-1",
        project_id="proj-alice",
        provider=AnalyticsProvider.YOUTUBE,
        account_reference="alice_ch",
        creator_id="alice",
        remote_post_id="post_alice_1",
        publish_timestamp=datetime.now(timezone.utc),
        confirmation_status=ReceiptConfirmationStatus.CONFIRMED,
    )
    repo.save_receipt(r_alice)

    # Bob's receipt
    r_bob = PublishedReceiptV1(
        receipt_id="rcpt-bob-1",
        project_id="proj-bob",
        provider=AnalyticsProvider.TIKTOK,
        account_reference="bob_ch",
        creator_id="bob",
        remote_post_id="post_bob_1",
        publish_timestamp=datetime.now(timezone.utc),
        confirmation_status=ReceiptConfirmationStatus.CONFIRMED,
    )
    repo.save_receipt(r_bob)

    # Alice queries receipts
    alice_receipts = repo.list_receipts(creator_id="alice")
    assert len(alice_receipts) == 1
    assert alice_receipts[0].receipt_id == "rcpt-alice-1"

    # Bob queries receipts
    bob_receipts = repo.list_receipts(creator_id="bob")
    assert len(bob_receipts) == 1
    assert bob_receipts[0].receipt_id == "rcpt-bob-1"

    # Alice cannot view Bob's observations
    assert repo.get_observations_for_receipt("rcpt-bob-1", creator_id="alice") == []


def test_analytics_rate_limit_backoff_persisted(tmp_path: Path):
    """
    Verify rate-limit backoff state is saved to disk and recovered across restarts.
    """
    repo1 = AnalyticsRepository(base_dir=tmp_path)
    backoff_time = datetime(2026, 10, 13, 15, 30, tzinfo=timezone.utc)
    repo1.set_rate_limit_backoff(AnalyticsProvider.TIKTOK, backoff_time)

    # Restart
    repo2 = AnalyticsRepository(base_dir=tmp_path)
    recovered = repo2.get_rate_limit_backoff(AnalyticsProvider.TIKTOK)
    assert recovered == backoff_time


def test_creative_feedback_sample_size_confidence_and_opt_in(tmp_path: Path):
    """
    Verify creative feedback engine enforces sample-size confidence guards
    and marks all hypotheses as requiring explicit creator opt-in.
    """
    repo = AnalyticsRepository(base_dir=tmp_path)
    engine = AnalyticsEngine(repository=repo)

    receipt = PublishedReceiptV1(
        receipt_id="rcpt-fbk-1",
        project_id="proj-fbk-1",
        provider=AnalyticsProvider.YOUTUBE,
        account_reference="ch_1",
        remote_post_id="post_fbk_1",
        publish_timestamp=datetime.now(timezone.utc),
        confirmation_status=ReceiptConfirmationStatus.CONFIRMED,
    )
    repo.save_receipt(receipt)

    # Low view count (50 views): confidence must be low (< 0.50) with confounder noted
    obs_low = MetricObservationV1(
        receipt_id="rcpt-fbk-1",
        provider=AnalyticsProvider.YOUTUBE,
        views=50,
        completion_rate=0.25,  # Low completion
        watch_time_seconds=2.0 * 50,
        likes=1,
    )
    repo.record_observation(obs_low)

    metrics_low = engine.get_aggregated_metrics("rcpt-fbk-1")
    fbk_low = CreativeFeedbackEngine.analyze_post_performance(
        receipt=receipt,
        metrics=metrics_low,
        sample_size_videos=1,
    )

    assert len(fbk_low.hypotheses) > 0
    for hyp in fbk_low.hypotheses:
        assert hyp.confidence_score <= 0.35
        assert any("Small sample size" in c for c in hyp.confounders_noted)
        assert hyp.creator_opt_in_required is True

    # High view count (5000 views) + 5 videos: confidence must be high (>= 0.70)
    obs_high = MetricObservationV1(
        receipt_id="rcpt-fbk-1",
        provider=AnalyticsProvider.YOUTUBE,
        views=5000,
        completion_rate=0.28,
        watch_time_seconds=3.0 * 5000,
        likes=120,
    )
    repo.record_observation(obs_high)

    metrics_high = engine.get_aggregated_metrics("rcpt-fbk-1")
    fbk_high = CreativeFeedbackEngine.analyze_post_performance(
        receipt=receipt,
        metrics=metrics_high,
        sample_size_videos=5,
    )

    for hyp in fbk_high.hypotheses:
        assert hyp.confidence_score >= 0.70
        assert hyp.creator_opt_in_required is True


def test_official_adapter_disabled_by_default_reports_not_connected():
    """
    Verify that OfficialPlatformAnalyticsAdapter truthfully reports NOT_CONNECTED
    and refuses unauthenticated metric polling when live credentials are not present.
    """
    adapter = OfficialPlatformAnalyticsAdapter(AnalyticsProvider.YOUTUBE)
    assert adapter.provider == AnalyticsProvider.YOUTUBE

    import asyncio
    status = asyncio.run(adapter.get_connection_status("test_account"))
    assert status == ProviderConnectionStatus.NOT_CONNECTED

    dummy_receipt = PublishedReceiptV1(
        receipt_id="rcpt-real-test",
        project_id="proj-1",
        provider=AnalyticsProvider.YOUTUBE,
        account_reference="test_account",
        remote_post_id="post_999",
        publish_timestamp=datetime.now(timezone.utc),
        confirmation_status=ReceiptConfirmationStatus.CONFIRMED,
    )
    obs = asyncio.run(adapter.fetch_metrics(dummy_receipt))
    assert obs is None
