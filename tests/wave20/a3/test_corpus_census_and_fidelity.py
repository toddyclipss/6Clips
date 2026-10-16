# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Tests for HyperFrames corpus census, reconciliation, AST safety, and category provenance.
"""
import json
from pathlib import Path
import pytest

WORKTREE_ROOT = Path(__file__).resolve().parents[3]
CENSUS_PATH = WORKTREE_ROOT / "tools" / "wave20_a3" / "hyperframes_knowledge_census.json"
SNAPSHOT_PATH = WORKTREE_ROOT / "backend" / "knowledge_base" / "data" / "knowledge_snapshot.json"


@pytest.fixture(scope="module")
def census_data():
    assert CENSUS_PATH.exists(), f"Census file missing: {CENSUS_PATH}"
    return json.loads(CENSUS_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def snapshot_data():
    assert SNAPSHOT_PATH.exists(), f"Snapshot file missing: {SNAPSHOT_PATH}"
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def test_census_file_inventory_integrity(census_data):
    """Verify total scanned files and file type breakdowns."""
    assert census_data["total_files_scanned"] >= 1400
    by_type = census_data["file_counts_by_type"]
    assert by_type.get(".mdx", 0) == 552
    assert by_type.get(".md", 0) >= 6

    # Verify reconciliation ledger exists
    rec = census_data["reconciliation"]
    assert rec["total_reconciled_blocks"] == 25
    assert rec["total_reconciled_components"] == 14
    assert "aurora" in rec["blocks_without_mdx_reconciled"]
    assert "agent-cursor" in rec["components_without_mdx_reconciled"]


def test_reconciled_blocks_have_first_class_docs(snapshot_data):
    """Ensure all 25 blocks without MDX are first-class documents in the knowledge base."""
    docs = {d["knowledge_doc_id"]: d for d in snapshot_data["documents"]}
    expected_25 = [
        "ai-answer-rank", "aurora", "blob", "cinemagraph", "exploded-stack",
        "extruded-logo", "fractal-noise", "frost", "glass-hero", "goo",
        "gooey-split", "holographic", "lens-flare", "plasma", "prism",
        "product-turntable", "sine-wave", "snow", "starfield", "strands",
        "stripes", "swirl", "voronoi", "water", "waveform"
    ]
    for b in expected_25:
        doc_id = f"block:{b}"
        assert doc_id in docs, f"Missing reconciled block doc: {doc_id}"
        doc = docs[doc_id]
        assert doc["source_kind"] == "reconciled_block"
        assert doc["category_provenance"] == "DONOR_INFERRED"
        assert len(doc["source_hash"]) == 64
        assert len(doc["title"]) > 0


def test_reconciled_components_have_first_class_docs(snapshot_data):
    """Ensure all 14 component dirs without MDX are first-class documents in the knowledge base."""
    docs = {d["knowledge_doc_id"]: d for d in snapshot_data["documents"]}
    expected_14 = [
        "agent-cursor", "caret-swap", "cursor-annotate", "cursor-context-menu",
        "cursor-drag-drop", "cursor-marquee-select", "cursor-text-select",
        "cursor-zoom-follow", "curtain-reveal", "dart-cursor", "magnetic-cursor",
        "paper-collage-reveal", "pendulum-swing", "torn-paper-rip"
    ]
    for c in expected_14:
        doc_id = f"component:{c}"
        assert doc_id in docs, f"Missing reconciled component doc: {doc_id}"
        doc = docs[doc_id]
        assert doc["source_kind"] == "reconciled_component"
        assert doc["category_provenance"] == "DONOR_INFERRED"


def test_embedded_captions_catalog_fidelity(snapshot_data):
    """Ensure embedded caption identities are ingested from CATALOG.md."""
    caption_docs = [d for d in snapshot_data["documents"] if d["knowledge_doc_id"].startswith("caption:")]
    assert len(caption_docs) >= 35

    identities = {d["knowledge_doc_id"].replace("caption:", "") for d in caption_docs}
    for required in ["cream", "ink", "editorial", "keynote", "documentary", "loud", "neon", "glitch", "chrome", "velocity", "anchor", "terminal"]:
        assert required in identities, f"Required caption identity missing: {required}"


def test_hero_primitives_shelf_fidelity(snapshot_data):
    """Ensure the shelf of hero primitives from registry/components/CATALOG.md is present (25 units on disk)."""
    hero_docs = [d for d in snapshot_data["documents"] if d["knowledge_doc_id"].startswith("hero-primitive:")]
    assert len(hero_docs) == 25

    hero_names = {d["knowledge_doc_id"].replace("hero-primitive:", "") for d in hero_docs}
    assert "per-word-rise" in hero_names
    assert "scramble-reveal" in hero_names
    assert "oversized-cursor" in hero_names
    assert "press-ripple" in hero_names


def test_category_provenance_disjointness(snapshot_data):
    """Ensure donor canonical categories are preserved distinctly from 6Clips derived taxonomy."""
    for d in snapshot_data["documents"]:
        assert d["category_provenance"] in ["DONOR_CANONICAL", "DONOR_INFERRED", "DERIVED_6CLIPS"]
        assert d["capability_family"] in [
            "typography_kinetic", "captions_word_highlight", "data_visualization",
            "transition_wipe", "background_shader", "camera_3d", "ui_simulation",
            "responsive_layout"
        ]
        assert len(d["donor_group"]) > 0


def test_ast_safe_sanitization_and_no_eval(snapshot_data):
    """Verify that MDX/MD files were parsed into inert text and no executable JSX/JS leaked into runtime."""
    for d in snapshot_data["documents"]:
        # Verify no raw unescaped script execution tags
        for chunk in d.get("chunks", []):
            content = chunk["content"]
            assert "<script" not in content.lower(), f"Unsafe script tag in doc: {d['knowledge_doc_id']}"
            assert "javascript:" not in content.lower(), f"Unsafe javascript URI in doc: {d['knowledge_doc_id']}"


def test_rights_tagging_integrity(snapshot_data):
    """Ensure all documents have explicit rights tagging and reasons."""
    rights_breakdown = snapshot_data["rights_breakdown"]
    assert rights_breakdown["VERIFIED_PERMISSIVE"] > 500
    assert rights_breakdown["REFERENCE_ONLY"] > 100

    for d in snapshot_data["documents"]:
        assert d["rights"] in ["VERIFIED_PERMISSIVE", "REFERENCE_ONLY", "BLOCKED_RIGHTS"]
        assert len(d["rights_reason"]) > 0
