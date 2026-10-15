# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
OAAS Provider Receipts & Real Publishing Subsystem.

Enforces genuine provider receipts, strict OAuth credential validation,
fail-closed publication boundaries, and authentic analytics ingestion.
"""
from backend.oaas_provider_receipts.receipt_store import (
    OAASReceiptStore,
    ProviderReceiptV2,
    ReceiptVerificationError,
)
from backend.oaas_provider_receipts.provider_client import (
    ProviderDispatcher,
    ProviderDispatchResult,
    ProviderCredentialError,
)
from backend.oaas_provider_receipts.queue_truth import (
    OAASQueueManager,
    PublishQueueState,
    JobLifecycleError,
)
from backend.oaas_provider_receipts.analytics_ingestor import (
    OAASAnalyticsIngestor,
    GroundedMetricObservation,
)

__all__ = [
    "OAASReceiptStore",
    "ProviderReceiptV2",
    "ReceiptVerificationError",
    "ProviderDispatcher",
    "ProviderDispatchResult",
    "ProviderCredentialError",
    "OAASQueueManager",
    "PublishQueueState",
    "JobLifecycleError",
    "OAASAnalyticsIngestor",
    "GroundedMetricObservation",
]
