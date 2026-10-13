# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 7 Role 3 Test Suite: HyperFrames Offline Blocks, Browser Export Overlay Contract,
Physical Alpha Probe, Reversible Timeline Operations, and Creative Recipe Execution.

Verifies:
1. Proof ladder across all 12 operational blocks (inventory, rights, packaged, dynamic_browser, persisted_in_project, video_export_mp4).
2. Honest terminal declarations (HYPERFRAMES_FULLY_INTEGRATED: NO, DONOR_BLOCKS_READY: 10, INDEPENDENT_BROWSER_VERIFIED: 0, MP4_COMPOSITION_VERIFIED: NOT_TESTED).
3. End-to-end overlay export contract with geometry, timing, alpha semantics, safe margins (>= 96px), keyframes, and FFmpeg filter recipe.
4. Physical alpha frame rendering and ffprobe pixel-level alpha probe verification.
5. Reversible document operations (revert_operation descriptor in project intent).
6. Creative recipe execution generating typed timeline items without donor prompts or remote plugins.
7. Zero-donor checkout runtime dependency (GT-20).
8. REST API endpoints for Wave 7 audit, overlay contract, physical alpha probe, and recipe execution.
"""
import json
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.catalog.manifest_service import (
    CatalogManifestService,
    CatalogManifestError,
    WAVE4_INTERNALIZED_BLOCKS,
    CORE_INTERNALIZED_BLOCKS,
    CATALOG_ROOT,
)
from backend.catalog.export_contract import (
    CatalogExportContract,
    CatalogExportContractError,
    TRANSPARENT_OVERLAY_BLOCKS,
)
from backend.catalog.creative_recipes import (
    CreativeRecipeEngine,
    CustomBlockPromptSpec,
)
from backend.catalog.project_intent_contract import (
    AddToProjectIntentRequest,
    CatalogProjectIntentAdapter,
)
from backend.catalog.router import router

app = FastAPI()
app.include_router(router, prefix="/api")
client = TestClient(app)


def test_wave7_factual_audit_and_proof_ladder():
    """Verify Wave 7 proof ladder across all 12 operational blocks and strict terminal declarations."""
    audit = CatalogManifestService.get_wave7_factual_audit()

    assert audit["wave"] == "WAVE_7"
    assert audit["whole_tree_audited"] is True
    assert audit["total_donor_files_audited"] == 9059
    assert audit["total_donor_bytes_audited"] == 852720453

    # Exact inventory counts
    assert audit["total_catalog_blocks_inventoried"] == 196
    assert audit["donor_origin_blocks_count"] == 10
    assert audit["original_substitutes_count"] == 2
    assert audit["total_operational_blocks"] == 12
    assert audit["unready_blocks_count"] == 186
    assert audit["not_ready_license_review_required"] == 168
    assert audit["not_ready_structural_fix_required"] == 18

    # Terminal declarations
    term = audit["terminal_declarations"]
    assert term["HYPERFRAMES_FULLY_INTEGRATED"] == "NO"
    assert term["DONOR_BLOCKS_READY"] == 10
    assert term["ORIGINAL_SUBSTITUTES_READY"] == 2
    assert term["TOTAL_OPERATIONAL_BLOCKS"] == 12
    assert term["INDEPENDENT_BROWSER_VERIFIED"] == 0
    assert term["MP4_COMPOSITION_VERIFIED"] == "NOT_TESTED"
    assert term["LEGACY_DONOR_RUNTIME_DEPENDENCY"] == "NO"
    assert term["UNREADY_DONOR_BLOCKS_QUARANTINED"] == 186

    # Proof ladder per block
    ladder = audit["proof_ladder_12_blocks"]
    assert len(ladder) == 12
    for block_id, proofs in ladder.items():
        assert proofs["inventory"] == "PASS"
        assert proofs["rights"] in ["PASS", "6CLIPS_ORIGINAL_APACHE_2_0"]
        assert proofs["packaged"] == "PASS"
        assert proofs["dynamic_browser"] == "UNVERIFIED_ROLE4_DEFERRED"  # Honest: deferred to Role 4
        assert proofs["persisted_in_project"] == "UNVERIFIED_ROLE1_DEFERRED"
        assert proofs["video_export_mp4"] == "UNVERIFIED_ROLE2_DEFERRED"  # Honest: deferred to Role 2


def test_e2e_overlay_contract_geometry_and_timing():
    """Verify e2e overlay contract geometry (9:16 safe margin >= 96px, 16:9), timing, keyframes, and FFmpeg filter."""
    # Test 9:16 aspect
    contract_916 = CatalogExportContract.generate_e2e_overlay_contract("yt-lower-third", aspect_ratio="9:16")
    assert contract_916["block_id"] == "yt-lower-third"
    assert contract_916["contract_type"] == "E2E_OVERLAY_EXPORT_CONTRACT"

    geom_916 = contract_916["geometry"]
    assert geom_916["target_aspect"] == "9:16"
    assert geom_916["viewport_width"] == 1080
    assert geom_916["viewport_height"] == 1920
    assert geom_916["card_bounding_box"]["x_px"] == 48
    assert geom_916["card_bounding_box"]["y_px"] == 1644
    assert geom_916["card_bounding_box"]["width_px"] == 984
    assert geom_916["card_bounding_box"]["height_px"] == 180
    assert geom_916["safe_margins"]["safe_margin_bottom_px"] >= 96
    assert (1920 - (geom_916["card_bounding_box"]["y_px"] + geom_916["card_bounding_box"]["height_px"])) >= 96

    timing = contract_916["timing"]
    assert timing["duration_seconds"] == 5.0
    assert timing["in_transition"]["start_seconds"] == 0.0
    assert timing["in_transition"]["end_seconds"] == 0.4
    assert timing["hold_window"]["start_seconds"] == 0.4
    assert timing["hold_window"]["end_seconds"] == 4.4
    assert timing["out_transition"]["start_seconds"] == 4.4
    assert timing["out_transition"]["end_seconds"] == 5.0

    alpha = contract_916["alpha_semantics"]
    assert alpha["alpha_channel_required"] is True
    assert alpha["pixel_format_target"] in ["yuva420p", "rgba"]

    ffmpeg = contract_916["ffmpeg_overlay_recipe"]
    assert "[0:v][1:v]overlay" in ffmpeg["filter_complex_template"]
    assert "format=auto" in ffmpeg["filter_complex_template"]

    # Test 16:9 aspect
    contract_169 = CatalogExportContract.generate_e2e_overlay_contract("yt-lower-third", aspect_ratio="16:9")
    geom_169 = contract_169["geometry"]
    assert geom_169["viewport_width"] == 1920
    assert geom_169["viewport_height"] == 1080
    assert geom_169["card_bounding_box"]["x_px"] == 80
    assert geom_169["card_bounding_box"]["y_px"] == 860
    assert geom_169["card_bounding_box"]["width_px"] == 820
    assert geom_169["card_bounding_box"]["height_px"] == 140
    assert (1080 - (geom_169["card_bounding_box"]["y_px"] + geom_169["card_bounding_box"]["height_px"])) >= 80


def test_physical_alpha_frame_probe():
    """Verify physical 1080x1920 RGBA frame generation and ffprobe alpha detection."""
    probe = CatalogExportContract.verify_physical_alpha_frame("yt-lower-third")

    assert probe["block_id"] == "yt-lower-third"
    assert probe["dimensions"]["width"] == 1080
    assert probe["dimensions"]["height"] == 1920
    assert probe["alpha_channel_detected"] is True
    assert probe["physical_alpha_verified"] is True
    assert probe["sample_pixel_transparent"][3] == 0
    assert probe["sample_pixel_opaque_card"][3] > 200
    assert probe["pixel_format_ffprobe"] in ["rgba", "yuva420p"]


def test_reversible_timeline_operations():
    """Verify reversible document operations (revert_operation descriptor in project intent)."""
    req = AddToProjectIntentRequest(
        project_id="proj-wave7-test",
        expected_revision=2,
        custom_variables={"channel_name": "@viral", "subscribe_prompt": "Subscribe"},
    )
    result = CatalogProjectIntentAdapter.create_add_to_project_intent("yt-lower-third", req)

    assert result.status == "VALIDATED_INTENT"
    assert result.revert_operation is not None
    assert result.revert_operation["action"] == "remove_timeline_item"
    assert result.revert_operation["item_id"] == result.timeline_item.item_id
    assert result.revert_operation["instance_id"] == result.timeline_item.instance_id
    assert result.revert_operation["track_index"] == result.timeline_item.track_index
    assert result.revert_operation["expected_revision"] == 3


def test_creative_recipe_execution():
    """Verify creative recipes execution translating steps into concrete typed timeline items."""
    recipes = CreativeRecipeEngine.get_registered_recipes()
    assert len(recipes) >= 3

    # Check the 3rd recipe: recipe_kinetic_hook_5s
    kinetic_recipe = next((r for r in recipes if r.recipe_id == "recipe_kinetic_hook_5s"), None)
    assert kinetic_recipe is not None
    assert kinetic_recipe.total_duration_seconds == 5.0
    assert len(kinetic_recipe.timeline_steps) == 2

    # Execute recipe into timeline items
    executed = CreativeRecipeEngine.execute_recipe_to_timeline(
        recipe_id="recipe_kinetic_hook_5s",
        project_id="proj-recipe-wave7",
    )

    assert executed["recipe_id"] == "recipe_kinetic_hook_5s"
    assert executed["recipe_status"] == "RECIPE_READY_RENDER_PENDING"
    assert len(executed["timeline_items"]) == 2
    assert len(executed["revert_operations"]) == 2
    assert executed["total_duration_seconds"] == 5.0

    # Verify first step item
    first_item = executed["timeline_items"][0]
    assert first_item["block_id"] == "plasma"
    assert first_item["start_time"] == 0.0
    assert first_item["duration"] == 2.0


def test_gt20_zero_donor_runtime_independence():
    """Verify zero-donor checkout runtime independence: all 12 operational blocks load valid manifests and export contracts from repo-local files."""
    for block_id in WAVE4_INTERNALIZED_BLOCKS:
        item = CatalogManifestService.get_item(block_id)
        assert item is not None
        assert item.get("internalized") is True or item.get("runtime_ready") is True

        contract = CatalogExportContract.generate_e2e_overlay_contract(block_id)
        assert contract["block_id"] == block_id


def test_rest_api_wave7_endpoints():
    """Verify Wave 7 REST API endpoints: audit, overlay contract, alpha probe, and recipe execution."""
    # 1. Audit endpoint
    res_audit = client.get("/api/catalog/wave7-audit")
    assert res_audit.status_code == 200
    data_audit = res_audit.json()
    assert data_audit["wave"] == "WAVE_7"
    assert data_audit["terminal_declarations"]["HYPERFRAMES_FULLY_INTEGRATED"] == "NO"
    assert data_audit["terminal_declarations"]["INDEPENDENT_BROWSER_VERIFIED"] == 0

    # 2. Overlay contract endpoint
    res_overlay = client.get("/api/catalog/blocks/yt-lower-third/overlay-contract?aspect_ratio=9:16")
    assert res_overlay.status_code == 200
    data_overlay = res_overlay.json()
    assert data_overlay["block_id"] == "yt-lower-third"
    assert data_overlay["geometry"]["safe_margins"]["safe_margin_bottom_px"] >= 96

    # 3. Alpha probe endpoint
    res_probe = client.get("/api/catalog/blocks/yt-lower-third/alpha-probe")
    assert res_probe.status_code == 200
    data_probe = res_probe.json()
    assert data_probe["block_id"] == "yt-lower-third"
    assert data_probe["alpha_channel_detected"] is True
    assert data_probe["sample_pixel_transparent"][3] == 0

    # 4. Recipe execution endpoint
    res_exec = client.post(
        "/api/catalog/creative-recipes/recipe_kinetic_hook_5s/execute?project_id=proj-api-test"
    )
    assert res_exec.status_code == 200
    data_exec = res_exec.json()
    assert data_exec["recipe_id"] == "recipe_kinetic_hook_5s"
    assert len(data_exec["timeline_items"]) == 2
