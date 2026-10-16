# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for NativeMotionRevisionAdapter: optimistic concurrency CAS and non-destructive element/caption patching."""

import asyncio
import json
import pytest
from backend.core.exceptions import RevisionConflictError
from backend.native_motion.adapter import NativeMotionRevisionAdapter
from backend.native_motion.generator import NativeMotionGenerator
from backend.native_motion.schema import (
    Constraints,
    CreativeBrief,
    WordTimestampSpec,
)
from backend.database import init_db
from backend.services.project_service import ProjectService


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.mark.asyncio
async def test_cas_apply_spec_and_revision_bump():
    # Create test project
    project = await ProjectService.create_project(name="Native Motion CAS Project", user_id="test_user")
    project_id = project.id
    init_rev = project.revision

    brief = CreativeBrief(topic="DeFi Protocol", intent="data", tone="tech")
    spec = NativeMotionGenerator.generate(brief, [], Constraints(aspect_ratio="9:16"), seed=42)

    # 1. Apply spec with matching expected_revision
    res = await NativeMotionRevisionAdapter.apply_native_motion_spec(
        project_id=project_id,
        expected_revision=init_rev,
        spec=spec,
        idempotency_key="nm_key_001",
    )
    assert res["revision"] == init_rev + 1

    # 2. Concurrency Conflict: wrong expected_revision must raise RevisionConflictError
    with pytest.raises(RevisionConflictError):
        await NativeMotionRevisionAdapter.apply_native_motion_spec(
            project_id=project_id,
            expected_revision=init_rev,  # Stale revision!
            spec=spec,
        )

    # 3. Idempotent retry returns existing revision
    res_idem = await NativeMotionRevisionAdapter.apply_native_motion_spec(
        project_id=project_id,
        expected_revision=init_rev,
        spec=spec,
        idempotency_key="nm_key_001",
    )
    assert res_idem["revision"] == init_rev + 1


@pytest.mark.asyncio
async def test_fine_grained_element_patching():
    project = await ProjectService.create_project(name="Element Patching Project", user_id="test_user")
    project_id = project.id

    brief = CreativeBrief(topic="Metric Counter", intent="data", tone="tech")
    spec = NativeMotionGenerator.generate(brief, [], Constraints(aspect_ratio="9:16"), seed=77)

    res1 = await NativeMotionRevisionAdapter.apply_native_motion_spec(
        project_id=project_id,
        expected_revision=project.revision,
        spec=spec,
    )
    curr_rev = res1["revision"]

    # Target the hero_title element
    res_patch = await NativeMotionRevisionAdapter.patch_motion_element(
        project_id=project_id,
        expected_revision=curr_rev,
        element_id="hero_title",
        property_patches={"text_content": "PATCHED HEADLINE", "font_size": 72.0},
    )
    assert res_patch["revision"] == curr_rev + 1

    # Verify updated content in saved document snapshot
    updated_proj = await ProjectService.get_project(project_id)
    updated_doc = json.loads(updated_proj.document_json)
    spec_content = json.loads(updated_doc["code"]["files"][0]["content"])
    hero_elem = next(e for e in spec_content["scenes"][0]["elements"] if e["id"] == "hero_title")
    assert hero_elem["text_config"]["content"] == "PATCHED HEADLINE"
    assert hero_elem["text_config"]["typography"]["font_size"] == 72.0


@pytest.mark.asyncio
async def test_fine_grained_caption_word_patching():
    project = await ProjectService.create_project(name="Caption Word Patch Project", user_id="test_user")
    project_id = project.id

    words = [
        WordTimestampSpec(word="ViralMint", start=0.0, end=0.8),
        WordTimestampSpec(word="produces", start=0.8, end=1.5),
        WordTimestampSpec(word="motion", start=1.5, end=2.2),
    ]
    brief = CreativeBrief(topic="Speech Motion", intent="story", tone="punchy")
    spec = NativeMotionGenerator.generate(brief, [], Constraints(aspect_ratio="9:16"), seed=12, words=words)

    res1 = await NativeMotionRevisionAdapter.apply_native_motion_spec(
        project_id=project_id,
        expected_revision=project.revision,
        spec=spec,
    )
    curr_rev = res1["revision"]

    # Patch word at index 1 ("produces" -> "creates" with custom color)
    res_word = await NativeMotionRevisionAdapter.patch_caption_word(
        project_id=project_id,
        expected_revision=curr_rev,
        word_index=1,
        new_word="creates",
        color_override="#10B981",
    )
    assert res_word["revision"] == curr_rev + 1

    updated_proj = await ProjectService.get_project(project_id)
    updated_doc = json.loads(updated_proj.document_json)
    spec_content = json.loads(updated_doc["code"]["files"][0]["content"])
    captions_elem = next(e for e in spec_content["scenes"][0]["elements"] if e["type"] == "captions")
    assert captions_elem["captions_config"]["words"][1]["word"] == "creates"
    assert captions_elem["captions_config"]["words"][1]["color_override"] == "#10B981"
