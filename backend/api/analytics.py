# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
FastAPI Router for Phase 11 Grounded Analytics, Messaging & Feedback.

Endpoints:
- GET  /api/analytics/status             - Returns platform connector status (NOT_CONNECTED, etc.)
- GET  /api/analytics/receipts           - Lists published post receipts
- POST /api/analytics/receipts           - Records a published receipt (from Phase 10 or test fixtures)
- POST /api/analytics/poll/{receipt_id}  - Triggers metric polling for a confirmed receipt
- GET  /api/analytics/post/{receipt_id}  - Retrieves aggregated post metrics & observation timeseries
- GET  /api/analytics/feedback/{receipt_id} - Retrieves non-destructive creative feedback hypotheses
- GET  /api/analytics/events             - Lists analytics notifications & events for messaging
- POST /api/analytics/fixtures/seed      - Seeds explicit test fixture receipts (marked is_test_fixture=True)
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.analytics.engine import AnalyticsEngine, AnalyticsRepository
from backend.analytics.feedback import CreativeFeedbackEngine
from backend.analytics.models import (
    AnalyticsProvider,
    MetricObservationSource,
    MetricObservationV1,
    ProviderConnectionStatus,
    PublishedReceiptV1,
    ReceiptConfirmationStatus,
)
from backend.analytics.providers import MockAnalyticsAdapter

router = APIRouter(prefix="/analytics", tags=["analytics"])

# Module-level engine instance (isolated from shared production DB)
_default_repo = AnalyticsRepository()
_default_engine = AnalyticsEngine(repository=_default_repo)


def get_analytics_engine() -> AnalyticsEngine:
    return _default_engine


@router.get("/status")
async def get_analytics_provider_status():
    """
    Check connection status across social analytics providers.
    Truthfully reports NOT_CONNECTED if no OAuth credentials exist.
    """
    engine = get_analytics_engine()
    statuses = {}
    for prov, adapter in engine.providers.items():
        st = await adapter.get_connection_status(account_ref="default")
        statuses[prov.value] = {
            "status": st.value,
            "connected": st == ProviderConnectionStatus.CONNECTED,
            "requires_action": st == ProviderConnectionStatus.AUTH_REQUIRED,
        }
    return {
        "providers": statuses,
        "mode": "DISCONNECTED" if all(s["status"] == "NOT_CONNECTED" for s in statuses.values()) else "ACTIVE",
    }


class ReceiptCreateRequest(BaseModel):
    project_id: str
    output_video_id: Optional[str] = None
    provider: AnalyticsProvider
    account_reference: str
    remote_post_id: str
    remote_post_url: Optional[str] = None
    publish_timestamp: Optional[datetime] = None
    confirmation_status: ReceiptConfirmationStatus = ReceiptConfirmationStatus.CONFIRMED
    metadata: Dict[str, Any] = {}


@router.get("/receipts")
async def list_published_receipts(creator_id: str = "local"):
    """List all registered publication receipts."""
    engine = get_analytics_engine()
    receipts = engine.repo.list_receipts(creator_id=creator_id)
    return {
        "total": len(receipts),
        "receipts": [r.model_dump() for r in receipts],
    }


@router.post("/receipts")
async def register_published_receipt(req: ReceiptCreateRequest):
    """
    Register a verified publication receipt from Phase 10 or testing.
    Unconfirmed receipts or fake receipts in production are rejected.
    """
    engine = get_analytics_engine()
    receipt = PublishedReceiptV1(
        project_id=req.project_id,
        output_video_id=req.output_video_id,
        provider=req.provider,
        account_reference=req.account_reference,
        remote_post_id=req.remote_post_id,
        remote_post_url=req.remote_post_url,
        publish_timestamp=req.publish_timestamp or datetime.now(timezone.utc),
        confirmation_status=req.confirmation_status,
        metadata=req.metadata,
    )
    is_fixture = bool(req.metadata.get("is_test_fixture")) or req.confirmation_status == ReceiptConfirmationStatus.SIMULATED_TEST
    try:
        saved = engine.register_receipt(receipt, is_test_fixture=is_fixture)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    return {"receipt": saved.model_dump()}



@router.post("/poll/{receipt_id}")
async def poll_receipt_metrics(receipt_id: str):
    """Poll remote or mock metrics for a specific publication receipt."""
    engine = get_analytics_engine()
    obs, err = await engine.poll_post_metrics(receipt_id=receipt_id)
    if err:
        return {
            "success": False,
            "error": err,
            "receipt_id": receipt_id,
        }
    return {
        "success": True,
        "observation": obs.model_dump() if obs else None,
    }


@router.get("/post/{receipt_id}")
async def get_post_metrics(receipt_id: str):
    """
    Get aggregated post metrics and chronological observation history.
    Truthfully returns NO_VERIFIED_METRICS if no observations exist.
    """
    engine = get_analytics_engine()
    receipt = engine.repo.get_receipt(receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    aggregate = engine.get_aggregated_metrics(receipt_id)
    if not aggregate:
        return {
            "status": "NO_VERIFIED_METRICS",
            "receipt": receipt.model_dump(),
            "aggregate": None,
        }

    return {
        "status": "VERIFIED_METRICS_PRESENT",
        "receipt": receipt.model_dump(),
        "aggregate": aggregate.model_dump(),
    }


@router.post("/post/{receipt_id}/mark-deleted")
async def mark_post_deleted(receipt_id: str):
    """Mark a published post as deleted on remote platform."""
    engine = get_analytics_engine()
    success = engine.mark_post_deleted(receipt_id)
    if not success:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return {"receipt_id": receipt_id, "status": "DELETED_ON_PLATFORM"}


@router.get("/summary")
async def get_multi_platform_summary(creator_id: str = "local"):
    """
    Get multi-platform analytics summary preserving native platform metrics
    without lossy cross-platform summation.
    """
    engine = get_analytics_engine()
    return engine.get_multi_platform_summary(creator_id=creator_id)


@router.get("/feedback/{receipt_id}")
async def get_creative_feedback(receipt_id: str):
    """
    Retrieve cautious, evidence-backed creative optimization hypotheses.
    """
    engine = get_analytics_engine()
    receipt = engine.repo.get_receipt(receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    aggregate = engine.get_aggregated_metrics(receipt_id)
    if not aggregate:
        raise HTTPException(
            status_code=400,
            detail="Cannot generate creative feedback: no verified metrics observed yet for this post.",
        )

    feedback = CreativeFeedbackEngine.analyze_post_performance(receipt=receipt, metrics=aggregate)
    return {"feedback": feedback.model_dump()}


@router.get("/events")
async def list_analytics_events():
    """List event notifications generated by analytics ingestion for downstream messaging."""
    engine = get_analytics_engine()
    events = engine.repo.list_notifications()
    return {
        "total": len(events),
        "events": [e.model_dump() for e in events],
    }


class SeedFixtureRequest(BaseModel):
    receipt_id: Optional[str] = None
    project_id: str = "proj-test-fixture-1"
    provider: AnalyticsProvider = AnalyticsProvider.YOUTUBE
    views: int = 1240
    likes: int = 88
    comments: int = 14
    shares: int = 5
    completion_rate: float = 0.32


@router.post("/fixtures/seed")
async def seed_test_fixture(req: SeedFixtureRequest):
    """
    Explicitly seeds verified test fixtures into the analytics engine with visual watermark flag.
    Does NOT affect production data.
    """
    engine = get_analytics_engine()

    # Register mock adapter for provider if not registered
    mock_adapter = MockAnalyticsAdapter(
        provider_type=req.provider,
        simulated_metrics={
            "views": req.views,
            "likes": req.likes,
            "comments": req.comments,
            "shares": req.shares,
            "completion_rate": req.completion_rate,
            "watch_time_seconds": req.views * 18.5,
        },
    )
    engine.register_provider(mock_adapter)

    receipt = PublishedReceiptV1(
        receipt_id=req.receipt_id or f"rcpt-fixture-{req.provider.value}",
        project_id=req.project_id,
        provider=req.provider,
        account_reference="fixture_account",
        remote_post_id="post-ext-fixture-99",
        remote_post_url=f"https://{req.provider.value}.com/watch?v=fixture99",
        publish_timestamp=datetime.now(timezone.utc),
        confirmation_status=ReceiptConfirmationStatus.SIMULATED_TEST,
        source="test_fixture_seed",
        metadata={"is_test_fixture": True, "watermark": "TEST_DATA"},
    )
    engine.repo.save_receipt(receipt)

    obs, _ = await engine.poll_post_metrics(receipt.receipt_id)

    return {
        "status": "FIXTURE_SEEDED",
        "receipt": receipt.model_dump(),
        "observation": obs.model_dump() if obs else None,
    }
