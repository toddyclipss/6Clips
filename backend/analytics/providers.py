# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Analytics Provider Interfaces and Adapters.

Enforces provider boundaries:
- AnalyticsProviderPort abstract contract
- Safe DisconnectedAnalyticsAdapter (returns NOT_CONNECTED truthfully without fake data)
- Deterministic MockAnalyticsAdapter for explicit test fixtures with strict test flags
- Strict prevention of unapproved network calls or credential reads
"""
from __future__ import annotations

import abc
from datetime import datetime, timezone
import hashlib
import logging
from typing import Dict, List, Optional

from backend.analytics.models import (
    AnalyticsProvider,
    MetricObservationSource,
    MetricObservationV1,
    ProviderConnectionStatus,
    PublishedReceiptV1,
)

logger = logging.getLogger(__name__)


class AnalyticsProviderPort(abc.ABC):
    """Abstract port for querying social platform analytics."""

    @property
    @abc.abstractmethod
    def provider(self) -> AnalyticsProvider:
        """Provider identifier."""
        pass

    @abc.abstractmethod
    async def get_connection_status(self, account_ref: str) -> ProviderConnectionStatus:
        """Check whether provider is authenticated and operational."""
        pass

    @abc.abstractmethod
    async def fetch_metrics(
        self,
        receipt: PublishedReceiptV1,
        window_start: Optional[datetime] = None,
        window_end: Optional[datetime] = None,
    ) -> Optional[MetricObservationV1]:
        """Fetch remote metrics for a verified published receipt."""
        pass


class DisconnectedAnalyticsAdapter(AnalyticsProviderPort):
    """
    Safe production default adapter when no platform OAuth or credentials are configured.
    Truthfully returns NOT_CONNECTED and None metrics instead of zeroes or synthetic traffic.
    """

    def __init__(self, provider_type: AnalyticsProvider):
        self._provider = provider_type

    @property
    def provider(self) -> AnalyticsProvider:
        return self._provider

    async def get_connection_status(self, account_ref: str) -> ProviderConnectionStatus:
        logger.info(
            "DisconnectedAnalyticsAdapter | provider=%s | account=%s | status=NOT_CONNECTED",
            self._provider.value,
            account_ref,
        )
        return ProviderConnectionStatus.NOT_CONNECTED

    async def fetch_metrics(
        self,
        receipt: PublishedReceiptV1,
        window_start: Optional[datetime] = None,
        window_end: Optional[datetime] = None,
    ) -> Optional[MetricObservationV1]:
        logger.info(
            "DisconnectedAnalyticsAdapter | refusing metric poll for disconnected provider=%s receipt=%s",
            self._provider.value,
            receipt.receipt_id,
        )
        return None


class MockAnalyticsAdapter(AnalyticsProviderPort):
    """
    Deterministic test adapter used exclusively for verified automated tests and preview fixtures.
    Flags all returned observations with is_test_fixture=True to guarantee zero leakage.
    Supports simulated rate limits, missing metrics, and error injection.
    """

    def __init__(
        self,
        provider_type: AnalyticsProvider,
        simulated_metrics: Optional[Dict[str, Any]] = None,
        simulate_rate_limit: bool = False,
        simulate_auth_required: bool = False,
        simulate_error: bool = False,
    ):
        self._provider = provider_type
        self.simulated_metrics = simulated_metrics or {}
        self.simulate_rate_limit = simulate_rate_limit
        self.simulate_auth_required = simulate_auth_required
        self.simulate_error = simulate_error
        self.fetch_call_count = 0

    @property
    def provider(self) -> AnalyticsProvider:
        return self._provider

    async def get_connection_status(self, account_ref: str) -> ProviderConnectionStatus:
        if self.simulate_auth_required:
            return ProviderConnectionStatus.AUTH_REQUIRED
        if self.simulate_rate_limit:
            return ProviderConnectionStatus.RATE_LIMITED
        if self.simulate_error:
            return ProviderConnectionStatus.ERROR
        return ProviderConnectionStatus.CONNECTED

    async def fetch_metrics(
        self,
        receipt: PublishedReceiptV1,
        window_start: Optional[datetime] = None,
        window_end: Optional[datetime] = None,
    ) -> Optional[MetricObservationV1]:
        self.fetch_call_count += 1

        if self.simulate_rate_limit or self.simulate_auth_required or self.simulate_error:
            return None

        # Verify publication receipt is confirmed
        if not receipt.is_eligible_for_polling():
            logger.warning(
                "MockAnalyticsAdapter | rejected unconfirmed receipt=%s status=%s",
                receipt.receipt_id,
                receipt.confirmation_status.value,
            )
            return None

        now = datetime.now(timezone.utc)
        payload = self.simulated_metrics.get(receipt.remote_post_id, self.simulated_metrics)

        # Distinguish explicitly observed values from missing values
        views = payload.get("views")
        impressions = payload.get("impressions")
        watch_time = payload.get("watch_time_seconds")
        likes = payload.get("likes")
        comments = payload.get("comments")
        shares = payload.get("shares")
        completion_rate = payload.get("completion_rate")

        missing = []
        if views is None:
            missing.append("views")
        if impressions is None:
            missing.append("impressions")
        if watch_time is None:
            missing.append("watch_time_seconds")
        if completion_rate is None:
            missing.append("completion_rate")
        if likes is None:
            missing.append("likes")
        if comments is None:
            missing.append("comments")
        if shares is None:
            missing.append("shares")

        resp_hash = hashlib.sha256(f"{receipt.remote_post_id}:{now.isoformat()}".encode()).hexdigest()[:12]

        return MetricObservationV1(
            receipt_id=receipt.receipt_id,
            provider=self._provider,
            observed_at=now,
            sampling_window_start=window_start,
            sampling_window_end=window_end or now,
            observation_source=MetricObservationSource.FIXTURE_VERIFIED,
            is_test_fixture=True,
            views=views,
            impressions=impressions,
            watch_time_seconds=watch_time,
            completion_rate=completion_rate,
            likes=likes,
            comments=comments,
            shares=shares,
            missing_metrics=missing,
            api_latency_ms=45.2,
            provider_response_hash=resp_hash,
            notes="Deterministic automated test fixture observation.",
        )
