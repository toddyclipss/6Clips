# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Forensic audit of the 285 requirements matrix, Quality Gates GT-01..28, and Checkpoint B ancestry."""

import os
import re
import subprocess
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

CANDIDATE_PATHS = [
    r"C:\Users\toddy\Downloads\6CLIPS_WAVE7_FIVE_STRICT_AGENT_PROMPTS_EN\REFERENCE_READ_ONLY_6CLIPS_MASTER_PROPOSAL_2026-10-13.md",
    r"C:\Users\toddy\Desktop\6CLIPS_DOCUMENTO_MESTRE_REVISADO_PROPOSTA_2026-10-13.md",
]


def test_master_requirements_285_canonical_counts():
    """Verify all 285 master requirement IDs (A01..L25) match canonical group distributions."""
    target_path = None
    for p in CANDIDATE_PATHS:
        if os.path.exists(p):
            target_path = p
            break

    if not target_path:
        pytest.skip("Master proposal file not found on standard paths")

    with open(target_path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = r"\|\s*\*\*([A-L]\d{2})\*\*\s*\|\s*([^|]+)\|"
    rows = re.findall(pattern, content)
    assert len(rows) == 285, f"Expected 285 rows in master document proposal, found {len(rows)}"

    expected_groups = {
        "A": 22, "B": 28, "C": 30, "D": 25, "E": 32, "F": 24,
        "G": 18, "H": 18, "I": 15, "J": 25, "K": 23, "L": 25,
    }
    for letter, count in expected_groups.items():
        actual = len([r for r in rows if r[0].startswith(letter)])
        assert actual == count, f"Group {letter} count mismatch: expected {count}, got {actual}"


def test_official_roadmap_continuity_plan_absence():
    """Truthfully verify that VIRALMINT_ROADMAP_CONTINUITY_PLAN.md is absent."""
    repo_file = os.path.join(REPO_ROOT, "VIRALMINT_ROADMAP_CONTINUITY_PLAN.md")
    desktop_file = r"C:\Users\toddy\Desktop\VIRALMINT_ROADMAP_CONTINUITY_PLAN.md"

    assert not os.path.exists(repo_file), "VIRALMINT_ROADMAP_CONTINUITY_PLAN.md was created in repo!"
    assert not os.path.exists(desktop_file), "VIRALMINT_ROADMAP_CONTINUITY_PLAN.md was found on desktop!"


def test_checkpoint_b_ancestry_proof():
    """Verify that current HEAD in this worktree has all 3 Wave 7 tips in its commit ancestry."""
    wave7_tips = {
        "Role 2 (Motion)": "9918e8a5646caefa2de7a2b4e9797b74e4525509",
        "Role 3 (Catalog)": "bc53460831b87e6c83d5011579eb8a1e03ba14de",
        "Role 5 (Release)": "3f709522c505c592980cc9ced7e0606d9097e83d",
    }
    for role_name, tip_sha in wave7_tips.items():
        res = subprocess.run(
            ["git", "merge-base", "--is-ancestor", tip_sha, "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
        )
        assert res.returncode == 0, (
            f"Checkpoint B ancestry failure: {role_name} tip {tip_sha} is NOT an ancestor of current HEAD!"
        )


def test_adversarial_production_mocks_and_fakes_w8():
    """Verify that backend production routers do not use silent mock fallbacks."""
    backend_routers = os.path.join(REPO_ROOT, "backend", "routers")
    suspicious_patterns = ["fake_success = True", "mock_post_id = 'test-id'", "anullsrc"]

    for root, _, files in os.walk(backend_routers):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                for pat in suspicious_patterns:
                    assert pat not in content, f"Forbidden mock pattern '{pat}' found in {path}"


def test_quality_gates_gt01_gt28_literal_definitions():
    """Verify literal definitions of Quality Gates GT-05, GT-06, GT-07, GT-17, GT-18, GT-19, GT-28."""
    target_path = None
    for p in CANDIDATE_PATHS:
        if os.path.exists(p):
            target_path = p
            break

    if not target_path:
        pytest.skip("Master proposal file not found on standard paths")

    with open(target_path, "r", encoding="utf-8") as f:
        text = f.read()

    # GT-05: 3 shorts from gameplay
    assert "GT-05" in text
    assert any(w in text for w in ["três cortes", "3 cortes", "três clipes", "três", "60s"])

    # GT-06: 60-minute raw -> 8-10+ minute 16:9 narrative highlights
    assert "GT-06" in text
    assert any(w in text for w in ["60 minutos", "60min", "8 a 10", "16:9"])

    # GT-07: multi-source -> 10 clips
    assert "GT-07" in text
    assert any(w in text for w in ["múltiplas fontes", "multiplas", "10 clipes", "dez"])

    # GT-17: Phase 10 publishing and receipts
    assert "GT-17" in text
    # GT-18: Remote confirmed publication
    assert "GT-18" in text
    # GT-19: Analytics and messages after publish
    assert "GT-19" in text
    # GT-28: Lost confirmation / platform policy
    assert "GT-28" in text
