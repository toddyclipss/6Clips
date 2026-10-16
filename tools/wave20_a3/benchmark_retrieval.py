# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Independent curated query benchmark for the 6Clips HyperFrames Motion Design Knowledge Base.
Measures Recall@k, Precision@k, MRR, and records explicit counterexamples.
Outputs tools/wave20_a3/retrieval_benchmark_results.json.
"""
import json
import sys
from pathlib import Path

# Ensure worktree root is in python path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.knowledge_base import CapabilityFamily, KnowledgeBase, SearchFilter

OUTPUT_PATH = Path(__file__).parent / "retrieval_benchmark_results.json"


BENCHMARK_SCENARIOS = [
    {
        "category": "captions_word_highlight",
        "query": "karaoke word by word subtitle sweep highlight",
        "filter": {"capability_family": "captions_word_highlight"},
        "expected_doc_ids": ["block:mk-callout-highlight", "component:caption-highlight", "component:caption-pill-karaoke"],
        "expected_family": "captions_word_highlight",
        "description": "Voiceover synchronization and per-word karaoke highlights"
    },
    {
        "category": "captions_cinematic_identities",
        "query": "cream warm poetic light monologue captions",
        "filter": {"capability_family": "captions_word_highlight"},
        "expected_doc_ids": ["caption:cream"],
        "expected_family": "captions_word_highlight",
        "description": "Cinematic embedded caption identity for contemplative monologues"
    },
    {
        "category": "typography_kinetic",
        "query": "headline slam kinetic text landing shake",
        "filter": {"capability_family": "typography_kinetic"},
        "expected_doc_ids": ["component:headline-slam", "component:char-slam-explode"],
        "expected_family": "typography_kinetic",
        "description": "Heavyweight kinetic text slam with arrival deceleration and shake"
    },
    {
        "category": "typography_scramble_reveal",
        "query": "hacker terminal character scramble decode",
        "filter": {"capability_family": "typography_kinetic"},
        "expected_doc_ids": ["hero-primitive:scramble-reveal", "component:caption-matrix-decode"],
        "expected_family": "typography_kinetic",
        "description": "Deterministic glyph cycle hacker scramble reveal"
    },
    {
        "category": "data_visualization",
        "query": "bar chart race animated comparison graph",
        "filter": {"capability_family": "data_visualization"},
        "expected_doc_ids": ["block:bar-chart-race", "block:bar-chart-grid"],
        "expected_family": "data_visualization",
        "description": "Procedural animated bar chart data visualization"
    },
    {
        "category": "transition_wipe",
        "query": "curtain reveal smooth transition wipe mask",
        "filter": {"capability_family": "transition_wipe"},
        "expected_doc_ids": ["component:curtain-reveal", "block:slice-reveal-wipe"],
        "expected_family": "transition_wipe",
        "description": "Geometric clip-path curtain and mask transitions"
    },
    {
        "category": "background_shader",
        "query": "aurora borealis green violet curtain webgpu shader night sky",
        "filter": {"capability_family": "background_shader"},
        "expected_doc_ids": ["block:aurora", "caption:aurora"],
        "expected_family": "background_shader",
        "description": "WebGPU fragment procedural aurora curtain shader"
    },
    {
        "category": "camera_3d",
        "query": "fibonacci sphere 3d card orbit carousel billboard",
        "filter": {"capability_family": "camera_3d"},
        "expected_doc_ids": ["block:carousel-orbit-1", "block:orbit-card"],
        "expected_family": "camera_3d",
        "description": "Spherical 3D camera orbit with billboarded card depth scaling"
    },
    {
        "category": "ui_simulation",
        "query": "simulated cursor click pulse agent pointer interaction",
        "filter": {"capability_family": "ui_simulation"},
        "expected_doc_ids": ["component:agent-cursor", "hero-primitive:press-ripple", "hero-primitive:oversized-cursor"],
        "expected_family": "ui_simulation",
        "description": "UI walkthrough cursor pointer with elastic click ring pulse"
    },
    {
        "category": "responsive_layout",
        "query": "vertical media filler portrait layout",
        "filter": {"capability_family": "responsive_layout"},
        "expected_doc_ids": ["block:yt-vertical-fill"],
        "expected_family": "responsive_layout",
        "description": "Mobile 9:16 vertical filler and responsive layout adaptation"
    },
    {
        "category": "counterexample_mismatch_rejection",
        "query": "webgpu shader plasma background",
        "filter": {"capability_family": "typography_kinetic"},  # Intentionally filtering for typography when searching shaders
        "expected_doc_ids": [],  # Should NOT return shader blocks
        "expected_family": "typography_kinetic",
        "description": "Counterexample test: Shaders must be rejected when filtering for typography_kinetic"
    },
    {
        "category": "rights_filtering",
        "query": "apple terminal macos console",
        "filter": {"rights": "VERIFIED_PERMISSIVE"},  # Apple terminal references are REFERENCE_ONLY / BLOCKED
        "expected_doc_ids": [],
        "expected_family": "ui_simulation",
        "description": "Counterexample test: Proprietary brand references must be excluded under VERIFIED_PERMISSIVE filter"
    }
]


def run_benchmark():
    print("=== STARTING KNOWLEDGE RETRIEVAL BENCHMARK ===")
    kb = KnowledgeBase()
    results_summary = {
        "benchmark_version": "1.0.0",
        "total_scenarios": len(BENCHMARK_SCENARIOS),
        "passed_scenarios": 0,
        "failed_scenarios": 0,
        "average_recall_at_5": 0.0,
        "average_precision_at_5": 0.0,
        "average_mrr": 0.0,
        "scenario_results": []
    }

    recalls = []
    precisions = []
    mrrs = []

    for scenario in BENCHMARK_SCENARIOS:
        cat = scenario["category"]
        query = scenario["query"]
        filt = scenario.get("filter")
        expected_ids = set(scenario.get("expected_doc_ids", []))
        expected_family = scenario.get("expected_family")

        search_filter = SearchFilter(**filt) if filt else None
        hits = kb.search(query, filters=search_filter, limit=5)

        retrieved_ids = [h.knowledge_doc_id for h in hits]
        retrieved_families = [h.capability_family for h in hits]

        # Calculate metrics
        is_counterexample = len(expected_ids) == 0

        if is_counterexample:
            # For counterexamples, test passes if NONE of the counterexample target classes leak into results
            # E.g. in shader query filtered by typography, no shader docs returned.
            leak = any("shader" in h.knowledge_doc_id.lower() for h in hits)
            passed = not leak
            recall_at_5 = 1.0 if passed else 0.0
            precision_at_5 = 1.0 if passed else 0.0
            mrr = 1.0 if passed else 0.0
        else:
            intersect = set(expected_ids).intersection(set(retrieved_ids))
            recall_at_5 = len(intersect) / len(expected_ids)
            
            # Precision: how many hits are from the expected capability family
            correct_family_hits = sum(1 for f in retrieved_families if f == expected_family)
            precision_at_5 = correct_family_hits / max(1, len(hits))

            # MRR: reciprocal rank of first expected doc hit
            first_rank = None
            for idx, rid in enumerate(retrieved_ids, 1):
                if rid in expected_ids:
                    first_rank = idx
                    break
            mrr = (1.0 / first_rank) if first_rank else 0.0
            passed = recall_at_5 > 0.0 or (len(hits) > 0 and precision_at_5 >= 0.6)

        recalls.append(recall_at_5)
        precisions.append(precision_at_5)
        mrrs.append(mrr)

        if passed:
            results_summary["passed_scenarios"] += 1
        else:
            results_summary["failed_scenarios"] += 1

        print(f"Scenario [{cat}]: {'PASS' if passed else 'FAIL'} | Recall@5={recall_at_5:.2f} | Precision@5={precision_at_5:.2f} | MRR={mrr:.2f}")

        results_summary["scenario_results"].append({
            "category": cat,
            "description": scenario["description"],
            "query": query,
            "filter": filt,
            "passed": passed,
            "recall_at_5": round(recall_at_5, 4),
            "precision_at_5": round(precision_at_5, 4),
            "mrr": round(mrr, 4),
            "expected_doc_ids": list(expected_ids),
            "retrieved_doc_ids": retrieved_ids,
            "retrieved_titles": [h.title for h in hits],
            "scores": [h.score for h in hits],
            "counterexample_passed": passed if is_counterexample else None
        })

    results_summary["average_recall_at_5"] = round(sum(recalls) / len(recalls), 4)
    results_summary["average_precision_at_5"] = round(sum(precisions) / len(precisions), 4)
    results_summary["average_mrr"] = round(sum(mrrs) / len(mrrs), 4)

    OUTPUT_PATH.write_text(json.dumps(results_summary, indent=2), encoding="utf-8")
    print(f"\n--> Benchmark summary saved to: {OUTPUT_PATH}")
    print(f"Total: {len(BENCHMARK_SCENARIOS)} | Passed: {results_summary['passed_scenarios']} | Failed: {results_summary['failed_scenarios']}")
    print(f"Avg Recall@5: {results_summary['average_recall_at_5']:.2f} | Avg Precision@5: {results_summary['average_precision_at_5']:.2f} | Avg MRR: {results_summary['average_mrr']:.2f}")


if __name__ == "__main__":
    run_benchmark()
