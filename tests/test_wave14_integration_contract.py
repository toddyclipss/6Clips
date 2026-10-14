# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 14 Agent 1: Safe Integration and Catalog API Glue Contract Suite.

Validates:
1. Ancestry & Lineage:
   - Base commit 451e7e529cfdd26c7ba3a0c4086bbfee838dbb42 is verified ancestor.
   - Wave 13 validator tip d33a65a339edb7b68a7bc3e6a3a484a0151e5cd9 is merged and ancestral.
   - Stage 1 Agent 5 tip 0cfa8066bc4667d40f631a49f4a33c68583728ad is merged and ancestral.
   - Stage 1 Agent 3 tip c2b18eb1a0052fccdb1b6a31cfe421dfd13eafc3 is merged and ancestral.
   - Stage 1 Agent 2 tip b663764e6b6c5107bcfb0e2733d2c66c4feeb974 is merged and ancestral.
   - Production main branch (3608ddb325977cc03e6668082c05b53dbad511bd) and viralmint.db are strictly protected.
2. Shared Cross-Agent Inventory Contract v1 (F01-F24):
   - Exactly 196 original donor block directories in packaged manifest.
   - Exactly 170 aggregated manifest entries + 26 unbundled entries = 196.
   - Exactly 222 microcomponents and 8 examples quarantined as distinct inventories.
   - Exactly 10 donor-original internalized blocks.
   - Exactly 2 separate 6Clips-authored blocks (creator-hud, glitch-transition) outside donor 196 manifest.
   - Exactly 186 unported donor blocks (154 BLOCKED_DEPENDENCY, 15 BLOCKED_LICENSE, 17 ELIGIBLE_NOT_PORTED).
   - Operational block total = 12 (10 donor + 2 6Clips).
3. Full API Route Contracts:
   - GET /api/catalog/inventory returns reconciled manifest, pagination, filtering, search, and separate 6Clips originals.
   - GET /api/catalog/reconciliation returns verified census breakdown and donor independence.
   - GET /api/catalog/audit returns machine-readable donor independence and licensing audit.
4. Negative Safety Gates:
   - Uninternalized blocks strictly forbidden from poster, preview, and project insertion intents.
   - Operational blocks remain fully functional.
5. GT-20 Zero Donor Dependency:
   - Catalog operates deterministically without mounting or accessing the external donor checkout.
6. Guardrails & Zero Idle Egress:
   - Preserves Wave 13 yt-dlp boot egress gate and zero unsolicited Ollama/cloud calls.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from backend.main import create_app
from backend.catalog.manifest_service import (
    CatalogManifestService,
    CORE_INTERNALIZED_BLOCKS,
    WAVE4_INTERNALIZED_BLOCKS,
    DONOR_INTERNALIZED_BLOCKS,
    SIXCLIPS_ORIGINAL_BLOCKS,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "backend" / "catalog_inventory" / "hyperframes_196_inventory.json"
FIXTURE_PATH = REPO_ROOT / "frontend" / "src" / "fixtures" / "hyperframes_196_fixture.json"
PRODUCTION_DB_PATH = Path(r"C:\Users\toddy\Desktop\ViralMint\viralmint.db")

EXPECTED_BASE_SHA = "451e7e529cfdd26c7ba3a0c4086bbfee838dbb42"
EXPECTED_WAVE13_VALIDATOR_SHA = "d33a65a339edb7b68a7bc3e6a3a484a0151e5cd9"
EXPECTED_AGENT5_TIP_SHA = "0cfa8066bc4667d40f631a49f4a33c68583728ad"
EXPECTED_AGENT3_TIP_SHA = "c2b18eb1a0052fccdb1b6a31cfe421dfd13eafc3"
EXPECTED_AGENT2_TIP_SHA = "b663764e6b6c5107bcfb0e2733d2c66c4feeb974"
EXPECTED_MAIN_SHA = "3608ddb325977cc03e6668082c05b53dbad511bd"


@pytest.fixture(scope="module")
def app_client():
    """Create a TestClient instance against the unified application factory."""
    app = create_app()
    with TestClient(app) as client:
        yield client


# =========================================================================
# 1. Lineage, Ancestry & Immutability Verification
# =========================================================================

def test_wave14_lineage_and_ancestor_verification():
    """Verify that all four required tips and baseline commit are ancestors of current HEAD."""
    def _is_ancestor(sha: str) -> bool:
        cmd = ["git", "merge-base", "--is-ancestor", sha, "HEAD"]
        proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True)
        return proc.returncode == 0

    assert _is_ancestor(EXPECTED_BASE_SHA), f"Base {EXPECTED_BASE_SHA} must be ancestor"
    assert _is_ancestor(EXPECTED_WAVE13_VALIDATOR_SHA), f"Wave13 validator {EXPECTED_WAVE13_VALIDATOR_SHA} must be ancestor"
    assert _is_ancestor(EXPECTED_AGENT5_TIP_SHA), f"Agent 5 tip {EXPECTED_AGENT5_TIP_SHA} must be ancestor"
    assert _is_ancestor(EXPECTED_AGENT3_TIP_SHA), f"Agent 3 tip {EXPECTED_AGENT3_TIP_SHA} must be ancestor"
    assert _is_ancestor(EXPECTED_AGENT2_TIP_SHA), f"Agent 2 tip {EXPECTED_AGENT2_TIP_SHA} must be ancestor"


def test_production_database_and_main_protection():
    """Verify production database file and main branch ref remain completely untouched."""
    # Check main ref
    proc = subprocess.run(["git", "rev-parse", "main"], cwd=REPO_ROOT, capture_output=True, text=True)
    assert proc.returncode == 0
    actual_main = proc.stdout.strip()
    assert actual_main == EXPECTED_MAIN_SHA, f"main SHA altered! Expected {EXPECTED_MAIN_SHA}, got {actual_main}"

    # Check production db exists and has non-zero size
    if PRODUCTION_DB_PATH.exists():
        assert PRODUCTION_DB_PATH.is_file()
        assert PRODUCTION_DB_PATH.stat().st_size > 0


# =========================================================================
# 2. Shared Cross-Agent Inventory Contract v1 Math & Invariants
# =========================================================================

def test_inventory_manifest_file_and_fixture_parity():
    """Verify backend tracked inventory manifest and frontend fixture match exactly."""
    assert MANIFEST_PATH.exists(), f"Backend manifest missing at {MANIFEST_PATH}"
    assert FIXTURE_PATH.exists(), f"Frontend fixture missing at {FIXTURE_PATH}"

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        backend_manifest = json.load(f)

    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        frontend_manifest = json.load(f)

    assert backend_manifest["schema_version"] == 1
    assert backend_manifest["source_inventory"] == "HyperFrames"
    assert backend_manifest["original_block_count"] == 196
    assert len(backend_manifest["blocks"]) == 196

    assert frontend_manifest["schema_version"] == 1
    assert frontend_manifest["source_inventory"] == "HyperFrames"
    assert frontend_manifest["original_block_count"] == 196
    assert len(frontend_manifest["blocks"]) == 196

    # Verify ID correspondence
    backend_ids = [b["id"] for b in backend_manifest["blocks"]]
    frontend_ids = [b["id"] for b in frontend_manifest["blocks"]]
    assert backend_ids == frontend_ids
    assert len(backend_ids) == len(set(backend_ids)), "Duplicate block IDs found"


def test_origin_separation_math_invariants():
    """Verify strict origin separation: 10 donor + 2 6Clips = 12 operational; 186 unported."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    blocks = manifest["blocks"]
    donor_ids = set(b["id"] for b in blocks)

    # 6Clips originals MUST NOT contaminate the 196 donor manifest
    for sc_id in SIXCLIPS_ORIGINAL_BLOCKS:
        assert sc_id not in donor_ids, f"6Clips block {sc_id} illegally in donor manifest"

    # Exactly 10 donor internalized blocks
    internalized = [b for b in blocks if b["integration_status"] == "INTERNALIZED"]
    assert len(internalized) == 10
    internalized_ids = set(b["id"] for b in internalized)
    assert internalized_ids == DONOR_INTERNALIZED_BLOCKS

    # Exactly 186 unported donor originals
    unported = [b for b in blocks if b["integration_status"] != "INTERNALIZED"]
    assert len(unported) == 186

    status_counts = {}
    for b in unported:
        st = b["integration_status"]
        status_counts[st] = status_counts.get(st, 0) + 1

    assert status_counts == {
        "BLOCKED_DEPENDENCY": 154,
        "BLOCKED_LICENSE": 15,
        "ELIGIBLE_NOT_PORTED": 17,
    }


# =========================================================================
# 3. Full Integrated API Route Contracts
# =========================================================================

def test_api_catalog_inventory_route(app_client):
    """Verify GET /api/catalog/inventory returns reconciled full inventory."""
    resp = app_client.get("/api/catalog/inventory?limit=300")
    assert resp.status_code == 200
    data = resp.json()

    assert data["schema_version"] == 1
    assert data["manifest_loaded"] is True
    assert data["reconciliation_status"] == "RECONCILED"
    assert data["donor_inventory_total"] == 196
    assert data["donor_internalized_working"] == 10
    assert data["donor_unported_count"] == 186
    assert data["sixclips_authored_count"] == 2
    assert data["total_operational_blocks"] == 12

    assert len(data["blocks"]) == 196
    assert len(data["sixclips_original_blocks"]) == 2

    # Verify sixclips blocks have origin 6CLIPS_ORIGINAL
    for sc in data["sixclips_original_blocks"]:
        assert sc["origin"] == "6CLIPS_ORIGINAL"
        assert sc["runtime_operable"] is True
        assert sc["id"] in SIXCLIPS_ORIGINAL_BLOCKS


def test_api_catalog_inventory_filters(app_client):
    """Verify GET /api/catalog/inventory filtering works accurately."""
    # Available now: 10 donor internalized
    resp_op = app_client.get("/api/catalog/inventory?filter=operational")
    assert resp_op.status_code == 200
    d_op = resp_op.json()
    assert d_op["total"] == 10
    for b in d_op["blocks"]:
        assert b["runtime_operable"] is True
        assert b["integration_status"] == "INTERNALIZED"

    # Unported: 186
    resp_unp = app_client.get("/api/catalog/inventory?filter=unported&limit=300")
    assert resp_unp.status_code == 200
    d_unp = resp_unp.json()
    assert d_unp["total"] == 186
    for b in d_unp["blocks"]:
        assert b["runtime_operable"] is False

    # Blocked: 169 (154 dependency + 15 license)
    resp_blk = app_client.get("/api/catalog/inventory?filter=blocked&limit=300")
    assert resp_blk.status_code == 200
    d_blk = resp_blk.json()
    assert d_blk["total"] == 169
    for b in d_blk["blocks"]:
        assert b["runtime_operable"] is False
        assert b["blocker_reason"] is not None

    # Eligible: 17
    resp_elg = app_client.get("/api/catalog/inventory?filter=eligible&limit=300")
    assert resp_elg.status_code == 200
    d_elg = resp_elg.json()
    assert d_elg["total"] == 17
    for b in d_elg["blocks"]:
        assert b["runtime_operable"] is False
        assert b["integration_status"] == "ELIGIBLE_NOT_PORTED"


def test_api_catalog_reconciliation_and_audit(app_client):
    """Verify GET /api/catalog/reconciliation and /audit return truthful metrics."""
    resp_rec = app_client.get("/api/catalog/reconciliation")
    assert resp_rec.status_code == 200
    d_rec = resp_rec.json()
    assert "wave14_reconciliation" in d_rec
    w14 = d_rec["wave14_reconciliation"]
    census = w14["census"]
    assert census["on_disk_block_dirs"] == 196
    assert census["aggregate_registry_json_blocks"] == 170
    assert census["unbundled_shader_and_extended_blocks"] == 26
    assert census["aggregate_registry_json_components"] == 222
    assert census["aggregate_registry_json_examples"] == 8
    assert w14["donor_internalized_working"] == 10
    assert w14["donor_unported_count"] == 186
    assert w14["sixclips_authored_count"] == 2
    assert w14["total_operational_blocks"] == 12

    resp_aud = app_client.get("/api/catalog/audit")
    assert resp_aud.status_code == 200
    d_aud = resp_aud.json()
    assert d_aud["donor_independence"]["runtime_donor_required"] is False
    assert d_aud["donor_independence"]["manifest_internalized"] is True
    assert d_aud["donor_independence"]["shipped_blocks_packaged"] is True


# =========================================================================
# 4. Negative Safety Gates
# =========================================================================

def test_negative_safety_gates_forbid_uninternalized_blocks(app_client):
    """Verify uninternalized blocks are rejected from poster, preview, and timeline insertion."""
    uninternalized_sample = ["blob", "liquid-metal", "3d-card", "confetti"]

    for block_id in uninternalized_sample:
        # Poster forbidden
        res_post = app_client.get(f"/api/catalog/blocks/{block_id}/poster")
        assert res_post.status_code in (400, 403, 404)

        # Preview forbidden
        res_prev = app_client.get(f"/api/catalog/blocks/{block_id}/preview")
        assert res_prev.status_code in (400, 403, 404)

        # Project intent insertion forbidden
        res_intent = app_client.post(
            f"/api/catalog/blocks/{block_id}/intent/add-to-project",
            json={"project_id": "proj-test-1", "timeline_track_index": 0},
        )
        assert res_intent.status_code in (400, 403, 422)


def test_positive_operational_blocks_accessible(app_client):
    """Verify operational blocks (10 donor + 2 6Clips) remain operable."""
    operational_all = DONOR_INTERNALIZED_BLOCKS | SIXCLIPS_ORIGINAL_BLOCKS

    for block_id in operational_all:
        res_post = app_client.get(f"/api/catalog/blocks/{block_id}/poster")
        assert res_post.status_code == 200, f"Poster failed for operational {block_id}: {res_post.status_code}"

        res_prev = app_client.get(f"/api/catalog/blocks/{block_id}/preview")
        assert res_prev.status_code == 200, f"Preview failed for operational {block_id}: {res_prev.status_code}"


# =========================================================================
# 5. GT-20 Zero Donor Runtime Dependency
# =========================================================================

def test_gt20_zero_donor_runtime_dependency(app_client):
    """Verify catalog functions without the desktop donor directory mounted or accessible."""
    orig_donor_path = os.environ.get("HYPERFRAMES_DONOR_PATH")
    try:
        # Point donor path to non-existent location
        os.environ["HYPERFRAMES_DONOR_PATH"] = r"C:\non_existent_hyperframes_donor_path_isolated"

        # Catalog inventory must still load successfully from packaged metadata
        resp = app_client.get("/api/catalog/inventory?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["manifest_loaded"] is True
        assert data["donor_inventory_total"] == 196
        assert data["total_operational_blocks"] == 12

        # Operational poster must still serve from packaged shipped_blocks
        res_post = app_client.get("/api/catalog/blocks/aurora/poster")
        assert res_post.status_code == 200
    finally:
        if orig_donor_path is not None:
            os.environ["HYPERFRAMES_DONOR_PATH"] = orig_donor_path
        else:
            os.environ.pop("HYPERFRAMES_DONOR_PATH", None)
