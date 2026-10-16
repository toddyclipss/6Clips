# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for Wave 20 Agent 5: Isolated Database Migration E2E & FFprobe Verification."""

import json
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path
import pytest

from backend.knowledge_migration.detector import LegacyBlockDetector
from backend.knowledge_migration.runner import MigrationRunner, compute_file_sha256

PROD_DB = Path(r"C:\Users\toddy\Desktop\ViralMint\viralmint.db")
TARGET_PROJECTS = [
    "85890621-dfd2-4802-aefa-bf287066644b",  # lower-third-bild
    "2e22f277-b337-4f88-81b4-2d8d4a5991ef",  # weight-wave
    "519ecd11-3825-4777-abd5-50eb48ae1c23",  # bar-chart-race
]


def test_isolated_migration_reopen_and_edit_cas():
    assert PROD_DB.exists()

    temp_dir = Path(tempfile.mkdtemp(prefix="e2e_migration_"))
    test_db = temp_dir / "viralmint.db"
    shutil.copy2(PROD_DB, test_db)

    runner = MigrationRunner()
    res = runner.execute_live_migration(test_db, target_project_ids=TARGET_PROJECTS, create_backup=True)
    assert res["status"] == "SUCCESS"
    assert res["total_migrated"] == 3

    conn = sqlite3.connect(test_db)
    cur = conn.cursor()

    # Verify each project reopens and can be edited with CAS
    for pid in TARGET_PROJECTS:
        row = cur.execute("SELECT revision, document_json FROM projects WHERE id = ?", (pid,)).fetchone()
        assert row is not None
        rev, doc_json = row
        doc = json.loads(doc_json)

        # Assert no legacy blocks
        refs = LegacyBlockDetector.detect_in_project_doc(doc)
        assert len(refs) == 0

        # Simulate editing with CAS: add note to metadata
        doc["metadata"]["user_edit_test"] = "CAS_EDIT_PASSED"
        new_doc_json = json.dumps(doc)
        new_rev = rev + 1

        cur.execute(
            "UPDATE projects SET document_json = ?, revision = ? WHERE id = ? AND revision = ?",
            (new_doc_json, new_rev, pid, rev)
        )
        assert cur.rowcount == 1, "CAS edit failed to update single row!"

    conn.commit()
    conn.close()

    shutil.rmtree(temp_dir, ignore_errors=True)


def test_migrated_mp4_physical_decode():
    proof_mp4 = Path("tools/wave20_a5/proofs/proof_migrated_native_lower_third.mp4")
    assert proof_mp4.exists(), f"MP4 proof not found: {proof_mp4}"

    cmd = ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(proof_mp4)]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    probe_data = json.loads(res.stdout)

    v_stream = next((s for s in probe_data.get("streams", []) if s.get("codec_type") == "video"), None)
    assert v_stream is not None
    assert v_stream["codec_name"] == "h264"
    assert v_stream["width"] == 1920
    assert v_stream["height"] == 1080
    assert float(probe_data["format"]["duration"]) > 0
