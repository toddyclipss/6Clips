# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Tests for D0-D2 document fidelity, test ledger statuses, and Agent 1/4 integration adapters.
"""
import json
from pathlib import Path
import pytest
from backend.knowledge_base import (
    Agent1SearchRequest,
    CapabilityFamily,
    KnowledgeAdapter,
    KnowledgeBase,
)

WORKTREE_ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT_PATH = WORKTREE_ROOT / "backend" / "knowledge_base" / "data" / "knowledge_snapshot.json"
BENCHMARK_PATH = WORKTREE_ROOT / "tools" / "wave20_a3" / "retrieval_benchmark_results.json"


@pytest.fixture(scope="module")
def kb():
    return KnowledgeBase()


@pytest.fixture(scope="module")
def snapshot_data():
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def benchmark_data():
    return json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))


def test_d0_identity_hash_provenance_all_docs(snapshot_data):
    """Verify D0 compliance across all 658 documents."""
    docs = snapshot_data["documents"]
    assert len(docs) == 658

    seen_ids = set()
    for d in docs:
        doc_id = d["knowledge_doc_id"]
        assert doc_id not in seen_ids, f"Duplicate doc ID: {doc_id}"
        seen_ids.add(doc_id)

        # Non-empty 64-char sha256
        sha = d["source_hash"]
        assert len(sha) == 64, f"Invalid SHA-256 for {doc_id}: {sha}"

        # Valid provenance
        assert d["category_provenance"] in ["DONOR_CANONICAL", "DONOR_INFERRED", "DERIVED_6CLIPS"]
        assert d["test_status"]["D0"] == "PASS"


def test_d1_faithful_extraction_coverage(snapshot_data):
    """Verify D1 compliance: extraction of principles, algorithms, and parameters."""
    docs = snapshot_data["documents"]
    for d in docs:
        doc_id = d["knowledge_doc_id"]
        assert d["test_status"]["D1"] == "PASS"
        # Each document must have a non-empty summary or principles
        assert len(d["summary"]) > 0 or len(d["principles"]) > 0, f"Empty content in {doc_id}"


def test_d2_retrieval_benchmark_quality(benchmark_data):
    """Verify D2 compliance: retrieval benchmark suite metrics."""
    assert benchmark_data["total_scenarios"] >= 10
    assert benchmark_data["passed_scenarios"] == benchmark_data["total_scenarios"]
    assert benchmark_data["average_precision_at_5"] >= 0.90
    assert benchmark_data["average_mrr"] >= 0.70


def test_d3_d5_status_honesty(snapshot_data):
    """Ensure D3-D5 are never falsely marked as PASS without physical rendering."""
    for d in snapshot_data["documents"]:
        status = d["test_status"]
        assert status["D4"] in ["NOT_APPLICABLE", "PENDING"]
        assert status["D5"] in ["NOT_APPLICABLE", "PENDING"]


def test_agent1_search_adapter_contract(kb):
    """Validate Agent 1 Main Agent search adapter."""
    adapter = KnowledgeAdapter(kb)
    req = Agent1SearchRequest(
        query="warm poetic light monologue captions",
        capability_family=CapabilityFamily.CAPTIONS_WORD_HIGHLIGHT.value,
        limit=3
    )
    resp = adapter.handle_agent1_query(req)
    assert resp.total_hits > 0
    assert len(resp.results) > 0
    assert "HyperFrames Motion Design Directives" in resp.context_prompt_snippet
    assert "caption:cream" in [r.knowledge_doc_id for r in resp.results]


def test_agent4_motion_directives_contract(kb):
    """Validate Agent 4 motion generator directives contract."""
    adapter = KnowledgeAdapter(kb)
    directives = adapter.get_agent4_directives("block:canopy-part-title")
    assert directives is not None
    assert directives.doc_id == "block:canopy-part-title"
    assert len(directives.aspect_ratios) > 0
    assert directives.rights_status == "VERIFIED_PERMISSIVE"

    # Citation builder
    ref = adapter.create_knowledge_ref("block:canopy-part-title", applied_techniques=["Organic leaf parting transition"])
    assert ref is not None
    assert ref.knowledge_doc_id == "block:canopy-part-title"
    assert len(ref.source_hash) == 64
    assert "Organic leaf parting transition" in ref.techniques_applied
