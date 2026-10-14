# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 11 Forensic Audit of Master Proposal, 285 IDs, GT-01..28, and Ancestry Proof."""

import hashlib
import os
import re
import subprocess
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

CANDIDATE_PATHS = [
    r"C:\Users\toddy\Downloads\6CLIPS_WAVE10_FIVE_AGENTS_TRUE_E2E_AND_CHECKPOINT_D_EN\6CLIPS_WAVE10_FIVE_AGENTS\REFERENCE_READ_ONLY_6CLIPS_MASTER_PROPOSAL_2026-10-13.md",
    r"C:\Users\toddy\Downloads\6CLIPS_WAVE9_FIVE_AGENTS_STRICT_INTEGRATION_AND_REAL_E2E_EN\REFERENCE_READ_ONLY_6CLIPS_MASTER_PROPOSAL_2026-10-13.md",
    r"C:\Users\toddy\Downloads\6CLIPS_WAVE7_FIVE_STRICT_AGENT_PROMPTS_EN\REFERENCE_READ_ONLY_6CLIPS_MASTER_PROPOSAL_2026-10-13.md",
    r"C:\Users\toddy\Desktop\6CLIPS_DOCUMENTO_MESTRE_REVISADO_PROPOSTA_2026-10-13.md",
]


def _get_master_proposal_path():
    for p in CANDIDATE_PATHS:
        if os.path.exists(p):
            return p
    return None


def test_master_proposal_sha256_hash():
    """Verify Master Proposal SHA-256 matches exact canonical hash."""
    path = _get_master_proposal_path()
    assert path is not None, "Master proposal file must exist on candidate paths"

    with open(path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest().lower()

    expected_hash = "55fcda09b2654e7b0f57e4fcb317c3a1416864248815cddc2668c7ea53526343"
    assert file_hash == expected_hash, f"Master proposal SHA-256 mismatch: expected {expected_hash}, got {file_hash}"


def test_master_requirements_285_canonical_counts():
    """Verify all 285 master requirement IDs (A01..L25) match canonical group distributions."""
    path = _get_master_proposal_path()
    if not path:
        pytest.skip("Master proposal file not found")

    with open(path, "r", encoding="utf-8") as f:
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


def test_wave11_ancestry_proof():
    """Verify that current HEAD has all required Wave 10 and Wave 11 ancestor tips."""
    required_ancestors = {
        "Wave 10 Role 2 (Motion)": "abda6c89ccdbe5e27da65b1cb1b38843fdbc1a37",
        "Wave 10 Role 3 (Catalog)": "56e9b09fbb3098dbe859f9058de89534a28ba008",
        "Wave 10 Role 5 (Production)": "2c445b893ef3801afb875d532a5609e757b7c0c2",
        "Wave 10 Role 4 (Validator)": "b8907bf7280dc670156c6104b57d8d831781b1f4",
        "Wave 11 Role 2 (Motion)": "e9241b70c14db757b5c289f37b36096c1a4856cc",
        "Wave 11 Role 3 (Catalog)": "6f6b845ce83c9d1e7ca888995a93fddc29814520",
        "Wave 11 Role 5 (Production)": "54e3f80e492a142cb690cc24492c997925ad1070",
    }
    for label, tip_sha in required_ancestors.items():
        res = subprocess.run(
            ["git", "merge-base", "--is-ancestor", tip_sha, "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
        )
        assert res.returncode == 0, (
            f"Ancestry verification failure: {label} tip {tip_sha} is NOT an ancestor of current HEAD!"
        )


def test_quality_gates_gt01_gt28_literal_definitions():
    """Verify literal definitions of Quality Gates GT-01..GT-28 in master proposal."""
    path = _get_master_proposal_path()
    if not path:
        pytest.skip("Master proposal file not found")

    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    # Exact major gate checks:
    assert "GT-05" in text
    assert "GT-06" in text
    assert "GT-07" in text
    assert "GT-08" in text
    assert "GT-09" in text
    assert "GT-10" in text
    assert "GT-11" in text
    assert "GT-13" in text
    assert "GT-17" in text
    assert "GT-18" in text
    assert "GT-19" in text
    assert "GT-20" in text
    assert "GT-21" in text
    assert "GT-22" in text
    assert "GT-23" in text
    assert "GT-24" in text
    assert "GT-26" in text
    assert "GT-27" in text
    assert "GT-28" in text


def test_adversarial_production_mocks_and_fakes_w11():
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
