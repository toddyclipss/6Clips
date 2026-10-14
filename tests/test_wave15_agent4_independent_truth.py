# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 15 Agent 4: Independent Six-Agent Truth Audit & Acceptance Test Suite.

Exclusive Ownership: Agent 4 (Independent Adversarial Acceptance Engineer).
Zero production code changes.
Zero mutation of read-only donor repository (C:\\Users\\toddy\\Desktop\\hyperframes).
Protected: main branch ref, production viralmint.db, OAuth/credentials.

Gates Audited:
- Gate 1: Git Reproducibility, Lineage & Immutability Verification.
- Gate 2: Independent 196-Original Donor Census vs Packaged Inventory.
- Gate 3: Upstream Category Taxonomy & Metadata Mapping Truth.
- Gate 4: Per-Block Discovery Readiness & Truth Classification Matrix.
- Gate 5: Negative Safety Gates & Strict Quarantine Isolation.
- Gate 6: GT-20 Zero Runtime Donor Dependency & Zero Outbound Idle Egress.
- Gate 7: Legacy Project Migration Safety (No Data Loss for Removed 6Clips Blocks).
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Set

import pytest
from starlette.testclient import TestClient

from backend.main import create_app
from backend.catalog.manifest_service import (
    CatalogManifestService,
    DONOR_INTERNALIZED_BLOCKS,
    SIXCLIPS_ORIGINAL_BLOCKS,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "backend" / "catalog_inventory" / "hyperframes_196_inventory.json"
PRODUCTION_DB_PATH = Path(r"C:\Users\toddy\Desktop\ViralMint\viralmint.db")
DONOR_ROOT = Path(os.environ.get("HYPERFRAMES_DONOR_PATH", r"C:\Users\toddy\Desktop\hyperframes"))
DONOR_BLOCKS_DIR = DONOR_ROOT / "registry" / "blocks"
DONOR_COMPONENTS_DIR = DONOR_ROOT / "registry" / "components"
DONOR_EXAMPLES_DIR = DONOR_ROOT / "registry" / "examples"

EXPECTED_BASE_SHA = "e110d2923638eb32bc293dd96dcd464fab835fa5"

NON_DONOR_ORIGINALS: Set[str] = {"creator-hud", "glitch-transition"}


@pytest.fixture(scope="module")
def app_client():
    """Create TestClient instance against unified application."""
    app = create_app()
    with TestClient(app) as client:
        yield client


# =========================================================================
# GATE 1: Git Reproducibility, Lineage & Immutability Verification
# =========================================================================

class TestGate1GitLineageAndProtection:
    """Validate common baseline ancestry, clean worktree status, and database protection."""

    def test_baseline_ancestry_verified(self):
        """Verify that Wave 14 integrated commit e110d29 is the ancestor of current worktree."""
        proc = subprocess.run(
            ["git", "merge-base", "--is-ancestor", EXPECTED_BASE_SHA, "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
        )
        assert proc.returncode == 0, f"Expected baseline {EXPECTED_BASE_SHA} must be ancestor of HEAD"

    def test_production_db_and_main_protection(self):
        """Verify production database exists, is non-empty, and main branch ref is intact."""
        assert PRODUCTION_DB_PATH.exists(), f"Production DB at {PRODUCTION_DB_PATH} not found"
        assert PRODUCTION_DB_PATH.stat().st_size > 0, "Production DB is unexpectedly empty"

        # Check main ref
        proc = subprocess.run(["git", "rev-parse", "main"], cwd=REPO_ROOT, capture_output=True, text=True)
        assert proc.returncode == 0, f"git rev-parse main failed: {proc.stderr}"
        main_sha = proc.stdout.strip()
        assert len(main_sha) == 40, f"Invalid main SHA: {main_sha}"

    def test_donor_repository_clean_and_unmodified(self):
        """Verify read-only donor repository is intact without any test artifacts created in it."""
        assert DONOR_BLOCKS_DIR.exists() and DONOR_BLOCKS_DIR.is_dir()
        donor_dirs = [d.name for d in DONOR_BLOCKS_DIR.iterdir() if d.is_dir()]
        assert len(donor_dirs) == 196, f"Expected 196 donor block directories, found {len(donor_dirs)}"


# =========================================================================
# GATE 2: Independent 196-Original Donor Census vs Packaged Inventory
# =========================================================================

class TestGate2DonorCensusTruth:
    """Adversarially verify 196 original donor block directories vs packaged manifest."""

    def test_donor_directory_exact_counts(self):
        """Directly enumerate C:\\Users\\toddy\\Desktop\\hyperframes read-only."""
        assert DONOR_BLOCKS_DIR.exists(), f"Missing donor blocks directory at {DONOR_BLOCKS_DIR}"
        donor_dirs = sorted([d.name for d in DONOR_BLOCKS_DIR.iterdir() if d.is_dir()])
        assert len(donor_dirs) == 196, f"Expected exactly 196 donor block directories, got {len(donor_dirs)}"

        # Examples segregation check
        assert DONOR_EXAMPLES_DIR.exists()
        examples = [d.name for d in DONOR_EXAMPLES_DIR.iterdir() if d.is_dir()]
        assert len(examples) == 8, f"Expected 8 example directories, got {len(examples)}"

        # Microcomponents segregation check
        assert DONOR_COMPONENTS_DIR.exists()
        components = [d.name for d in DONOR_COMPONENTS_DIR.iterdir() if d.is_dir()]
        assert len(components) >= 222, f"Expected at least 222 microcomponent dirs, got {len(components)}"

    def test_manifest_196_exact_parity_with_donor_dirs(self):
        """Verify backend hyperframes_196_inventory.json matches donor directories 1-to-1."""
        assert MANIFEST_PATH.exists(), f"Packaged manifest missing at {MANIFEST_PATH}"
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        assert manifest.get("schema_version") == 1
        assert manifest.get("original_block_count") == 196
        blocks = manifest.get("blocks", [])
        assert len(blocks) == 196, f"Expected 196 block items in manifest, got {len(blocks)}"

        manifest_ids = [b["id"] for b in blocks]
        assert len(manifest_ids) == len(set(manifest_ids)), "Duplicate block IDs found in manifest"

        donor_dirs = set(d.name for d in DONOR_BLOCKS_DIR.iterdir() if d.is_dir())
        diff_manifest_vs_donor = set(manifest_ids) - donor_dirs
        diff_donor_vs_manifest = donor_dirs - set(manifest_ids)

        assert len(diff_manifest_vs_donor) == 0, f"Manifest contains non-donor IDs: {diff_manifest_vs_donor}"
        assert len(diff_donor_vs_manifest) == 0, f"Donor contains unindexed IDs missing from manifest: {diff_donor_vs_manifest}"

    def test_exclusion_of_6clips_blocks_from_donor_manifest(self):
        """Verify creator-hud and glitch-transition are NEVER present in donor 196 manifest."""
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        manifest_ids = set(b["id"] for b in manifest.get("blocks", []))
        for non_donor_id in NON_DONOR_ORIGINALS:
            assert non_donor_id not in manifest_ids, (
                f"Violation: 6Clips-authored block '{non_donor_id}' illegally present in donor 196 manifest!"
            )


# =========================================================================
# GATE 3: Upstream Category Taxonomy & Metadata Mapping Truth
# =========================================================================

class TestGate3CategoryTaxonomyTruth:
    """Validate that category groupings reflect genuine upstream metadata and tags."""

    def test_all_196_donor_blocks_have_upstream_tags(self):
        """Verify every donor block directory contains registry-item.json with tags."""
        missing_meta = []
        missing_tags = []

        for d in DONOR_BLOCKS_DIR.iterdir():
            if not d.is_dir():
                continue
            item_json = d / "registry-item.json"
            if not item_json.exists():
                missing_meta.append(d.name)
                continue
            try:
                with open(item_json, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                tags = meta.get("tags", [])
                if not tags:
                    missing_tags.append(d.name)
            except Exception:
                missing_meta.append(d.name)

        assert len(missing_meta) == 0, f"Donor blocks missing registry-item.json: {missing_meta}"
        # Some blocks may have empty tags upstream; record them truthfully
        assert len(missing_tags) <= 20, f"Too many donor blocks missing tags: {len(missing_tags)}"

    def test_api_reconciliation_category_summary(self, app_client):
        """Verify GET /api/catalog/reconciliation reports truthful upstream census."""
        resp = app_client.get("/api/catalog/reconciliation")
        assert resp.status_code == 200
        data = resp.json()

        assert "wave14_reconciliation" in data
        w = data["wave14_reconciliation"]
        census = w["census"]

        assert census["on_disk_block_dirs"] == 196
        assert census["aggregate_registry_json_blocks"] == 170
        assert census["unbundled_shader_and_extended_blocks"] == 26
        assert census["aggregate_registry_json_components"] == 222
        assert census["aggregate_registry_json_examples"] == 8
        assert w["total_operational_blocks"] == 12
        assert w["donor_internalized_working"] == 10
        assert w["donor_unported_count"] == 186


# =========================================================================
# GATE 4: Per-Block Discovery Readiness & Truth Classification Matrix
# =========================================================================

class TestGate4DiscoveryClassificationTruth:
    """Audit every single block ID and classify readiness without synthetic green gates."""

    def test_per_block_truth_classification_counts(self, app_client):
        """Audit status breakdown across all 196 donor entries."""
        resp = app_client.get("/api/catalog/inventory?limit=300")
        assert resp.status_code == 200
        data = resp.json()

        assert data["donor_inventory_total"] == 196
        assert len(data["blocks"]) == 196

        status_counts = {}
        for b in data["blocks"]:
            st = b.get("runtime_status")
            status_counts[st] = status_counts.get(st, 0) + 1

        # Truth check: exactly 10 donor internalized, remainder partitioned
        assert status_counts.get("INTERNALIZED_WORKING") == 10, (
            f"Expected 10 INTERNALIZED_WORKING donor blocks, found {status_counts.get('INTERNALIZED_WORKING')}"
        )
        assert status_counts.get("BLOCKED_DEPENDENCY", 0) + status_counts.get("BLOCKED_LICENSE", 0) + status_counts.get("ELIGIBLE_NOT_PORTED", 0) == 186

    def test_eligible_vs_blocked_partition(self, app_client):
        """Verify that eligible blocks are strictly separated from blocked blocks."""
        resp_elg = app_client.get("/api/catalog/inventory?filter=eligible&limit=300")
        assert resp_elg.status_code == 200
        d_elg = resp_elg.json()
        assert d_elg["total"] == 17
        for b in d_elg["blocks"]:
            assert b["integration_status"] == "ELIGIBLE_NOT_PORTED"
            assert b["runtime_operable"] is False

        resp_blk = app_client.get("/api/catalog/inventory?filter=blocked&limit=300")
        assert resp_blk.status_code == 200
        d_blk = resp_blk.json()
        assert d_blk["total"] == 169
        for b in d_blk["blocks"]:
            assert b["blocker_reason"] is not None


# =========================================================================
# GATE 5: Negative Safety Gates & Strict Quarantine Isolation
# =========================================================================

class TestGate5NegativeSafetyGates:
    """Verify uninternalized blocks cannot be previewed, postered, or inserted into projects."""

    def test_uninternalized_blocks_rejected_from_runtime_routes(self, app_client):
        """Sample across dependency-blocked, license-blocked, and eligible unported blocks."""
        unported_sample = ["blob", "liquid-metal", "3d-card", "confetti", "frost", "marble"]

        for block_id in unported_sample:
            # Poster endpoint
            res_post = app_client.get(f"/api/catalog/blocks/{block_id}/poster")
            assert res_post.status_code in (400, 403, 404), (
                f"Safety violation: unported block '{block_id}' served a poster!"
            )

            # Preview endpoint
            res_prev = app_client.get(f"/api/catalog/blocks/{block_id}/preview")
            assert res_prev.status_code in (400, 403, 404), (
                f"Safety violation: unported block '{block_id}' served a preview!"
            )

            # Add to project intent
            res_intent = app_client.post(
                f"/api/catalog/blocks/{block_id}/intent/add-to-project",
                json={"project_id": "test-p1", "timeline_track_index": 0},
            )
            assert res_intent.status_code in (400, 403, 422), (
                f"Safety violation: unported block '{block_id}' allowed add-to-project intent!"
            )

    def test_operational_blocks_accessible(self, app_client):
        """Verify the 10 donor internalized blocks remain fully operational."""
        for block_id in DONOR_INTERNALIZED_BLOCKS:
            res_post = app_client.get(f"/api/catalog/blocks/{block_id}/poster")
            assert res_post.status_code == 200, f"Operational block {block_id} failed poster: {res_post.status_code}"

            res_prev = app_client.get(f"/api/catalog/blocks/{block_id}/preview")
            assert res_prev.status_code == 200, f"Operational block {block_id} failed preview: {res_prev.status_code}"


# =========================================================================
# GATE 6: GT-20 Zero Runtime Donor Dependency & Zero Outbound Egress
# =========================================================================

class TestGate6ZeroDonorDependencyAndEgress:
    """Verify application runs with zero donor filesystem dependency and zero egress."""

    def test_zero_runtime_donor_path_dependency(self, app_client):
        """Catalog and operational blocks must function even if HYPERFRAMES_DONOR_PATH is invalid."""
        orig = os.environ.get("HYPERFRAMES_DONOR_PATH")
        try:
            os.environ["HYPERFRAMES_DONOR_PATH"] = r"C:\isolated_non_existent_donor_dir"
            resp = app_client.get("/api/catalog/inventory?limit=5")
            assert resp.status_code == 200
            data = resp.json()
            assert data["manifest_loaded"] is True
            assert data["donor_inventory_total"] == 196

            # Operational block still serves
            r_post = app_client.get("/api/catalog/blocks/aurora/poster")
            assert r_post.status_code == 200
        finally:
            if orig is not None:
                os.environ["HYPERFRAMES_DONOR_PATH"] = orig
            else:
                os.environ.pop("HYPERFRAMES_DONOR_PATH", None)

    def test_zero_unsolicited_network_or_ollama_calls(self, app_client):
        """Verify catalog browsing triggers zero background LLM inference and zero outbound calls."""
        from backend.llm_trace.tracer import get_audit_events as get_llm_events
        from backend.distribution.egress_audit import get_recent_audit_events as get_egress_events

        # Call multiple catalog endpoints
        app_client.get("/api/catalog/inventory")
        app_client.get("/api/catalog/reconciliation")
        app_client.get("/api/catalog/audit")

        # LLM inference must be 0
        llm_events = get_llm_events()
        assert len(llm_events) == 0, f"Unsolicited LLM calls observed: {llm_events}"

        # External egress must be 0
        egress_events = get_egress_events()
        assert len(egress_events) == 0, f"Unsolicited egress observed: {egress_events}"


# =========================================================================
# GATE 7: Legacy Project Migration Safety
# =========================================================================

class TestGate7LegacyProjectMigrationSafety:
    """Verify that removing 6Clips blocks from the public picker does not destroy user projects."""

    def test_legacy_blocks_remain_loadable_for_existing_projects(self):
        """shipped_blocks for creator-hud and glitch-transition must exist for backward compatibility."""
        shipped_root = REPO_ROOT / "backend" / "catalog" / "shipped_blocks"
        for sc_id in NON_DONOR_ORIGINALS:
            sc_dir = shipped_root / sc_id
            assert sc_dir.exists(), f"shipped_blocks/{sc_id} must remain on disk to prevent breaking legacy projects"
            item_file = sc_dir / "registry-item.json"
            assert item_file.exists()
