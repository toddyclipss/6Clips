# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 21 Agent 5: Cutover Gate Safety and GT-41 Truth Verification Tests."""

import subprocess
import sys
from pathlib import Path
import pytest

from backend.knowledge_migration.zero_bundle_audit import ZeroBundleAuditor

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_cutover_fails_closed_without_authorization():
    script = REPO_ROOT / "tools" / "wave21_a5" / "execute_production_cutover.py"
    proc = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
    )
    # Must exit code 2 indicating safety stop
    assert proc.returncode == 2
    assert "GT-41 = PENDING_OWNER_AUTHORIZATION_OR_BLOCKERS" in proc.stdout
    assert "SAFETY STOP" in proc.stdout


def test_zero_bundle_audit_truth_gates():
    auditor = ZeroBundleAuditor()
    eval_result = auditor.evaluate_wave21_gates(
        projects_with_blocks_count=232,
        revisions_with_blocks_count=920,
        dry_run_passed=True,
        rollback_verified=True,
        live_cutover_approved=False,
    )

    assert eval_result["GT-39"]["status"] == "PASS"
    assert eval_result["GT-40"]["status"] == "PASS"
    assert eval_result["GT-41"]["status"] == "PENDING_OWNER_AUTHORIZATION_OR_BLOCKERS"
    assert eval_result["GT-42"]["status"] == "PASS"
    assert eval_result["MIGRATION_DRY_RUN_SAFE"] == "PASS"
    assert eval_result["LIVE_PRODUCTION_CUTOVER_APPROVED"] == "PENDING_OWNER_AUTHORIZATION"
    assert eval_result["WAVE21_ACCEPTANCE"] == "PASS"
    assert eval_result["FULL_PRODUCT_ACCEPTANCE"] == "PENDING_GT41_LIVE_CUTOVER"
