# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 21 Agent 5: Isolated Database Migration E2E Test."""

from pathlib import Path
import pytest

from backend.config import settings
from backend.knowledge_migration.runner import MigrationRunner, compute_file_sha256


def test_isolated_clone_migration_full_batch(tmp_path):
    raw_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
    prod_db = Path(raw_path).resolve()
    if not prod_db.exists():
        candidate = Path(r"C:\Users\toddy\Desktop\ViralMint\viralmint.db").resolve()
        if candidate.exists():
            prod_db = candidate

    assert prod_db.exists()
    prod_sha_before = compute_file_sha256(prod_db)

    clone_db = tmp_path / "isolated_full_migration.db"

    runner = MigrationRunner()
    result = runner.execute_isolated_clone_migration(
        source_db_path=prod_db,
        isolated_db_path=clone_db,
    )

    # Source DB must remain strictly unmodified
    prod_sha_after = compute_file_sha256(prod_db)
    assert prod_sha_before == prod_sha_after

    # Clone DB migration success
    assert result["status"] == "SUCCESS"
    assert result["source_db_unmodified"] is True
    assert result["migrated_projects_count"] == 232
    assert result["migrated_revisions_count"] == 920
    assert result["residual_project_blocks"] == 0
    assert result["residual_revision_blocks"] == 0
    assert result["clean_zero_legacy_blocks"] is True
