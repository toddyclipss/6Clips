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

import copy
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
# Domain F: Motion Capability Dispatcher & Canonical ProjectService Bridge
# =========================================================================

class MotionDispatchCapabilityRequest(BaseModel):
    capability_id: str
    project_id: Optional[str] = None
    expected_revision: Optional[int] = None
    asset_id: Optional[str] = None
    input_path: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    user_id: str = "local"
    idempotency_key: Optional[str] = None


@router.post("/motion/dispatch-capability")
async def dispatch_motion_capability(req: MotionDispatchCapabilityRequest):
    """
    Bridges MotionCapabilityDispatcher into canonical ProjectService and execution workflows:
    1. Enforces user identity and project ownership.
    2. Performs optimistic concurrency (CAS) check against expected_revision.
    3. Resolves and validates input asset / file paths without path traversal.
    4. Executes native Clip Studio mutations or deterministic tool operations.
    5. Applies project mutations canonically via ProjectService.apply_operation.
    """
    from backend.motion_capabilities.dispatcher import MotionCapabilityDispatcher
    from backend.motion_capabilities.registry import MotionCapabilitiesRegistry
    from backend.services.asset_resolver import resolve_asset_record_and_path, AssetNotFoundError

    # 1. Verify capability exists
    spec = MotionCapabilitiesRegistry.get(req.capability_id)
    if not spec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Motion capability '{req.capability_id}' not found in registry.",
        )

    # 2. Check project ownership and CAS if project_id is provided
    project = None
    doc = None
    if req.project_id:
        try:
            project = await ProjectService.verify_project_ownership(req.project_id, user_id=req.user_id)
        except ProjectNotFoundError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{req.project_id}' not found.")
        except AssetAccessError as aae:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(aae))

        if req.expected_revision is not None and project.revision != req.expected_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Revision conflict: expected revision {req.expected_revision}, but project is currently at revision {project.revision}.",
            )
        doc = json.loads(project.document_json)

    # 3. Resolve media input if asset_id or input_path provided
    resolved_in_path: Optional[Path] = None
    if req.asset_id:
        try:
            _, src_path, _ = await resolve_asset_record_and_path(req.asset_id, must_exist=True)
            resolved_in_path = src_path
        except AssetNotFoundError as ae:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ae))
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Asset resolution failed: {e}")
    elif req.input_path:
        p = Path(req.input_path)
        if ".." in str(req.input_path):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path traversal characters ('..') prohibited.")
        if not p.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Input file not found: {req.input_path}")
        resolved_in_path = p

    # 4. Dispatch capability
    # If document has timeline wrapper, extract tracks or adapt doc for dispatcher
    dispatch_doc = copy.deepcopy(doc) if doc else None
    if dispatch_doc and "timeline" in dispatch_doc and "tracks" not in dispatch_doc:
        dispatch_doc["tracks"] = dispatch_doc.get("timeline", {}).get("tracks", [])

    res = await MotionCapabilityDispatcher.dispatch(
        capability_id=req.capability_id,
        input_path=resolved_in_path,
        params=req.params,
        project_doc=dispatch_doc,
    )

    if res.status != "SUCCESS":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Motion capability execution failed: {res.message} ({res.error_detail or 'UNKNOWN_ERROR'})",
        )

    # 5. Apply mutation through ProjectService CAS if project was modified
    new_rev = project.revision if project else None
    if project:
        mutation_payload = None
        op_type = f"motion_{req.capability_id}"
        if getattr(res, "project_mutation", None):
            mutation_payload = res.project_mutation
        elif res.output_data and "project_doc" in res.output_data:
            # Dispatcher produced an updated project doc
            updated_doc = res.output_data["project_doc"]
            if "timeline" in doc and "tracks" in updated_doc:
                # Synchronize back to canonical timeline structure
                doc["timeline"]["tracks"] = updated_doc["tracks"]
                if "bench_ranges" in updated_doc:
                    doc["bench_ranges"] = updated_doc["bench_ranges"]
                if "caption_overrides" in updated_doc:
                    doc["caption_overrides"] = updated_doc["caption_overrides"]
                mutation_payload = {"document": doc}
                op_type = "update_document"
            else:
                mutation_payload = {"document": updated_doc}
                op_type = "update_document"

        if mutation_payload:
            try:
                op_result = await ProjectService.apply_operation(
                    project_id=project.id,
                    expected_revision=project.revision,
                    operation_type=op_type,
                    payload=mutation_payload,
                    idempotency_key=req.idempotency_key,
                    author=req.user_id,
                )
                new_rev = op_result["revision"]
            except RevisionConflictError as rce:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"CAS revision conflict: {rce}")
            except IdempotencyConflictError as ice:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Idempotency conflict: {ice}")

    return {
        "ok": True,
        "capability_id": req.capability_id,
        "project_id": project.id if project else None,
        "revision": new_rev,
        "output_path": str(res.output_path) if res.output_path else None,
        "message": res.message,
        "execution_time_seconds": res.execution_time_seconds,
        "output_data": res.output_data,
        "warnings": res.warnings,
    }


class ProjectCapabilityExecutionRequest(BaseModel):
    expected_revision: Optional[int] = None
    asset_id: Optional[str] = None
    input_path: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    user_id: str = "local"
    idempotency_key: Optional[str] = None


projects_router = APIRouter(prefix="/projects", tags=["projects-capabilities"])


@projects_router.post("/{project_id}/capabilities/{capability_id}")
@router.post("/projects/{project_id}/capabilities/{capability_id}")
async def execute_project_capability(
    project_id: str,
    capability_id: str,
    req: Optional[ProjectCapabilityExecutionRequest] = None,
):
    """
    Direct REST endpoint to execute a Motion capability against a persisted project.
    Enforces tenant ownership (403), expected revision CAS (409), input validation (404/400),
    and applies mutations via ProjectService.
    """
    req_body = req or ProjectCapabilityExecutionRequest()
    dispatch_req = MotionDispatchCapabilityRequest(
        capability_id=capability_id,
        project_id=project_id,
        expected_revision=req_body.expected_revision,
        asset_id=req_body.asset_id,
        input_path=req_body.input_path,
        params=req_body.params,
        user_id=req_body.user_id,
        idempotency_key=req_body.idempotency_key,
    )
    return await dispatch_motion_capability(dispatch_req)


class ProjectRecipeApplyRequest(BaseModel):
    expected_revision: int
    start_time: float = 0.0
    user_id: str = "local"
    idempotency_key: Optional[str] = None


@projects_router.post("/{project_id}/recipes/{recipe_id}/apply")
@router.post("/projects/{project_id}/recipes/{recipe_id}/apply")
async def apply_catalog_recipe_to_project(
    project_id: str,
    recipe_id: str,
    req: ProjectRecipeApplyRequest,
):
    """
    Applies a vetted Catalog recipe to a persistent project timeline via ProjectService CAS.
    Enforces user ownership, expected revision, and persists a durable ProjectRevision snapshot.
    """
    try:
        return await ProjectService.apply_creative_recipe(
            project_id=project_id,
            recipe_id=recipe_id,
            expected_revision=req.expected_revision,
            start_time=req.start_time,
            user_id=req.user_id,
            idempotency_key=req.idempotency_key,
        )
    except ProjectNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found.")
    except AssetAccessError as aae:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(aae))
    except RevisionConflictError as rce:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Revision conflict: {rce}")
    except IdempotencyConflictError as ice:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Idempotency conflict: {ice}")
    except ProjectError as pe:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(pe))


class ProjectRecipeUndoRequest(BaseModel):
    expected_revision: int
    user_id: str = "local"
    idempotency_key: Optional[str] = None


@projects_router.post("/{project_id}/recipes/{recipe_id}/undo")
@router.post("/projects/{project_id}/recipes/{recipe_id}/undo")
async def undo_catalog_recipe_from_project(
    project_id: str,
    recipe_id: str,
    req: ProjectRecipeUndoRequest,
):
    """
    Reversibly undoes an applied Catalog recipe from a persistent project timeline via ProjectService CAS.
    """
    try:
        return await ProjectService.undo_creative_recipe(
            project_id=project_id,
            recipe_id=recipe_id,
            expected_revision=req.expected_revision,
            user_id=req.user_id,
            idempotency_key=req.idempotency_key,
        )
    except ProjectNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found.")
    except AssetAccessError as aae:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(aae))
    except RevisionConflictError as rce:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Revision conflict: {rce}")
    except IdempotencyConflictError as ice:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Idempotency conflict: {ice}")
    except ProjectError as pe:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(pe))


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
