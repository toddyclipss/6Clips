# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 12 Stage 3: Master Proposal Hash & 285 Canonical Requirements Audit.

Verifies:
1. Reference proposal SHA-256 integrity: 55fcda09b2654e7b0f57e4fcb317c3a1416864248815cddc2668c7ea53526343.
2. Canonical 285 requirement counts: A22, B28, C30, D25, E32, F24, G18, H18, I15, J25, K23, L25.
3. Absence of unauthorized fabricated VIRALMINT_ROADMAP_CONTINUITY_PLAN.md.
4. Complete Git ancestry verification from Wave 11 baseline to Wave 12 integrated head.
"""

import hashlib
import os
from pathlib import Path
import re
import subprocess
import pytest

EXPECTED_PROPOSAL_SHA256 = "55fcda09b2654e7b0f57e4fcb317c3a1416864248815cddc2668c7ea53526343"
PROPOSAL_SEARCH_PATHS = [
    Path("C:/Users/toddy/Downloads/6CLIPS_WAVE12_FIVE_AGENTS_P0_IDLE_OLLAMA_AND_EXTERNAL_API_FORENSICS_EN/6clips_wave12_prompts/REFERENCE_READ_ONLY_6CLIPS_MASTER_PROPOSAL_2026-10-13.md"),
    Path(__file__).resolve().parent.parent.parent / "REFERENCE_READ_ONLY_6CLIPS_MASTER_PROPOSAL_2026-10-13.md",
]

EXPECTED_BUCKET_COUNTS = {
    "A": 22,
    "B": 28,
    "C": 30,
    "D": 25,
    "E": 32,
    "F": 24,
    "G": 18,
    "H": 18,
    "I": 15,
    "J": 25,
    "K": 23,
    "L": 25,
}
EXPECTED_TOTAL_REQUIREMENTS = 285


def get_proposal_path() -> Path:
    for p in PROPOSAL_SEARCH_PATHS:
        if p.is_file():
            return p
    pytest.skip("Reference proposal markdown file not found in known paths")


def test_master_proposal_sha256_hash():
    """Verify exact SHA-256 hash of the master proposal document."""
    proposal_path = get_proposal_path()
    content = proposal_path.read_bytes()
    actual_hash = hashlib.sha256(content).hexdigest().lower()
    assert actual_hash == EXPECTED_PROPOSAL_SHA256, (
        f"Proposal SHA-256 mismatch!\nExpected: {EXPECTED_PROPOSAL_SHA256}\nActual:   {actual_hash}"
    )


def test_master_requirements_285_canonical_counts():
    """Verify proposal contains exactly 285 individually tracked requirement IDs across 12 buckets."""
    proposal_path = get_proposal_path()
    text = proposal_path.read_text(encoding="utf-8")

    # Match IDs formatted like `### A01:`, `### B15:`, `| J11 |`, etc.
    id_pattern = re.compile(r"\b([A-L])(\d{2})\b")
    found_matches = id_pattern.findall(text)

    # Deduplicate unique IDs
    unique_ids: dict[str, set[str]] = {letter: set() for letter in EXPECTED_BUCKET_COUNTS}
    for letter, num in found_matches:
        unique_ids[letter].add(f"{letter}{num}")

    total_unique = sum(len(ids) for ids in unique_ids.values())
    for letter, expected_count in EXPECTED_BUCKET_COUNTS.items():
        actual_count = len(unique_ids[letter])
        assert actual_count == expected_count, (
            f"Bucket {letter} mismatch: expected {expected_count}, found {actual_count}. "
            f"IDs: {sorted(unique_ids[letter])}"
        )

    assert total_unique == EXPECTED_TOTAL_REQUIREMENTS, (
        f"Total requirement count mismatch: expected {EXPECTED_TOTAL_REQUIREMENTS}, got {total_unique}"
    )


def test_official_roadmap_continuity_plan_absence():
    """Verify that absent official roadmap file has NOT been fabricated in repo root."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    fabricated_file = repo_root / "VIRALMINT_ROADMAP_CONTINUITY_PLAN.md"
    assert not fabricated_file.exists(), (
        "VIRALMINT_ROADMAP_CONTINUITY_PLAN.md must NOT be created or fabricated in repository. "
        "Reference proposal is proposal-only."
    )


def test_git_ancestry_proof():
    """Verify full git ancestry of the Wave 12 integrated head."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    base_w11 = "cc2d7cf113eae15ecdb27a3418e6b44aa1855d7b"
    validator_w11 = "7056e342c19ba2713a2e8177ae0f170db974ab47"
    w12_integrated_head = "98a1b4d5bc71c2f54c932794057c26cc8911e81c"

    def is_ancestor(ancestor_sha: str, descendant_sha: str) -> bool:
        res = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor_sha, descendant_sha],
            cwd=str(repo_root),
            capture_output=True,
        )
        return res.returncode == 0

    assert is_ancestor(base_w11, w12_integrated_head), f"{base_w11} is not an ancestor of {w12_integrated_head}"
    assert is_ancestor(validator_w11, w12_integrated_head), f"{validator_w11} is not an ancestor of {w12_integrated_head}"
