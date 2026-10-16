# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Tests for per-document acceptance ledger integrity, D0-D5 statuses, rights honesty,
and exact reconciliation across all 658 records.
"""
import csv
import json
from pathlib import Path
import pytest

WORKTREE_ROOT = Path(__file__).resolve().parents[3]
LEDGER_JSON_PATH = WORKTREE_ROOT / "tools" / "wave21_a3" / "knowledge_document_acceptance.json"
LEDGER_CSV_PATH = WORKTREE_ROOT / "tools" / "wave21_a3" / "knowledge_document_acceptance.csv"


@pytest.fixture(scope="module")
def ledger_json():
    return json.loads(LEDGER_JSON_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ledger_csv():
    with open(LEDGER_CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def test_ledger_file_parity_and_count(ledger_json, ledger_csv):
    """Verify CSV and JSON ledgers contain identical 658 records."""
    assert len(ledger_json["documents"]) == 658
    assert len(ledger_csv) == 658

    json_ids = [d["doc_id"] for d in ledger_json["documents"]]
    csv_ids = [r["doc_id"] for r in ledger_csv]
    assert json_ids == csv_ids


def test_d0_identity_hash_all_docs(ledger_json):
    """Verify D0 compliance for all 658 documents: 64-char sha256 and valid path."""
    for d in ledger_json["documents"]:
        doc_id = d["doc_id"]
        assert len(d["source_hash"]) == 64, f"Invalid SHA-256 for {doc_id}"
        assert len(d["source_path"]) > 0, f"Empty source path for {doc_id}"
        assert d["D0"] == "PASS", f"D0 must be PASS for {doc_id}"


def test_d1_parse_fidelity_and_syntax_artifact_honesty(ledger_json):
    """Verify D1 faithful extraction and honest handling of syntax artifact."""
    for d in ledger_json["documents"]:
        doc_id = d["doc_id"]
        if doc_id == "caption:-------------":
            # Must be marked FAIL for parse fidelity
            assert d["D1"] == "FAIL"
            assert d["blocker_code"] == "SYNTAX_TABLE_SEPARATOR_ARTIFACT"
            assert d["rights"] == "BLOCKED_RIGHTS"
        else:
            assert d["D1"] == "PASS", f"D1 must be PASS for legitimate doc {doc_id}"


def test_rights_reassessment_defense(ledger_json):
    """Verify rights reassessment eliminates inaccurate blanket permissive flags."""
    rights_breakdown = ledger_json["breakdown_by_rights"]
    assert "VERIFIED_PERMISSIVE" in rights_breakdown
    assert "REFERENCE_ONLY" in rights_breakdown
    assert "BLOCKED_RIGHTS" in rights_breakdown

    # Ensure brand-referencing documents are never marked VERIFIED_PERMISSIVE
    brand_docs = [
        "block:apple-money-count",
        "block:instagram-follow",
        "block:slack-notification-ad",
        "block:tiktok-follow",
        "block:x-post",
        "block:yt-lower-third",
        "block:vpn-youtube-spot",
    ]
    doc_map = {d["doc_id"]: d for d in ledger_json["documents"]}
    for bd in brand_docs:
        if bd in doc_map:
            assert doc_map[bd]["rights"] in ("REFERENCE_ONLY", "BLOCKED_RIGHTS"), f"{bd} must not be VERIFIED_PERMISSIVE"
            assert len(doc_map[bd]["rights_reason"]) > 0


def test_d4_applicability_and_rationales(ledger_json):
    """Verify D4 applicability: conceptual docs are NOT_APPLICABLE with rationale; actionable docs are PASS or BLOCKED."""
    for d in ledger_json["documents"]:
        doc_id = d["doc_id"]
        applicable = d["applicable_D4"]
        status = d["D4"]

        if not applicable:
            assert status == "NOT_APPLICABLE", f"Non-applicable doc {doc_id} must have D4=NOT_APPLICABLE"
            assert len(d["d4_rationale"]) > 0, f"Non-applicable doc {doc_id} must have a rationale"
        else:
            assert status in ("PASS", "BLOCKED"), f"Applicable doc {doc_id} must have D4=PASS or BLOCKED"
            if status == "PASS":
                assert d["applied_spec_id"] is not None and len(d["applied_spec_id"]) > 0
            elif status == "BLOCKED":
                assert len(d["blocker_code"]) > 0, f"Blocked doc {doc_id} must specify blocker_code"


def test_d5_applicability_and_render_proofs(ledger_json):
    """Verify D5 physical rendering status and representative proofs."""
    doc_map = {d["doc_id"]: d for d in ledger_json["documents"]}

    # Check representative physical renders
    rep_ids = [
        "component:headline-slam",
        "hero-primitive:per-word-rise",
        "caption:cream",
        "caption:anchor",
        "hero-primitive:oversized-cursor",
        "hero-primitive:press-ripple",
        "block:bar-chart-race",
        "hero-primitive:chart-story",
        "component:curtain-reveal",
        "block:cross-warp-morph",
    ]
    for rid in rep_ids:
        doc = doc_map[rid]
        assert doc["D5"] == "PASS", f"{rid} must have D5=PASS"
        assert doc["evidence_path"].endswith(".mp4"), f"{rid} must link physical MP4 evidence"
        evidence_file = WORKTREE_ROOT / doc["evidence_path"]
        assert evidence_file.exists(), f"Evidence file {evidence_file} must exist on disk"


def test_exact_reconciliation_summary(ledger_json):
    """Verify zero overlap and exact reconciliation: total == usable + reference + blocked."""
    summary = ledger_json["reconciliation_summary"]
    total = summary["total_documents"]
    usable = summary["fully_usable_native_motion_d4_pass"]
    reference = summary["limited_reference_conceptual_d4_na"]
    blocked = summary["blocked_pending_dependencies_d4_blocked"]

    assert total == 658
    assert usable == 405
    assert reference == 165
    assert blocked == 88
    assert usable + reference + blocked == total
    assert summary["exact_sum_matches_total"] is True
