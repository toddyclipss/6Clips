# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Catalog API Router: clean REST endpoints for the HyperFrames feature catalog."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Response
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/catalog", tags=["catalog"])


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
    return CatalogManifestService.get_reconciliation_summary()


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
    }


@router.get("/blocks/{block_id}/poster")
async def get_block_poster(
    block_id: str,
    aspect_ratio: str = Query("9:16", description="Target aspect ratio: '9:16' or '16:9'"),
    version: Optional[str] = Query(None),
):
    """Serve cached truthful poster image for catalog block."""
    try:
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
    except (CatalogManifestError, Exception) as e:
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
        return CatalogProjectIntentAdapter.create_add_to_project_intent(block_id, payload)
    except CatalogManifestError as e:
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
