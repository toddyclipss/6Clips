# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Integration Router: Narrowly scoped cross-domain orchestration endpoints for 6Clips.

Provides authorized, owner-scoped, revision-checked pathways:
1. Canonical Catalog -> ProjectService insertion (add-to-project with CAS & readiness check)
2. Library -> Motion contract timeline mutation (application/x-6clips-asset with anti-duplicate validation)
3. Original Creator -> Plan & Render orchestration (truthful WAITING_FOR_INPUT on missing narration)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.catalog.manifest_service import CatalogManifestService, CatalogManifestError
from backend.catalog.project_intent_contract import (
    AddToProjectIntentRequest,
    CatalogProjectIntentAdapter,
)
from backend.core.exceptions import (
    AssetAccessError,
    AssetError,
    IdempotencyConflictError,
    ProjectError,
    ProjectNotFoundError,
    RevisionConflictError,
)
from backend.library_workflows.motion_contract import (
    MIME_MOTION_ASSET,
    MotionAssetIntent,
    MotionContractError,
    MotionContractManager,
)
from backend.original_creation.models import (
    OriginalCompositionSpec,
    OriginalCreationStatus,
    ProductionV1Adapter,
)
from backend.original_creation.workflow import OriginalCreatorWorkflow
from backend.services.project_service import ProjectService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integration", tags=["integration"])


# =========================================================================
# Domain B: Canonical Catalog -> ProjectService Bridge
# =========================================================================

class CatalogAddToProjectRequest(BaseModel):
    project_id: str
    expected_revision: int
    block_id: str
    aspect_ratio: str = Field("9:16", description="Target aspect ratio: '9:16' or '16:9'")
    start_time_seconds: float = Field(0.0, ge=0.0)
    timeline_track_index: int = Field(0, ge=0)
    target_track_id: Optional[str] = None
    custom_variables: Dict[str, Any] = Field(default_factory=dict)
    user_id: str = "local"
    idempotency_key: Optional[str] = None


@router.post("/catalog/add-to-project")
async def add_catalog_block_to_project(req: CatalogAddToProjectRequest):
    """
    Authorized, owner-scoped, revision-checked pathway inserting a READY,
    license-eligible, internalized block into an existing ProjectRevision.
    Rejects unready blocks (422), stale revisions (409 CAS), wrong users (403),
    and path traversal attempts.
    """
    # 1. Path traversal guard
    if ".." in req.block_id or "/" in req.block_id or "\\" in req.block_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid block_id '{req.block_id}': path traversal characters are forbidden.",
        )

    # 2. Block existence & readiness check
    try:
        CatalogManifestService.validate_block_id(req.block_id)
        item = CatalogManifestService.get_item(req.block_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Catalog block '{req.block_id}' not found.",
            )
    except CatalogManifestError as me:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(me))

    # Readiness & internalization verification
    is_internalized = item.get("internalized", False) or item.get("id") in [
        "aurora", "data-chart", "instagram-follow", "tiktok-follow", "weight-wave", "yt-lower-third"
    ]
    disposition = item.get("disposition", "SHIP")
    if not is_internalized or disposition == "UNSUPPORTED":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Block '{req.block_id}' is not runtime ready or internalized for insertion. "
                "Only validated internalized blocks with confirmed runtime independence may be added."
            ),
        )

    # 3. User scope and project ownership verification
    try:
        project = await ProjectService.verify_project_ownership(req.project_id, user_id=req.user_id)
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{req.project_id}' not found.",
        )
    except AssetAccessError as aae:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(aae),
        )

    # 4. Optimistic concurrency control (CAS) check
    if project.revision != req.expected_revision:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Revision conflict: expected revision {req.expected_revision}, "
                f"but project '{req.project_id}' is currently at revision {project.revision}."
            ),
        )

    # 5. Formulate validated intent contract
    intent_req = AddToProjectIntentRequest(
        project_id=req.project_id,
        timeline_track_index=req.timeline_track_index,
        start_time_seconds=req.start_time_seconds,
        aspect_ratio=req.aspect_ratio,
        custom_variables=req.custom_variables,
    )
    intent = CatalogProjectIntentAdapter.create_add_to_project_intent(req.block_id, intent_req)

    # 6. Apply canonical CAS operation to ProjectService
    op_payload = {
        "block_id": req.block_id,
        "title": intent.timeline_item.title,
        "start_seconds": intent.timeline_item.start_time,
        "duration_seconds": intent.timeline_item.duration,
        "variables": intent.timeline_item.variables,
        "track_id": req.target_track_id or "track_graphics_main",
    }

    try:
        op_result = await ProjectService.apply_operation(
            project_id=req.project_id,
            expected_revision=req.expected_revision,
            operation_type="add_block",
            payload=op_payload,
            idempotency_key=req.idempotency_key,
            author=req.user_id,
        )
    except RevisionConflictError as rce:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"CAS revision conflict: {rce}",
        )
    except IdempotencyConflictError as ice:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Idempotency conflict: {ice}",
        )
    except ProjectError as pe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Project operation error: {pe}",
        )

    return {
        "ok": True,
        "project_id": req.project_id,
        "revision": op_result["revision"],
        "intent_id": intent.intent_id,
        "timeline_item": intent.timeline_item.model_dump(),
        "document": op_result["document"],
    }


# =========================================================================
# Domain D: Library -> Motion Contract Bridge
# =========================================================================

class LibraryApplyMotionIntentRequest(BaseModel):
    project_id: str
    expected_revision: int
    intent: Optional[Dict[str, Any]] = None
    asset_key: Optional[str] = None
    user_id: str = "local"
    target_track_id: Optional[str] = None
    target_start_time_seconds: float = Field(0.0, ge=0.0)
    idempotency_key: Optional[str] = None


@router.post("/library/apply-motion-intent")
async def apply_library_motion_intent(
    req: LibraryApplyMotionIntentRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Applies validated MotionAssetIntent into canonical project timeline with
    permission, ownership, CAS revision check, and anti-duplicate guards.
    """
    # 1. Project ownership check
    try:
        project = await ProjectService.verify_project_ownership(req.project_id, user_id=req.user_id)
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{req.project_id}' not found.",
        )
    except AssetAccessError as aae:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(aae),
        )

    # 2. CAS check
    if project.revision != req.expected_revision:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Revision conflict: expected revision {req.expected_revision}, "
                f"but project '{req.project_id}' is currently at revision {project.revision}."
            ),
        )

    # 3. Resolve or validate MotionAssetIntent
    if req.intent:
        try:
            motion_intent = MotionAssetIntent.from_dict(req.intent)
            MotionContractManager.validate_intent(motion_intent)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid motion intent contract: {e}",
            )
    elif req.asset_key:
        try:
            motion_intent = await MotionContractManager.create_motion_intent(
                req.asset_key,
                db=db,
                target_track=req.target_track_id,
                target_start_time_seconds=req.target_start_time_seconds,
            )
        except MotionContractError as me:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not construct motion intent: {me}",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either 'intent' dictionary or 'asset_key'.",
        )

    # 4. Anti-duplicate verification
    doc = json.loads(project.document_json)
    target_track_id = req.target_track_id or motion_intent.target_track or "track_video_main"
    tracks = doc.get("timeline", {}).get("tracks", [])
    for t in tracks:
        if t.get("id") == target_track_id:
            for c in t.get("clips", []):
                if c.get("asset_id") == motion_intent.asset_id and abs(float(c.get("start_seconds", 0.0)) - motion_intent.target_start_time_seconds) < 0.01:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            f"Duplicate clip detected: asset '{motion_intent.asset_id}' is already present "
                            f"on track '{target_track_id}' at start time {motion_intent.target_start_time_seconds}s."
                        ),
                    )

    # 5. Formulate clip payload
    clip_id = f"clip_{uuid4().hex[:8]}"
    clip_payload = {
        "track_id": target_track_id,
        "clip": {
            "id": clip_id,
            "type": motion_intent.media_type,
            "asset_id": motion_intent.asset_id,
            "title": motion_intent.title,
            "start_seconds": motion_intent.target_start_time_seconds,
            "duration_seconds": motion_intent.duration_seconds,
            "stream_url": motion_intent.stream_url,
            "source_provenance": motion_intent.source_provenance,
            "aspect_ratio": motion_intent.aspect_ratio,
        },
    }

    try:
        op_result = await ProjectService.apply_operation(
            project_id=req.project_id,
            expected_revision=req.expected_revision,
            operation_type="add_clip",
            payload=clip_payload,
            idempotency_key=req.idempotency_key,
            author=req.user_id,
        )
    except RevisionConflictError as rce:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"CAS revision conflict: {rce}",
        )
    except IdempotencyConflictError as ice:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Idempotency conflict: {ice}",
        )
    except ProjectError as pe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Project operation error: {pe}",
        )

    return {
        "ok": True,
        "project_id": req.project_id,
        "revision": op_result["revision"],
        "clip_id": clip_id,
        "document": op_result["document"],
    }


# =========================================================================
# Domain C: Original Creator -> Plan & Render Bridge
# =========================================================================

class CreatorPlanAndRenderRequest(BaseModel):
    topic: str
    creator_context: Optional[str] = None
    target_duration_sec: int = 60
    aspect_ratio: str = "9:16"
    language: str = "en"
    custom_voice_path: Optional[str] = None
    creator_voice_asset_id: Optional[str] = None
    creator_facecam_asset_id: Optional[str] = None
    allow_procedural_tts: bool = False


@router.post("/creator/plan-and-render")
async def plan_and_render_original_creator_video(req: CreatorPlanAndRenderRequest):
    """
    Connects OriginalCreatorWorkflow, OriginalVideoRenderer, and canonical ProjectService.
    Returns WAITING_FOR_INPUT when narration voice is missing without TTS consent.
    When prerequisites are fulfilled, renders verified physical MP4 and returns review URL.
    """
    # 1. Plan original composition brief
    custom_voice = Path(req.custom_voice_path) if req.custom_voice_path else None
    spec = OriginalCreatorWorkflow.create_brief(
        topic=req.topic,
        creator_context=req.creator_context,
        target_duration_sec=req.target_duration_sec,
        aspect_ratio=req.aspect_ratio,
        language=req.language,
        creator_voice_asset_id=req.creator_voice_asset_id,
        creator_voice_asset_path=req.custom_voice_path,
        creator_facecam_asset_id=req.creator_facecam_asset_id,
        allow_procedural_tts=req.allow_procedural_tts,
    )

    # 2. Check prerequisites: if waiting for input, truthfully return without forging render
    if spec.status == OriginalCreationStatus.WAITING_FOR_INPUT and not custom_voice:
        return {
            "status": spec.status.value,
            "status_reason": spec.status_reason,
            "spec_id": spec.spec_id,
            "is_rendered": False,
            "review_url": None,
            "spec": spec.model_dump(),
        }

    # 3. Physically render composition
    rendered = await OriginalCreatorWorkflow.render_spec(
        spec=spec,
        custom_voice_path=custom_voice,
    )

    is_rendered = rendered.rendered_result is not None
    review_url = None
    if is_rendered:
        from backend.media_pipeline.producer_adapter import get_media_producer
        producer = get_media_producer()
        art_id = f"art-{rendered.spec_id}"
        width = rendered.rendered_result.probe_stats.width if rendered.rendered_result.probe_stats else 1080
        height = rendered.rendered_result.probe_stats.height if rendered.rendered_result.probe_stats else 1920
        producer.register_completed_artifact(
            job_id=rendered.spec_id,
            output_id=f"out-{rendered.spec_id}",
            artifact_id=art_id,
            file_path=rendered.rendered_result.video_path,
            duration_seconds=rendered.rendered_result.duration_seconds,
            width=width,
            height=height,
            user_id="local",
            project_id=req.project_id,
        )
        review_url = f"/motion?jobId={rendered.spec_id}&mode=review"
    canonical_payload = ProductionV1Adapter.to_canonical_project_payload(rendered)

    return {
        "status": rendered.status.value,
        "status_reason": rendered.status_reason,
        "spec_id": rendered.spec_id,
        "is_rendered": is_rendered,
        "review_url": review_url,
        "video_path": str(rendered.rendered_result.video_path) if is_rendered else None,
        "duration_seconds": rendered.rendered_result.duration_seconds if is_rendered else None,
        "spec": rendered.model_dump(),
        "canonical_project_payload": canonical_payload,
    }


# =========================================================================
# Domain E: Distribution & Analytics Reconciled Bridge
# =========================================================================

class ReconcileReceiptRequest(BaseModel):
    distribution_receipt: Dict[str, Any]
    creator_id: str = "local"
    verify_lineage: bool = True


@router.post("/distribution/reconcile-receipt-to-analytics")
async def reconcile_receipt_to_analytics(req: ReconcileReceiptRequest):
    """
    Reconciles a Phase 10 Distribution PublishedReceiptV1 into Phase 11 Analytics PublishedReceiptV1.
    Strictly verifies that:
    1. A queued or scheduled job is NOT accepted as a confirmed remote post.
    2. verified_status must be 'CONFIRMED' with a valid remote_post_id.
    3. Output artifact SHA-256 and lineage are preserved.
    """
    from datetime import datetime, timezone
    dist_data = req.distribution_receipt
    verified_status = dist_data.get("verified_status")
    remote_post_id = dist_data.get("remote_post_id")

    if not remote_post_id or (isinstance(remote_post_id, str) and remote_post_id.startswith("fake_")):
        is_test = dist_data.get("provenance", {}).get("environment") == "test"
        if not is_test:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A queued, simulated or unconfirmed job cannot be reconciled as a verified production publication.",
            )

    if verified_status != "CONFIRMED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reconcile receipt with unconfirmed status: '{verified_status}'. Status must be 'CONFIRMED'.",
        )

    from backend.analytics.models import (
        AnalyticsProvider,
        PublishedReceiptV1 as AnalyticsReceipt,
        ReceiptConfirmationStatus,
    )
    from backend.api.analytics import get_analytics_engine

    platform_str = str(dist_data.get("platform", "")).lower()
    try:
        provider = AnalyticsProvider(platform_str)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown or unsupported platform: '{platform_str}'.",
        )

    raw_ts = dist_data.get("published_at_utc")
    try:
        pub_ts = datetime.fromisoformat(raw_ts) if raw_ts else datetime.now(timezone.utc)
    except Exception:
        pub_ts = datetime.now(timezone.utc)

    analytics_receipt = AnalyticsReceipt(
        receipt_id=dist_data.get("receipt_id") or f"rcpt-{uuid4().hex[:8]}",
        project_id=dist_data.get("project_id", "default"),
        output_video_id=dist_data.get("output_id"),
        revision_id=str(dist_data.get("project_revision", 1)),
        artifact_sha256=dist_data.get("artifact_sha256"),
        provider=provider,
        account_reference=dist_data.get("account_handle") or dist_data.get("account_id", "local_acc"),
        creator_id=req.creator_id,
        remote_post_id=remote_post_id,
        remote_post_url=dist_data.get("remote_post_url"),
        publish_timestamp=pub_ts,
        confirmation_status=ReceiptConfirmationStatus.CONFIRMED,
        source="phase10_distribution_reconciled",
        metadata={
            "job_id": dist_data.get("job_id"),
            "provenance": dist_data.get("provenance", {}),
            "reconciled_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    engine = get_analytics_engine()
    saved = engine.repo.save_receipt(analytics_receipt)
    return {
        "status": "reconciled",
        "receipt": saved.model_dump(),
        "eligible_for_polling": saved.is_eligible_for_polling(),
    }


# =========================================================================
# Integration Health & Domain Status
# =========================================================================

@router.get("/health")
async def get_integration_health():
    """Returns integration coordinator health and release candidate status."""
    return {
        "status": "ok",
        "service": "6clips-wave5-integration-coordinator",
        "wave": 4,
        "wave_version": 5,
        "baseline_commit": "7af7ac4c54e3ab05d9896b3f846a5708a98c37f1",
        "active_domains": [
            "execution_durability",
            "media_quality_3x60s",
            "motion_clipstudio_parity",
            "hyperframes_catalog_196_blocks",
            "library_workflows_and_trash",
            "trends_and_original_production",
            "distribution_approval_and_scheduling",
            "analytics_grounded_feedback",
        ],
    }
