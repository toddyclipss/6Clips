# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for NativeMotionGenerator determinism, brief diversity, and non-template generation."""

from backend.native_motion.generator import NativeMotionGenerator
from backend.native_motion.schema import Constraints, CreativeBrief, KnowledgeRef


def test_generator_deterministic_seed_replay():
    brief = CreativeBrief(topic="DeFi Liquidity Surge", intent="data", tone="tech")
    kref = KnowledgeRef(
        doc_id="doc-data-01",
        source_path="docs/techniques/data.md",
        content_hash="hash123",
        section="charts",
    )
    constraints = Constraints(aspect_ratio="9:16", max_duration_seconds=3.0)

    spec_run1 = NativeMotionGenerator.generate(brief, [kref], constraints, seed=9999)
    spec_run2 = NativeMotionGenerator.generate(brief, [kref], constraints, seed=9999)

    assert spec_run1.model_dump_json() == spec_run2.model_dump_json()
    assert spec_run1.id == spec_run2.id
    assert spec_run1.scenes[0].elements[3].chart_config.dataset[0].value == \
           spec_run2.scenes[0].elements[3].chart_config.dataset[0].value


def test_generator_structural_diversity_across_briefs():
    b_data = CreativeBrief(topic="Crypto Metrics", intent="data", tone="tech")
    b_editorial = CreativeBrief(topic="Modernist Architecture", intent="editorial", tone="luxury")
    b_kinetic = CreativeBrief(topic="Hype Motivation", intent="story", tone="punchy")

    kref = KnowledgeRef(
        doc_id="doc-gen-01",
        source_path="docs/techniques/motion.md",
        content_hash="hash456",
        section="motion",
    )

    spec_data = NativeMotionGenerator.generate(b_data, [kref], Constraints(aspect_ratio="9:16", max_duration_seconds=3.0), seed=1)
    spec_editorial = NativeMotionGenerator.generate(b_editorial, [kref], Constraints(aspect_ratio="16:9", max_duration_seconds=3.0), seed=2)
    spec_kinetic = NativeMotionGenerator.generate(b_kinetic, [kref], Constraints(aspect_ratio="9:16", max_duration_seconds=3.0), seed=3)

    # Topology element types
    topo_data = [e.type for e in spec_data.scenes[0].elements]
    topo_editorial = [e.type for e in spec_editorial.scenes[0].elements]
    topo_kinetic = [e.type for e in spec_kinetic.scenes[0].elements]

    # Must be structurally distinct
    assert topo_data != topo_editorial
    assert "data_chart" in topo_data
    assert "data_chart" not in topo_editorial
    assert spec_data.width != spec_editorial.width
    assert spec_data.height != spec_editorial.height


def test_generator_no_196_donor_blocks_used():
    b = CreativeBrief(topic="Pure Native Motion", intent="data", tone="tech")
    spec = NativeMotionGenerator.generate(b, [], Constraints(aspect_ratio="9:16"), seed=42)

    spec_json = spec.model_dump_json()
    assert "creator-hud" not in spec_json
    assert "glitch-transition" not in spec_json
    assert "iframe" not in spec_json
    assert "hyperframes/registry" not in spec_json
