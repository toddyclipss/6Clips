# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Tests for retrieval benchmark quality, precision/recall metrics, adversarial query coverage,
and prompt injection defense.
"""
import json
from pathlib import Path
import pytest

WORKTREE_ROOT = Path(__file__).resolve().parents[3]
BENCHMARK_PATH = WORKTREE_ROOT / "tools" / "wave21_a3" / "knowledge_retrieval_benchmark.json"


@pytest.fixture(scope="module")
def benchmark_data():
    return json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))


def test_targeted_retrieval_coverage_and_quality(benchmark_data):
    """Verify targeted retrieval covered all 657 legitimate documents with high precision."""
    metrics = benchmark_data["targeted_retrieval_metrics"]

    assert metrics["tested_queries_denominator"] == 657
    assert metrics["direct_id_precision_at_3"] >= 0.85
    assert metrics["semantic_precision_at_1"] >= 0.90
    assert metrics["semantic_precision_at_5"] >= 0.95
    assert metrics["mean_reciprocal_rank"] >= 0.90


def test_adversarial_suite_breadth_and_pass_rate(benchmark_data):
    """Verify adversarial test suite includes >= 60 scenarios with >= 85% pass rate."""
    adv_metrics = benchmark_data["adversarial_suite_metrics"]

    assert adv_metrics["total_adversarial_scenarios"] >= 60
    assert adv_metrics["pass_rate"] >= 0.85

    # Check category distribution
    cats = adv_metrics["breakdown_by_category"]
    assert "captions_vs_typography" in cats
    assert "competing_near_duplicates" in cats
    assert "shader_vs_2d" in cats
    assert "natural_language_paraphrases" in cats
    assert "rights_defense" in cats
    assert "false_brand_similarity" in cats
    assert "injection_defense" in cats


def test_prompt_injection_neutralization(benchmark_data):
    """Verify all malicious prompt injection queries passed safely without execution."""
    injection_scenarios = [
        s for s in benchmark_data["adversarial_scenarios"] if s["category"] == "injection_defense"
    ]
    assert len(injection_scenarios) >= 5
    for sc in injection_scenarios:
        assert sc["passed"] is True, f"Injection scenario {sc['id']} failed: {sc['query']}"


def test_rights_filtering_defense(benchmark_data):
    """Verify rights defense scenarios accurately filter out blocked/unvendored media."""
    rights_scenarios = [
        s for s in benchmark_data["adversarial_scenarios"] if s["category"] == "rights_defense"
    ]
    assert len(rights_scenarios) >= 5
    for sc in rights_scenarios:
        assert sc["passed"] is True, f"Rights defense scenario {sc['id']} failed: {sc['query']}"
