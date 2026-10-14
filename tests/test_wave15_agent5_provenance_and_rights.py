# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 15 Agent 5: Provenance, Rights, Native Categories & Project Migration Suite.

Validates:
1. Authoritative 196-block manifest schema and integrity in hyperframes_196_inventory.json.
2. Strict exclusion of 6Clips-authored blocks (creator-hud, glitch-transition) from donor inventory.
3. Native HyperFrames category taxonomy (171 verified from docs/snippets/catalog-gallery-data.mdx).
4. Explicit flagging of 25 unindexed blocks as SOURCE_CATEGORY_MISSING with labeled proposed fallbacks.
5. 7 independent proof classes tracked per unique ID.
6. Safe non-destructive project migration contracts with rollback and idempotency guarantees.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from backend.catalog_migration.project_migrator import (
    ProjectBlockMigrator,
    MigrationStatus,
    RETIRED_BLOCK_IDS,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "backend" / "catalog_inventory" / "hyperframes_196_inventory.json"
DONOR_PATH = Path(r"C:\Users\toddy\Desktop\hyperframes")


@pytest.fixture(scope="module")
def manifest_data():
    assert MANIFEST_PATH.exists(), f"Authoritative manifest missing at {MANIFEST_PATH}"
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


class TestWave15Agent5ProvenanceAndRights:
    """Authoritative checks for donor 196 provenance, licensing, and category recovery."""

    def test_01_manifest_schema_and_exact_196_donor_count(self, manifest_data):
        assert manifest_data.get("schema_version") == 2
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

        # All missing blocks must have a clearly labeled proposed fallback category
        for b in missing_blocks:
            assert b["taxonomy"]["category_id"] is None
            assert b["taxonomy"]["proposed_fallback_category"] is not None
            assert len(b["taxonomy"]["proposed_fallback_category"]) > 0

    def test_04_seven_independent_proof_classes_per_block(self, manifest_data):
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


class TestWave15Agent5ProjectMigration:
    """Deterministic and non-destructive project migration contracts."""

    def test_05_clean_document_inspection(self):
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

    def test_06_legacy_document_detection_and_migration(self):
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

        migrated_clips = migration.document["timeline"]["tracks"][0]["clips"]
        c1 = next(c for c in migrated_clips if c["id"] == "c1")
        assert c1.get("is_legacy_retired") is True
        assert c1.get("migration_policy") == "PRESERVE_SNAPSHOT"

    def test_07_migration_idempotency_and_rollback(self):
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
        # Migration 1
        mig1 = ProjectBlockMigrator.migrate_document(legacy_doc)
        assert mig1.status == MigrationStatus.MIGRATED_SUCCESS

        # Rollback
        rolled_back = ProjectBlockMigrator.rollback_document(mig1)
        assert rolled_back.status == MigrationStatus.ROLLBACK_SUCCESS
        assert rolled_back.document == legacy_doc

        # Idempotency
        mig2 = ProjectBlockMigrator.migrate_document(mig1.document)
        assert mig2.status == MigrationStatus.VERIFIED_CURRENT
        assert mig2.affected_count == 0
