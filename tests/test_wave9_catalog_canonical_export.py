# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 9 Catalog Canonical Export & Rigorous 12-Block Proof Ladder Test Suite:
Validates:
1. Whole donor source audit (9,059 files, 852,720,453 bytes, 196 catalog blocks).
2. 12 operational blocks (10 donor + 2 original substitutes) with 12-row proof ladder.
3. 186 unready historical blocks strictly quarantined.
4. Deterministic multi-timestamp browser animation sequence with temporal pixel variance & alpha transparency.
5. Canonical Motion Export Contract v2.0.0 for Role 2 integration.
6. Standalone transparent video overlay generation with ffprobe alpha channel inspection.
7. Vetted creative skills safely transformed into executable 6Clips recipes (zero donor prompts executed).
8. Negative tests: license quarantine, prototype pollution, script injection, path traversal, cross-user isolation, undo rollback.
9. FastAPI REST endpoints for Wave 9 audit, export contract, and multi-timestamp sequence.
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


def test_wave9_donor_audit_whole_tree_and_196_inventory():
    """Verify donor whole-tree audit records and 196 total catalog inventory."""
    audit = CatalogManifestService.get_wave9_factual_audit()
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
    assert term["CANONICAL_EXPORT_CONTRACT_VERSION"] == "2.0.0"
    assert term["MEDIA_PIPELINE_CANONICAL_MP4"] == "ROLE2_RENDER_PIPELINE_PENDING"
    assert term["LEGACY_DONOR_RUNTIME_DEPENDENCY"] == "NO"
    assert term["UNREADY_DONOR_BLOCKS_QUARANTINED"] == 186


def test_wave9_12_block_proof_ladder():
    """Verify the 12-row proof ladder contains all 12 operational blocks with truthful stage statuses."""
    audit = CatalogManifestService.get_wave9_factual_audit()
    proof_ladder = audit["proof_ladder_12_blocks"]
    assert len(proof_ladder) == 12

    for b_id in OPERATIONAL_12_BLOCKS:
        assert b_id in proof_ladder
        entry = proof_ladder[b_id]
        assert entry["block_id"] == b_id
        if b_id in DONOR_10_BLOCKS:
            assert entry["donor_vs_original"] == "DONOR_HYPERFRAMES"
            assert "Apache-2.0" in entry["license"]
        else:
            assert entry["donor_vs_original"] == "SIXCLIPS_ORIGINAL_SUBSTITUTE"
            assert entry["license"] == "Apache-2.0"

        assert entry["self_contained_assets"] == "PASS"
        assert entry["browser_animated"] == "PASS"
        assert entry["inserted_project"] == "PASS"
        assert entry["reload_persisted"] == "PASS"
        assert entry["native_motion_preview"] == "PASS"
        assert entry["canonical_mp4_status"] == "ROLE2_RENDER_PIPELINE_PENDING"
        assert entry["zero_external_cdn"] is True
        assert entry["zero_donor_dependency"] is True


def test_wave9_multi_timestamp_sequence_and_pixel_variance():
    """Verify Playwright multi-timestamp frame capture, temporal pixel variance, and alpha channel."""
    seq = CatalogExportContract.capture_multi_timestamp_sequence(
        block_id="creator-hud",
        timestamps=[0.0, 1.0, 2.0],
    )
    assert seq["block_id"] == "creator-hud"
    assert seq["total_frames_captured"] == 3
    assert len(seq["frames"]) == 3
    assert seq["temporal_variance_verified"] is True
    assert seq["unique_frame_states_count"] == 3

    # Check distinct frame hashes across timestamps
    hashes = [f["sha256"] for f in seq["frames"]]
    assert len(set(hashes)) == 3, "Expected 3 distinct frame hashes over time for dynamic animation"


def test_wave9_canonical_motion_export_contract_v2():
    """Verify Version 2.0.0 Canonical Motion Export Contract geometry, safe margins, and FFmpeg filter."""
    contract_9_16 = CatalogExportContract.generate_canonical_motion_export_contract(
        block_id="yt-lower-third",
        aspect_ratio="9:16",
    )
    assert contract_9_16["schema_version"] == "2.0.0"
    assert contract_9_16["ffmpeg_overlay_recipe"]["consumer_role"] == "Role 2 (Motion Media Pipeline)"
    assert contract_9_16["pipeline_consumer_target"] == "backend.media_pipeline.clip_renderer.render_output_clip"
    assert contract_9_16["aspect_ratio"] == "9:16"
    assert contract_9_16["geometry"]["canvas_width"] == 1080
    assert contract_9_16["geometry"]["canvas_height"] == 1920
    assert contract_9_16["geometry"]["safe_margins"]["safe_margin_bottom_px"] == 96
    assert contract_9_16["alpha_semantics"]["frame_sequence_pixel_format"] == "rgba"
    assert "[0:v][1:v]overlay" in contract_9_16["ffmpeg_overlay_recipe"]["filter_complex_template"]
    assert contract_9_16["canonical_mp4_status"] == "ROLE2_RENDER_PIPELINE_PENDING"

    # Test 16:9 layout margins
    contract_16_9 = CatalogExportContract.generate_canonical_motion_export_contract(
        block_id="yt-lower-third",
        aspect_ratio="16:9",
    )
    assert contract_16_9["geometry"]["canvas_width"] == 1920
    assert contract_16_9["geometry"]["canvas_height"] == 1080
    assert contract_16_9["geometry"]["safe_margins"]["safe_margin_bottom_px"] == 80


def test_wave9_transparent_video_overlay_generation():
    """Verify physical transparent video overlay generation with FFmpeg and ffprobe alpha detection."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        res = CatalogExportContract.generate_transparent_video_overlay(
            block_id="creator-hud",
            aspect_ratio="9:16",
            duration_seconds=1.0,
            temp_dir=Path(tmp_dir),
        )
        assert res["block_id"] == "creator-hud"
        assert os.path.exists(res["video_path"])
        assert res["video_size_bytes"] > 0
        assert res["alpha_channel_detected"] is True
        assert res["ready_for_role2_media_pipeline"] is True
        assert res["ffprobe_analysis"]["codec_name"] in ("png", "prores", "qtrle")


def test_wave9_quarantine_rejection_for_unready_blocks():
    """Wave 9 Negative Safety Gate: Enforces quarantine rejection on all 186 unready blocks."""
    # camcorder-hud is quarantined (license review required)
    with pytest.raises(CatalogManifestError, match="quarantined: license review or structural fixes required"):
        CatalogManifestService.validate_block_for_project_insertion("camcorder-hud")

    # Verify project intent adapter honors strict quarantine
    req = AddToProjectIntentRequest(
        project_id="test_proj_1",
        strict_quarantine=True,
    )
    with pytest.raises(CatalogManifestError, match="quarantined: license review or structural fixes required"):
        CatalogProjectIntentAdapter.create_add_to_project_intent("camcorder-hud", req)


def test_wave9_variable_injection_and_prototype_pollution():
    """Wave 9 Negative Test: Reject prototype pollution and sanitize malicious variable injections."""
    req_malicious = AddToProjectIntentRequest(
        project_id="test_proj_2",
        custom_variables={
            "__proto__": "polluted",
            "prototype": "polluted",
            "title": "<script>alert('xss')</script>SafeTitle",
            "color": "javascript:evil()",
        },
    )
    # Prototype pollution key must raise CatalogManifestError
    with pytest.raises(CatalogManifestError, match="Disallowed parameter key"):
        CatalogProjectIntentAdapter.create_add_to_project_intent("yt-lower-third", req_malicious)

    # Safe variable with script injection tags stripped
    req_xss = AddToProjectIntentRequest(
        project_id="test_proj_3",
        custom_variables={
            "channel_name": "<script>alert('xss')</script>CleanChannel",
        },
    )
    res = CatalogProjectIntentAdapter.create_add_to_project_intent("yt-lower-third", req_xss)
    assert "<script>" not in res.timeline_item.variables["channel_name"]
    assert "CleanChannel" in res.timeline_item.variables["channel_name"]


def test_wave9_custom_source_code_injection_rejection():
    """Wave 9 Negative Test: Custom source code rejects path traversal, eval, remote CDNs, and token exfiltration."""
    bad_sources = [
        "import ../../secret.js",
        "<script src='https://cdn.malicious.com/payload.js'></script>",
        "const evil = eval('alert(1)');",
        "fetch('/api/token').then(t => exfiltrate(t));",
    ]
    for bad in bad_sources:
        req = AddToProjectIntentRequest(
            project_id="proj_custom_source",
            project_owned_source=bad,
        )
        with pytest.raises(CatalogManifestError):
            CatalogProjectIntentAdapter.create_add_to_project_intent("flowing-gradient", req)


def test_wave9_cross_user_isolation():
    """Wave 9 Cross-User Isolation: Different user IDs receive independent instances and scoped documents."""
    req_user_a = AddToProjectIntentRequest(
        project_id="proj_shared",
        owning_user_id="user_alice",
        custom_variables={"channel_name": "Alice Channel"},
    )
    req_user_b = AddToProjectIntentRequest(
        project_id="proj_shared",
        owning_user_id="user_bob",
        custom_variables={"channel_name": "Bob Channel"},
    )
    res_a = CatalogProjectIntentAdapter.create_add_to_project_intent("yt-lower-third", req_user_a)
    res_b = CatalogProjectIntentAdapter.create_add_to_project_intent("yt-lower-third", req_user_b)

    assert res_a.timeline_item.instance_id != res_b.timeline_item.instance_id
    assert res_a.timeline_item.owning_user_id == "user_alice"
    assert res_b.timeline_item.owning_user_id == "user_bob"
    assert res_a.timeline_item.variables["channel_name"] == "Alice Channel"
    assert res_b.timeline_item.variables["channel_name"] == "Bob Channel"


def test_wave9_undo_revert_operation_integrity():
    """Wave 9 Undo Operation: Validated intent returns reversible document descriptor with CAS increment."""
    req = AddToProjectIntentRequest(
        project_id="proj_undo_test",
        expected_revision=5,
        timeline_track_index=1,
    )
    res = CatalogProjectIntentAdapter.create_add_to_project_intent("plasma", req)
    revert = res.revert_operation
    assert revert["action"] == "remove_timeline_item"
    assert revert["target_project_id"] == "proj_undo_test"
    assert revert["item_id"] == res.timeline_item.item_id
    assert revert["instance_id"] == res.timeline_item.instance_id
    assert revert["track_index"] == 1
    assert revert["expected_revision"] == 6  # CAS revision incremented for rollback
    assert revert["reversible"] is True


def test_wave9_vetted_creative_skills_safe_transformation():
    """Wave 9 Vetted Skills: Creative recipes safely transformed into project instructions (zero donor prompts)."""
    recipes = CreativeRecipeEngine.get_registered_recipes()
    assert len(recipes) >= 4
    recipe_ids = [r.recipe_id for r in recipes]
    assert "recipe_faceless_short_15s" in recipe_ids
    assert "recipe_kinetic_hook_5s" in recipe_ids
    assert "recipe_social_cta_burst_6s" in recipe_ids

    # Apply recipe to dummy project document
    doc = {"timeline": {"tracks": [{"clips": []}]}}
    updated = CreativeRecipeEngine.apply_recipe_to_project_document(
        doc=doc,
        recipe_id="recipe_faceless_short_15s",
        start_time=0.0,
    )
    assert updated["success"] is True
    assert updated["recipe_id"] == "recipe_faceless_short_15s"
    assert updated["inserted_clips_count"] > 0
    total_clips = sum(len(t.get("clips", [])) for t in doc["timeline"]["tracks"])
    assert total_clips == updated["inserted_clips_count"]


def test_wave9_zero_donor_checkout_runtime_dependency():
    """Wave 9 GT-20: Catalog runs entirely from internal assets without accessing donor checkout."""
    for b_id in OPERATIONAL_12_BLOCKS:
        assets_res = CatalogExportContract.verify_self_contained_assets(b_id)
        assert assets_res["fully_self_contained"] is True
        assert assets_res["missing_count"] == 0
        assert assets_res["zero_donor_checkout_dependency"] is True


def test_wave9_fastapi_endpoints():
    """Wave 9 REST API Endpoints: /api/catalog/wave9-audit and /api/catalog/blocks/{id}/canonical-export-contract."""
    # Test wave9 audit endpoint
    res_audit = client.get("/api/catalog/wave9-audit")
    assert res_audit.status_code == 200
    audit_data = res_audit.json()
    assert audit_data["wave"] == "WAVE_9"
    assert audit_data["total_operational_blocks"] == 12
    assert audit_data["terminal_declarations"]["MEDIA_PIPELINE_CANONICAL_MP4"] == "ROLE2_RENDER_PIPELINE_PENDING"

    # Test canonical export contract endpoint
    res_contract = client.get("/api/catalog/blocks/yt-lower-third/canonical-export-contract?aspect_ratio=9:16")
    assert res_contract.status_code == 200
    contract_data = res_contract.json()
    assert contract_data["schema_version"] == "2.0.0"
    assert contract_data["ffmpeg_overlay_recipe"]["consumer_role"] == "Role 2 (Motion Media Pipeline)"
    assert contract_data["geometry"]["safe_margins"]["safe_margin_bottom_px"] == 96

    # Test quarantine error on unready block
    res_quarantined = client.get("/api/catalog/blocks/camcorder-hud/canonical-export-contract")
    assert res_quarantined.status_code == 400
    assert "quarantined" in res_quarantined.json()["detail"].lower()
