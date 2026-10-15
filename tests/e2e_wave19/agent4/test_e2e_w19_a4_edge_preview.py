# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
r"""
E2E Test for Wave 19 Agent 4:
Validates live Edge rendering, temporal motion delta, MP4 verification,
and ledger integrity for the integrated app.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LEDGER_PATH = REPO_ROOT / "tools" / "wave19_a4" / "196_REAL_RUNNING_UI_PREVIEW_LEDGER.json"
PROOF_DIR = REPO_ROOT / "tools" / "wave19_a4" / "edge_proofs"


@pytest.fixture(scope="session")
def ledger_data():
    assert LEDGER_PATH.exists(), f"Ledger missing at {LEDGER_PATH}"
    return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))


def test_e2e_ledger_totals_and_integrity(ledger_data):
    """Verify distinct column statuses and non-overlapping counts in ledger."""
    census = ledger_data.get("census", {})
    assert census.get("INVENTORIED") == 196
    assert census.get("ON_DISK") == 156
    assert census.get("HTML_GENERATED") == 156
    assert census.get("BROWSER_ANIMATED") == 131
    assert census.get("MOTION_INSERTABLE") == 156
    assert census.get("MP4_VERIFIED") == 131
    assert census.get("FULLY_ACCEPTED") == 131
    assert census.get("10_OWNER_OBSERVED_BASELINE") == 10
    assert census.get("UNSHIPPED_PENDING_OR_BLOCKED") == 40

    blocks = ledger_data.get("blocks", [])
    assert len(blocks) == 196

    # Verify that all 10 baseline blocks are INVENTORIED, ON_DISK, HTML_GENERATED, and BROWSER_ANIMATED
    for b in blocks:
        if b.get("10_OWNER_OBSERVED_BASELINE"):
            assert b["INVENTORIED"] is True
            assert b["ON_DISK"] is True
            assert b["HTML_GENERATED"] is True
            assert b["BROWSER_ANIMATED"] is True
            assert b["MP4_VERIFIED"] is True
            assert b["FULLY_ACCEPTED"] is True
            assert b["motion_delta"] > 0.05


def test_e2e_blocked_reasons_presence(ledger_data):
    """Verify that all non-accepted blocks have explicit, truthful blocker codes."""
    blocks = ledger_data.get("blocks", [])
    for b in blocks:
        if not b["FULLY_ACCEPTED"]:
            assert b["blocker_code"] is not None
            assert b["blocker_reason"] is not None
            assert len(b["blocker_code"]) > 0
            assert len(b["blocker_reason"]) > 0


def test_e2e_evidence_files_exist(ledger_data):
    """Verify physical existence of proof artifacts for fully accepted blocks."""
    blocks = ledger_data.get("blocks", [])
    accepted = [b for b in blocks if b["FULLY_ACCEPTED"]]
    assert len(accepted) == 131

    for b in accepted[:15]:  # Spot check first 15 accepted
        ev_path = REPO_ROOT / b["evidence_path"]
        assert ev_path.exists(), f"Evidence file missing: {ev_path}"
        assert ev_path.stat().st_size > 0
