# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Catalog API Router: clean REST endpoints for the HyperFrames feature catalog."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Response, Body
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from backend.catalog.manifest_service import CatalogManifestService, CatalogManifestError
from backend.catalog.poster_service import CatalogPosterService, CatalogPosterError
from backend.catalog.preview_engine import CatalogPreviewEngine
from backend.catalog.ghost_preview import GhostPreviewContract
from backend.catalog.project_intent_contract import (
    AddToProjectIntentRequest,
    AddToProjectIntentResult,
    CatalogProjectIntentAdapter,
)
from backend.catalog.render_probe import CatalogRenderProbe, CatalogRenderProbeError
from backend.catalog.vetted_capabilities import VettedCapabilityRegistry

from backend.catalog.export_contract import CatalogExportContract, CatalogExportContractError
from backend.catalog.creative_recipes import CreativeRecipeEngine, CustomBlockPromptSpec

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/wave11-audit")
async def get_wave11_audit():
    """Return Wave 11 12-block verification audit, proof ledger, state machine status, and canonical export contract v2.2.0."""
    return CatalogManifestService.get_wave11_factual_audit()


@router.get("/state-machine")
async def get_catalog_state_machine():
    """Return single source-of-truth Catalog state machine definition and supported transitions."""
    return {
        "status": "ACTIVE",
        "states": ["LOADING", "READY_ITEMS", "EMPTY_FILTER", "ERROR_RETRYABLE", "OFFLINE_BLOCKED"],
        "initial_state": "LOADING",
        "terminal_skeleton_guard": True,
        "cancellation_semantics": "ABORT_SUPERSEDED_REQUESTS",
        "stale_filter_guard": "ACTIVE_REQUEST_ID_MATCH",
        "retry_action_enabled": True,
        "working_blocks_count": 12,
        "withheld_donor_blocks_count": 186,
        "total_inventoried": 196,
    }


@router.get("/wave10-audit")
async def get_wave10_audit():
    """Return Wave 10 12-block verification audit, 12-row proof ledger, canonical export contract v2.1.0, and quarantine status."""
    return CatalogManifestService.get_wave10_factual_audit()


@router.post("/blocks/{block_id}/edited-instance-sequence")
async def post_block_edited_instance_sequence(
    block_id: str,
    payload: Dict[str, Any] = Body(default_factory=dict),
):
    """Capture Playwright browser frames across multiple timestamps for an EDITED instance with custom variables."""
    try:
        import asyncio
        custom_vars = payload.get("custom_variables") or {}
        timestamps = payload.get("timestamps") or [0.0, 1.0, 2.0]
        aspect_ratio = payload.get("aspect_ratio") or "9:16"
        instance_id = payload.get("instance_id")
        return await asyncio.to_thread(
            CatalogExportContract.capture_edited_instance_sequence,
            block_id=block_id,
            custom_variables=custom_vars,
            timestamps=timestamps,
            aspect_ratio=aspect_ratio,
            instance_id=instance_id,
        )
    except (CatalogManifestError, CatalogExportContractError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Error generating edited instance sequence for %s: %s", block_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/blocks/{block_id}/canonical-instance-mp4-overlay")
async def post_block_canonical_instance_mp4_overlay(
    block_id: str,
    payload: Dict[str, Any] = Body(default_factory=dict),
):
    """Render canonical transparent overlay video from an EDITED block instance with ffprobe analysis."""
    try:
        import asyncio
        custom_vars = payload.get("custom_variables") or {}
        aspect_ratio = payload.get("aspect_ratio") or "9:16"
        duration_seconds = float(payload.get("duration_seconds", 2.0))
        return await asyncio.to_thread(
            CatalogExportContract.render_canonical_instance_mp4_overlay,
            block_id=block_id,
            custom_variables=custom_vars,
            aspect_ratio=aspect_ratio,
            duration_seconds=duration_seconds,
        )
    except (CatalogManifestError, CatalogExportContractError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Error generating canonical instance mp4 overlay for %s: %s", block_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/creative-recipes/{recipe_id}/modify-in-document")
async def modify_recipe_in_document(
    recipe_id: str,
    payload: Dict[str, Any] = Body(...),
):
    """Modify parameters across all timeline clips inserted by the specified recipe."""
    try:
        doc = payload.get("document") or {}
        variable_overrides = payload.get("variable_overrides") or {}
        return CreativeRecipeEngine.modify_recipe_in_project_document(
            doc=doc,
            recipe_id=recipe_id,
            variable_overrides=variable_overrides,
        )
    except (CatalogManifestError, Exception) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/creative-recipes/{recipe_id}/undo-from-document")
async def undo_recipe_from_document(
    recipe_id: str,
    payload: Dict[str, Any] = Body(...),
):
    """Reversibly remove all timeline clips and code files inserted by the specified recipe."""
    try:
        doc = payload.get("document") or {}
        return CreativeRecipeEngine.undo_recipe_from_project_document(
            doc=doc,
            recipe_id=recipe_id,
        )
    except (CatalogManifestError, Exception) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/wave9-audit")
async def get_wave9_audit():
    """Return Wave 9 12-block verification audit, 12-row proof ladder, canonical export contract v2.0.0, and quarantine status."""
    return CatalogManifestService.get_wave9_factual_audit()


@router.get("/blocks/{block_id}/multi-timestamp-sequence")
async def get_block_multi_timestamp_sequence(
    block_id: str,
    timestamps: Optional[str] = Query(None, description="Comma-separated timestamps e.g. 0.0,1.0,2.0"),
):
    """Capture Playwright browser frames across multiple timestamps to verify physical animation and alpha transparency."""
    try:
        import asyncio
        parsed_ts = [float(t.strip()) for t in timestamps.split(",")] if timestamps else [0.0, 1.0, 2.0]
        return await asyncio.to_thread(
            CatalogExportContract.capture_multi_timestamp_sequence,
            block_id=block_id,
            timestamps=parsed_ts,
        )
    except (CatalogManifestError, CatalogExportContractError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Error generating multi-timestamp sequence for %s: %s", block_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/blocks/{block_id}/canonical-export-contract")
async def get_block_canonical_export_contract(
    block_id: str,
    aspect_ratio: str = Query("9:16", description="Target aspect ratio: '9:16' or '16:9'"),
):
    """Return Wave 9 Version 2.0.0 Canonical Motion Export Contract with layout safe margins and FFmpeg recipes for Role 2."""
    try:
        return CatalogExportContract.generate_canonical_motion_export_contract(
            block_id=block_id,
            aspect_ratio=aspect_ratio,
        )
    except (CatalogManifestError, CatalogExportContractError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Error generating canonical export contract for %s: %s", block_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/blocks/{block_id}/transparent-overlay-video")
async def get_block_transparent_overlay_video(
    block_id: str,
    aspect_ratio: str = Query("9:16", description="Target aspect ratio: '9:16' or '16:9'"),
    duration_seconds: float = Query(2.0, ge=0.5, le=30.0),
):
    """Generate physical transparent overlay video with alpha channel verified by ffprobe."""
    try:
        import asyncio
        return await asyncio.to_thread(
            CatalogExportContract.generate_transparent_video_overlay,
            block_id=block_id,
            aspect_ratio=aspect_ratio,
            duration_seconds=duration_seconds,
        )
    except (CatalogManifestError, CatalogExportContractError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Error generating transparent overlay video for %s: %s", block_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wave8-audit")
async def get_wave8_audit():
    """Return Wave 8 12-block verification audit, proof ladder per block, and real browser/MP4 proofs."""
    return CatalogManifestService.get_wave8_factual_audit()


@router.get("/blocks/{block_id}/browser-proof")
async def get_block_browser_proof(
    block_id: str,
    viewport_width: int = Query(1080, ge=320, le=3840),
    viewport_height: int = Query(1920, ge=320, le=3840),
):
    """Run real local browser execution and capture timed visual proof with temporal variance."""
    try:
        import asyncio
        return await asyncio.to_thread(
            CatalogExportContract.verify_dynamic_browser_proof,
            block_id=block_id,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
        )
    except (CatalogManifestError, CatalogExportContractError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Error generating browser proof for %s: %s", block_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/blocks/{block_id}/mp4-proof")
async def get_block_mp4_proof(
    block_id: str,
    aspect_ratio: str = Query("9:16", description="Target aspect ratio: '9:16' or '16:9'"),
):
    """Run physical FFmpeg MP4 composition with ffprobe analysis and sampled video frames."""
    try:
        import asyncio
        return await asyncio.to_thread(
            CatalogExportContract.render_e2e_mp4_overlay_proof,
            block_id=block_id,
            aspect_ratio=aspect_ratio,
        )
    except (CatalogManifestError, CatalogExportContractError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Error generating MP4 proof for %s: %s", block_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/creative-recipes/{recipe_id}/apply-to-document")
async def apply_recipe_to_document(
    recipe_id: str,
    payload: Dict[str, Any] = Body(...),
):
    """Apply vetted creative recipe to canonical project document, inserting real timeline clips and code files."""
    try:
        doc = payload.get("document") or {}
        start_time = float(payload.get("start_time", 0.0))
        return CreativeRecipeEngine.apply_recipe_to_project_document(
            doc=doc,
            recipe_id=recipe_id,
            start_time=start_time,
        )
    except (CatalogManifestError, Exception) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/wave7-audit")
async def get_wave7_audit():
    """Return Wave 7 renderability audit, proof ladder per block, and export contracts."""
    return CatalogManifestService.get_wave7_factual_audit()


@router.get("/blocks/{block_id}/overlay-contract")
async def get_block_overlay_contract(
    block_id: str,
    aspect_ratio: str = Query("9:16", description="Target aspect ratio: '9:16' or '16:9'"),
):
    """Return verifiable E2E overlay export contract with timing, safe margins, and alpha semantics."""
    try:
        return CatalogExportContract.generate_e2e_overlay_contract(block_id=block_id, aspect_ratio=aspect_ratio)
    except (CatalogManifestError, CatalogExportContractError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/blocks/{block_id}/alpha-probe")
async def get_block_alpha_probe(block_id: str):
    """Verify physical RGBA frame with alpha transparency for overlay block."""
    try:
        return CatalogExportContract.verify_physical_alpha_frame(block_id=block_id)
    except (CatalogManifestError, CatalogExportContractError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/creative-recipes/{recipe_id}/execute")
async def execute_recipe_to_timeline(
    recipe_id: str,
    project_id: str = Query("proj_draft", description="Target composition project ID"),
    owning_user_id: str = Query("user_default", description="Owning user ID"),
):
    """Translate vetted creative recipe into validated timeline items ready for ProjectService insertion."""
    try:
        return CreativeRecipeEngine.execute_recipe_to_timeline(
            recipe_id=recipe_id,
            project_id=project_id,
            owning_user_id=owning_user_id,
        )
    except (CatalogManifestError, Exception) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/wave6-audit")
async def get_wave6_audit():
    """Return Wave 6 functional blocks, vetted recipes, and proof ladder verification status."""
    return CatalogManifestService.get_wave6_factual_audit()


@router.get("/creative-recipes")
async def get_creative_recipes():
    """Return vetted creative editor/agent recipes adhering to motion doctrines."""
    recipes = CreativeRecipeEngine.get_registered_recipes()
    return {"count": len(recipes), "recipes": [r.model_dump() for r in recipes]}


@router.get("/creative-recipes/{recipe_id}")
async def get_creative_recipe_by_id(recipe_id: str):
    """Return specific creative editor/agent recipe by ID."""
    recipe = CreativeRecipeEngine.get_recipe_by_id(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail=f"Creative recipe '{recipe_id}' not found.")
    return recipe.model_dump()


@router.post("/synthesize-block")
async def synthesize_custom_block(spec: CustomBlockPromptSpec):
    """Synthesize a new legitimate, offline-capable, licensed custom block from prompt spec (GT-14)."""
    try:
        return CreativeRecipeEngine.synthesize_custom_block(spec)
    except Exception as e:
        logger.error("Failed to synthesize custom block: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/blocks/{block_id}/export-manifest")
async def get_block_export_manifest(
    block_id: str,
    aspect_ratio: str = Query("9:16", description="Target aspect ratio: '9:16' or '16:9'"),
):
    """Generate machine-readable export manifest consumable by Role 2 FFmpeg pipeline."""
    try:
        return CatalogExportContract.generate_export_manifest(block_id=block_id, aspect_ratio=aspect_ratio)
    except (CatalogManifestError, CatalogExportContractError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/blocks/{block_id}/frame-proof")
async def get_block_frame_proof(
    block_id: str,
    aspect_ratio: str = Query("9:16", description="Target aspect ratio: '9:16' or '16:9'"),
    sample_count: int = Query(5, ge=2, le=20),
):
    """Compute deterministic multi-timestamp frame proofs verifying dynamic temporal motion."""
    try:
        return CatalogExportContract.compute_dynamic_frame_proof(
            block_id=block_id,
            aspect_ratio=aspect_ratio,
            sample_count=sample_count,
        )
    except (CatalogManifestError, CatalogExportContractError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/wave5-audit")
async def get_wave5_audit():
    """Return Wave 5 whole-tree audit, donor vs 6Clips separation, and rigorous verification gates."""
    return CatalogManifestService.get_wave5_factual_audit()


@router.get("/vetted-capabilities")
async def get_vetted_capabilities():
    """Return vetted creative motion doctrines, continuous camera laws, and caption models."""
    items = VettedCapabilityRegistry.get_all_vetted_doctrines()
    for it in items:
        it["id"] = it.get("doctrine_id")
    return {"count": len(items), "capabilities": items}


@router.get("/vetted-capabilities/{capability_id}")
async def get_vetted_capability_by_id(capability_id: str):
    """Return single vetted creative capability by ID."""
    try:
        return VettedCapabilityRegistry.get_vetted_doctrine(capability_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Vetted capability '{capability_id}' not found.")


@router.get("/source-audit/summary")
async def get_source_audit_summary():
    """Return the machine-readable summary of the 9,059 audited source files in the donor tree."""
    import json
    sum_path = Path(__file__).parent / "hyperframes_source_tree_audit_summary.json"
    if not sum_path.exists():
        raise HTTPException(status_code=404, detail="Audit summary not generated.")
    return json.loads(sum_path.read_text(encoding="utf-8"))


@router.get("/source-audit/records")
async def query_source_audit_records(
    category: Optional[str] = Query(None, description="Filter by category (registry-block, monorepo-package, skill, etc.)"),
    query: Optional[str] = Query(None, description="Search query over file path or intended utility"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Query paginated records from the 9,059-file whole-tree audit inventory."""
    return CatalogManifestService.query_source_audit_records(
        category=category,
        query=query,
        limit=limit,
        offset=offset,
    )


@router.get("/factual-counts")
async def get_factual_counts(wave: int = Query(3, description="Wave version for factual counts: 3 or 4")):
    """Return factual counts for acceptance reporting."""
    return CatalogManifestService.get_factual_counts(wave=wave)


@router.get("/wave4-factual-counts")
async def get_wave4_factual_counts():
    """Return factual counts for Wave 4 Role 3 acceptance reporting."""
    return CatalogManifestService.get_wave4_factual_counts()


@router.get("/factual-audit")
async def get_factual_audit():
    """Return before/after audit comparison between Wave 3 baseline and Wave 4 expanded counts."""
    return CatalogManifestService.get_factual_audit()


@router.get("/category-summary")
async def get_category_summary():
    """Return per-category breakdown of operational items and actionable blockers."""
    return CatalogManifestService.get_category_summary()


@router.get("/probes/all")
async def probe_all_blocks():
    """Run physical render probes across all internalized blocks."""
    return CatalogRenderProbe.probe_all_internalized_blocks()


@router.get("/blocks/{block_id}/probe")
async def probe_single_block(
    block_id: str,
    aspect_ratio: str = Query("9:16", description="Target aspect ratio: '9:16' or '16:9'"),
):
    """Run physical render probe for a specific block buffer."""
    try:
        return CatalogRenderProbe.probe_block_render(block_id=block_id, aspect_ratio=aspect_ratio)
    except (CatalogManifestError, CatalogRenderProbeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Error probing block %s: %s", block_id, e)
        raise HTTPException(status_code=500, detail="Could not execute render probe.")


@router.get("/items")
async def list_catalog_items(
    category: Optional[str] = Query(None, description="Filter by category (all, call-to-action, typography, etc.)"),
    search: Optional[str] = Query(None, description="Search by title, description, or tags"),
    aspect_ratio: Optional[str] = Query(None, description="Filter by supported aspect ratio (9:16 or 16:9)"),
    disposition: Optional[str] = Query(None, description="Filter by disposition (SHIP, FIX, UNSUPPORTED)"),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List catalog blocks with truthful poster and preview URLs, aspect compatibility, and release dispositions."""
    res = CatalogManifestService.list_items(
        category=category,
        search=search,
        aspect_ratio=aspect_ratio,
        disposition=disposition,
        limit=limit,
        offset=offset,
    )
    enriched_items = []
    for it in res["items"]:
        b_id = it.get("id")
        enriched_items.append({
            **it,
            "poster_url": f"/api/catalog/blocks/{b_id}/poster",
            "preview_url": f"/api/catalog/blocks/{b_id}/preview",
        })

    return {
        "total": res["total"],
        "limit": res["limit"],
        "offset": res["offset"],
        "items": enriched_items,
        "facets": res["facets"],
    }


@router.get("/items/{block_id}")
async def get_catalog_item(block_id: str):
    """Get single catalog block details including variables, license, and provenance."""
    try:
        item = CatalogManifestService.get_item(block_id)
        if not item:
            raise HTTPException(status_code=404, detail=f"Catalog block '{block_id}' not found.")
        return {
            **item,
            "poster_url": f"/api/catalog/blocks/{block_id}/poster",
            "preview_url": f"/api/catalog/blocks/{block_id}/preview",
            "ghost_config": GhostPreviewContract.get_preview_config(block_id),
        }
    except CatalogManifestError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/inventory")
async def get_catalog_inventory(
    filter: Optional[str] = Query(None, description="Filter mode: 'all', 'operational', 'unported', 'needs_adaptation', 'blocked', 'eligible'"),
    search: Optional[str] = Query(None, description="Search by ID, title, description, or blocker reason"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(50, ge=1, le=300),
    offset: int = Query(0, ge=0),
    snapshot: bool = Query(False, description="Return complete unpaginated 196-item snapshot"),
):
    """
    Wave 15 / Wave 14: Truthful full-inventory endpoint reconciling packaged v1 metadata
    from backend/catalog_inventory/hyperframes_196_inventory.json with actual on-disk shipped blocks.
    Supports complete snapshot traversal to avoid row truncation.
    """
    try:
        return CatalogManifestService.list_wave14_inventory_items(
            filter_type=filter,
            search=search,
            category=category,
            limit=limit,
            offset=offset,
            snapshot=snapshot,
        )
    except CatalogManifestError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Error listing catalog inventory: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/inventory/snapshot")
async def get_catalog_inventory_snapshot():
    """Return complete unpaginated 196-item donor inventory snapshot."""
    try:
        return CatalogManifestService.list_wave14_inventory_items(limit=300, offset=0, snapshot=True)
    except CatalogManifestError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/wave15-audit")
async def get_wave15_audit():
    """Return Wave 15 canonical inventory reconciliation, proof ladder, and native category taxonomy."""
    try:
        return CatalogManifestService.get_wave15_factual_audit()
    except Exception as e:
        logger.error("Error generating wave15 audit: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wave14-audit")
async def get_wave14_audit():
    """Return Wave 14 Stage 1 full inventory reconciliation and census audit."""
    try:
        return CatalogManifestService.get_wave14_reconciliation()
    except CatalogManifestError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Error generating wave14 audit: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/manifest")
async def get_full_manifest():
    """Return the entire canonical runtime manifest with all catalog blocks."""
    try:
        items = CatalogManifestService.get_all_items()
        summary = CatalogManifestService.get_reconciliation_summary()
        return {
            "total_blocks": len(items),
            "reconciliation": summary["reconciliation"],
            "dispositions": summary["block_inventory"],
            "items": items,
        }
    except CatalogManifestError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reconciliation")
async def get_reconciliation():
    """Return evidence-backed reconciliation metrics (196 historical dirs, 170 aggregate items, 26 unbundled)."""
    base_summary = CatalogManifestService.get_reconciliation_summary()
    base_summary["wave14_reconciliation"] = CatalogManifestService.get_wave14_reconciliation()
    return base_summary


@router.get("/audit")
async def get_catalog_audit():
    """Return catalog licenses, donor independence status, and provenance inventory."""
    inventory = CatalogManifestService.get_license_inventory()
    summary = CatalogManifestService.get_reconciliation_summary()
    return {
        "donor_independence": {
            "runtime_donor_required": False,
            "manifest_internalized": True,
            "shipped_blocks_packaged": True,
        },
        "inventory": inventory,
        "summary": summary,
        "factual_audit": CatalogManifestService.get_factual_audit(),
        "wave14_reconciliation": CatalogManifestService.get_wave14_reconciliation(),
    }


@router.get("/blocks/{block_id}/poster")
async def get_block_poster(
    block_id: str,
    aspect_ratio: str = Query("9:16", description="Target aspect ratio: '9:16' or '16:9'"),
    version: Optional[str] = Query(None),
):
    """Serve cached truthful poster image for catalog block."""
    try:
        CatalogManifestService.validate_block_operable(block_id, allow_retired=True)
        poster_path = CatalogPosterService.get_poster_path(
            block_id,
            version_hash=version,
            aspect_ratio=aspect_ratio,
        )
        return FileResponse(
            poster_path,
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=86400, immutable",
                "Access-Control-Allow-Origin": "*",
            },
        )
    except (CatalogManifestError, CatalogPosterError) as e:
        err_msg = str(e).lower()
        if "quarantined" in err_msg or "uninternalized" in err_msg:
            raise HTTPException(status_code=403, detail=str(e))
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Error serving poster for %s: %s", block_id, e)
        raise HTTPException(status_code=500, detail="Could not generate poster image.")


@router.get("/blocks/{block_id}/preview")
async def get_block_preview(
    block_id: str,
    aspect_ratio: str = Query("9:16", description="Target aspect ratio: '9:16' or '16:9'"),
    version: Optional[str] = Query(None),
    viewport_width: Optional[int] = Query(None, description="Custom viewport width for responsive inspection"),
    viewport_height: Optional[int] = Query(None, description="Custom viewport height for responsive inspection"),
):
    """Serve standalone animated HTML preview for catalog block."""
    try:
        CatalogManifestService.validate_block_operable(block_id)
        html = CatalogPreviewEngine.get_preview_html(
            block_id,
            version_hash=version,
            aspect_ratio=aspect_ratio,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
        )
        return HTMLResponse(
            html,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "no-cache",
            },
        )
    except CatalogManifestError as e:
        err_msg = str(e).lower()
        if "retired" in err_msg:
            raise HTTPException(status_code=409, detail=str(e))
        if "quarantined" in err_msg or "uninternalized" in err_msg:
            raise HTTPException(status_code=403, detail=str(e))
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/blocks/{block_id}/assets/{asset_name:path}")
async def get_block_asset(block_id: str, asset_name: str):
    """Serve bundled local assets (images, fonts) for shipped blocks with strict boundary checks."""
    CatalogManifestService.validate_block_id(block_id)
    if any(bad in asset_name for bad in ["..", "\\", "%2e", "%2f", "\x00"]):
        raise HTTPException(status_code=400, detail="Invalid asset name")
    shipped_root = Path(__file__).parent / "shipped_blocks"
    asset_file = (shipped_root / block_id / "assets" / asset_name).resolve()
    base_assets_dir = (shipped_root / block_id / "assets").resolve()
    if not str(asset_file).startswith(str(base_assets_dir)) or not asset_file.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")
    media_type = "image/jpeg" if asset_name.endswith(".jpg") else "font/woff2" if asset_name.endswith(".woff2") else "application/octet-stream"
    return FileResponse(asset_file, media_type=media_type)


@router.get("/blocks/{block_id}/lib/{lib_name:path}")
async def get_block_lib(block_id: str, lib_name: str):
    """Serve bundled vendor scripts/shaders for shipped blocks with strict boundary checks."""
    CatalogManifestService.validate_block_id(block_id)
    if any(bad in lib_name for bad in ["..", "\\", "%2e", "%2f", "\x00"]):
        raise HTTPException(status_code=400, detail="Invalid library name")
    shipped_root = Path(__file__).parent / "shipped_blocks"
    lib_file = (shipped_root / block_id / "lib" / lib_name).resolve()
    base_lib_dir = (shipped_root / block_id / "lib").resolve()
    if not str(lib_file).startswith(str(base_lib_dir)) or not lib_file.is_file():
        raise HTTPException(status_code=404, detail="Library file not found")
    media_type = "application/javascript" if lib_name.endswith(".js") else "text/plain"
    return FileResponse(lib_file, media_type=media_type)


@router.get("/blocks/{block_id}/ghost-config")
async def get_block_ghost_config(
    block_id: str,
    aspect_ratio: str = Query("9:16"),
):
    """Return non-destructive hover preview configuration."""
    CatalogManifestService.validate_block_id(block_id)
    return GhostPreviewContract.get_preview_config(block_id, aspect_ratio=aspect_ratio)


@router.post("/blocks/{block_id}/intent/add-to-project", response_model=AddToProjectIntentResult)
async def create_add_to_project_intent(
    block_id: str,
    payload: AddToProjectIntentRequest,
):
    """
    Validate and produce a normalized timeline item insertion intent for coordinator wiring.
    Does NOT mutate ProjectService directly (strictly respects component ownership boundaries).
    """
    try:
        CatalogManifestService.validate_block_operable(block_id)
        return CatalogProjectIntentAdapter.create_add_to_project_intent(block_id, payload, strict_quarantine=True)
    except CatalogManifestError as e:
        err_msg = str(e).lower()
        if "retired" in err_msg:
            raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Error creating add-to-project intent for %s: %s", block_id, e)
        raise HTTPException(status_code=500, detail="Could not create add-to-project intent.")


@router.post("/blocks/{block_id}/invalidate-poster")
async def invalidate_block_poster(block_id: str):
    """Invalidate cached poster images for this block when source or variables change."""
    try:
        deleted_count = CatalogPosterService.invalidate_block_poster(block_id)
        return {
            "block_id": block_id,
            "status": "CACHE_INVALIDATED",
            "deleted_posters_count": deleted_count,
        }
    except CatalogManifestError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Error invalidating poster for %s: %s", block_id, e)
        raise HTTPException(status_code=500, detail="Could not invalidate poster.")
