# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Tests for KnowledgeBase search, deterministic BM25 retrieval, and offline airgap validation.
"""
import socket
import pytest
from backend.knowledge_base import (
    CapabilityFamily,
    KnowledgeBase,
    RightsFlag,
    SearchFilter,
)


@pytest.fixture(scope="module")
def kb():
    return KnowledgeBase()


def test_offline_airgap_guarantee(monkeypatch, kb):
    """Ensure search and lookup never make external network connections."""
    def guarded_socket(*args, **kwargs):
        raise RuntimeError("AIRGAP VIOLATION: External socket creation attempted during knowledge retrieval!")

    monkeypatch.setattr(socket, "socket", guarded_socket)

    # Perform searches and direct lookups with network blocked
    res1 = kb.search("karaoke word by word sweep", limit=5)
    assert len(res1) > 0

    res2 = kb.get_by_id("block:canopy-part-title")
    assert res2 is not None

    cats = kb.list_categories()
    assert len(cats["donor_canonical_groups"]) > 0


def test_deterministic_bm25_scoring(kb):
    """Verify that repeated searches produce bit-for-bit identical scores and ranking."""
    query = "kinetic typography headline slam shake arrival"
    run1 = kb.search(query, limit=5)
    run2 = kb.search(query, limit=5)

    assert len(run1) == len(run2)
    for h1, h2 in zip(run1, run2):
        assert h1.knowledge_doc_id == h2.knowledge_doc_id
        assert h1.score == h2.score
        assert h1.title == h2.title


def test_direct_id_lookups(kb):
    """Verify direct lookups across all document types."""
    # 1. Block doc
    doc1 = kb.get_by_id("block:canopy-part-title")
    assert doc1 is not None
    assert doc1.title == "Canopy Part Title"
    assert doc1.donor_group == "3d-motion"

    # 2. Reconciled block
    doc2 = kb.get_by_id("block:aurora")
    assert doc2 is not None
    assert doc2.source_kind == "reconciled_block"

    # 3. Component doc
    doc3 = kb.get_by_id("component:caption-clip-wipe")
    assert doc3 is not None
    assert doc3.capability_family == CapabilityFamily.CAPTIONS_WORD_HIGHLIGHT

    # 4. Caption identity
    doc4 = kb.get_by_id("caption:cream")
    assert doc4 is not None
    assert doc4.donor_group == "text-captions"

    # 5. Hero primitive
    doc5 = kb.get_by_id("hero-primitive:per-word-rise")
    assert doc5 is not None
    assert "Hero Primitive" in doc5.title


def test_multifaceted_filtering(kb):
    """Verify multi-faceted filtering on capability family, donor group, rights, and aspect ratio."""
    # 1. Capability family filter
    shader_filter = SearchFilter(capability_family=CapabilityFamily.BACKGROUND_SHADER)
    shader_hits = kb.search("light wave particle", filters=shader_filter, limit=10)
    for h in shader_hits:
        assert h.capability_family == CapabilityFamily.BACKGROUND_SHADER.value

    # 2. Rights filter
    perm_filter = SearchFilter(rights=RightsFlag.VERIFIED_PERMISSIVE)
    perm_hits = kb.search("code terminal animation", filters=perm_filter, limit=10)
    for h in perm_hits:
        assert h.rights == RightsFlag.VERIFIED_PERMISSIVE.value

    # 3. Captions suitability filter
    cap_filter = SearchFilter(captions_suitability=True)
    cap_hits = kb.search("typography subtitle", filters=cap_filter, limit=5)
    for h in cap_hits:
        assert h.capability_family == CapabilityFamily.CAPTIONS_WORD_HIGHLIGHT.value


def test_category_separation_contract(kb):
    """Verify list_categories separates canonical donor groups from 6Clips derived taxonomy."""
    cats = kb.list_categories()
    assert "donor_canonical_groups" in cats
    assert "derived_6clips_capability_families" in cats

    donor_groups = cats["donor_canonical_groups"]
    assert "3d-motion" in donor_groups
    assert "carousels" in donor_groups
    assert "text-captions" in donor_groups
    assert "data-charts" in donor_groups

    families = cats["derived_6clips_capability_families"]
    assert "typography_kinetic" in families
    assert "captions_word_highlight" in families
    assert "data_visualization" in families
    assert "background_shader" in families
    assert "camera_3d" in families
    assert "ui_simulation" in families
    assert "responsive_layout" in families


def test_technique_retrieval_and_citations(kb):
    """Verify get_techniques returns permitted code citations."""
    techs = kb.get_techniques(capability_family=CapabilityFamily.TYPOGRAPHY_KINETIC)
    assert len(techs) > 0
    first = techs[0]
    assert "knowledge_doc_id" in first
    assert "citation" in first
    assert "source_hash" in first
    assert len(first["source_hash"]) == 64
    assert "principles" in first
