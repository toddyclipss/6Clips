# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Test Suite for Chat Revision Deltas (Requirement 5).
Validates mutations on the SAME canonical Project timeline, CAS concurrency checks,
and contextual feedback modifications.
"""

import pytest

from backend.core.exceptions import RevisionConflictError
from backend.database import init_db
from backend.oaas_knowledge_orchestrator.models import NativeMotionSpecContract
from backend.oaas_knowledge_orchestrator.motion_generator_adapter import NativeMotionGeneratorAdapter
from backend.oaas_knowledge_orchestrator.revision_delta_engine import RevisionDeltaEngine
from backend.services.project_service import ProjectService


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.mark.asyncio
async def test_revision_delta_cinematic_typography_and_cas():
    # Setup project with initial motion spec at revision 2
    proj = await ProjectService.create_project(name="Delta Test", aspect_ratio="9:16")
    spec = NativeMotionGeneratorAdapter.generate_spec(
        brief="Promo video for coffee",
        knowledge_refs=[],
        constraints={"aspect_ratio": "9:16", "duration_seconds": 4.0},
    )
    await NativeMotionGeneratorAdapter.compile_and_commit_to_project(
        project_id=proj.id,
        expected_revision=1,
        spec=spec,
    )

    # Revision 1: Make second title more cinematic
    delta1 = await RevisionDeltaEngine.apply_feedback_delta(
        project_id=proj.id,
        expected_revision=2,
        user_feedback="make the second title more cinematic with high contrast",
    )

    assert delta1["resulting_revision"] == 3
    assert any("cinematic" in d for d in delta1["applied_deltas"])

    # Verify project mutated in-place
    p3 = await ProjectService.get_project(proj.id)
    assert p3.revision == 3

    # Revision 2: Remove dead air
    delta2 = await RevisionDeltaEngine.apply_feedback_delta(
        project_id=proj.id,
        expected_revision=3,
        user_feedback="remove dead air and tighten pacing",
    )
    assert delta2["resulting_revision"] == 4
    assert any("trimmed_dead_air" in d for d in delta2["applied_deltas"])

    # Revision 3: Synchronize captions
    delta3 = await RevisionDeltaEngine.apply_feedback_delta(
        project_id=proj.id,
        expected_revision=4,
        user_feedback="synchronize the emphasized words in captions",
    )
    assert delta3["resulting_revision"] == 5
    assert any("synchronized_word_highlight" in d for d in delta3["applied_deltas"])

    # Revision 4: Reframe to 16:9
    delta4 = await RevisionDeltaEngine.apply_feedback_delta(
        project_id=proj.id,
        expected_revision=5,
        user_feedback="change aspect ratio to 16:9 widescreen",
    )
    assert delta4["resulting_revision"] == 6
    p6 = await ProjectService.get_project(proj.id)
    assert p6.aspect_ratio == "16:9"


@pytest.mark.asyncio
async def test_revision_delta_stale_expected_revision_raises_cas_conflict():
    proj = await ProjectService.create_project(name="CAS Test", aspect_ratio="9:16")
    # Proj is at revision 1, but we pass expected_revision=5
    with pytest.raises(RevisionConflictError) as exc_info:
        await RevisionDeltaEngine.apply_feedback_delta(
            project_id=proj.id,
            expected_revision=5,
            user_feedback="make it faster",
        )
    assert exc_info.value.current_revision == 1
    assert exc_info.value.expected_revision == 5
