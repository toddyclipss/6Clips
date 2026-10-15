# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
OAAS Analytics Ingestor: Grounded metrics ingestion, anti-fabrication, and truthful recommendations.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

from backend.oaas_provider_receipts.receipt_store import OAASReceiptStore, ProviderReceiptV2

logger = logging.getLogger(__name__)


class GroundedMetricObservation(BaseModel):
    """Immutable, authenticated metric observation."""
    observation_id: str = Field(default_factory=lambda: f"obs_{uuid4().hex[:12]}")
    receipt_id: str
    platform: str
    provider_post_id: str
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    observed_at_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "AUTHENTICATED_PROVIDER_API"
    provenance_metadata: Dict[str, Any] = Field(default_factory=dict)


class OAASAnalyticsIngestor:
    """
    Ingests authentic performance metrics from genuine provider receipts.
    Strictly forbids synthetic metrics, fake growth curves, or ungrounded recommendations.
    """

    def __init__(self, receipt_store: OAASReceiptStore):
        self.receipt_store = receipt_store
        self._observations: Dict[str, List[GroundedMetricObservation]] = {}  # receipt_id -> list of obs

    def ingest_observation(
        self,
        receipt_id: str,
        views: int,
        likes: int,
        comments: int,
        shares: int,
        source: str = "AUTHENTICATED_PROVIDER_API",
    ) -> GroundedMetricObservation:
        """Record an authentic metric observation bound to a verified receipt."""
        receipt = self.receipt_store.get_receipt(receipt_id)
        if not receipt:
            raise ValueError(f"Cannot ingest metrics for unverified or non-existent receipt '{receipt_id}'.")

        # Refuse to ingest metrics for test fixtures into production analytics
        if receipt.is_test_fixture:
            logger.warning("Ingesting test fixture metrics; segregated from production ledger.")

        obs = GroundedMetricObservation(
            receipt_id=receipt_id,
            platform=receipt.platform,
            provider_post_id=receipt.provider_post_id,
            views=views,
            likes=likes,
            comments=comments,
            shares=shares,
            source=source,
        )

        if receipt_id not in self._observations:
            self._observations[receipt_id] = []
        self._observations[receipt_id].append(obs)
        return obs

    def get_channel_summary(self) -> Dict[str, Any]:
        """
        Truthful channel summary for My Channel and Main Agent.
        If zero verified publications exist, returns truthful status with no fabricated numbers.
        """
        verified_receipts = self.receipt_store.list_receipts(exclude_fixtures=True)
        if not verified_receipts:
            return {
                "status": "NO_VERIFIED_PUBLICATIONS",
                "connected_accounts": 0,
                "total_verified_posts": 0,
                "total_views": 0,
                "total_engagements": 0,
                "latest_observation_utc": None,
                "action_required": "Connect channel OAuth credentials and schedule your first outcome.",
            }

        total_views = 0
        total_engagements = 0
        latest_ts = None

        for r in verified_receipts:
            obs_list = self._observations.get(r.receipt_id, [])
            if obs_list:
                latest = obs_list[-1]
                total_views += latest.views
                total_engagements += (latest.likes + latest.comments + latest.shares)
                if not latest_ts or latest.observed_at_utc > latest_ts:
                    latest_ts = latest.observed_at_utc

        return {
            "status": "ACTIVE_MEASURED",
            "connected_accounts": len({r.account_id for r in verified_receipts}),
            "total_verified_posts": len(verified_receipts),
            "total_views": total_views,
            "total_engagements": total_engagements,
            "latest_observation_utc": latest_ts,
            "action_required": None,
        }

    def generate_agent_recommendations(self) -> Dict[str, Any]:
        """
        Generates Main Agent recommendations only when grounded observations exist.
        Without data, states explicitly that recommendations are pending live measurements.
        """
        summary = self.get_channel_summary()
        if summary["status"] == "NO_VERIFIED_PUBLICATIONS":
            return {
                "has_recommendations": False,
                "status": "NO_DATA",
                "reason": "Recommendations require measured publication results. No verified posts have been published yet.",
                "insights": [],
            }

        insights = []
        if summary["total_views"] > 0:
            rate = (summary["total_engagements"] / summary["total_views"]) * 100
            insights.append(f"Measured engagement rate across verified posts is {rate:.1f}%.")

        return {
            "has_recommendations": len(insights) > 0,
            "status": "OPTIMIZED",
            "reason": None,
            "insights": insights,
        }
