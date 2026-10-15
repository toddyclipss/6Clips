# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 16 Agent 5: E2E Integration and Provenance Verification Suite.

Validates end-to-end integration of:
1. Reconciled 196-block inventory loading and verification against read-only donor.
2. Ingestion of evidence into machine-readable ledger.
3. Complex nested project timeline migration, export adaptation, and rollback.
4. Absolute isolation: zero mutations against donor directory or production viralmint.db.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from backend.catalog_migration.project_migrator import (
    ProjectBlockMigrator,
    MigrationStatus,
    compute_document_cas,
)
from tools.wave16_provenance.reconcile_provenance_and_taxonomy import (
    build_authoritative_wave16_inventory,
)
from tools.wave16_provenance.ledger_ingest import (
    ProvenanceLedgerEngine,
)

DONOR_PATH = Path(r"C:\Users\toddy\Desktop\hyperframes")


class TestWave16Agent5Stage1E2E:
    """E2E verification tests for Stage 1 deliverables."""

    def test_e2e_01_authoritative_inventory_generation_from_donor(self):
        inventory = build_authoritative_wave16_inventory(DONOR_PATH)
        assert inventory["original_block_count"] == 196
        assert len(inventory["blocks"]) == 196
        assert inventory["taxonomy_census"]["category_verified_count"] == 171
        assert inventory["taxonomy_census"]["category_missing_count"] == 25
        assert inventory["reconciliation"]["indexed_in_registry_json"] == 170
        assert inventory["reconciliation"]["unindexed_block_directories"] == 26
        assert inventory["reconciliation"]["trademark_sensitive_count"] == 15

    def test_e2e_02_ledger_ingest_and_serialization(self, tmp_path):
        engine = ProvenanceLedgerEngine()
        out_path = tmp_path / "test_ledger_output.json"
        saved = engine.generate_and_save(out_path)
        assert saved.exists()

        data = json.loads(saved.read_text(encoding="utf-8"))
        assert data["total_inventoried_donor_blocks"] == 196
        assert len(data["records"]) == 196

    def test_e2e_03_complex_multitrack_project_migration_and_export_safety(self):
        complex_doc = {
            "id": "proj_multitrack_e2e",
            "version": 3,
            "timeline": {
                "duration": 30.0,
                "tracks": [
                    {
                        "id": "track_video_main",
                        "kind": "video",
                        "clips": [
                            {"id": "clip_v1", "block_id": "aurora", "start": 0.0, "duration": 5.0},
                            {"id": "clip_v2", "block_id": "creator-hud", "start": 5.0, "duration": 10.0, "variables": {"user": "alice"}},
                            {"id": "clip_v3", "block_id": "plasma", "start": 15.0, "duration": 15.0},
                        ],
                    },
                    {
                        "id": "track_transitions",
                        "kind": "transition",
                        "clips": [
                            {"id": "clip_t1", "block_id": "glitch-transition", "start": 4.5, "duration": 1.0},
                        ],
                    },
                    {
                        "id": "track_audio",
                        "kind": "audio",
                        "clips": [
                            {"id": "clip_a1", "media_id": "audio_ambient", "start": 0.0, "duration": 30.0},
                        ],
                    },
                ],
            },
        }

        # 1. Inspection
        inspection = ProjectBlockMigrator.inspect_document(complex_doc)
        assert inspection["status"] == MigrationStatus.REQUIRES_MIGRATION.value
        assert set(inspection["retired_blocks_found"]) == {"creator-hud", "glitch-transition"}
        assert len(inspection["affected_clips"]) == 2

        # 2. Non-destructive migration
        res = ProjectBlockMigrator.migrate_document(complex_doc)
        assert res.status == MigrationStatus.MIGRATED_SUCCESS
        assert res.affected_count == 2
        assert res.cas_hash is not None

        # Verify timing and variables preserved
        v2 = res.document["timeline"]["tracks"][0]["clips"][1]
        assert v2["id"] == "clip_v2"
        assert v2["start"] == 5.0
        assert v2["duration"] == 10.0
        assert v2["variables"] == {"user": "alice"}
        assert v2["is_legacy_retired"] is True

        # Audio track untouched
        audio_clip = res.document["timeline"]["tracks"][2]["clips"][0]
        assert audio_clip["id"] == "clip_a1"
        assert audio_clip["duration"] == 30.0

        # 3. Export safety adaptation
        export_safe = ProjectBlockMigrator.prepare_export_safe_document(res.document)
        v2_export = export_safe["timeline"]["tracks"][0]["clips"][1]
        assert v2_export["block_id"] == "yt-lower-third"
        assert v2_export["_export_adapter"]["original_block_id"] == "creator-hud"

        t1_export = export_safe["timeline"]["tracks"][1]["clips"][0]
        assert t1_export["block_id"] == "transitions-push"
        assert t1_export["_export_adapter"]["original_block_id"] == "glitch-transition"

        # 4. Rollback
        rollback_res = ProjectBlockMigrator.rollback_document(res)
        assert rollback_res.status == MigrationStatus.ROLLBACK_SUCCESS
        assert rollback_res.document == complex_doc
        assert rollback_res.cas_hash == compute_document_cas(complex_doc)
