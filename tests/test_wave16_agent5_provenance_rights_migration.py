# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 16 Agent 5: Authoritative Provenance, Rights, Native Taxonomy & Project Migration Test Suite.

Validates:
1. Authoritative 196-block manifest schema and integrity in hyperframes_196_inventory.json.
2. Strict exclusion of 6Clips-authored blocks (creator-hud, glitch-transition) from donor inventory.
3. Native HyperFrames category taxonomy (171 verified from docs/snippets/catalog-gallery-data.mdx).
4. Explicit flagging of 25 unindexed blocks as SOURCE_CATEGORY_MISSING with labeled proposed fallbacks.
5. In-depth resolution of 171/25 vs 178/18 Agent 4 tag-heuristic and 170 registry.json counts.
6. Granular rights status for all 159 pending originals with deep audit of 15 trademark-sensitive items.
7. Safe non-destructive project migration contracts with rollback, revision CAS tracking, and export-safe adapter.
8. Machine-readable 196-per-ID ledger ingest engine and validation contracts.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from backend.catalog_migration.project_migrator import (
    ProjectBlockMigrator,
    MigrationStatus,
    RETIRED_BLOCK_IDS,
    EXPORT_SAFE_SUBSTITUTIONS,
    compute_document_cas,
)
from tools.wave16_provenance.reconcile_provenance_and_taxonomy import (
    TRADEMARK_SENSITIVE_ITEMS,
    TWENTY_FIVE_MISSING_FALLBACKS,
)
from tools.wave16_provenance.ledger_ingest import (
    ProvenanceLedgerEngine,
    VALID_STATUSES,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "backend" / "catalog_inventory" / "hyperframes_196_inventory.json"
DISCREPANCY_PATH = REPO_ROOT / "tools" / "wave16_provenance" / "discrepancy_audit_report.json"
RIGHTS_PATH = REPO_ROOT / "tools" / "wave16_provenance" / "rights_and_licensing_audit.json"
DONOR_PATH = Path(r"C:\Users\toddy\Desktop\hyperframes")


@pytest.fixture(scope="module")
def manifest_data():
    assert MANIFEST_PATH.exists(), f"Authoritative manifest missing at {MANIFEST_PATH}"
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def discrepancy_data():
    assert DISCREPANCY_PATH.exists(), f"Discrepancy report missing at {DISCREPANCY_PATH}"
    return json.loads(DISCREPANCY_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rights_data():
    assert RIGHTS_PATH.exists(), f"Rights report missing at {RIGHTS_PATH}"
    return json.loads(RIGHTS_PATH.read_text(encoding="utf-8"))


class TestWave16Agent5ProvenanceAndTaxonomy:
    """Authoritative checks for donor 196 provenance, licensing, and category recovery."""

    def test_01_manifest_schema_and_exact_196_donor_count(self, manifest_data):
        assert manifest_data.get("schema_version") in (1, 2)
        assert manifest_data.get("source_inventory") == "HyperFrames"
        assert manifest_data.get("original_block_count") == 196
        blocks = manifest_data.get("blocks", [])
        assert len(blocks) == 196, f"Expected exactly 196 blocks, got {len(blocks)}"

        ids = [b["id"] for b in blocks]
        assert len(ids) == len(set(ids)), "Duplicate block IDs found in manifest!"

    def test_02_strict_exclusion_of_retired_6clips_blocks(self, manifest_data):
        manifest_ids = {b["id"] for b in manifest_data["blocks"]}
        for retired_id in RETIRED_BLOCK_IDS:
            assert retired_id not in manifest_ids, (
                f"Retired 6Clips block '{retired_id}' illegally present in 196 donor manifest!"
            )
        # Filter check
        test_list = ["aurora", "creator-hud", "plasma", "glitch-transition"]
        filtered = ProjectBlockMigrator.filter_public_donor_catalog(test_list)
        assert filtered == ["aurora", "plasma"]

    def test_03_upstream_native_category_taxonomy_reconciliation(self, manifest_data):
        census = manifest_data.get("taxonomy_census", {})
        assert census.get("total_donor_blocks") == 196
        assert census.get("category_verified_count") == 171
        assert census.get("category_missing_count") == 25

        blocks = manifest_data["blocks"]
        verified_blocks = [b for b in blocks if b["taxonomy"]["category_status"] == "SOURCE_CATEGORY_VERIFIED"]
        missing_blocks = [b for b in blocks if b["taxonomy"]["category_status"] == "SOURCE_CATEGORY_MISSING"]

        assert len(verified_blocks) == 171
        assert len(missing_blocks) == 25

        # All 25 missing blocks must have a clearly labeled proposed fallback category and reasoning
        for b in missing_blocks:
            assert b["taxonomy"]["category_id"] is None
            assert b["taxonomy"]["proposed_fallback_category"] is not None
            assert len(b["taxonomy"]["proposed_fallback_category"]) > 0
            assert b["taxonomy"]["fallback_reasoning"] is not None

    def test_04_taxonomy_discrepancy_explanation(self, discrepancy_data):
        assert discrepancy_data["total_donor_blocks"] == 196
        assert discrepancy_data["indexed_in_catalog_gallery_mdx"] == 171
        assert discrepancy_data["missing_from_catalog_gallery_mdx"] == 25
        assert discrepancy_data["indexed_in_registry_json"] == 170
        assert discrepancy_data["unindexed_in_registry_json"] == 26
        assert discrepancy_data["agent4_tag_heuristic_matched"] == 178
        assert discrepancy_data["agent4_tag_heuristic_missing"] == 18
        assert "week-in-merges" in discrepancy_data["discrepancy_root_cause"]
        assert len(discrepancy_data["unindexed_blocks_25"]) == 25

    def test_05_granular_rights_and_trademark_audit(self, rights_data, manifest_data):
        assert rights_data["source_code_spdx"] == "Apache-2.0"
        assert rights_data["trademark_sensitive_count"] == 15
        assert len(rights_data["trademark_sensitive_blocks"]) == 15

        tm_ids = {b["id"] for b in rights_data["trademark_sensitive_blocks"]}
        assert tm_ids == set(TRADEMARK_SENSITIVE_ITEMS.keys())

        # Verify trademark vs license distinction
        for b in rights_data["trademark_sensitive_blocks"]:
            rights_info = b["rights_and_licensing"]
            assert rights_info["source_code_spdx"] == "Apache-2.0"
            assert rights_info["brand_trademark_status"] == "TRADEMARK_SENSITIVE"
            assert "actionable_clearance_path" in rights_info
            assert len(rights_info["actionable_clearance_path"]) > 0

    def test_06_seven_independent_proof_classes_per_block(self, manifest_data):
        proof_summary = manifest_data.get("proof_class_summary", {})
        assert proof_summary.get("source_inventoried") == 196
        assert proof_summary.get("source_ported") == 37
        assert proof_summary.get("runtime_ready") == 27
        assert proof_summary.get("browser_preview_verified") == 37
        assert proof_summary.get("motion_edit_verified") == 0
        assert proof_summary.get("render_artifact_verified") == 37
        assert proof_summary.get("rights_cleared") == 37
        assert proof_summary.get("blocked_unported") == 159

        # Ensure every block has all 7 boolean proof classes
        for b in manifest_data["blocks"]:
            assert "source_inventoried" in b and b["source_inventoried"] is True
            assert "source_ported" in b and isinstance(b["source_ported"], bool)
            assert "runtime_ready" in b and isinstance(b["runtime_ready"], bool)
            assert "browser_preview_verified" in b and isinstance(b["browser_preview_verified"], bool)
            assert "motion_edit_verified" in b and isinstance(b["motion_edit_verified"], bool)
            assert "render_artifact_verified" in b and isinstance(b["render_artifact_verified"], bool)
            assert "rights_cleared" in b and isinstance(b["rights_cleared"], bool)


class TestWave16Agent5ProjectMigration:
    """Deterministic and non-destructive project migration contracts."""

    def test_07_clean_document_inspection(self):
        clean_doc = {
            "id": "proj_clean_1",
            "timeline": {
                "tracks": [
                    {
                        "id": "track_1",
                        "clips": [
                            {"id": "clip_1", "block_id": "aurora", "title": "Aurora"},
                            {"id": "clip_2", "block_id": "data-chart", "title": "Data Chart"},
                        ],
                    }
                ]
            },
        }
        res = ProjectBlockMigrator.inspect_document(clean_doc)
        assert res["status"] == MigrationStatus.VERIFIED_CURRENT.value
        assert res["has_retired_blocks"] is False
        assert len(res["retired_blocks_found"]) == 0

    def test_08_legacy_document_detection_and_non_destructive_migration(self):
        legacy_doc = {
            "id": "proj_legacy_1",
            "timeline": {
                "tracks": [
                    {
                        "id": "track_video",
                        "clips": [
                            {"id": "c1", "block_id": "creator-hud", "title": "Old Creator HUD"},
                            {"id": "c2", "block_id": "aurora", "title": "Aurora"},
                            {"id": "c3", "block_id": "glitch-transition", "title": "Old Glitch"},
                        ],
                    }
                ]
            },
        }
        inspection = ProjectBlockMigrator.inspect_document(legacy_doc)
        assert inspection["status"] == MigrationStatus.REQUIRES_MIGRATION.value
        assert inspection["has_retired_blocks"] is True
        assert set(inspection["retired_blocks_found"]) == {"creator-hud", "glitch-transition"}
        assert len(inspection["affected_clips"]) == 2

        # Non-destructive migration
        migration = ProjectBlockMigrator.migrate_document(legacy_doc, substitute_donor_counterparts=False)
        assert migration.status == MigrationStatus.MIGRATED_SUCCESS
        assert migration.affected_count == 2
        assert migration.rollback_snapshot is not None
        assert migration.cas_hash is not None

        migrated_clips = migration.document["timeline"]["tracks"][0]["clips"]
        c1 = next(c for c in migrated_clips if c["id"] == "c1")
        assert c1.get("is_legacy_retired") is True
        assert c1.get("migration_policy") == "PRESERVE_SNAPSHOT"

    def test_09_export_safe_document_adapter(self):
        legacy_doc = {
            "id": "proj_export_legacy",
            "timeline": {
                "tracks": [
                    {
                        "id": "t1",
                        "clips": [
                            {"id": "c1", "block_id": "creator-hud", "duration": 5.0, "params": {"speed": 1}},
                            {"id": "c2", "block_id": "glitch-transition", "duration": 1.0},
                            {"id": "c3", "block_id": "plasma", "duration": 3.0},
                        ],
                    }
                ]
            },
        }
        export_doc = ProjectBlockMigrator.prepare_export_safe_document(legacy_doc)
        assert export_doc["metadata"]["export_safe_adapted"] is True

        # Ensure original doc is unchanged
        assert legacy_doc["timeline"]["tracks"][0]["clips"][0]["block_id"] == "creator-hud"

        # Check export-safe doc has adapted clips
        clips = export_doc["timeline"]["tracks"][0]["clips"]
        assert clips[0]["block_id"] == EXPORT_SAFE_SUBSTITUTIONS["creator-hud"]
        assert clips[0]["_export_adapter"]["original_block_id"] == "creator-hud"
        assert clips[0]["duration"] == 5.0
        assert clips[0]["params"] == {"speed": 1}

        assert clips[1]["block_id"] == EXPORT_SAFE_SUBSTITUTIONS["glitch-transition"]
        assert clips[1]["_export_adapter"]["original_block_id"] == "glitch-transition"

        assert clips[2]["block_id"] == "plasma"
        assert "_export_adapter" not in clips[2]

    def test_10_migration_idempotency_and_rollback(self):
        legacy_doc = {
            "id": "proj_rollback_test",
            "timeline": {
                "tracks": [
                    {
                        "id": "t1",
                        "clips": [
                            {"id": "c1", "block_id": "creator-hud", "title": "Creator HUD"},
                        ],
                    }
                ]
            },
        }
        orig_cas = compute_document_cas(legacy_doc)

        # Migration 1
        mig1 = ProjectBlockMigrator.migrate_document(legacy_doc)
        assert mig1.status == MigrationStatus.MIGRATED_SUCCESS

        # Rollback
        rolled_back = ProjectBlockMigrator.rollback_document(mig1)
        assert rolled_back.status == MigrationStatus.ROLLBACK_SUCCESS
        assert rolled_back.document == legacy_doc
        assert rolled_back.cas_hash == orig_cas

        # Idempotency
        mig2 = ProjectBlockMigrator.migrate_document(mig1.document)
        assert mig2.status == MigrationStatus.VERIFIED_CURRENT
        assert mig2.affected_count == 0

    def test_11_project_revision_preservation(self):
        revision_record = {
            "revision_id": "rev_001_abc",
            "version_counter": 1,
            "document": {
                "id": "proj_rev_test",
                "timeline": {
                    "tracks": [
                        {
                            "id": "t1",
                            "clips": [
                                {"id": "c1", "block_id": "creator-hud"},
                            ],
                        }
                    ]
                },
            },
        }
        migrated_rev = ProjectBlockMigrator.migrate_project_revision(revision_record)
        assert migrated_rev["version_counter"] == 2
        assert migrated_rev["previous_revision_id"] == "rev_001_abc"
        assert migrated_rev["cas_hash"] is not None
        assert len(migrated_rev["revision_history"]) == 1
        assert migrated_rev["revision_history"][0]["action"] == "WAVE16_NON_DESTRUCTIVE_MIGRATION"


class TestWave16Agent5LedgerIngest:
    """Verification of the machine-readable 196-per-ID ledger engine."""

    def test_12_ledger_ingest_generation(self):
        engine = ProvenanceLedgerEngine()
        summary = engine.ingest_all_evidence()
        assert summary["total_inventoried_donor_blocks"] == 196
        assert len(summary["records"]) == 196
        assert summary["retired_6clips_blocks_count"] == 0

        # Check all statuses are valid
        for rec in summary["records"]:
            assert rec["status"] in VALID_STATUSES
            assert "proof_preview" in rec
            assert "proof_inserted" in rec
            assert "proof_export" in rec
            assert "proof_full_e2e" in rec
            assert "taxonomy" in rec
            assert "rights" in rec
