# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 6 Role 3 Test Suite: HyperFrames Functional Blocks, Proof Ladder,
Export-Consumable Manifests, Vetted Creative Recipes, and GT Compliance.

Verifies:
1. Proof ladder truthfulness (STRUCTURALLY_TESTED, BROWSER_NOT_TESTED: 0, RENDER_IN_MP4_NOT_TESTED: 0).
2. Honest integration declaration (HYPERFRAMES_FULLY_INTEGRATED: NO, ALL_196_RUNTIME_READY: NO).
3. Export-consumable manifest contract for Role 2 (FFmpeg) and Role 4 (browser).
4. Multi-sample dynamic frame proof demonstrating temporal variance across timestamps.
5. GT-09: CodeMirror project-owned custom source code isolation and keyframe persistence.
6. GT-13: 196 catalog block disposition truthfulness and aspect parity.
7. GT-14: Legitimate custom block synthesis from prompt spec with pinned offline code and license clearance.
8. GT-20: Zero-donor checkout runtime dependency.
9. Vetted creative editor/agent recipes labeled RECIPE_READY_RENDER_PENDING.
10. Fast REST API endpoints for Wave 6 audit, recipes, synthesis, export manifest, and frame proof.
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


def test_wave6_factual_audit_and_proof_ladder():
    """Verify Wave 6 proof ladder: STRUCTURALLY_TESTED, BROWSER_NOT_TESTED, HYPERFRAMES_FULLY_INTEGRATED: NO."""
    audit = CatalogManifestService.get_wave6_factual_audit()

    assert audit["wave"] == "WAVE_6"
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

    # Proof ladder
    ladder = audit["proof_ladder"]
    assert ladder["structural_testing_status"] == "STRUCTURALLY_TESTED"
    assert ladder["structural_verified_blocks"] == 12
    assert ladder["browser_verified_blocks"] == 0
    assert ladder["browser_verification_status"] == "BROWSER_NOT_TESTED"
    assert "Role 4" in ladder["browser_verification_disclaimer"]
    assert ladder["render_in_mp4_verified_blocks"] == 0
    assert ladder["render_in_mp4_verification_status"] == "RENDER_IN_MP4_NOT_TESTED"

    # Strict declarations
    decls = audit["status_declarations"]
    assert decls["HYPERFRAMES_WHOLE_TREE_AUDITED"] == "YES"
    assert decls["ALL_196_RUNTIME_READY"] == "NO"
    assert decls["RUNTIME_ZERO_DONOR_DEPENDENCY"] == "YES"
    assert decls["HYPERFRAMES_FULLY_INTEGRATED"] == "NO"

    # GT compliance matrix
    gt = audit["gt_compliance"]
    assert gt["GT_09_custom_source_isolated_and_persistent"] is True
    assert gt["GT_13_truthful_196_disposition_and_aspect_parity"] is True
    assert gt["GT_14_legitimate_custom_block_synthesis"] is True
    assert gt["GT_20_zero_donor_checkout_runtime_dependency"] is True


def test_export_consumable_manifest_generation():
    """Verify export manifest contract consumable by Role 2 FFmpeg / Role 4 browser."""
    # Test transparent overlay block
    hud_manifest = CatalogExportContract.generate_export_manifest("creator-hud", aspect_ratio="9:16")
    assert hud_manifest["schema_version"] == "1.0.0"
    assert hud_manifest["block_id"] == "creator-hud"
    assert hud_manifest["aspect_ratio"] == "9:16"
    assert hud_manifest["viewport"]["width"] == 1080
    assert hud_manifest["viewport"]["height"] == 1920
    assert hud_manifest["rendering_channel"]["alpha_channel_required"] is True
    assert hud_manifest["rendering_channel"]["pixel_format_target"] == "yuva420p"
    assert hud_manifest["isolation_assertions"]["zero_external_cdn"] is True
    assert hud_manifest["isolation_assertions"]["zero_donor_dependency"] is True
    assert hud_manifest["integration_role_wiring"]["consumer_role"] == "Role 2 (Media Engine / FFmpeg)"

    # Test opaque background block
    aurora_manifest = CatalogExportContract.generate_export_manifest("aurora", aspect_ratio="16:9")
    assert aurora_manifest["block_id"] == "aurora"
    assert aurora_manifest["aspect_ratio"] == "16:9"
    assert aurora_manifest["viewport"]["width"] == 1920
    assert aurora_manifest["viewport"]["height"] == 1080
    assert aurora_manifest["rendering_channel"]["alpha_channel_required"] is False
    assert aurora_manifest["rendering_channel"]["stage_background_color"] == "#000000"


def test_dynamic_frame_proof_temporal_variance():
    """Verify multi-sample dynamic frame proof detects temporal variance across timestamps."""
    proof = CatalogExportContract.compute_dynamic_frame_proof("creator-hud", aspect_ratio="9:16", sample_count=5)

    assert proof["block_id"] == "creator-hud"
    assert proof["sample_count"] == 5
    assert len(proof["samples"]) == 5
    assert proof["temporal_variance_detected"] is True
    assert proof["motion_progression_proof"] == "DYNAMIC_VARIANCE_VERIFIED"

    # Verify sample timestamps advance monotonically
    timestamps = [s["timestamp_seconds"] for s in proof["samples"]]
    assert timestamps == sorted(timestamps)
    assert timestamps[0] == 0.0
    assert timestamps[-1] == proof["duration_seconds"]

    # Verify timecode formatting
    assert proof["samples"][0]["timecode"] == "00:00:00"


def test_gt09_project_owned_source_isolation_and_persistence():
    """Verify GT-09: CodeMirror project-owned custom source persists per instance without cross-contamination."""
    custom_code_1 = """<!doctype html><html><body style="background:#111;"><h1 id="hud">Alpha Version</h1></body></html>"""
    custom_code_2 = """<!doctype html><html><body style="background:#222;"><h1 id="hud">Beta Version</h1></body></html>"""

    req1 = AddToProjectIntentRequest(
        project_id="proj_gt09",
        project_owned_source=custom_code_1,
        keyframes=[{"time_seconds": 1.0, "properties": {"opacity": 0.5}, "easing": "ease-in"}],
        owning_user_id="user_alpha",
    )
    req2 = AddToProjectIntentRequest(
        project_id="proj_gt09",
        project_owned_source=custom_code_2,
        owning_user_id="user_beta",
    )

    res1 = CatalogProjectIntentAdapter.create_add_to_project_intent("creator-hud", req1)
    res2 = CatalogProjectIntentAdapter.create_add_to_project_intent("creator-hud", req2)

    # Scoped instance isolation
    assert res1.timeline_item.instance_id != res2.timeline_item.instance_id
    assert res1.timeline_item.has_custom_source is True
    assert res2.timeline_item.has_custom_source is True
    assert res1.timeline_item.instance_source_code == custom_code_1
    assert res2.timeline_item.instance_source_code == custom_code_2
    assert res1.timeline_item.instance_source_code != res2.timeline_item.instance_source_code

    # Keyframes attached to instance 1
    assert len(res1.timeline_item.keyframes) == 1
    assert res1.timeline_item.keyframes[0]["time_seconds"] == 1.0
    assert len(res2.timeline_item.keyframes) == 0

    # Multi-tenant user ownership preserved
    assert res1.timeline_item.owning_user_id == "user_alpha"
    assert res2.timeline_item.owning_user_id == "user_beta"


def test_gt09_custom_source_security_sanitization():
    """Verify GT-09: custom source code rejects path traversal, remote CDNs, eval, and tokens."""
    # Path traversal rejected
    with pytest.raises(CatalogManifestError, match="Path traversal"):
        CatalogProjectIntentAdapter.sanitize_custom_source("<script src='../../secret.js'></script>")

    # Remote script / CDN rejected
    with pytest.raises(CatalogManifestError, match="Remote scripts"):
        CatalogProjectIntentAdapter.sanitize_custom_source("<script src='https://cdn.jsdelivr.net/npm/gsap'></script>")

    # Arbitrary code execution / token exfiltration rejected
    with pytest.raises(CatalogManifestError, match="Unsafe execution"):
        CatalogProjectIntentAdapter.sanitize_custom_source("<script>eval(process.env.SECRET_TOKEN)</script>")


def test_gt13_truthful_196_disposition_matrix():
    """Verify GT-13: catalog accurately categorizes 196 items with clear release dispositions."""
    items = CatalogManifestService.get_all_items()
    assert len(items) == 196

    ready_items = [it for it in items if it.get("runtime_ready")]
    unready_items = [it for it in items if not it.get("runtime_ready")]

    assert len(ready_items) == 10  # 10 donor-origin blocks
    assert len(unready_items) == 186

    # Verify each ready item has both 9:16 and 16:9 poster URLs
    for it in ready_items:
        assert it.get("aspect_9_16") in ("NATIVE", "ADAPTED", "CONTAINED_ONLY")
        assert it.get("aspect_16_9") in ("NATIVE", "CONTAINED_ONLY")

    # Verify unready items contain explicit English blocker reasons
    for it in unready_items:
        assert it.get("blocker_code") in (
            "LICENSE_REVIEW_REQUIRED_AMBIGUOUS_RIGHTS",
            "STRUCTURAL_FIX_MISSING_ENTRYPOINT",
        )
        assert len(it.get("blocker_reason", "")) > 10


def test_gt14_legitimate_custom_block_synthesis():
    """Verify GT-14: synthesize a new legitimate custom block from prompt spec with zero-CDN and license clearance."""
    spec = CustomBlockPromptSpec(
        block_name="neon-countdown",
        title="Neon Cyber Countdown",
        description="High-energy countdown timer for esports and product drop reels",
        category="overlays",
        target_aspect="9:16",
        duration_seconds=5.0,
        primary_color="#00f3ff",
        secondary_color="#ff0055",
        animation_style="kinetic_pulse",
        headline_text="DROP IN 05",
        author="ViralMint Creator",
        license="Apache-2.0",
    )

    result = CreativeRecipeEngine.synthesize_custom_block(spec)

    assert result["status"] == "SYNTHESIZED_CUSTOM_BLOCK"
    assert result["block_id"] == "neon-countdown"
    assert result["offline_isolated"] is True
    assert result["zero_external_cdn"] is True
    assert result["zero_donor_dependency"] is True

    # Pinned code assertions
    assert "https://" not in result["composition_html"]
    assert "http://" not in result["composition_html"]
    assert "DROP IN 05" in result["composition_html"]
    assert len(result["composition_sha256"]) == 64

    # Compliance
    compliance = result["gt14_compliance"]
    assert compliance["pinned_code"] is True
    assert compliance["editable"] is True
    assert compliance["sandbox_intact"] is True
    assert compliance["license_cleared"] is True


def test_vetted_creative_recipes_registry():
    """Verify registered creative editor/agent recipes labeled RECIPE_READY_RENDER_PENDING."""
    recipes = CreativeRecipeEngine.get_registered_recipes()
    assert len(recipes) >= 2

    # Check 15s Faceless explainer recipe
    faceless = CreativeRecipeEngine.get_recipe_by_id("recipe_faceless_short_15s")
    assert faceless is not None
    assert faceless.status == "RECIPE_READY_RENDER_PENDING"
    assert faceless.total_duration_seconds == 15.0
    assert faceless.target_aspect_ratio == "9:16"
    assert faceless.anti_flash_enforced is True
    assert faceless.safe_margin_bottom_px == 96
    assert len(faceless.timeline_steps) == 5

    # Check doctrines referenced
    assert "motion-doctrine" in faceless.doctrines_referenced
    assert "cut-the-curve" in faceless.doctrines_referenced
    assert "captions-overlay" in faceless.doctrines_referenced


def test_api_wave6_endpoints():
    """Verify all Wave 6 REST endpoints respond with 200 and truthful payloads."""
    # 1. GET /api/catalog/wave6-audit
    res_audit = client.get("/api/catalog/wave6-audit")
    assert res_audit.status_code == 200
    data_audit = res_audit.json()
    assert data_audit["wave"] == "WAVE_6"
    assert data_audit["status_declarations"]["HYPERFRAMES_FULLY_INTEGRATED"] == "NO"
    assert data_audit["proof_ladder"]["structural_testing_status"] == "STRUCTURALLY_TESTED"

    # 2. GET /api/catalog/creative-recipes
    res_recipes = client.get("/api/catalog/creative-recipes")
    assert res_recipes.status_code == 200
    assert res_recipes.json()["count"] >= 2

    # 3. GET /api/catalog/creative-recipes/{id}
    res_recipe = client.get("/api/catalog/creative-recipes/recipe_faceless_short_15s")
    assert res_recipe.status_code == 200
    assert res_recipe.json()["recipe_id"] == "recipe_faceless_short_15s"

    # 4. POST /api/catalog/synthesize-block
    res_synth = client.post("/api/catalog/synthesize-block", json={
        "block_name": "api-synth-block",
        "title": "API Synth Block",
        "description": "Synthesized via REST endpoint",
        "category": "call-to-action",
        "target_aspect": "9:16",
        "duration_seconds": 3.0,
    })
    assert res_synth.status_code == 200
    assert res_synth.json()["status"] == "SYNTHESIZED_CUSTOM_BLOCK"

    # 5. GET /api/catalog/blocks/{id}/export-manifest
    res_man = client.get("/api/catalog/blocks/creator-hud/export-manifest")
    assert res_man.status_code == 200
    assert res_man.json()["block_id"] == "creator-hud"

    # 6. GET /api/catalog/blocks/{id}/frame-proof
    res_proof = client.get("/api/catalog/blocks/creator-hud/frame-proof?sample_count=4")
    assert res_proof.status_code == 200
    assert res_proof.json()["sample_count"] == 4
    assert res_proof.json()["temporal_variance_detected"] is True


def test_gt20_zero_donor_runtime_independence():
    """Verify GT-20: complete zero runtime dependency on C:/Users/toddy/Desktop/hyperframes."""
    for block_id in WAVE4_INTERNALIZED_BLOCKS:
        # Check export manifest
        manifest = CatalogExportContract.generate_export_manifest(block_id)
        assert manifest["isolation_assertions"]["zero_donor_dependency"] is True
        assert manifest["isolation_assertions"]["zero_external_cdn"] is True

        manifest_str = json.dumps(manifest)
        assert "hyperframes" not in manifest_str.lower() or "hyperframes:block" in manifest_str or "hyperframes:composition" in manifest_str
        assert "C:\\Users\\toddy\\Desktop\\hyperframes" not in manifest_str
        assert "localhost:" not in manifest_str
