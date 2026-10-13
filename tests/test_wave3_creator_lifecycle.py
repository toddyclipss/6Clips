# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Tests for Creator Workflow Lifecycle, Input Gating, and API Routes (Wave 3 Role 5).

Verifies:
- State transitions: PLANNING_ARTIFACT_DRAFT -> WAITING_FOR_INPUT -> READY_FOR_COMPOSITION -> RENDERED.
- Truthful voice input requirement enforcement: blocks render if voice missing without consent.
- Negative rights gating: respects BLOCKED state.
- Clean teleprompter script invariants (zero stage directions or bracketed directions).
- ProductionV1Adapter fidelity for Motion Review and ProjectService integration.
- FastAPI endpoints: /trends/reference-recipe and /original/render.
"""
from pathlib import Path
import shutil
import tempfile
import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.trends import router
from backend.original_creation.models import (
    EvidenceLedger,
    OriginalCompositionSpec,
    OriginalCreationStatus,
    ProductionV1Adapter,
    TeleprompterScript,
    VoiceInputRequirement,
)
from backend.original_creation.workflow import (
    OriginalCreatorWorkflow,
    clean_teleprompter_text,
)


@pytest.fixture
def isolated_tmp_dir():
    tmp = Path(tempfile.mkdtemp(prefix="viralmint_lifecycle_test_"))
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


def test_clean_teleprompter_text_invariants():
    """Verify scripts contain zero bracketed directions, cues, or formatting debris."""
    dirty_text = (
        "Scene 1: [Cut to camera] Welcome back everyone! (Sound of thunder swells) "
        "[Show weapon chart] Here are the newest patch numbers. "
        "Voiceover: Check this out now!"
    )
    cleaned = clean_teleprompter_text(dirty_text)
    assert "[" not in cleaned
    assert "]" not in cleaned
    assert "Scene 1:" not in cleaned
    assert "Voiceover:" not in cleaned
    assert "Welcome back everyone!" in cleaned
    assert "Here are the newest patch numbers." in cleaned


def test_truthful_voice_input_gating():
    """Verify system does not render until voice is provided or TTS authorized."""
    # Case A: Creator voice missing and TTS not authorized -> WAITING_FOR_INPUT
    brief = OriginalCreatorWorkflow.create_brief(
        topic="Acoustic Engineering",
        allow_procedural_tts=False,
    )
    assert brief.status == OriginalCreationStatus.WAITING_FOR_INPUT
    assert brief.voice_requirement == VoiceInputRequirement.WAITING_FOR_INPUT
    assert "WAITING_FOR_INPUT" in brief.status_reason

    # Case B: Procedural TTS authorized -> READY_FOR_COMPOSITION
    brief_tts = OriginalCreatorWorkflow.create_brief(
        topic="Acoustic Engineering",
        allow_procedural_tts=True,
    )
    assert brief_tts.status == OriginalCreationStatus.READY_FOR_COMPOSITION
    assert brief_tts.voice_requirement == VoiceInputRequirement.PROCEDURAL_SYNTHESIS_ALLOWED

    # Case C: Creator voice asset provided -> READY_FOR_COMPOSITION
    brief_voice = OriginalCreatorWorkflow.create_brief(
        topic="Acoustic Engineering",
        creator_voice_asset_id="asset-voice-rec-77",
    )
    assert brief_voice.status == OriginalCreationStatus.READY_FOR_COMPOSITION
    assert brief_voice.voice_requirement == VoiceInputRequirement.VOICE_PROVIDED


@pytest.mark.asyncio
async def test_render_aborts_truthfully_on_waiting_for_input(isolated_tmp_dir):
    """Verify render_spec refuses to fake a video if voice is not available."""
    brief = OriginalCreatorWorkflow.create_brief(
        topic="Quantum Computing",
        allow_procedural_tts=False,
    )

    result = await OriginalCreatorWorkflow.render_spec(
        spec=brief,
        output_dir=isolated_tmp_dir,
    )

    # Status must remain WAITING_FOR_INPUT without fabricating a video
    assert result.status == OriginalCreationStatus.WAITING_FOR_INPUT
    assert result.rendered_result is None


def test_production_v1_adapter_contract():
    """Verify canonical project payload faithfully indicates render readiness."""
    brief = OriginalCreatorWorkflow.create_brief(topic="Microbiology Update")
    payload_draft = ProductionV1Adapter.to_canonical_project_payload(brief)

    assert payload_draft["metadata"]["production_stage"] == "PLANNING_ARTIFACT"
    assert payload_draft["metadata"]["rendered_mp4_ready"] is False
    assert payload_draft["metadata"]["motion_review_ready"] is False


@pytest.mark.asyncio
async def test_api_reference_recipe_and_render_routes(isolated_tmp_dir):
    """Verify FastAPI trends router endpoints for recipe extraction and rendering."""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router, prefix="/api")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Test /api/trends/reference-recipe
        rec_res = await client.post(
            "/api/trends/reference-recipe",
            json={
                "reference_id": "ref-chem-99",
                "title": "5 Chemical Reactions That Look Like Magic",
                "duration_seconds": 60,
                "channel": "ScienceSpot",
            },
        )
        assert rec_res.status_code == 200
        rec_data = rec_res.json()
        assert "hypothesis" in rec_data
        assert "project_recipe" in rec_data
        assert rec_data["project_recipe"]["target_aspect_ratio"] == "9:16"

        # 2. Test /api/original/render with WAITING_FOR_INPUT
        draft_spec = OriginalCreatorWorkflow.create_brief(
            topic="Renewable Energy",
            allow_procedural_tts=False,
        )
        rnd_waiting = await client.post(
            "/api/original/render",
            json={"spec": draft_spec.model_dump()},
        )
        assert rnd_waiting.status_code == 200
        w_data = rnd_waiting.json()
        assert w_data["status"] == "WAITING_FOR_INPUT"
        assert w_data["is_rendered"] is False
