# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for Wave 20 Agent 5: Backup Creation, Restorability & Reversible Rollback."""

import hashlib
import json
import shutil
import sqlite3
import tempfile
from pathlib import Path
import pytest

from backend.knowledge_migration.rollback import RollbackEngine
from backend.knowledge_migration.runner import MigrationRunner, compute_file_sha256

PROD_DB = Path(r"C:\Users\toddy\Desktop\ViralMint\viralmint.db")


def test_backup_and_bit_for_bit_rollback():
    assert PROD_DB.exists(), f"Production DB not found: {PROD_DB}"

    temp_dir = Path(tempfile.mkdtemp(prefix="rollback_test_"))
    test_db = temp_dir / "viralmint.db"
    shutil.copy2(PROD_DB, test_db)

    manifest_path = temp_dir / "rollback_manifest.json"
    rollback_engine = RollbackEngine(manifest_path=manifest_path)
    runner = MigrationRunner(rollback_engine=rollback_engine)

    # Pick 1 project with blocks
    target_id = "85890621-dfd2-4802-aefa-bf287066644b"

    # Read original doc and hash
    conn = sqlite3.connect(test_db)
    cur = conn.cursor()
    orig_rev, orig_doc_json = cur.execute("SELECT revision, document_json FROM projects WHERE id = ?", (target_id,)).fetchone()
    conn.close()
    orig_hash = hashlib.sha256(orig_doc_json.encode("utf-8")).hexdigest()

    # Migrate target project
    res = runner.execute_live_migration(test_db, target_project_ids=[target_id], create_backup=True)
    assert res["status"] == "SUCCESS"
    assert res["backup_path"] is not None
    assert Path(res["backup_path"]).exists()

    # Verify project is migrated
    conn = sqlite3.connect(test_db)
    cur = conn.cursor()
    mig_rev, mig_doc_json = cur.execute("SELECT revision, document_json FROM projects WHERE id = ?", (target_id,)).fetchone()
    assert mig_rev == orig_rev + 1
    mig_doc = json.loads(mig_doc_json)
    from backend.knowledge_migration.detector import LegacyBlockDetector
    assert LegacyBlockDetector.detect_in_project_doc(mig_doc) == []
    assert "native_motion_v1" in mig_doc_json
    conn.close()

    # Rollback project
    ok, msg = rollback_engine.rollback_project_in_db(test_db, target_id)
    assert ok is True

    # Verify bit-for-bit restored original doc
    conn = sqlite3.connect(test_db)
    cur = conn.cursor()
    restored_rev, restored_doc_json = cur.execute("SELECT revision, document_json FROM projects WHERE id = ?", (target_id,)).fetchone()
    conn.close()

    assert restored_rev == mig_rev + 1
    restored_hash = hashlib.sha256(restored_doc_json.encode("utf-8")).hexdigest()
    assert restored_hash == orig_hash, f"Hash mismatch after rollback: {restored_hash} != {orig_hash}"

    shutil.rmtree(temp_dir, ignore_errors=True)
