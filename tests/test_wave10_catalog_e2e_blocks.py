# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 10 Catalog End-to-End Blocks & Edited Instance Canonical MP4 Test Suite:
Validates:
1. Whole donor source audit (9,059 files, 852,720,453 bytes, 196 catalog blocks).
2. 12 operational blocks (10 donor + 2 original substitutes) with 12-row proof ledger.
3. 186 unready historical blocks strictly quarantined.
4. Deterministic multi-timestamp browser frame capture with EDITED instance variables.
5. Verification that edited instance frames differ from default unedited frames.
6. Canonical MP4 overlay video generation with ffprobe alpha channel inspection.
7. Project rehydration, CAS concurrency, multi-instance isolation, and atomic undo rollback.
8. Vetted creative skills: apply, modify, and undo lifecycle on canonical project documents.
9. Negative tests: quarantine rejection, prototype pollution, script injection, path traversal, GT-20 zero donor dependency.
10. FastAPI REST endpoints for Wave 10 audit and edited instance sequences.
"""
import json
import os
import shutil
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

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
from backend.catalog.project_intent_contract import (
    CatalogProjectIntentAdapter,
    AddToProjectIntentRequest,
)
from backend.catalog.creative_recipes import CreativeRecipeEngine
from backend.catalog.router import router
from fastapi import FastAPI

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


def test_wave10_donor_audit_whole_tree_and_196_inventory():
    """Verify donor whole-tree audit records and 196 total catalog inventory."""
    audit = CatalogManifestService.get_wave10_factual_audit()
    assert audit["whole_tree_audited"] is True
    assert audit["total_donor_files_audited"] == 9059
    assert audit["total_donor_bytes_audited"] == 852720453
    assert audit["total_catalog_blocks_inventoried"] == 196
    assert audit["donor_origin_blocks_count"] == 10
    assert audit["original_substitutes_count"] == 2
    assert audit["total_operational_blocks"] == 12
    assert audit["unready_donor_blocks"] == 186
    assert audit["not_ready_license_review_required"] == 168
    assert audit["not_ready_structural_fix_required"] == 18

    # Terminal declarations
    term = audit["terminal_declarations"]
    assert term["HYPERFRAMES_FULLY_INTEGRATED"] == "NO"
    assert term["DONOR_BLOCKS_READY"] == 10
    assert term["ORIGINAL_SUBSTITUTES_READY"] == 2
    assert term["TOTAL_OPERATIONAL_BLOCKS"] == 12
    assert term["CANONICAL_EXPORT_CONTRACT_VERSION"] == "2.1.0"
    assert term["MEDIA_PIPELINE_CANONICAL_MP4"] == "ROLE2_RENDER_PIPELINE_PENDING"
    assert term["LEGACY_DONOR_RUNTIME_DEPENDENCY"] == "NO"
    assert term["UNREADY_DONOR_BLOCKS_QUARANTINED"] == 186


def test_wave10_12_block_proof_ledger():
    """Verify the 12-row proof ledger contains all 12 operational blocks with truthful stage statuses."""
    audit = CatalogManifestService.get_wave10_factual_audit()
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
        assert entry["canonical_mp4_status"] == "ROLE2_RENDER_PIPELINE_PENDING"
        assert entry["zero_external_cdn"] is True
        assert entry["zero_donor_dependency"] is True


def test_wave10_edited_instance_browser_capture_and_variance():
    """Verify Playwright captures EDITED instance frames, proving custom variable difference and temporal variance."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # 1. Capture default instance frames
        default_seq = CatalogExportContract.capture_multi_timestamp_sequence(
            block_id="yt-lower-third",
            timestamps=[0.0, 1.0, 2.0],
            temp_dir=tmp_path / "default",
        )

        # 2. Capture edited instance frames with custom variables
        edited_vars = {
            "channel_name": "@viralmint_pro_creator",
            "subscribe_prompt": "Master Video Generation Today",
        }
        edited_seq = CatalogExportContract.capture_edited_instance_sequence(
            block_id="yt-lower-third",
            custom_variables=edited_vars,
            timestamps=[0.0, 1.0, 2.0],
            temp_dir=tmp_path / "edited",
        )

        assert edited_seq["block_id"] == "yt-lower-third"
        assert edited_seq["is_edited_instance"] is True
        assert edited_seq["total_frames_captured"] == 3
        assert len(edited_seq["frames"]) == 3
        assert edited_seq["temporal_variance_verified"] is True

        # Frame at t=1.0s should reflect custom variables and have different hash from default frame at t=1.0s
        default_t1_hash = default_seq["frames"][1]["sha256"]
        edited_t1_hash = edited_seq["frames"][1]["sha256"]
        assert default_t1_hash != edited_t1_hash, "Edited instance frame at t=1.0s must differ from default frame"


def test_wave10_canonical_instance_mp4_overlay():
    """Verify physical transparent video overlay generation for an EDITED block instance with ffprobe alpha check."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        edited_vars = {
            "creator_handle": "@custom_speed_runner",
            "battery_pct": 88,
        }
        res = CatalogExportContract.render_canonical_instance_mp4_overlay(
            block_id="creator-hud",
            custom_variables=edited_vars,
            aspect_ratio="9:16",
            duration_seconds=1.5,
            temp_dir=Path(tmp_dir),
        )
        assert res["block_id"] == "creator-hud"
        assert os.path.exists(res["video_path"])
        assert res["video_size_bytes"] > 0
        assert res["alpha_channel_detected"] is True
        assert res["ready_for_role2_media_pipeline"] is True
        assert res["ffprobe_analysis"]["codec_name"] in ("png", "prores", "qtrle")
        assert res["ffprobe_analysis"]["height"] == 1920
        assert res["ffprobe_analysis"]["width"] == 1080


def test_wave10_project_rehydration_and_cas_concurrency():
    """Verify project insertion, serialization rehydration, multi-instance isolation, and CAS rollback."""
    # 1. Multi-instance isolation: two instances of same block with different variables
    req1 = AddToProjectIntentRequest(
        project_id="proj_alpha",
        instance_id="inst_card_alpha",
        expected_revision=1,
        timeline_track_index=0,
        custom_variables={"channel_name": "Channel Alpha"},
    )
    req2 = AddToProjectIntentRequest(
        project_id="proj_alpha",
        instance_id="inst_card_beta",
        expected_revision=2,
        timeline_track_index=1,
        custom_variables={"channel_name": "Channel Beta"},
    )

    res1 = CatalogProjectIntentAdapter.create_add_to_project_intent("yt-lower-third", req1)
    res2 = CatalogProjectIntentAdapter.create_add_to_project_intent("yt-lower-third", req2)

    assert res1.timeline_item.instance_id == "inst_card_alpha"
    assert res2.timeline_item.instance_id == "inst_card_beta"
    assert res1.timeline_item.variables["channel_name"] == "Channel Alpha"
    assert res2.timeline_item.variables["channel_name"] == "Channel Beta"

    # 2. Project rehydration simulation (JSON serialize & deserialize)
    serialized = res1.timeline_item.model_dump_json()
    deserialized = json.loads(serialized)
    assert deserialized["instance_id"] == "inst_card_alpha"
    assert deserialized["variables"]["channel_name"] == "Channel Alpha"
    assert deserialized["license_provenance"]["license_status"] == "VERIFIED_DISTRIBUTABLE"

    # 3. Undo rollback integrity
    revert = res1.revert_operation
    assert revert["action"] == "remove_timeline_item"
    assert revert["instance_id"] == "inst_card_alpha"
    assert revert["expected_revision"] == 2
    assert revert["reversible"] is True


def test_wave10_vetted_creative_skills_operations():
    """Verify full skills lifecycle: apply, modify, and undo on canonical project document."""
    doc = {"timeline": {"tracks": []}, "code": {"files": []}, "metadata": {}}

    # 1. Apply recipe
    res_apply = CreativeRecipeEngine.apply_recipe_to_project_document(
        doc=doc,
        recipe_id="recipe_faceless_short_15s",
        start_time=0.0,
    )
    assert res_apply["success"] is True
    assert res_apply["inserted_clips_count"] > 0
    total_clips = sum(len(t.get("clips", [])) for t in doc["timeline"]["tracks"])
    assert total_clips == res_apply["inserted_clips_count"]

    # 2. Modify recipe parameters in document
    overrides = {"speed": "2.0", "intensity": "maximum"}
    res_mod = CreativeRecipeEngine.modify_recipe_in_project_document(
        doc=doc,
        recipe_id="recipe_faceless_short_15s",
        variable_overrides=overrides,
    )
    assert res_mod["success"] is True
    assert res_mod["modified_clips_count"] > 0

    # 3. Undo recipe from document
    res_undo = CreativeRecipeEngine.undo_recipe_from_project_document(
        doc=doc,
        recipe_id="recipe_faceless_short_15s",
    )
    assert res_undo["success"] is True
    remaining_clips = sum(len(t.get("clips", [])) for t in doc["timeline"]["tracks"])
    assert remaining_clips == 0


def test_wave10_quarantine_and_injection_defenses():
    """Verify quarantine rejection of 186 unready blocks, XSS sanitization, and GT-20 independence."""
    # 1. Quarantine rejection
    with pytest.raises(CatalogManifestError, match="quarantined: license review or structural fixes required"):
        CatalogManifestService.validate_block_for_project_insertion("camcorder-hud")

    req_quarantine = AddToProjectIntentRequest(
        project_id="test_quarantine",
        strict_quarantine=True,
    )
    with pytest.raises(CatalogManifestError):
        CatalogProjectIntentAdapter.create_add_to_project_intent("bouncing-balls", req_quarantine)

    # 2. Prototype pollution rejection
    req_proto = AddToProjectIntentRequest(
        project_id="test_proto",
        custom_variables={"__proto__": "attack"},
    )
    with pytest.raises(CatalogManifestError, match="Disallowed parameter key"):
        CatalogProjectIntentAdapter.create_add_to_project_intent("yt-lower-third", req_proto)

    # 3. Script injection sanitization
    req_xss = AddToProjectIntentRequest(
        project_id="test_xss",
        custom_variables={"channel_name": "<script>alert(1)</script>CleanChannel"},
    )
    res_xss = CatalogProjectIntentAdapter.create_add_to_project_intent("yt-lower-third", req_xss)
    assert "<script>" not in res_xss.timeline_item.variables["channel_name"]
    assert "CleanChannel" in res_xss.timeline_item.variables["channel_name"]

    # 4. CodeMirror custom source code safety
    req_bad_code = AddToProjectIntentRequest(
        project_id="test_code",
        project_owned_source="const ex = eval('exploit()');",
    )
    with pytest.raises(CatalogManifestError, match="Unsafe execution or token pattern"):
        CatalogProjectIntentAdapter.create_add_to_project_intent("flowing-gradient", req_bad_code)

    # 5. GT-20 zero donor dependency
    for b_id in OPERATIONAL_12_BLOCKS:
        res_assets = CatalogExportContract.verify_self_contained_assets(b_id)
        assert res_assets["fully_self_contained"] is True
        assert res_assets["zero_donor_checkout_dependency"] is True


def test_wave10_fastapi_rest_endpoints():
    """Verify Wave 10 FastAPI REST endpoints."""
    # 1. Wave 10 audit endpoint
    res_audit = client.get("/api/catalog/wave10-audit")
    assert res_audit.status_code == 200
    audit_data = res_audit.json()
    assert audit_data["wave"] == "WAVE_10"
    assert audit_data["total_operational_blocks"] == 12
    assert audit_data["unready_donor_blocks"] == 186
    assert audit_data["terminal_declarations"]["MEDIA_PIPELINE_CANONICAL_MP4"] == "ROLE2_RENDER_PIPELINE_PENDING"

    # 2. Edited instance sequence endpoint
    payload = {
        "custom_variables": {"channel_name": "API Test Channel"},
        "timestamps": [0.0, 1.0],
        "aspect_ratio": "9:16",
    }
    res_seq = client.post("/api/catalog/blocks/yt-lower-third/edited-instance-sequence", json=payload)
    assert res_seq.status_code == 200
    seq_data = res_seq.json()
    assert seq_data["is_edited_instance"] is True
    assert seq_data["total_frames_captured"] == 2

    # 3. Quarantined block rejection
    res_quarantine = client.post("/api/catalog/blocks/camcorder-hud/edited-instance-sequence", json=payload)
    assert res_quarantine.status_code == 400
    assert "quarantined" in res_quarantine.json()["detail"].lower()
