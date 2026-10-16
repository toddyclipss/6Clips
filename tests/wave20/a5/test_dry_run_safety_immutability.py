# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for Wave 20 Agent 5: Dry-Run Safety & Zero Database Mutation Invariant."""

import shutil
import sqlite3
import tempfile
from pathlib import Path
import pytest

from backend.knowledge_migration.runner import MigrationRunner, compute_file_sha256

PROD_DB = Path(r"C:\Users\toddy\Desktop\ViralMint\viralmint.db")


def test_dry_run_zero_mutation_guarantee():
    assert PROD_DB.exists(), f"Production DB not found: {PROD_DB}"

    # Use a disposable copy to strictly test the runner's dry-run immutability logic
    temp_dir = Path(tempfile.mkdtemp(prefix="dry_run_test_"))
    test_db = temp_dir / "test_copy.db"
    shutil.copy2(PROD_DB, test_db)

    sha_before = compute_file_sha256(test_db)
    runner = MigrationRunner()
    result = runner.run_dry_run(test_db)
    sha_after = compute_file_sha256(test_db)

    assert result["status"] == "PASS"
    assert result["database_sha256_unmodified"] is True
    assert sha_before == sha_after, "FATAL: Dry-run mutated the database file!"

    shutil.rmtree(temp_dir, ignore_errors=True)


def test_dry_run_on_nonexistent_db_fails_closed():
    runner = MigrationRunner()
    fake_path = Path("non_existent_viralmint_db_12345.db")
    result = runner.run_dry_run(fake_path)
    assert result["status"] == "BLOCKED_USER_DATA_ACCESS"
