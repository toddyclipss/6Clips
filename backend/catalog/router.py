# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Catalog API Router: clean REST endpoints for the HyperFrames feature catalog."""
from __future__ import annotations

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from backend.catalog.manifest_service import CatalogManifestService, CatalogManifestError
from backend.catalog.poster_service import CatalogPosterService, CatalogPosterError
from backend.catalog.preview_engine import CatalogPreviewEngine
from backend.catalog.ghost_preview import GhostPreviewContract

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/catalog", tags=["catalog"])


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
    """Return the entire canonical runtime manifest with all 196 catalog blocks."""
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
):
    """Serve standalone animated HTML preview for catalog block."""
    try:
        html = CatalogPreviewEngine.get_preview_html(
            block_id,
            version_hash=version,
            aspect_ratio=aspect_ratio,
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


@router.get("/blocks/{block_id}/ghost-config")
async def get_block_ghost_config(
    block_id: str,
    aspect_ratio: str = Query("9:16"),
):
    """Return non-destructive hover preview configuration."""
    CatalogManifestService.validate_block_id(block_id)
    return GhostPreviewContract.get_preview_config(block_id, aspect_ratio=aspect_ratio)
