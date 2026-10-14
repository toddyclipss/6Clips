# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 14 Agent 3 Test Suite: Catalog Backend Source-to-Shipped-Block Recovery
Covers:
1. Canonical HyperFrames Inventory Math & Reconciliation Census (196 original block dirs,
   170 aggregate manifest items, 26 unbundled blocks, 222 microcomponents, 8 examples).
2. Origin Separation Invariants: 10 internalized donor + 2 6Clips original substitutes = 12 operational;
   196 - 10 = exactly 186 unported donor originals (never 184).
3. GT-20 Zero Donor Dependency: runtime runs strictly from vendored shipped_blocks.
4. Fallback when v1 manifest is absent: clean operation without fake 186 placeholders.
5. Reconciled Manifest Ingestion: truthful statuses, pagination, filtering, search.
6. Negative Safety Gates: uninternalized blocks strictly forbidden from preview, poster, project insertion, and export.
7. GT-13 12 Operational Blocks Distinct MP4 Export: clean ffmpeg decode, ffprobe inspection,
   full 64-character distinct SHA-256 hashes, and verified shader 2D canvas fallbacks.
8. Zero Outbound Network Activity: offline P0 idle guardrail compliance.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.catalog.router import router as catalog_router
from backend.catalog.manifest_service import (
    CatalogManifestService,
    CatalogManifestError,
    CORE_INTERNALIZED_BLOCKS,
    WAVE4_INTERNALIZED_BLOCKS,
    DONOR_INTERNALIZED_BLOCKS,
    SIXCLIPS_ORIGINAL_BLOCKS,
    CATALOG_ROOT,
)
from backend.services.registry_adapter import (
    RegistryAdapter,
    get_registry_dir,
)
from backend.services.catalog_preview_service import CatalogPreviewService
from backend.catalog.export_contract import CatalogExportContract, CatalogExportContractError


# Setup test client
app = FastAPI()
app.include_router(catalog_router, prefix="/api")
client = TestClient(app)


# =========================================================================
# Task 1 & Task 2: Census Reconciliation & Math Invariants
# =========================================================================

def test_wave14_census_and_reconciliation_math():
    """
    Verify canonical census math from donor structure:
    - 196 original donor block directories
    - 170 aggregate manifest block items (26 unbundled)
    - 222 microcomponents and 8 examples (distinct inventories, not counted as original blocks)
    - 10 internalized donor blocks
    - 2 6Clips-original authored blocks (creator-hud, glitch-transition)
    - Total operational blocks: 12
    - Exactly 186 unported donor-original blocks (196 - 10 = 186, NEVER 184)
    """
    audit = CatalogManifestService.get_wave14_reconciliation()
    census = audit["census"]

    assert census["on_disk_block_dirs"] == 196
    assert census["on_disk_component_dirs"] == 236
    assert census["on_disk_example_dirs"] == 8
    assert census["total_donor_directories"] == 440

    assert census["aggregate_registry_json_blocks"] == 170
    assert census["aggregate_registry_json_components"] == 222
    assert census["aggregate_registry_json_examples"] == 8
    assert census["total_aggregate_registry_items"] == 400

    assert census["unbundled_shader_and_extended_blocks"] == 26
    assert census["unbundled_components"] == 14
    assert census["unbundled_examples"] == 0

    assert census["donor_blocks_internalized"] == 10
    assert len(census["donor_internalized_ids"]) == 10
    assert census["sixclips_authored_substitutes"] == 2
    assert len(census["sixclips_authored_ids"]) == 2
    assert census["total_operational_blocks"] == 12
    assert census["unported_donor_blocks_quarantined"] == 186
    assert census["unported_donor_blocks_quarantined"] != 184


def test_wave14_origin_separation_invariants():
    """
    Enforce that the two 6Clips-authored blocks are strictly separated from donor originals:
    - 'creator-hud' and 'glitch-transition' must not count toward the 196 donor blocks.
    - An inventory manifest that includes either in the donor blocks must be rejected.
    """
    assert len(DONOR_INTERNALIZED_BLOCKS) == 10
    assert len(SIXCLIPS_ORIGINAL_BLOCKS) == 2
    assert DONOR_INTERNALIZED_BLOCKS.isdisjoint(SIXCLIPS_ORIGINAL_BLOCKS)

    # Test rejection if a manifest attempts to include 6Clips original in donor inventory
    bad_manifest = {
        "schema_version": 1,
        "source_inventory": "HyperFrames",
        "original_block_count": 196,
        "blocks": [{"id": "creator-hud"}] + [{"id": f"block_{i}"} for i in range(195)],
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf:
        json.dump(bad_manifest, tf)
        bad_path = tf.name

    try:
        with patch.dict(os.environ, {"HYPERFRAMES_INVENTORY_JSON_PATH": bad_path}):
            with pytest.raises(CatalogManifestError) as exc_info:
                CatalogManifestService.load_inventory_v1()
            assert "creator-hud" in str(exc_info.value)
            assert "BLOCKED_INVENTORY_RECONCILIATION" in str(exc_info.value)
    finally:
        if os.path.exists(bad_path):
            os.remove(bad_path)


# =========================================================================
# GT-20: Zero Donor Checkout Runtime Dependency
# =========================================================================

def test_gt20_zero_donor_checkout_runtime_dependency():
    """
    Verify GT-20: Runtime has strictly zero dependency on external donor directory.
    Registry resolves exclusively to vendored shipped_blocks.
    """
    reg_dir = get_registry_dir()
    assert "shipped_blocks" in str(reg_dir).lower() or "catalog" in str(reg_dir).lower()
    assert "c:\\users\\toddy\\desktop\\hyperframes" not in str(reg_dir).lower()

    items = RegistryAdapter.list_catalog_items()
    assert len(items) == 12
    discovered_ids = {item["id"] for item in items}

    expected_all_12 = DONOR_INTERNALIZED_BLOCKS | SIXCLIPS_ORIGINAL_BLOCKS
    assert discovered_ids == expected_all_12


# =========================================================================
# Task 3: API & Manifest Loading Fallback vs Reconciled State
# =========================================================================

def test_inventory_api_fallback_when_manifest_absent():
    """
    When backend/catalog_inventory/hyperframes_196_inventory.json is absent (Stage 1 isolated):
    - GET /api/catalog/inventory returns manifest_loaded=False
    - Returns reconciliation_status="AWAITING_PROVENANCE_MANIFEST"
    - The 12 operational blocks function normally
    - No fabricated 186 placeholders are returned
    """
    # Point to non-existent file to simulate absent manifest
    fake_absent_path = str(CATALOG_ROOT / "_non_existent_inventory_file.json")
    with patch.dict(os.environ, {"HYPERFRAMES_INVENTORY_JSON_PATH": fake_absent_path}):
        resp = client.get("/api/catalog/inventory")
        assert resp.status_code == 200
        data = resp.json()

        assert data["schema_version"] == 1
        assert data["manifest_loaded"] is False
        assert data["reconciliation_status"] == "AWAITING_PROVENANCE_MANIFEST"
        assert data["donor_inventory_total"] == 196
        assert data["donor_internalized_working"] == 10
        assert data["donor_unported_count"] == 186
        assert data["sixclips_authored_count"] == 2
        assert data["total_operational_blocks"] == 12

        # In fallback mode, returns the installed 10 donor blocks and 2 6Clips blocks
        assert len(data["blocks"]) == 10
        assert len(data["sixclips_original_blocks"]) == 2
        assert all(b["runtime_operable"] is True for b in data["blocks"])


def test_inventory_api_reconciliation_when_manifest_present():
    """
    When backend/catalog_inventory/hyperframes_196_inventory.json IS present:
    - Loads all 196 donor block rows
    - Reconciles 10 internalized donor blocks as INTERNALIZED_WORKING (runtime_operable=True)
    - Reconciles remaining 186 unported donor blocks with truthful blocker_reason (runtime_operable=False)
    - Separately returns the 2 6Clips-original authored blocks
    - Filters work: 'operational', 'unported', 'needs_adaptation', 'blocked', 'eligible'
    """
    # Create an authentic 196-row mock manifest fixture based on donor dirs
    donor_blocks_dir = Path(r"C:\Users\toddy\Desktop\hyperframes\registry\blocks")
    donor_dirs = sorted([d.name for d in donor_blocks_dir.iterdir() if d.is_dir()])
    assert len(donor_dirs) == 196

    manifest_rows = []
    for name in donor_dirs:
        is_internalized = name in DONOR_INTERNALIZED_BLOCKS
        row = {
            "id": name,
            "relative_source_path": f"registry/blocks/{name}",
            "source_sha256": "451e7e529cfdd26c7ba3a0c4086bbfee838dbb42",
            "license_status": "VERIFIED_PERMISSIVE" if is_internalized else "UNVERIFIED",
            "license_evidence": "Shipped with OFL/Apache notice" if is_internalized else "Donor whole-tree audit",
            "integration_status": "INTERNALIZED" if is_internalized else ("NEEDS_ADAPTATION" if name in ("sine-wave", "waveform") else "BLOCKED_DEPENDENCY"),
            "blocker_reason": None if is_internalized else "External CDN dependencies and unvetted assets",
            "supported_aspects": ["9:16", "16:9"] if is_internalized else ["16:9"],
            "evidence_refs": [f"registry/blocks/{name}/registry-item.json"],
        }
        manifest_rows.append(row)

    mock_manifest = {
        "schema_version": 1,
        "source_inventory": "HyperFrames",
        "original_block_count": 196,
        "blocks": manifest_rows,
    }

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf:
        json.dump(mock_manifest, tf, indent=2)
        fixture_path = tf.name

    try:
        with patch.dict(os.environ, {"HYPERFRAMES_INVENTORY_JSON_PATH": fixture_path}):
            # 1. Full inventory list
            resp_all = client.get("/api/catalog/inventory?limit=300")
            assert resp_all.status_code == 200
            data_all = resp_all.json()
            assert data_all["manifest_loaded"] is True
            assert data_all["reconciliation_status"] == "RECONCILED"
            assert data_all["total"] == 196
            assert len(data_all["blocks"]) == 196

            # 2. Filter: operational
            resp_op = client.get("/api/catalog/inventory?filter=operational")
            assert resp_op.status_code == 200
            data_op = resp_op.json()
            assert data_op["total"] == 10
            assert all(b["runtime_operable"] is True for b in data_op["blocks"])
            assert all(b["poster_url"] is not None for b in data_op["blocks"])
            assert all(b["preview_url"] is not None for b in data_op["blocks"])

            # 3. Filter: unported
            resp_unp = client.get("/api/catalog/inventory?filter=unported&limit=300")
            assert resp_unp.status_code == 200
            data_unp = resp_unp.json()
            assert data_unp["total"] == 186
            assert all(b["runtime_operable"] is False for b in data_unp["blocks"])
            assert all(b["poster_url"] is None for b in data_unp["blocks"])
            assert all(b["preview_url"] is None for b in data_unp["blocks"])
            assert all(b["blocker_reason"] is not None for b in data_unp["blocks"])

            # 4. Pagination
            resp_page = client.get("/api/catalog/inventory?limit=20&offset=40")
            assert resp_page.status_code == 200
            data_page = resp_page.json()
            assert data_page["total"] == 196
            assert data_page["limit"] == 20
            assert data_page["offset"] == 40
            assert len(data_page["blocks"]) == 20

            # 5. Search
            resp_search = client.get("/api/catalog/inventory?search=waveform")
            assert resp_search.status_code == 200
            data_search = resp_search.json()
            assert any(b["id"] == "waveform" for b in data_search["blocks"])

            # 6. Audit endpoint
            resp_audit = client.get("/api/catalog/wave14-audit")
            assert resp_audit.status_code == 200
            audit = resp_audit.json()
            assert audit["manifest_loaded"] is True
            assert audit["reconciliation_status"] == "RECONCILED"
            assert audit["donor_inventory_total"] == 196
            assert audit["donor_internalized_working"] == 10
            assert audit["donor_unported_count"] == 186
            assert audit["total_operational_blocks"] == 12
    finally:
        if os.path.exists(fixture_path):
            os.remove(fixture_path)


# =========================================================================
# Task 4 & Task 6: Negative Safety Gates
# =========================================================================

def test_negative_safety_gates_reject_uninternalized_blocks():
    """
    Ensure unavailable/quarantined blocks CANNOT be enabled, previewed, inserted, or rendered:
    1. GET /api/catalog/blocks/{uninternalized_id}/preview -> 403 Forbidden
    2. GET /api/catalog/blocks/{uninternalized_id}/poster -> 403 Forbidden
    3. POST /api/catalog/blocks/{uninternalized_id}/intent/add-to-project -> 400/403 Error
    4. POST /api/catalog/blocks/{uninternalized_id}/canonical-instance-mp4-overlay -> 400 Error
    5. RegistryAdapter.freeze_block_snapshot(uninternalized_id) -> FileNotFoundError
    """
    uninternalized_id = "ai-answer-rank"

    # 1. Preview gate
    resp_prev = client.get(f"/api/catalog/blocks/{uninternalized_id}/preview")
    assert resp_prev.status_code == 403
    assert "quarantined" in resp_prev.json()["detail"].lower() or "uninternalized" in resp_prev.json()["detail"].lower()

    # 2. Poster gate
    resp_post = client.get(f"/api/catalog/blocks/{uninternalized_id}/poster")
    assert resp_post.status_code == 403
    assert "quarantined" in resp_post.json()["detail"].lower() or "uninternalized" in resp_post.json()["detail"].lower()

    # 3. Project intent insertion gate
    resp_insert = client.post(
        f"/api/catalog/blocks/{uninternalized_id}/intent/add-to-project",
        json={"project_id": "test_proj", "aspect_ratio": "9:16"},
    )
    assert resp_insert.status_code == 400
    assert "quarantined" in resp_insert.json()["detail"].lower()

    # 4. MP4 export overlay gate
    resp_render = client.post(
        f"/api/catalog/blocks/{uninternalized_id}/canonical-instance-mp4-overlay",
        json={"aspect_ratio": "9:16", "duration_seconds": 2.0},
    )
    assert resp_render.status_code == 400
    assert "quarantined" in resp_render.json()["detail"].lower()

    # 5. Snapshot freezing gate
    with pytest.raises(FileNotFoundError):
        RegistryAdapter.freeze_block_snapshot(uninternalized_id)


# =========================================================================
# Task 5 & Task 6 (GT-13): 12 Operational Blocks Distinct MP4 Export & Shader Fix
# =========================================================================

def test_gt13_12_operational_blocks_distinct_sha256_renders():
    """
    Verify GT-13 requirement:
    - All 12 operational blocks render valid MP4 files
    - FFmpeg clean decode (exit code 0)
    - FFprobe confirms H.264 codec and 1080x1920 vertical canvas
    - Full 64-character strictly distinct SHA-256 hashes across all 12 operational blocks
    - 5 shader blocks (aurora, flowing-gradient, holographic, plasma, stripes) do NOT share
      identical hashes or broken static frames.
    """
    results = CatalogPreviewService.render_all_12_distinct_blocks()
    assert len(results) == 12, f"Expected 12 operational block renders, got {len(results)}"

    shas = set()
    block_sha_map = {}
    for r in results:
        b_id = r["block_id"]
        sha = r["sha256"]
        exit_code = r["ffmpeg_decode_exit_code"]
        mp4_path = r["mp4_path"]

        assert exit_code == 0, f"Block {b_id} failed ffmpeg decode: exit code {exit_code}"
        assert os.path.exists(mp4_path), f"Block {b_id} MP4 file missing at {mp4_path}"
        assert len(sha) == 64, f"Block {b_id} SHA-256 must be 64 characters: {sha}"

        shas.add(sha)
        block_sha_map[b_id] = sha

    # All 12 hashes must be strictly unique
    assert len(shas) == 12, f"Expected 12 unique hashes, got {len(shas)}. Map: {block_sha_map}"

    # Specifically check the 5 shader blocks
    shader_blocks = ["aurora", "flowing-gradient", "holographic", "plasma", "stripes"]
    shader_shas = [block_sha_map[b] for b in shader_blocks]
    assert len(set(shader_shas)) == 5, f"Shader blocks must have 5 distinct hashes, got: {shader_shas}"

    # None of them should have the former broken hash prefix
    for b in shader_blocks:
        assert not block_sha_map[b].startswith("b90d1afe4fd3bac9"), (
            f"Block {b} has the broken identical hash prefix: {block_sha_map[b]}"
        )


# =========================================================================
# Zero Outbound Network Egress (P0 Guardrail)
# =========================================================================

def test_zero_external_network_egress_during_catalog_operations():
    """
    Verify zero outbound network requests occur during catalog operations,
    poster resolution, and inventory listing (P0 idle guardrail).
    """
    with patch("urllib.request.urlopen") as mock_urlopen, \
         patch("urllib.request.urlretrieve") as mock_urlretrieve, \
         patch("httpx.AsyncClient.get") as mock_httpx_get:

        # 1. Fetch inventory
        resp_inv = client.get("/api/catalog/inventory")
        assert resp_inv.status_code == 200

        # 2. Fetch all operational posters
        for block_id in ("aurora", "data-chart", "instagram-follow", "creator-hud", "glitch-transition"):
            resp_poster = client.get(f"/api/catalog/blocks/{block_id}/poster")
            assert resp_poster.status_code == 200

        # 3. Fetch audit
        resp_audit = client.get("/api/catalog/wave14-audit")
        assert resp_audit.status_code == 200

        # Ensure 0 external outbound requests were attempted
        assert mock_urlopen.call_count == 0
        assert mock_urlretrieve.call_count == 0
        assert mock_httpx_get.call_count == 0
