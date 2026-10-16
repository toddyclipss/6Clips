# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for Real KnowledgeBase Grounding & Citation Fidelity (Wave 21 Agent 4)."""

import pytest
from backend.native_motion.generator import NativeMotionGenerator
from backend.native_motion.schema import CreativeBrief, Constraints


def test_real_knowledge_base_retrieval_and_directives():
    """Verify generator queries real KnowledgeBase and extracts authentic doc metadata."""
    brief = CreativeBrief(
        topic="Kinetic Data Chart and Metric Acceleration",
        intent="data",
        tone="tech",
    )
    krefs = NativeMotionGenerator.retrieve_knowledge_for_brief(brief, limit=3)
    assert len(krefs) > 0, "Expected at least 1 KnowledgeRef from KnowledgeBase"

    for ref in krefs:
        assert ref.doc_id, "doc_id must be non-empty"
        assert ref.source_path, "source_path must be non-empty"
        assert len(ref.content_hash) >= 32, "content_hash must be a valid hex hash"
        assert isinstance(ref.principles, list)


def test_knowledge_refs_attached_to_generated_scenes():
    """Verify generated multi-scene specs attach knowledge references with provenance."""
    brief = CreativeBrief(
        topic="Autonomous Coding Systems",
        intent="explain",
        tone="tech",
    )
    spec = NativeMotionGenerator.generate(
        brief=brief,
        constraints=Constraints(aspect_ratio="9:16", max_duration_seconds=10.0),
        seed=101,
    )
    assert len(spec.knowledge_refs) > 0
    # Every scene should also inherit or reference knowledge
    for s in spec.scenes:
        assert isinstance(s.knowledge_refs, list)
        assert len(s.knowledge_refs) > 0


def test_fail_closed_zero_fake_citations():
    """Verify that non-existent topics do not invent fake HyperFrames donor IDs."""
    brief = CreativeBrief(
        topic="ZZZZ_COMPLETELY_UNMATCHED_FICTIONAL_TOPIC_9999",
        intent="unknown_intent",
        tone="unknown_tone",
    )
    krefs = NativeMotionGenerator.retrieve_knowledge_for_brief(brief, limit=2)
    # Must never invent arbitrary fake block names like 'block:fake-block-123'
    for ref in krefs:
        assert not ref.doc_id.startswith("fake_")
        assert ref.source_path.endswith((".md", ".mdx", ".py"))
