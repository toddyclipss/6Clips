# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 21 Agent 5: Simulated Failure and Rollback Rehearsal Tests."""

from pathlib import Path
import pytest

from backend.config import settings
from backend.knowledge_migration.runner import MigrationRunner, compute_file_sha256


def test_simulated_failure_rollback_canaries(tmp_path):
    raw_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
    prod_db = Path(raw_path).resolve()
    if not prod_db.exists():
        candidate = Path(r"C:\Users\toddy\Desktop\ViralMint\viralmint.db").resolve()
        if candidate.exists():
            prod_db = candidate

    assert prod_db.exists()
    prod_sha_before = compute_file_sha256(prod_db)

    runner = MigrationRunner()
    report = runner.run_rollback_rehearsal(
        source_db_path=prod_db,
        scratch_dir=tmp_path,
    )

    # Source DB must remain strictly unmodified
    prod_sha_after = compute_file_sha256(prod_db)
    assert prod_sha_before == prod_sha_after

    assert report["status"] == "PASS"
    assert report["all_canaries_passed"] is True

    reh = report["rehearsals"]
    assert reh["failure_at_25_percent"]["bit_for_bit_identical"] is True
    assert reh["failure_at_25_percent"]["status"] == "PASS"

    assert reh["failure_at_75_percent"]["bit_for_bit_identical"] is True
    assert reh["failure_at_75_percent"]["status"] == "PASS"
