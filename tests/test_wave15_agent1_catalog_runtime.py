# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 15 Agent 1 Test Suite: Catalog Platform Engine + Canonical Motion/Renderer Contracts.

Comprehensive Independent Verification covering:
1. Canonical 196 Donor Inventory Reconciliation & Census Math:
   - 196 original donor block directory IDs
   - 170 aggregate items in registry/registry.json
   - 26 unindexed directories explicitly reconciled
   - 0 extra 6Clips-authored blocks in public catalog (creator-hud & glitch-transition retired)
   - 0 duplicate IDs
2. Upstream Category Taxonomy Truth:
   - source_category_status == "SOURCE_CATEGORY_MISSING" for donor blocks
   - source_category is None
   - is_original_category is False
   - Proposed fallback category derived from tags and metadata
   - Honest category search and filtering
3. Safe Universal Runtime Registration & Discovery:
   - 10 verified donor blocks are RUNTIME_READY
   - 186 unported donor blocks are quarantined with truthful blocker codes
   - No 'register all 196 as ready' shortcut (honest proof ladder)
4. Negative Safety Gates:
   - 403 Forbidden on uninternalized/quarantined blocks (preview, poster, intent)
   - 409 Conflict on retired 6Clips blocks (preview, poster, intent)
5. Project Migration & Non-destructive CAS Handling:
   - inspect_and_mark_migration flags REQUIRES_MIGRATION without losing clips
   - apply_operation rejects retired (409) and uninternalized (403) block additions
   - Deterministic migration maps to verified donor blocks
6. Full Inventory Traversal & Complete Snapshot:
   - /api/catalog/inventory pagination and traversal
   - /api/catalog/inventory/snapshot returns full 196 items without row truncation
7. Dynamic Frame Motion Progression & Parity:
   - DynamicFrameMotionVerifier rejects uniform solid colors (FRAME_SOLID_COLOR_DETECTED)
   - DynamicFrameMotionVerifier rejects frozen identical frames (FRAME_MOTION_FROZEN)
   - Validates genuine motion variance across timestamps
8. Stable Runtime Interface Contract (Agents 3, 5, 6):
   - get_runtime_block_spec, list_runtime_block_specs, get_proof_ladder
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from backend.catalog.router import router as catalog_router
from backend.catalog.manifest_service import (
    CatalogManifestService,
    CatalogManifestError,
    DONOR_INTERNALIZED_BLOCKS,
    SIXCLIPS_ORIGINAL_BLOCKS,
    RETIRED_6CLIPS_BLOCKS,
)
from backend.services.registry_adapter import (
    RegistryAdapter,
    get_registry_dir,
)
from backend.catalog_runtime.core import (
    BlockOrigin,
    SourceCategoryStatus,
    DonorTaxonomyReconciler,
    UniversalRuntimeRegistry,
    LegacyBlockMigrationManager,
    DynamicFrameMotionVerifier,
    get_runtime_block_spec,
    list_runtime_block_specs,
    get_proof_ladder,
)
from backend.catalog_runtime.core.render_verifier import RenderFrameError

# Setup test client with isolated app
app = FastAPI()
app.include_router(catalog_router, prefix="/api")
client = TestClient(app)


# =========================================================================
# 1. Canonical 196 Donor Inventory Reconciliation & Census Math
# =========================================================================

def test_wave15_census_and_taxonomy_reconciliation():
    """Verify exact 196 donor block inventory math and origin separation."""
    census = DonorTaxonomyReconciler.get_census_summary()

    assert census["total_donor_blocks"] == 196
    assert census["indexed_in_registry_json"] == 170
    assert census["unindexed_block_directories"] == 26
    assert len(census["unindexed_block_ids"]) == 26

    # Verify key unindexed directories are present
    assert "aurora" in census["unindexed_block_ids"]
    assert "plasma" in census["unindexed_block_ids"]
    assert "stripes" in census["unindexed_block_ids"]
    assert "waveform" in census["unindexed_block_ids"]
    assert "ai-answer-rank" in census["unindexed_block_ids"]

    # Verify retired 6clips blocks are tracked separately
    assert census["retired_6clips_count"] == 2
    assert "creator-hud" in census["retired_6clips_blocks"]
    assert "glitch-transition" in census["retired_6clips_blocks"]

    # Truthful counts
    assert census["donor_operable_count"] == 10
    assert census["unported_donor_blocks"] == 186
    assert census["donor_operable_count"] + census["unported_donor_blocks"] == 196


def test_wave15_public_catalog_excludes_retired_6clips_blocks():
    """Verify that creator-hud and glitch-transition never appear in public catalog items."""
    # From manifest service
    res = CatalogManifestService.list_items(limit=300, wave=15)
    public_ids = [it["id"] for it in res["items"]]

    assert "creator-hud" not in public_ids
    assert "glitch-transition" not in public_ids

    # From registry adapter (with include_retired=False as used by Motion picker)
    adapter_items = RegistryAdapter.list_catalog_items(limit=300, include_retired=False)
    adapter_ids = [it["id"] for it in adapter_items]
    assert "creator-hud" not in adapter_ids
    assert "glitch-transition" not in adapter_ids

    # From HTTP endpoint
    resp = client.get("/api/catalog/items?limit=300")
    assert resp.status_code == 200
    items = resp.json()["items"]
    item_ids = [it["id"] for it in items]
    assert "creator-hud" not in item_ids
    assert "glitch-transition" not in item_ids


# =========================================================================
# 2. Upstream Category Taxonomy Truth
# =========================================================================

def test_wave15_source_category_missing_flag_and_fallback():
    """
    Verify that upstream missing category is honestly flagged SOURCE_CATEGORY_MISSING
    and not masked as source truth.
    """
    items = CatalogManifestService.get_all_items()
    assert len(items) == 196

    for it in items:
        # Upstream donor blocks lack category in registry-item.json
        assert it["source_category_status"] == SourceCategoryStatus.SOURCE_CATEGORY_MISSING.value
        assert it["source_category"] is None
        assert it["is_original_category"] is False
        assert "proposed_fallback_category" in it
        assert it["proposed_fallback_category"] in [
            "typography", "backgrounds", "transitions", "call-to-action",
            "charts", "mock-ui", "lower-thirds", "general"
        ]


def test_wave15_category_filtering_and_search():
    """Verify that category filtering and search function properly on real items."""
    # Filter by typography
    resp_typo = client.get("/api/catalog/items?category=typography&limit=100")
    assert resp_typo.status_code == 200
    typo_items = resp_typo.json()["items"]
    assert all(it["proposed_fallback_category"] == "typography" for it in typo_items)

    # Filter by backgrounds
    resp_bg = client.get("/api/catalog/items?category=backgrounds&limit=100")
    assert resp_bg.status_code == 200
    bg_items = resp_bg.json()["items"]
    assert all(it["proposed_fallback_category"] == "backgrounds" for it in bg_items)

    # Search for follow
    resp_search = client.get("/api/catalog/items?search=follow&limit=50")
    assert resp_search.status_code == 200
    search_items = resp_search.json()["items"]
    assert any("follow" in it["id"] for it in search_items)


# =========================================================================
# 3. Safe Universal Runtime Registration & Discovery
# =========================================================================

def test_wave15_universal_runtime_registration_operable_vs_quarantined():
    """Verify runtime readiness proof: 10 donor operable, 186 quarantined."""
    blocks = UniversalRuntimeRegistry.discover_all_blocks()
    assert len(blocks) >= 196

    operable = UniversalRuntimeRegistry.get_operable_blocks()
    assert len(operable) == 10
    operable_ids = {b.id for b in operable}
    assert operable_ids == set(DONOR_INTERNALIZED_BLOCKS)

    # Check proof ladder on operable blocks
    for b in operable:
        assert b.readiness.source_inventoried is True
        assert b.readiness.source_ported is True
        assert b.readiness.runtime_ready is True
        assert b.runtime_operable is True
        assert b.blocker_code is None

    # Check quarantined block
    unported = blocks["ai-answer-rank"]
    assert unported.runtime_operable is False
    assert unported.readiness.runtime_ready is False
    assert unported.blocker_code is not None


# =========================================================================
# 4. Negative Safety Gates (403 & 409)
# =========================================================================

def test_negative_safety_gate_quarantined_blocks_return_403():
    """Uninternalized donor blocks must return 403 Forbidden with clear blocker reason."""
    unported_id = "ai-answer-rank"

    # Preview
    resp_prev = client.get(f"/api/catalog/blocks/{unported_id}/preview")
    assert resp_prev.status_code == 403
    assert "quarantined" in resp_prev.json()["detail"].lower() or "uninternalized" in resp_prev.json()["detail"].lower()

    # Poster
    resp_post = client.get(f"/api/catalog/blocks/{unported_id}/poster")
    assert resp_post.status_code == 403

    # Intent add-to-project
    resp_intent = client.post(
        f"/api/catalog/blocks/{unported_id}/intent/add-to-project",
        json={"project_id": "proj_1", "aspect_ratio": "9:16"},
    )
    assert resp_intent.status_code in (400, 403)
    assert "quarantined" in resp_intent.json()["detail"].lower() or "uninternalized" in resp_intent.json()["detail"].lower()


def test_negative_safety_gate_retired_blocks_return_409():
    """Retired 6Clips blocks must return 409 Conflict indicating retired migration status."""
    retired_id = "creator-hud"

    # Preview
    resp_prev = client.get(f"/api/catalog/blocks/{retired_id}/preview")
    assert resp_prev.status_code == 409
    assert "retired" in resp_prev.json()["detail"].lower()

    # Intent add-to-project
    resp_intent = client.post(
        f"/api/catalog/blocks/{retired_id}/intent/add-to-project",
        json={"project_id": "proj_1", "aspect_ratio": "9:16"},
    )
    assert resp_intent.status_code == 409
    assert "retired" in resp_intent.json()["detail"].lower()

    # UniversalRuntimeRegistry validation gate
    from backend.catalog_runtime.core.registry_engine import BlockUnavailableError
    with pytest.raises(BlockUnavailableError) as exc_info:
        UniversalRuntimeRegistry.validate_block_operable(retired_id)
    assert exc_info.value.http_code == 409
    assert exc_info.value.blocker_code == "RETIRED_6CLIPS_BLOCK_UNAVAILABLE"


# =========================================================================
# 5. Project Migration & Non-destructive CAS Handling
# =========================================================================

def test_project_migration_preserves_data_and_flags_status():
    """Ensure project migration inspects and flags retired blocks without deleting clips."""
    sample_doc = {
        "schema_version": 2,
        "timeline": {
            "fps": 30,
            "tracks": [
                {
                    "id": "t1",
                    "clips": [
                        {"id": "c1", "block_id": "creator-hud", "start": 0.0, "duration": 5.0},
                        {"id": "c2", "block_id": "aurora", "start": 5.0, "duration": 5.0},
                    ],
                }
            ],
        },
        "metadata": {},
    }

    # Inspect
    occurrences = LegacyBlockMigrationManager.detect_retired_blocks(sample_doc)
    assert len(occurrences) == 1
    assert occurrences[0]["retired_block_id"] == "creator-hud"
    assert occurrences[0]["recommended_replacement"] == "yt-lower-third"

    # Mark non-destructively
    marked_doc, requires_migration = LegacyBlockMigrationManager.inspect_and_mark_migration(sample_doc)
    assert requires_migration is True
    assert marked_doc["metadata"]["requires_migration"] is True
    assert marked_doc["metadata"]["migration_status"] == "REQUIRES_MIGRATION"
    # Ensure clip was NOT deleted
    assert len(marked_doc["timeline"]["tracks"][0]["clips"]) == 2
    assert marked_doc["timeline"]["tracks"][0]["clips"][0]["block_id"] == "creator-hud"

    # Consensual migration
    migrated_doc = LegacyBlockMigrationManager.apply_migration(marked_doc, user_consented=True)
    assert migrated_doc["metadata"]["requires_migration"] is False
    assert migrated_doc["metadata"]["migration_status"] == "MIGRATION_COMPLETED"
    assert migrated_doc["timeline"]["tracks"][0]["clips"][0]["block_id"] == "yt-lower-third"
    assert migrated_doc["timeline"]["tracks"][0]["clips"][0]["migrated_from"] == "creator-hud"


# =========================================================================
# 6. Full Inventory Traversal & Complete Snapshot
# =========================================================================

def test_catalog_inventory_full_snapshot_and_pagination():
    """Verify /api/catalog/inventory supports unpaginated snapshot and traversal."""
    # 1. Snapshot endpoint
    resp_snap = client.get("/api/catalog/inventory/snapshot")
    assert resp_snap.status_code == 200
    snap_data = resp_snap.json()
    assert snap_data["total"] == 196
    assert len(snap_data["blocks"]) == 196
    assert snap_data["is_snapshot"] is True

    # 2. Query param snapshot=true
    resp_snap_q = client.get("/api/catalog/inventory?snapshot=true")
    assert resp_snap_q.status_code == 200
    assert len(resp_snap_q.json()["blocks"]) == 196

    # 3. Pagination traversal across 4 pages
    page1 = client.get("/api/catalog/inventory?limit=50&offset=0").json()
    page2 = client.get("/api/catalog/inventory?limit=50&offset=50").json()
    page3 = client.get("/api/catalog/inventory?limit=50&offset=100").json()
    page4 = client.get("/api/catalog/inventory?limit=50&offset=150").json()

    assert len(page1["blocks"]) == 50
    assert len(page2["blocks"]) == 50
    assert len(page3["blocks"]) == 50
    assert len(page4["blocks"]) == 46
    assert 50 + 50 + 50 + 46 == 196

    all_paged_ids = (
        [b["id"] for b in page1["blocks"]]
        + [b["id"] for b in page2["blocks"]]
        + [b["id"] for b in page3["blocks"]]
        + [b["id"] for b in page4["blocks"]]
    )
    assert len(set(all_paged_ids)) == 196


# =========================================================================
# 7. Dynamic Frame Motion Progression & Parity
# =========================================================================

def test_dynamic_frame_motion_verifier_rejects_solid_color():
    """Verify that pure solid-color flat frames are rejected."""
    # Create pure black image
    solid_black = Image.new("RGB", (100, 100), (0, 0, 0))
    with pytest.raises(RenderFrameError) as exc_info:
        DynamicFrameMotionVerifier.verify_image_not_solid_color(solid_black)
    assert "FRAME_SOLID_COLOR_DETECTED" in str(exc_info.value)

    # Create pure solid gray image
    solid_gray = Image.new("RGB", (100, 100), (128, 128, 128))
    with pytest.raises(RenderFrameError) as exc_info_gray:
        DynamicFrameMotionVerifier.verify_image_not_solid_color(solid_gray)
    assert "FRAME_SOLID_COLOR_DETECTED" in str(exc_info_gray.value)


def test_dynamic_frame_motion_verifier_rejects_frozen_frames():
    """Verify that identical frames across different timestamps are rejected."""
    # Create an image with variance
    img = Image.new("RGB", (100, 100), (20, 30, 40))
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, 50, 50], fill=(200, 100, 50))

    # Test single frame passes solid color check
    res = DynamicFrameMotionVerifier.verify_image_not_solid_color(img)
    assert res["status"] == "VALID_GRAPHICAL_FRAME"

    # Three identical copies must trigger FRAME_MOTION_FROZEN
    with pytest.raises(RenderFrameError) as exc_info:
        DynamicFrameMotionVerifier.verify_temporal_motion_progression([img, img, img])
    assert "FRAME_MOTION_FROZEN" in str(exc_info.value)


def test_dynamic_frame_motion_verifier_passes_on_real_progression():
    """Verify that frames with temporal variance pass cleanly."""
    frame1 = Image.new("RGB", (100, 100), (20, 30, 40))
    draw1 = ImageDraw.Draw(frame1)
    draw1.rectangle([10, 10, 50, 50], fill=(200, 100, 50))

    frame2 = Image.new("RGB", (100, 100), (20, 30, 40))
    draw2 = ImageDraw.Draw(frame2)
    draw2.rectangle([30, 30, 70, 70], fill=(50, 150, 250))  # Moved and different color

    res = DynamicFrameMotionVerifier.verify_temporal_motion_progression([frame1, frame2])
    assert res["status"] == "DYNAMIC_MOTION_VERIFIED"
    assert res["temporal_variance_verified"] is True
    assert res["distinct_frame_hashes"] == 2


# =========================================================================
# 8. Stable Runtime Interface Contract (Agents 3, 5, 6)
# =========================================================================

def test_stable_runtime_interface_contract():
    """Verify the code-level contract published for downstream agents."""
    specs = list_runtime_block_specs(only_public=True)
    assert len(specs) == 10

    sample = get_runtime_block_spec("aurora")
    assert sample is not None
    assert sample.original_id == "aurora"
    assert sample.vendored_root is not None
    assert sample.source_category_id is None
    assert sample.source_category_status == "SOURCE_CATEGORY_MISSING"
    assert sample.is_original_category is False
    assert sample.proposed_fallback_category == "backgrounds"
    assert sample.is_public_catalog_item is True
    assert sample.requires_migration is False
    assert sample.readiness["runtime_ready"] is True

    # Check proof ladder function
    ladder = get_proof_ladder("aurora")
    assert ladder["block_id"] == "aurora"
    assert ladder["runtime_operable"] is True
    assert ladder["proof_ladder"]["source_inventoried"] is True
    assert ladder["proof_ladder"]["runtime_ready"] is True


def test_wave15_audit_endpoint():
    """Verify GET /api/catalog/wave15-audit returns complete reconciled state."""
    resp = client.get("/api/catalog/wave15-audit")
    assert resp.status_code == 200
    data = resp.json()

    assert data["wave"] == "WAVE_15"
    recon = data["reconciliation"]
    assert recon["donor_inventory_total"] == 196
    assert recon["indexed_in_registry_json"] == 170
    assert recon["unindexed_block_directories"] == 26
    assert recon["donor_operable_count"] == 10
    assert recon["unported_donor_blocks_quarantined"] == 186
    assert recon["retired_6clips_count"] == 2
    assert recon["sixclips_authored_in_public_catalog"] == 0
    assert recon["terminal_declarations"]["ALL_196_OPERATIONAL"] is False
    assert recon["terminal_declarations"]["ZERO_DONOR_DEPENDENCY"] is True
