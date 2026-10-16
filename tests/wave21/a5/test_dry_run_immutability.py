# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 21 Agent 5: Dry-Run Immutability and Safety Tests."""

from pathlib import Path
import pytest

from backend.config import settings
from backend.knowledge_migration.runner import MigrationRunner, compute_file_sha256


def test_dry_run_guarantees_zero_database_mutations():
    raw_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
    prod_db = Path(raw_path).resolve()
    if not prod_db.exists():
        candidate = Path(r"C:\Users\toddy\Desktop\ViralMint\viralmint.db").resolve()
        if candidate.exists():
            prod_db = candidate

    assert prod_db.exists()

    sha_before = compute_file_sha256(prod_db)

    runner = MigrationRunner()
    report = runner.run_dry_run(prod_db)

    sha_after = compute_file_sha256(prod_db)

    assert sha_before == sha_after, "FATAL: Dry run modified database!"
    assert report["status"] == "PASS"
    assert report["database_sha256_unmodified"] is True
    assert report["projects_dependent_on_blocks"] == 232
    assert report["revisions_dependent_on_blocks"] == 920
