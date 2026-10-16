# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Contract and Generation Tests for NativeMotionGeneratorAdapter (Agent 4 Contract).
Validates structural originality, parametric scene graphs, and canonical project CAS commit.
"""

import pytest

from backend.database import init_db
from backend.oaas_knowledge_orchestrator.models import KnowledgeCitation, NativeMotionSpecContract
from backend.oaas_knowledge_orchestrator.motion_generator_adapter import NativeMotionGeneratorAdapter
from backend.services.project_service import ProjectService


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


def test_motion_generator_adapter_creates_valid_spec():
    citation = KnowledgeCitation(
        knowledge_doc_id="hf-doc-kinetic-01",
        source_path="docs/catalog/components/typography/kinetic.mdx",
        source_hash="0" * 64,
        technique="kinetic_spring_easing",
    )
    spec = NativeMotionGeneratorAdapter.generate_spec(
        brief="Launch announcement for sustainable fashion brand",
        knowledge_refs=[citation],
        constraints={"aspect_ratio": "9:16", "duration_seconds": 4.0},
    )

    assert isinstance(spec, NativeMotionSpecContract)
    assert spec.spec_version == "native_motion_v1"
    assert spec.aspect_ratio == "9:16"
    assert spec.target_duration_sec == 4.0
    assert len(spec.scenes) >= 1
    assert len(spec.captions) >= 1


def test_distinct_briefs_produce_structurally_diverse_layouts():
    """
    Ensure the generator does NOT produce identical layouts with only text/color swaps.
    A kinetic text brief and a data visualization brief must produce distinct scene/element topologies.
    """
    cit_kinetic = KnowledgeCitation(
        knowledge_doc_id="hf-doc-k1",
        source_path="docs/kinetic.mdx",
        source_hash="1" * 64,
        technique="spring_kinetic",
    )
    cit_chart = KnowledgeCitation(
        knowledge_doc_id="hf-doc-c1",
        source_path="docs/chart.mdx",
        source_hash="2" * 64,
        technique="procedural_bar_growth",
    )

    spec_kinetic = NativeMotionGeneratorAdapter.generate_spec(
        brief="High energy kinetic typography release",
        knowledge_refs=[cit_kinetic],
        constraints={"aspect_ratio": "9:16", "duration_seconds": 3.0},
    )

    spec_chart = NativeMotionGeneratorAdapter.generate_spec(
        brief="Quarterly revenue growth and data chart performance",
        knowledge_refs=[cit_chart],
        constraints={"aspect_ratio": "16:9", "duration_seconds": 7.0},
    )

    fp_kinetic = NativeMotionGeneratorAdapter.compute_spec_fingerprint(spec_kinetic)
    fp_chart = NativeMotionGeneratorAdapter.compute_spec_fingerprint(spec_chart)

    assert fp_kinetic != fp_chart, "Both specifications produced identical structural fingerprints!"
    assert len(spec_kinetic.scenes) != len(spec_chart.scenes)


@pytest.mark.asyncio
async def test_compile_and_commit_to_project_bumps_cas_revision():
    project = await ProjectService.create_project(name="Test Motion Compile", aspect_ratio="9:16")
    base_rev = project.revision
    assert base_rev == 1

    spec = NativeMotionGeneratorAdapter.generate_spec(
        brief="Simple test motion",
        knowledge_refs=[],
        constraints={"aspect_ratio": "9:16", "duration_seconds": 3.0},
    )

    res = await NativeMotionGeneratorAdapter.compile_and_commit_to_project(
        project_id=project.id,
        expected_revision=base_rev,
        spec=spec,
        author="main_agent",
    )

    assert res["revision"] == 2
    updated = await ProjectService.get_project(project.id)
    assert updated.revision == 2

    # Check tracks created
    doc = res["document"]
    tracks = doc.get("timeline", {}).get("tracks", [])
    assert len(tracks) >= 2
    track_types = {t.get("type") for t in tracks}
    assert "video" in track_types
    assert "captions" in track_types
