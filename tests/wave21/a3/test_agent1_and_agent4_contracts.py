# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Tests for Agent 1 and Agent 4 integration contracts, safety constraints,
and citation builders.
"""
from pathlib import Path
import pytest

from backend.knowledge_base import (
    Agent1SearchRequest,
    Agent1SearchResponse,
    CapabilityFamily,
    KnowledgeAdapter,
    KnowledgeBase,
    KnowledgeRef,
    MotionDirectives,
    RightsFlag,
)

WORKTREE_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def kb():
    return KnowledgeBase()


@pytest.fixture(scope="module")
def adapter(kb):
    return KnowledgeAdapter(kb)


def test_agent1_search_contract_and_prompt_formatting(adapter):
    """Verify Agent 1 search contract returns structured hits and formatted LLM context."""
    req = Agent1SearchRequest(
        query="kinetic headline slam impact",
        capability_family=CapabilityFamily.TYPOGRAPHY_KINETIC.value,
        limit=3
    )
    resp = adapter.handle_agent1_query(req)

    assert isinstance(resp, Agent1SearchResponse)
    assert resp.total_hits > 0
    assert len(resp.results) > 0
    assert "HyperFrames Motion Design Directives" in resp.context_prompt_snippet
    assert "component:headline-slam" in [r.knowledge_doc_id for r in resp.results]


def test_agent1_exclude_blocked_rights_defense(adapter):
    """Verify Agent 1 chat search strictly excludes BLOCKED_RIGHTS documents."""
    req = Agent1SearchRequest(
        query="heygen avatar promo card",
        exclude_blocked=True,
        limit=5
    )
    resp = adapter.handle_agent1_query(req)
    for r in resp.results:
        assert r.rights != RightsFlag.BLOCKED_RIGHTS.value
        assert r.knowledge_doc_id != "block:heygen-avatar-promo-card"


def test_agent4_motion_directives_contract(adapter):
    """Verify Agent 4 motion generator directives contract produces typed MotionDirectives."""
    directives = adapter.get_agent4_directives("component:curtain-reveal")

    assert isinstance(directives, MotionDirectives)
    assert directives.doc_id == "component:curtain-reveal"
    assert directives.capability_family == CapabilityFamily.TRANSITION_WIPE.value
    assert len(directives.aspect_ratios) > 0
    assert directives.requires_webgpu is False
    assert directives.rights_status == "VERIFIED_PERMISSIVE"


def test_agent4_citation_builder_fidelity(adapter):
    """Verify KnowledgeRef citation builder produces traceable citation with SHA-256."""
    ref = adapter.create_knowledge_ref(
        "component:headline-slam",
        applied_techniques=["Deceleration arrival curve", "Camera impact shake"]
    )

    assert isinstance(ref, KnowledgeRef)
    assert ref.knowledge_doc_id == "component:headline-slam"
    assert len(ref.source_hash) == 64
    assert ref.capability_family == CapabilityFamily.TYPOGRAPHY_KINETIC.value
    assert "Deceleration arrival curve" in ref.techniques_applied
