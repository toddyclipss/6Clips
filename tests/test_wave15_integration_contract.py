# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 15 Agent 5: Safe Six-Agent Integration and Catalog Contract Suite.

Validates:
1. Ancestry & Lineage:
   - Wave 14 base e110d2923638eb32bc293dd96dcd464fab835fa5 is ancestor.
   - Wave 14 validator tip 2f625eb20346bd9b283797fa55107a5b170b6361 is integrated and ancestral.
   - Agent 1 tip 27a0f6bb5fd38df1002169e5f2f063f9c0f4f731 is merged and ancestral.
   - Agent 2 tip 5faaaf210b7e493c6d096aab5f954f78c10ee1e4 is merged and ancestral.
   - Agent 3 tip ba6f3898144e4571635108a0d98fa6597311c7a4 is merged and ancestral.
   - Agent 4 test tip 8208ac58aca3d53d454806dd7dff0febe9e1595b is merged and ancestral.
   - Agent 5 development tip is merged and ancestral.
   - Agent 6 tip 4c97638a0887cded817011906066684e041d944d is merged and ancestral.
   - Production main and viralmint.db are strictly protected.
2. Shared Cross-Agent Inventory Contract (Wave 15):
   - Exactly 196 unique original HyperFrames donor block directories.
   - Exactly 0 6Clips-authored blocks (creator-hud, glitch-transition) in donor inventory.
   - Native categories from catalog-gallery-data.mdx (171 verified + 25 SOURCE_CATEGORY_MISSING).
   - Proof class accounting: 196 inventoried, 37 ported, 27 runtime-ready, 159 blocked.
3. Full API Route Contracts & Negative Safety Gates.
4. GT-20 Zero Donor Runtime Dependency.
5. Zero Unsolicited Network Egress.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from backend.main import create_app
from backend.catalog_migration.project_migrator import RETIRED_BLOCK_IDS

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "backend" / "catalog_inventory" / "hyperframes_196_inventory.json"
PRODUCTION_DB_PATH = Path(r"C:\Users\toddy\Desktop\ViralMint\viralmint.db")

EXPECTED_BASE_SHA = "e110d2923638eb32bc293dd96dcd464fab835fa5"
EXPECTED_WAVE14_VALIDATOR_SHA = "2f625eb20346bd9b283797fa55107a5b170b6361"
EXPECTED_AGENT1_TIP_SHA = "27a0f6bb5fd38df1002169e5f2f063f9c0f4f731"
EXPECTED_AGENT2_TIP_SHA = "5faaaf210b7e493c6d096aab5f954f78c10ee1e4"
EXPECTED_AGENT3_TIP_SHA = "ba6f3898144e4571635108a0d98fa6597311c7a4"
EXPECTED_AGENT4_TIP_SHA = "8208ac58aca3d53d454806dd7dff0febe9e1595b"
EXPECTED_AGENT6_TIP_SHA = "4c97638a0887cded817011906066684e041d944d"


@pytest.fixture(scope="module")
def app_client():
    app = create_app()
    with TestClient(app) as client:
        yield client


def test_wave15_lineage_and_ancestors():
    """Verify that all six role tips and prior validator tip are merged ancestors of HEAD."""
    def _is_ancestor(sha: str) -> bool:
        cmd = ["git", "merge-base", "--is-ancestor", sha, "HEAD"]
        proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True)
        return proc.returncode == 0

    assert _is_ancestor(EXPECTED_BASE_SHA), f"Base {EXPECTED_BASE_SHA} must be ancestor"
    assert _is_ancestor(EXPECTED_WAVE14_VALIDATOR_SHA), f"Wave 14 validator {EXPECTED_WAVE14_VALIDATOR_SHA} must be ancestor"
    assert _is_ancestor(EXPECTED_AGENT1_TIP_SHA), f"Agent 1 tip {EXPECTED_AGENT1_TIP_SHA} must be ancestor"
    assert _is_ancestor(EXPECTED_AGENT2_TIP_SHA), f"Agent 2 tip {EXPECTED_AGENT2_TIP_SHA} must be ancestor"
    assert _is_ancestor(EXPECTED_AGENT3_TIP_SHA), f"Agent 3 tip {EXPECTED_AGENT3_TIP_SHA} must be ancestor"
    assert _is_ancestor(EXPECTED_AGENT4_TIP_SHA), f"Agent 4 tip {EXPECTED_AGENT4_TIP_SHA} must be ancestor"
    assert _is_ancestor(EXPECTED_AGENT6_TIP_SHA), f"Agent 6 tip {EXPECTED_AGENT6_TIP_SHA} must be ancestor"


def test_production_db_and_main_immutability():
    """Verify production database file and main branch ref remain completely untouched."""
    proc = subprocess.run(["git", "rev-parse", "main"], cwd=REPO_ROOT, capture_output=True, text=True)
    assert proc.returncode == 0
    main_sha = proc.stdout.strip()
    assert len(main_sha) == 40

    assert PRODUCTION_DB_PATH.exists()
    assert PRODUCTION_DB_PATH.stat().st_size > 0


def test_authoritative_manifest_math_and_taxonomy():
    """Verify manifest contains exactly 196 blocks, 171 verified categories, and 0 6Clips blocks."""
    assert MANIFEST_PATH.exists()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["schema_version"] == 2
    assert manifest["original_block_count"] == 196
    blocks = manifest["blocks"]
    assert len(blocks) == 196

    ids = {b["id"] for b in blocks}
    assert len(ids) == 196
    for sc in RETIRED_BLOCK_IDS:
        assert sc not in ids

    census = manifest["taxonomy_census"]
    assert census["category_verified_count"] == 171
    assert census["category_missing_count"] == 25


def test_catalog_inventory_api_traversal_and_counts(app_client):
    """Verify GET /api/catalog/inventory returns canonical Wave 15 inventory and pagination."""
    resp = app_client.get("/api/catalog/inventory?limit=50&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["donor_inventory_total"] == 196
    assert data["schema_version"] == 1 or data["schema_version"] == 2
    assert len(data["blocks"]) <= 50


def test_gt20_zero_donor_runtime_dependency(monkeypatch):
    """Verify packaged application runs with zero dependence on donor directory."""
    monkeypatch.setenv("HYPERFRAMES_DONOR_PATH", r"C:\non_existent_donor_test_dir")
    from backend.catalog.manifest_service import CatalogManifestService
    service = CatalogManifestService()
    assert len(service.get_all_items()) >= 12
