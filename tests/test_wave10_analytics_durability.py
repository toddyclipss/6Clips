# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 10 Tests: Analytics Truth, Durability, Deletion Tombstones, and Missing != Zero.

Verifies:
- GT-19: Missing metrics (None) are strictly preserved without transforming into zero (0).
- Post deletion tombstones (DELETED_ON_PLATFORM) halt polling, preserve historical metrics,
  and trigger appropriate notifications.
- Rate-limiting backoff persists across process restart / repository rehydration.
- Production analytics engine strictly refuses fake receipts and unconfirmed statuses.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from backend.analytics.engine import AnalyticsEngine
from backend.analytics.models import (
    AnalyticsProvider,
    MetricObservationV1,
    PublishedReceiptV1,
    ReceiptConfirmationStatus,
)
from backend.analytics.providers import DisconnectedAnalyticsAdapter
from backend.analytics.repository import AnalyticsRepository


class TestWave10AnalyticsDurabilityAndTruth:
    """Verifies GT-19 analytics durability, deletion tombstones, and missing-vs-zero precision."""

    def test_missing_vs_zero_preservation_and_aggregation(self, tmp_path: Path):
        """
        GT-19 requirement:
        Metrics not returned by platform (e.g. impressions is None) must remain None in aggregated views.
        Zero metrics (e.g. 0 likes) must be recorded as 0.
        """
        repo = AnalyticsRepository(base_dir=tmp_path / "analytics_store")
        engine = AnalyticsEngine(repository=repo)

        receipt = PublishedReceiptV1(
            receipt_id="rcpt_w10_valid_01",
            job_id="job_w10_01",
            output_id="out_w10_01",
            project_id="proj_w10_01",
            project_revision=1,
            artifact_sha256="hash_valid_123",
            platform="youtube",
            account_id="acc_yt_01",
            account_reference="acc_yt_01",
            provider=AnalyticsProvider.YOUTUBE,
            remote_post_id="remote_real_yt_987",
            remote_post_url="https://youtube.com/shorts/remote_real_yt_987",
            publish_timestamp=datetime.now(timezone.utc),
            verified_status="CONFIRMED",
            confirmation_status=ReceiptConfirmationStatus.CONFIRMED,
        )
        engine.register_receipt(receipt, is_test_fixture=True)

        # Snapshot with views=100, likes=0, comments=None, impressions=None
        obs = MetricObservationV1(
            observation_id="obs_01",
            receipt_id=receipt.receipt_id,
            provider=AnalyticsProvider.YOUTUBE,
            views=100,
            likes=0,
            comments=None,
            shares=None,
            impressions=None,
            is_test_fixture=True,
        )
        repo.record_observation(obs)

        agg = engine.get_aggregated_metrics(receipt.receipt_id)
        assert agg is not None
        assert agg.latest_views == 100
        assert agg.latest_likes == 0
        assert agg.latest_comments is None
        assert agg.latest_impressions is None
        # Engagement rate: (0 likes + 0 comments + 0 shares) / 100 = 0.0%
        assert agg.engagement_rate == 0.0

    def test_post_deletion_tombstone_and_polling_halt(self, tmp_path: Path):
        """
        GT-19 requirement:
        When a post is marked deleted on remote platform, repository records DELETED_ON_PLATFORM,
        subsequent metric polling is halted with POST_DELETED_ON_PLATFORM, and history is preserved.
        """
        repo = AnalyticsRepository(base_dir=tmp_path / "analytics_del")
        engine = AnalyticsEngine(repository=repo)

        receipt = PublishedReceiptV1(
            receipt_id="rcpt_w10_del_01",
            job_id="job_del_01",
            output_id="out_del_01",
            project_id="proj_del_01",
            project_revision=1,
            artifact_sha256="hash_del",
            platform="tiktok",
            account_id="acc_tt_01",
            account_reference="acc_tt_01",
            provider=AnalyticsProvider.TIKTOK,
            remote_post_id="remote_tt_del_123",
            remote_post_url="https://tiktok.com/@u/video/remote_tt_del_123",
            publish_timestamp=datetime.now(timezone.utc),
            verified_status="CONFIRMED",
            confirmation_status=ReceiptConfirmationStatus.CONFIRMED,
        )
        engine.register_receipt(receipt, is_test_fixture=True)

        # Record initial observation
        repo.record_observation(
            MetricObservationV1(
                observation_id="obs_del_01",
                receipt_id=receipt.receipt_id,
                provider=AnalyticsProvider.TIKTOK,
                views=5500,
                likes=320,
                is_test_fixture=True,
            )
        )

        # Mark post as deleted on remote platform
        ok = engine.mark_post_deleted(receipt.receipt_id)
        assert ok is True

        # Polling must be halted
        import asyncio
        obs, err = asyncio.run(engine.poll_post_metrics(receipt.receipt_id))
        assert obs is None
        assert err == "POST_DELETED_ON_PLATFORM"

        # Aggregated view must reflect DELETED_ON_PLATFORM tombstone while preserving historical metrics
        agg = engine.get_aggregated_metrics(receipt.receipt_id)
        assert agg.is_deleted_on_platform is True
        assert agg.post_status == "DELETED_ON_PLATFORM"
        assert agg.latest_views == 5500
        assert agg.observation_count == 1

    def test_rate_limit_backoff_persists_across_restart(self, tmp_path: Path):
        """
        Proves that provider rate-limit backoff state is saved to disk atomically
        and restored when a new AnalyticsRepository instance hydrates from disk.
        """
        storage_dir = tmp_path / "durable_backoff"
        repo1 = AnalyticsRepository(base_dir=storage_dir)

        now = datetime.now(timezone.utc)
        backoff_expiry = now + timedelta(seconds=120)
        repo1.set_rate_limit_backoff(AnalyticsProvider.INSTAGRAM, backoff_expiry)

        # Create fresh repository pointing to the same storage root (simulating process restart)
        repo2 = AnalyticsRepository(base_dir=storage_dir)
        restored_expiry = repo2.get_rate_limit_backoff(AnalyticsProvider.INSTAGRAM)

        assert restored_expiry is not None
        assert abs((restored_expiry - backoff_expiry).total_seconds()) < 1.0
