# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Contract and Retrieval Tests for KnowledgeBaseAdapter (Agent 3 Contract).
"""

import pytest

from backend.oaas_knowledge_orchestrator.knowledge_adapter import (
    KnowledgeBaseAdapter,
    TestOnlyKnowledgeAdapter,
)
from backend.oaas_knowledge_orchestrator.models import KnowledgeCitation


def test_test_only_adapter_retrieval_relevance():
    hits = TestOnlyKnowledgeAdapter.search("kinetic word typography", limit=2)
    assert len(hits) >= 1
    top = hits[0]
    assert "kinetic" in top["techniques"].lower() or "typography" in top["donor_group"].lower()
    assert top["rights"] == "PERMITTED_INERT_TECHNIQUE"
    assert len(top["source_hash"]) == 64


def test_knowledge_base_adapter_returns_validated_citations():
    citations, is_prod = KnowledgeBaseAdapter.search_knowledge("bar chart numeric data", limit=2)
    assert isinstance(citations, list)
    assert len(citations) >= 1

    cit = citations[0]
    assert isinstance(cit, KnowledgeCitation)
    assert cit.knowledge_doc_id.startswith("hf-doc-")
    assert cit.source_path.endswith(".mdx")
    assert len(cit.source_hash) == 64
    assert cit.rights == "PERMITTED_INERT_TECHNIQUE"
    assert cit.donor_group is not None


def test_retired_block_slugs_are_never_returned():
    # Attempting to search with an old slug must never return the slug as doc_id
    citations, _ = KnowledgeBaseAdapter.search_knowledge("aurora flowing-gradient", limit=5)
    for c in citations:
        assert c.knowledge_doc_id not in {"aurora", "flowing-gradient", "data-chart", "kinetic-type"}
