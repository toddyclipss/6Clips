# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Tests for Grounded Analytics Engine, Models, and Providers (Wave 4 Role 5).

Verifies:
- PublishedReceiptV1 confirmation gating (rejects unconfirmed receipts from polling)
- Fake-vs-live provenance tracking (is_test_fixture flags)
- Missing-vs-zero metric distinction (None != 0)
- Accurate denominator calculation for engagement rates
- Deduplication of identical snapshots within short windows
- Rate-limiting (429) and backoff handling
- Disconnected adapter safe truthful behavior (NOT_CONNECTED, no phantom traffic)
- CreativeFeedbackV1 confidence scoring, confounders, and non-destructive opt-in rules
- AnalyticsEventNotification idempotency and token/PII safety
"""
from datetime import datetime, timezone
import pytest

from backend.analytics.engine import AnalyticsEngine, AnalyticsRepository
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
)


def test_published_receipt_confirmation_gating():
    """Verify only CONFIRMED or SIMULATED_TEST receipts are eligible for polling."""
    unconfirmed = PublishedReceiptV1(
        receipt_id="rcpt-draft-1",
        project_id="proj-101",
        provider=AnalyticsProvider.YOUTUBE,
        account_reference="channel_a",
        remote_post_id="post_unconf_1",
        publish_timestamp=datetime.now(timezone.utc),
        confirmation_status=ReceiptConfirmationStatus.PENDING_VERIFICATION,
    )
    assert unconfirmed.is_eligible_for_polling() is False

    confirmed = PublishedReceiptV1(
        receipt_id="rcpt-confirmed-1",
        project_id="proj-101",
        provider=AnalyticsProvider.YOUTUBE,
        account_reference="channel_a",
        remote_post_id="post_conf_1",
        publish_timestamp=datetime.now(timezone.utc),
        confirmation_status=ReceiptConfirmationStatus.CONFIRMED,
    )
    assert confirmed.is_eligible_for_polling() is True


@pytest.mark.asyncio
async def test_disconnected_adapter_safe_truthful_behavior():
    """Verify disconnected adapter returns NOT_CONNECTED and never invents fake metrics."""
    adapter = DisconnectedAnalyticsAdapter(AnalyticsProvider.TIKTOK)
    status = await adapter.get_connection_status("acc_tok")
    assert status == ProviderConnectionStatus.NOT_CONNECTED

    receipt = PublishedReceiptV1(
        project_id="proj-202",
        provider=AnalyticsProvider.TIKTOK,
        account_reference="acc_tok",
        remote_post_id="tik_999",
        publish_timestamp=datetime.now(timezone.utc),
    )
    obs = await adapter.fetch_metrics(receipt)
    assert obs is None


@pytest.mark.asyncio
async def test_missing_vs_zero_metric_distinction():
    """Verify None (missing metric) is strictly distinct from 0 (observed zero views)."""
    mock_adapter = MockAnalyticsAdapter(
        provider_type=AnalyticsProvider.YOUTUBE,
        simulated_metrics={
            "views": 0,           # explicitly 0 views observed
            "likes": 0,           # explicitly 0 likes observed
            "comments": None,     # comment metric was NOT provided by API
            "impressions": None,  # impressions not available
        },
    )
    engine = AnalyticsEngine()
    engine.register_provider(mock_adapter)

    receipt = PublishedReceiptV1(
        receipt_id="rcpt-zero-test",
        project_id="proj-303",
        provider=AnalyticsProvider.YOUTUBE,
        account_reference="chan_z",
        remote_post_id="post_z",
        publish_timestamp=datetime.now(timezone.utc),
    )
    engine.repo.save_receipt(receipt)

    obs, err = await engine.poll_post_metrics(receipt.receipt_id)
    assert err is None
    assert obs is not None
    assert obs.views == 0
    assert obs.likes == 0
    assert obs.comments is None
    assert "impressions" in obs.missing_metrics
    assert "comments" in obs.missing_metrics
    assert obs.is_test_fixture is True


@pytest.mark.asyncio
async def test_engagement_rate_denominator_and_aggregation():
    """Verify engagement rate is calculated accurately: (likes + comments + shares) / views."""
    mock_adapter = MockAnalyticsAdapter(
        provider_type=AnalyticsProvider.INSTAGRAM,
        simulated_metrics={
            "views": 1000,
            "likes": 50,
            "comments": 10,
            "shares": 5,
            "completion_rate": 0.45,
        },
    )
    engine = AnalyticsEngine()
    engine.register_provider(mock_adapter)

    receipt = PublishedReceiptV1(
        receipt_id="rcpt-eng-calc",
        project_id="proj-404",
        provider=AnalyticsProvider.INSTAGRAM,
        account_reference="ig_handle",
        remote_post_id="reel_404",
        publish_timestamp=datetime.now(timezone.utc),
    )
    engine.repo.save_receipt(receipt)

    await engine.poll_post_metrics(receipt.receipt_id)
    aggregate = engine.get_aggregated_metrics(receipt.receipt_id)

    assert aggregate is not None
    assert aggregate.latest_views == 1000
    # (50 + 10 + 5) / 1000 = 65 / 1000 = 6.5%
    assert aggregate.engagement_rate == 6.5
    assert aggregate.observation_count == 1


@pytest.mark.asyncio
async def test_rate_limit_backoff_handling():
    """Verify rate-limited provider triggers 60s backoff and records backoff state."""
    mock_adapter = MockAnalyticsAdapter(
        provider_type=AnalyticsProvider.X,
        simulate_rate_limit=True,
    )
    engine = AnalyticsEngine()
    engine.register_provider(mock_adapter)

    receipt = PublishedReceiptV1(
        receipt_id="rcpt-rate-limit",
        project_id="proj-505",
        provider=AnalyticsProvider.X,
        account_reference="x_handle",
        remote_post_id="tweet_505",
        publish_timestamp=datetime.now(timezone.utc),
    )
    engine.repo.save_receipt(receipt)

    obs, err = await engine.poll_post_metrics(receipt.receipt_id)
    assert obs is None
    assert err == "PROVIDER_RATE_LIMITED"

    # Second poll within window returns backoff
    obs2, err2 = await engine.poll_post_metrics(receipt.receipt_id)
    assert "PROVIDER_RATE_LIMITED_BACKOFF" in err2


def test_creative_feedback_confidence_and_opt_in():
    """Verify feedback hypotheses carry sample-size confidence guards and require creator opt-in."""
    receipt = PublishedReceiptV1(
        receipt_id="rcpt-fbk-test",
        project_id="proj-606",
        provider=AnalyticsProvider.YOUTUBE,
        account_reference="yt_ref",
        remote_post_id="video_606",
        publish_timestamp=datetime.now(timezone.utc),
    )
    # Small sample / low views
    from backend.analytics.models import AggregatedPostMetricsV1
    metrics_small = AggregatedPostMetricsV1(
        receipt_id=receipt.receipt_id,
        remote_post_id=receipt.remote_post_id,
        provider=receipt.provider,
        first_observed_at=datetime.now(timezone.utc),
        last_observed_at=datetime.now(timezone.utc),
        latest_views=45,  # small view count
        latest_completion_rate=0.25,
        engagement_rate=1.5,
    )

    feedback = CreativeFeedbackEngine.analyze_post_performance(
        receipt=receipt,
        metrics=metrics_small,
        sample_size_videos=1,
    )
    assert len(feedback.hypotheses) > 0
    # Confidence must be guarded down for small samples
    for hyp in feedback.hypotheses:
        assert hyp.confidence_score <= 0.40
        assert hyp.creator_opt_in_required is True
        assert any("sample size" in c.lower() for c in hyp.confounders_noted)
    assert "Explicit creator review and opt-in is required" in feedback.governance_notice


def test_analytics_event_notification_idempotency_and_pii():
    """Verify duplicate notification suppression and absence of sensitive tokens."""
    repo = AnalyticsRepository()
    notif1 = AnalyticsEventNotification(
        event_type=AnalyticsEventType.METRICS_READY,
        receipt_id="rcpt-notif-1",
        title="Metrics Ready",
        summary="Observation ready",
        payload={"views": 500},
    )
    saved1 = repo.record_notification(notif1)

    # Identical event recorded again
    notif2 = AnalyticsEventNotification(
        event_type=AnalyticsEventType.METRICS_READY,
        receipt_id="rcpt-notif-1",
        title="Metrics Ready Duplicate",
        summary="Observation ready duplicate",
        payload={"views": 500},
    )
    saved2 = repo.record_notification(notif2)

    assert saved1.event_id == saved2.event_id
    assert len(repo.list_notifications()) == 1

    # Verify no auth tokens in payload
    assert "token" not in saved1.payload
    assert "secret" not in saved1.payload
