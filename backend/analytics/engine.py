# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Durable Analytics Ingestion and Aggregation Engine.

Provides:
- In-memory & isolated storage repository for PublishedReceiptV1 and MetricObservationV1
- Append-only time-series ingestion
- Snapshot deduplication within the same sampling window
- Idempotent aggregation across post lifecycles
- Distinction between missing metrics (None) and observed zeroes (0)
- Engagement rate calculation with accurate denominators: (likes + comments + shares) / views
- Rate-limiting, retry, and backoff tracker
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import logging
from typing import Dict, List, Optional, Tuple

from backend.analytics.models import (
    AggregatedPostMetricsV1,
    AnalyticsEventType,
    AnalyticsEventNotification,
    AnalyticsProvider,
    MetricObservationV1,
    ProviderConnectionStatus,
    PublishedReceiptV1,
    ReceiptConfirmationStatus,
)
from backend.analytics.providers import (
    AnalyticsProviderPort,
    DisconnectedAnalyticsAdapter,
)

from backend.analytics.repository import AnalyticsRepository

logger = logging.getLogger(__name__)


class AnalyticsEngine:
    """
    Orchestrates post metric polling, durable ingestion, and cross-window aggregation.
    """

    def __init__(
        self,
        repository: Optional[AnalyticsRepository] = None,
        provider_adapters: Optional[Dict[AnalyticsProvider, AnalyticsProviderPort]] = None,
    ):
        self.repo = repository or AnalyticsRepository()
        self.providers: Dict[AnalyticsProvider, AnalyticsProviderPort] = provider_adapters or {
            p: DisconnectedAnalyticsAdapter(p) for p in AnalyticsProvider
        }

    def register_provider(self, adapter: AnalyticsProviderPort) -> None:
        self.providers[adapter.provider] = adapter

    def register_receipt(
        self,
        receipt: PublishedReceiptV1,
        is_test_fixture: bool = False,
    ) -> PublishedReceiptV1:
        """
        Register a verified publication receipt from Phase 10 or test fixtures.
        Guards:
        - In production (is_test_fixture=False), strictly rejects receipts with fake_ prefixes.
        - In production, strictly rejects unconfirmed receipts (e.g. ACCEPTED, SCHEDULED, DISPATCHING).
        - Persists receipt to durable repository.
        """
        if not is_test_fixture and not receipt.metadata.get("is_test_fixture"):
            if receipt.remote_post_id.startswith("fake_") or receipt.receipt_id.startswith("fake_"):
                raise ValueError("Production analytics ingest strictly rejects unverified fake receipts.")
            if receipt.confirmation_status not in (ReceiptConfirmationStatus.CONFIRMED, ReceiptConfirmationStatus.SIMULATED_TEST):
                raise ValueError(
                    f"Unconfirmed receipt status '{receipt.confirmation_status.value}' cannot be ingested as published post."
                )

        return self.repo.save_receipt(receipt)

    async def poll_post_metrics(
        self,
        receipt_id: str,
        window_start: Optional[datetime] = None,
        window_end: Optional[datetime] = None,
    ) -> Tuple[Optional[MetricObservationV1], Optional[str]]:
        """
        Poll external or mock metrics for a single verified receipt.
        Returns (observation, error_reason).
        """
        receipt = self.repo.get_receipt(receipt_id)
        if not receipt:
            return None, "RECEIPT_NOT_FOUND"

        if not receipt.is_eligible_for_polling():
            return None, f"UNCONFIRMED_RECEIPT_STATUS_{receipt.confirmation_status.value}"

        adapter = self.providers.get(receipt.provider)
        if not adapter:
            return None, "NO_ADAPTER_REGISTERED"

        # Rate limit / backoff check from durable repository
        now = datetime.now(timezone.utc)
        backoff_until = self.repo.get_rate_limit_backoff(receipt.provider)
        if backoff_until and now < backoff_until:
            wait_sec = int((backoff_until - now).total_seconds())
            return None, f"PROVIDER_RATE_LIMITED_BACKOFF_{wait_sec}S"

        # Check connection status
        status = await adapter.get_connection_status(receipt.account_reference)
        if status == ProviderConnectionStatus.NOT_CONNECTED:
            return None, "PROVIDER_NOT_CONNECTED"
        if status == ProviderConnectionStatus.AUTH_REQUIRED:
            self.repo.record_notification(
                AnalyticsEventNotification(
                    event_type=AnalyticsEventType.ACCOUNT_AUTH_REQUIRED,
                    receipt_id=receipt.receipt_id,
                    provider=receipt.provider,
                    remote_post_id=receipt.remote_post_id,
                    title="Account Authentication Required",
                    summary=f"OAuth connection expired or revoked for {receipt.provider.value}. Re-authentication required.",
                    requires_user_action=True,
                )
            )
            return None, "PROVIDER_AUTH_REQUIRED"
        if status == ProviderConnectionStatus.RATE_LIMITED:
            self.repo.set_rate_limit_backoff(receipt.provider, now + timedelta(seconds=60))
            return None, "PROVIDER_RATE_LIMITED"
        if status == ProviderConnectionStatus.ERROR:
            return None, "PROVIDER_ERROR"


        # Execute metric fetch
        observation = await adapter.fetch_metrics(
            receipt=receipt,
            window_start=window_start,
            window_end=window_end,
        )

        if not observation:
            return None, "NO_DATA_RETURNED"

        # Deduplication check: do not append identical observation if recorded within 60s
        existing = self.repo.get_observations_for_receipt(receipt_id)
        if existing:
            last = existing[-1]
            if (
                last.observed_at
                and abs((observation.observed_at - last.observed_at).total_seconds()) < 60
                and last.provider_response_hash == observation.provider_response_hash
            ):
                logger.info("Deduplicated identical observation for receipt %s", receipt_id)
                return last, None

        self.repo.record_observation(observation)

        # Notify downstream that metrics are ready
        self.repo.record_notification(
            AnalyticsEventNotification(
                event_type=AnalyticsEventType.METRICS_READY,
                receipt_id=receipt.receipt_id,
                provider=receipt.provider,
                remote_post_id=receipt.remote_post_id,
                title="Metrics Updated",
                summary=f"Recorded fresh metric observation with {observation.views or 0} views.",
                payload={"views": observation.views, "likes": observation.likes},
            )
        )

        return observation, None

    def get_aggregated_metrics(self, receipt_id: str) -> Optional[AggregatedPostMetricsV1]:
        """
        Build an aggregated view of a post from all recorded metric snapshots.
        Carefully preserves the missing-vs-zero distinction.
        Calculates engagement rate accurately: (likes + comments + shares) / views.
        """
        receipt = self.repo.get_receipt(receipt_id)
        if not receipt:
            return None

        observations = self.repo.get_observations_for_receipt(receipt_id)
        if not observations:
            return None

        # Sort chronologically
        sorted_obs = sorted(observations, key=lambda x: x.observed_at)
        latest = sorted_obs[-1]

        # Calculate engagement rate safely
        views = latest.views
        likes = latest.likes or 0
        comments = latest.comments or 0
        shares = latest.shares or 0

        eng_rate = None
        if views is not None and views > 0:
            eng_rate = round(((likes + comments + shares) / views) * 100.0, 2)

        return AggregatedPostMetricsV1(
            receipt_id=receipt.receipt_id,
            remote_post_id=receipt.remote_post_id,
            provider=receipt.provider,
            creator_id=receipt.creator_id,
            first_observed_at=sorted_obs[0].observed_at,
            last_observed_at=latest.observed_at,
            observation_count=len(sorted_obs),
            is_test_fixture=latest.is_test_fixture,
            latest_views=latest.views,
            latest_impressions=latest.impressions,
            latest_watch_time_seconds=latest.watch_time_seconds,
            latest_likes=latest.likes,
            latest_comments=latest.comments,
            latest_shares=latest.shares,
            latest_completion_rate=latest.completion_rate,
            engagement_rate=eng_rate,
            history_snapshots=sorted_obs,
        )
