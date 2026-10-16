# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for Conversational Localized CAS Mutation (Wave 21 Agent 4)."""

import json
import pytest
from backend.database import init_db
from backend.native_motion.adapter import NativeMotionRevisionAdapter
from backend.native_motion.generator import NativeMotionGenerator
from backend.native_motion.schema import Constraints, CreativeBrief
from backend.services.project_service import ProjectService


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.mark.asyncio
async def test_conversational_mutation_preserves_unrelated_scenes():
    """Verify that patching an element in Scene 1 leaves Scene 2 and timestamps untouched."""
    project = await ProjectService.create_project(name="Conversational CAS Project", user_id="test_user")
    project_id = project.id

    brief = CreativeBrief(
        topic="Global Renewable Energy Expansion",
        intent="education",
        tone="tech",
    )
    # Generate multi-scene spec (25.0s, 4 scenes)
    spec = NativeMotionGenerator.build_benchmark_b1(approach="A", seed=101)
    orig_s2_content = spec.scenes[1].elements[2].text_config.content
    orig_s2_start = spec.scenes[1].start_time
    orig_s3_start = spec.scenes[2].start_time

    # Apply initial spec
    res1 = await NativeMotionRevisionAdapter.apply_native_motion_spec(
        project_id=project_id,
        expected_revision=project.revision,
        spec=spec,
    )
    rev1 = res1["revision"]

    # Target an element in Scene 1 only
    target_elem_id = "b1a_s0_text_callout"
    res_patch = await NativeMotionRevisionAdapter.patch_motion_element(
        project_id=project_id,
        expected_revision=rev1,
        element_id=target_elem_id,
        property_patches={"text_content": "+450 GWh SURGE"},
    )
    assert res_patch["revision"] == rev1 + 1

    # Fetch updated project and verify preservation of unrelated scenes
    proj_updated = await ProjectService.get_project(project_id)
    doc = json.loads(proj_updated.document_json)
    spec_data = json.loads(doc["code"]["files"][0]["content"])

    # Target element was mutated
    s1_elem = next(e for e in spec_data["scenes"][0]["elements"] if e["id"] == target_elem_id)
    assert s1_elem["text_config"]["content"] == "+450 GWh SURGE"

    # Scene 2 element is identical to original
    s2_elem = next(e for e in spec_data["scenes"][1]["elements"] if e["id"] == "b1a_s1_text_callout")
    assert s2_elem["text_config"]["content"] == orig_s2_content

    # Timeline timestamps for Scene 2 and 3 are preserved
    assert spec_data["scenes"][1]["start_time"] == orig_s2_start
    assert spec_data["scenes"][2]["start_time"] == orig_s3_start
