# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 18 Agent 5 Test Suite: Native Editor Commands, CAS Concurrency, 30-Workflow Parity, and 196 Ledger.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
import pytest

from backend.oaas_editor_native.models import (
    NativeCommandRequest,
    NativeCommandType,
    ParityStatus,
)
from backend.oaas_editor_native.registry import NativeCapabilityRegistry
from backend.oaas_editor_native.executor import (
    NativeCommandExecutor,
    CASConcurrencyError,
    CommandExecutionError,
)
from backend.oaas_editor_native.migrator import LegacyProjectMigrator

ROOT_DIR = Path(__file__).resolve().parents[1]


class TestWave18Agent5NativeEditorAndParity:
    """Verifies atomic CAS command execution, capability registry, and migration."""

    def test_01_registry_has_exact_30_legacy_capabilities(self):
        reg = NativeCapabilityRegistry()
        all_caps = reg.list_all()
        assert len(all_caps) == 30, f"Expected 30 legacy capabilities, found {len(all_caps)}"

        tools = reg.get_by_category(is_clip_studio=False)
        clips = reg.get_by_category(is_clip_studio=True)
        assert len(tools) == 21, f"Expected 21 Tools, found {len(tools)}"
        assert len(clips) == 9, f"Expected 9 Clip Studio workflows, found {len(clips)}"

    def test_02_atomic_cas_split_command(self):
        initial_doc = {
            "schema_version": "oaas.motion.v18",
            "revision_number": 1,
            "tracks": [
                {
                    "id": "track_1",
                    "clips": [
                        {"id": "clip_main", "start_time": 0.0, "duration": 10.0, "source_offset": 0.0}
                    ],
                }
            ],
        }

        req = NativeCommandRequest(
            project_id="proj_alpha",
            target_revision_id=1,
            action=NativeCommandType.SPLIT,
            parameters={"clip_id": "clip_main", "split_time": 4.0},
        )

        new_doc, res = NativeCommandExecutor.execute(initial_doc, 1, req)
        assert res.success is True
        assert res.new_revision_id == 2
        assert new_doc["revision_number"] == 2

        clips = new_doc["tracks"][0]["clips"]
        assert len(clips) == 2
        assert clips[0]["id"] == "clip_main"
        assert clips[0]["duration"] == 4.0
        assert clips[1]["start_time"] == 4.0
        assert clips[1]["duration"] == 6.0
        assert clips[1]["source_offset"] == 4.0

    def test_03_atomic_cas_trim_and_slip_commands(self):
        doc = {
            "schema_version": "oaas.motion.v18",
            "revision_number": 2,
            "tracks": [
                {
                    "id": "track_1",
                    "clips": [
                        {"id": "clip_a", "start_time": 0.0, "duration": 8.0, "source_offset": 1.0}
                    ],
                }
            ],
        }

        # Trim
        trim_req = NativeCommandRequest(
            project_id="proj_alpha",
            target_revision_id=2,
            action=NativeCommandType.TRIM,
            parameters={"clip_id": "clip_a", "trim_start": 1.0, "trim_end": 2.0},
        )
        doc_trimmed, res_trim = NativeCommandExecutor.execute(doc, 2, trim_req)
        assert res_trim.success is True
        clip = doc_trimmed["tracks"][0]["clips"][0]
        assert clip["duration"] == 5.0

        # Slip
        slip_req = NativeCommandRequest(
            project_id="proj_alpha",
            target_revision_id=3,
            action=NativeCommandType.SLIP,
            parameters={"clip_id": "clip_a", "offset_delta": 2.5},
        )
        doc_slipped, res_slip = NativeCommandExecutor.execute(doc_trimmed, 3, slip_req)
        assert res_slip.success is True
        assert doc_slipped["tracks"][0]["clips"][0]["source_offset"] == 3.5

    def test_04_atomic_cas_ripple_delete(self):
        doc = {
            "schema_version": "oaas.motion.v18",
            "revision_number": 1,
            "tracks": [
                {
                    "id": "track_1",
                    "clips": [
                        {"id": "c1", "start_time": 0.0, "duration": 3.0},
                        {"id": "c2", "start_time": 3.0, "duration": 4.0},
                        {"id": "c3", "start_time": 7.0, "duration": 5.0},
                    ],
                }
            ],
        }

        # Delete c2 with ripple: c3 should shift left from 7.0 to 3.0
        req = NativeCommandRequest(
            project_id="proj_beta",
            target_revision_id=1,
            action=NativeCommandType.RIPPLE_DELETE,
            parameters={"clip_id": "c2"},
        )
        new_doc, res = NativeCommandExecutor.execute(doc, 1, req)
        assert res.success is True
        clips = new_doc["tracks"][0]["clips"]
        assert len(clips) == 2
        assert clips[0]["id"] == "c1"
        assert clips[1]["id"] == "c3"
        assert clips[1]["start_time"] == 3.0

    def test_05_atomic_cas_concurrency_rejection(self):
        doc = {"revision_number": 5}
        req = NativeCommandRequest(
            project_id="proj_gamma",
            target_revision_id=4,  # Stale revision
            action=NativeCommandType.DELETE_CLIP,
            parameters={"clip_id": "c1"},
        )
        with pytest.raises(CASConcurrencyError, match="CAS Concurrency Rejection"):
            NativeCommandExecutor.execute(doc, 5, req)

    def test_06_crop_and_reframe_aspect_ratio_mutation(self):
        doc = {
            "revision_number": 1,
            "aspect_ratio": "16:9",
            "tracks": [{"id": "t1", "clips": [{"id": "c1"}]}],
        }
        req = NativeCommandRequest(
            project_id="proj_reframe",
            target_revision_id=1,
            action=NativeCommandType.REFRAME,
            parameters={"clip_id": "c1", "aspect_ratio": "9:16"},
        )
        new_doc, res = NativeCommandExecutor.execute(doc, 1, req)
        assert res.success is True
        assert new_doc["aspect_ratio"] == "9:16"
        assert new_doc["tracks"][0]["clips"][0]["reframe"]["aspect_ratio"] == "9:16"

    def test_07_captions_and_silence_settings_mutation(self):
        doc = {"revision_number": 1}
        req_silence = NativeCommandRequest(
            project_id="proj_silence",
            target_revision_id=1,
            action=NativeCommandType.REMOVE_SILENCE,
            parameters={"threshold_db": -28.0, "min_duration": 0.4},
        )
        doc2, res1 = NativeCommandExecutor.execute(doc, 1, req_silence)
        assert res1.success is True
        assert doc2["silence_settings"]["threshold_db"] == -28.0

        req_caps = NativeCommandRequest(
            project_id="proj_silence",
            target_revision_id=2,
            action=NativeCommandType.CAPTIONS_EDIT,
            parameters={"overrides": {"00:01:23": "CorrectedWord"}},
        )
        doc3, res2 = NativeCommandExecutor.execute(doc2, 2, req_caps)
        assert res2.success is True
        assert doc3["caption_overrides"]["00:01:23"] == "CorrectedWord"

    def test_08_legacy_project_migrator_non_destructive(self):
        legacy = {
            "clips": [
                {"id": "legacy_clip_1", "duration": 6.0}
            ],
            "silence_threshold": -32.0,
            "caption_corrections": {"00:02": "Hello"},
        }
        migrated = LegacyProjectMigrator.migrate_legacy_document(legacy)
        assert migrated["schema_version"] == "oaas.motion.v18"
        assert "_legacy_migration_backup" in migrated
        assert migrated["tracks"][0]["clips"][0]["id"] == "legacy_clip_1"
        assert migrated["silence_settings"]["threshold_db"] == -32.0
        assert migrated["caption_overrides"]["00:02"] == "Hello"
        assert "document_sha256" in migrated

    def test_09_evidence_ledger_reconciliation(self):
        ledger_path = ROOT_DIR / "backend" / "catalog_inventory" / "wave18_196_per_id_ledger.json"
        assert ledger_path.exists(), "wave18_196_per_id_ledger.json must exist"
        with open(ledger_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["total_inventoried"] == 196
        assert data["owner_observed_preview_count"] == 10
        assert data["retired_blocks_in_donor_inventory"] == 0
        assert data["trademark_sensitive_count"] == 15

    def test_10_legacy_30_csv_and_196_preview_csv_exist(self):
        csv30 = ROOT_DIR / "docs" / "wave18_native_parity" / "legacy_30_capability_parity.csv"
        csv196 = ROOT_DIR / "docs" / "wave18_native_parity" / "hyperframes_196_preview_truth.csv"
        assert csv30.exists()
        assert csv196.exists()

        with open(csv30, "r", encoding="utf-8") as f:
            rows = list(csv.reader(f))
            assert len(rows) == 31  # 1 header + 30 rows

        with open(csv196, "r", encoding="utf-8") as f:
            rows = list(csv.reader(f))
            assert len(rows) == 197  # 1 header + 196 rows
