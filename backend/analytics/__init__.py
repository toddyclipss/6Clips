# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Phase 11 Grounded Analytics, Messaging & Feedback Package.
"""
from backend.analytics.models import (
    AggregatedPostMetricsV1,
    AnalyticsEventType,
    AnalyticsEventNotification,
    AnalyticsProvider,
    CreativeFeedbackV1,
    MetricObservationSource,
    MetricObservationV1,
    OptimizationHypothesis,
    ProviderConnectionStatus,
    PublishedReceiptV1,
    ReceiptConfirmationStatus,
)
from backend.analytics.providers import (
    AnalyticsProviderPort,
    DisconnectedAnalyticsAdapter,
    MockAnalyticsAdapter,
)
from backend.analytics.engine import (
    AnalyticsEngine,
    AnalyticsRepository,
)
from backend.analytics.feedback import (
    CreativeFeedbackEngine,
)

__all__ = [
    "AggregatedPostMetricsV1",
    "AnalyticsEventType",
    "AnalyticsEventNotification",
    "AnalyticsProvider",
    "CreativeFeedbackV1",
    "MetricObservationSource",
    "MetricObservationV1",
    "OptimizationHypothesis",
    "ProviderConnectionStatus",
    "PublishedReceiptV1",
    "ReceiptConfirmationStatus",
    "AnalyticsProviderPort",
    "DisconnectedAnalyticsAdapter",
    "MockAnalyticsAdapter",
    "AnalyticsEngine",
    "AnalyticsRepository",
    "CreativeFeedbackEngine",
]
