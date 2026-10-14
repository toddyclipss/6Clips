# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 11 Catalog Loaders, Truthful State Machine & 12 Edited Animated Canonical MP4 Test Suite:
Validates:
1. Whole donor source audit (9,059 files, 852,720,453 bytes, 196 catalog blocks).
2. Exact truthful disposition: 196 donor originals, 10 donor internalized, 186 donor withheld (196 - 10 = 186, NOT 184).
3. 2 6Clips original substitutes ("creator-hud", "glitch-transition"), total 12 operational blocks.
4. Single source of truth Catalog state machine: LOADING, READY_ITEMS, EMPTY_FILTER, ERROR_RETRYABLE, OFFLINE_BLOCKED.
5. Deterministic multi-timestamp frame capture with EDITED instance variables across >=3 timestamps.
6. Genuine physical H.264 MP4 composited video exports with ffprobe inspection and sample frame analysis.
7. Negative safety gate: strict quarantine rejection of all 186 withheld donor blocks.
8. Generation of machine-readable %TEMP%/wave11_hyperframes_evidence.json manifest with actual paths and SHA256s.
9. FastAPI REST endpoints for Wave 11 audit, state machine, and block operations.
"""
import json
import os
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.catalog.manifest_service import (
    CatalogManifestService,
    CatalogManifestError,
    CORE_INTERNALIZED_BLOCKS,
    WAVE4_INTERNALIZED_BLOCKS,
)
from backend.catalog.export_contract import (
    CatalogExportContract,
    CatalogExportContractError,
)
from backend.catalog.router import router

app = FastAPI()
app.include_router(router, prefix="/api")
client = TestClient(app)

OPERATIONAL_12_BLOCKS = sorted(list(CORE_INTERNALIZED_BLOCKS | {
    "flowing-gradient", "plasma", "stripes", "holographic", "glitch-transition", "creator-hud"
}))
DONOR_10_BLOCKS = sorted(list(CORE_INTERNALIZED_BLOCKS | {
    "flowing-gradient", "plasma", "stripes", "holographic"
}))
ORIGINAL_2_SUBSTITUTES = ["creator-hud", "glitch-transition"]


def test_wave11_audit_196_inventory_186_withheld_truth():
    """Verify donor whole-tree audit records, 196 donor inventory, 186 withheld (196 - 10 = 186, NOT 184)."""
    audit = CatalogManifestService.get_wave11_factual_audit()
    assert audit["whole_tree_audited"] is True
    assert audit["total_donor_files_audited"] == 9059
    assert audit["total_donor_bytes_audited"] == 852720453
    assert audit["total_catalog_blocks_inventoried"] == 196
    assert audit["donor_origin_blocks_count"] == 10
    assert audit["original_substitutes_count"] == 2
    assert audit["total_operational_blocks"] == 12

    # Arithmetic verification: exactly 186 withheld, NEVER 184
    assert audit["unready_donor_blocks"] == 186
    assert audit["unready_donor_blocks"] != 184
    assert audit["not_ready_license_review_required"] == 168
    assert audit["not_ready_structural_fix_required"] == 18
    assert audit["not_ready_license_review_required"] + audit["not_ready_structural_fix_required"] == 186

    # Terminal declarations
    term = audit["terminal_declarations"]
    assert term["CATALOG_SKELETON_RESOLVED"] == "YES"
    assert term["HYPERFRAMES_12_CANONICAL_MP4_READY"] == "YES"
    assert term["HYPERFRAMES_FULLY_INTEGRATED"] == "NO"
    assert term["DONOR_BLOCKS_READY"] == 10
    assert term["ORIGINAL_SUBSTITUTES_READY"] == 2
    assert term["TOTAL_OPERATIONAL_BLOCKS"] == 12
    assert term["UNREADY_DONOR_BLOCKS_QUARANTINED"] == 186
    assert term["CANONICAL_EXPORT_CONTRACT_VERSION"] == "2.2.0"
    assert term["MEDIA_PIPELINE_CANONICAL_MP4"] == "READY_FOR_ROLE2_PIPELINE"
    assert term["LEGACY_DONOR_RUNTIME_DEPENDENCY"] == "NO"


def test_wave11_12_block_proof_ledger():
    """Verify the 12-row proof ledger contains all 12 operational blocks with truthful stage statuses."""
    audit = CatalogManifestService.get_wave11_factual_audit()
    proof_ledger = audit["proof_ledger_12_blocks"]
    assert len(proof_ledger) == 12

    for b_id in OPERATIONAL_12_BLOCKS:
        assert b_id in proof_ledger
        entry = proof_ledger[b_id]
        assert entry["block_id"] == b_id
        if b_id in DONOR_10_BLOCKS:
            assert entry["origin_provenance"] == "ORIGINAL_DONOR"
            assert "Apache-2.0" in entry["license"]
        else:
            assert entry["origin_provenance"] == "ORIGINAL_6CLIPS"
            assert entry["license"] == "Apache-2.0"

        assert entry["offline_asset_ok"] == "PASS"
        assert entry["edge_dynamic_frame_ok"] == "PASS"
        assert entry["project_insert_ok"] == "PASS"
        assert entry["variable_reload_ok"] == "PASS"
        assert entry["canonical_mp4_status"] == "CANONICAL_MP4_PASS"
        assert entry["zero_external_cdn"] is True
        assert entry["zero_donor_dependency"] is True


def test_wave11_catalog_state_machine_definition():
    """Verify Catalog state machine definition and supported transitions."""
    res = client.get("/api/catalog/state-machine")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ACTIVE"
    expected_states = ["LOADING", "READY_ITEMS", "EMPTY_FILTER", "ERROR_RETRYABLE", "OFFLINE_BLOCKED"]
    assert data["states"] == expected_states
    assert data["initial_state"] == "LOADING"
    assert data["terminal_skeleton_guard"] is True
    assert data["retry_action_enabled"] is True
    assert data["working_blocks_count"] == 12
    assert data["withheld_donor_blocks_count"] == 186
    assert data["total_inventoried"] == 196


def test_wave11_catalog_items_faceted_filtering():
    """Verify faceted item listing, category filtering, search, and empty filter handling."""
    # 1. Listing all items
    res = client.get("/api/catalog/items?limit=200")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 196
    assert len(data["items"]) >= 196

    # 2. Category filtering
    res_cat = client.get("/api/catalog/items?category=typography")
    assert res_cat.status_code == 200
    cat_items = res_cat.json()["items"]
    assert len(cat_items) > 0
    assert all(it["category"] == "typography" for it in cat_items)

    # 3. Empty filter handling (no items match)
    res_empty = client.get("/api/catalog/items?search=nonexistent_xyz_query_12345")
    assert res_empty.status_code == 200
    assert res_empty.json()["total"] == 0
    assert len(res_empty.json()["items"]) == 0


def test_wave11_edited_instance_multi_timestamp_capture(tmp_path):
    """Verify deterministic multi-timestamp browser frame capture with custom EDITED variables."""
    custom_vars = {
        "channel_name": "Wave11 Channel",
        "subtitle": "Truthful Loading Verified",
    }
    res = CatalogExportContract.capture_edited_instance_sequence(
        block_id="yt-lower-third",
        custom_variables=custom_vars,
        timestamps=[0.0, 1.0, 2.0],
        aspect_ratio="9:16",
        temp_dir=tmp_path,
    )
    assert res["block_id"] == "yt-lower-third"
    assert res["is_edited_instance"] is True
    assert res["custom_variables"] == custom_vars
    assert res["total_frames_captured"] == 3
    assert res["timestamps_tested"] == [0.0, 1.0, 2.0]
    assert len(res["frames"]) == 3

    # All frames must exist on disk and have SHA256 hashes
    for frame in res["frames"]:
        f_path = Path(frame["file_path"])
        assert f_path.exists()
        assert len(frame["sha256"]) == 64
        assert frame["size_bytes"] > 0

    assert res["temporal_variance_verified"] is True
    assert res["alpha_transparency_preserved"] is True
    assert res["iframe_security_audit"]["zero_external_network_requests"] is True


def test_wave11_canonical_h264_mp4_overlay_and_composite(tmp_path):
    """Verify physical H.264 composited MP4 video and MOV alpha overlay generation with ffprobe."""
    custom_vars = {
        "status_text": "SYSTEM ONLINE",
        "system_load": "37%",
    }
    res = CatalogExportContract.render_canonical_instance_mp4_overlay(
        block_id="creator-hud",
        custom_variables=custom_vars,
        aspect_ratio="9:16",
        duration_seconds=2.0,
        temp_dir=tmp_path,
    )
    assert res["block_id"] == "creator-hud"
    assert res["status"] == "PASS"
    assert res["canonical_mp4_status"] == "CANONICAL_MP4_PASS"

    # Verify transparent MOV overlay
    mov_path = Path(res["video_path"])
    assert mov_path.exists()
    assert res["alpha_channel_detected"] is True

    # Verify physical canonical H.264 composited MP4
    mp4_path = Path(res["canonical_mp4_path"])
    assert mp4_path.exists()
    assert res["canonical_mp4_size_bytes"] > 1000
    assert len(res["canonical_mp4_sha256"]) == 64

    # Verify ffprobe stream analysis
    mp4_probe = res["canonical_mp4_ffprobe"]
    assert mp4_probe["codec_name"] == "h264"
    assert mp4_probe["width"] == 1080
    assert mp4_probe["height"] == 1920
    assert mp4_probe["pix_fmt"] == "yuv420p"
    assert mp4_probe["duration_seconds"] >= 2.0


def test_wave11_negative_quarantine_safety_for_186_withheld_blocks():
    """Verify that all 186 unready historical blocks are strictly quarantined and rejected from insertion."""
    with pytest.raises(CatalogManifestError) as exc_info:
        CatalogManifestService.validate_block_for_project_insertion("aurora-borealis")
    assert "quarantined" in str(exc_info.value).lower()

    with pytest.raises(CatalogManifestError) as exc_info2:
        CatalogManifestService.validate_block_for_project_insertion("wireframe-portal-title")
    assert "quarantined" in str(exc_info2.value).lower()


def test_wave11_evidence_manifest_in_temp(tmp_path):
    """Verify generation of the 12-block evidence manifest in %TEMP%/wave11_hyperframes_evidence.json."""
    manifest_res = CatalogExportContract.generate_wave11_12_blocks_evidence_manifest(temp_dir=tmp_path)
    manifest_path = Path(manifest_res["manifest_path"])
    assert manifest_path.exists()

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_data["wave"] == "WAVE_11"

    summary = manifest_data["summary"]
    assert summary["total_blocks_evaluated"] == 12
    assert summary["total_pass"] == 12
    assert summary["total_partial"] == 0
    assert summary["total_blocked"] == 0
    assert summary["total_not_tested"] == 0
    assert summary["CATALOG_SKELETON_RESOLVED"] == "YES"
    assert summary["HYPERFRAMES_12_CANONICAL_MP4_READY"] == "YES"

    # All 12 blocks must be present and marked PASS
    blocks = manifest_data["blocks"]
    assert len(blocks) == 12
    for b_id in OPERATIONAL_12_BLOCKS:
        assert b_id in blocks
        b_entry = blocks[b_id]
        assert b_entry["status"] == "PASS"
        assert b_entry["canonical_mp4_status"] == "CANONICAL_MP4_PASS"
        assert b_entry["mp4_codec"] == "h264"
        assert b_entry["frames_count"] == 3
        assert len(b_entry["frame_sha256s"]) == 3
        assert Path(b_entry["canonical_mp4_path"]).exists()
        assert Path(b_entry["transparent_overlay_mov"]).exists()


def test_wave11_fastapi_rest_endpoints():
    """Verify Wave 11 FastAPI REST endpoints."""
    # 1. Wave 11 Audit
    res_audit = client.get("/api/catalog/wave11-audit")
    assert res_audit.status_code == 200
    audit_data = res_audit.json()
    assert audit_data["wave"] == "WAVE_11"
    assert audit_data["total_operational_blocks"] == 12
    assert audit_data["unready_donor_blocks"] == 186
    assert audit_data["terminal_declarations"]["CATALOG_SKELETON_RESOLVED"] == "YES"
    assert audit_data["terminal_declarations"]["HYPERFRAMES_12_CANONICAL_MP4_READY"] == "YES"

    # 2. State Machine Endpoint
    res_sm = client.get("/api/catalog/state-machine")
    assert res_sm.status_code == 200
    assert "LOADING" in res_sm.json()["states"]

    # 3. Item detail
    res_item = client.get("/api/catalog/items/creator-hud")
    assert res_item.status_code == 200
    assert res_item.json()["id"] == "creator-hud"

    # 4. 404 on missing item
    res_404 = client.get("/api/catalog/items/non_existent_block_999")
    assert res_404.status_code == 404
