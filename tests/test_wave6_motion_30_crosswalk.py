# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 6 test suite: 30-feature executable crosswalk, CAS revision adapter, and timeline attachments."""

import json
import os
import subprocess
from pathlib import Path
import pytest
from fastapi import HTTPException

from backend.motion_capabilities import (
    ALL_CAPABILITIES_SPEC,
    MotionCapabilitiesRegistry,
    MotionCapabilityDispatcher,
    MotionToolRunnerAdapter,
    ParityTier,
)
from backend.database import init_db
from backend.services.project_service import ProjectService


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Ensure database schema is created for project service tests."""
    await init_db()


@pytest.fixture(scope="module")
def small_video_fixture(tmp_path_factory):
    """Generate a real 1-second 320x240 MP4 media fixture with audio."""
    tmp_dir = tmp_path_factory.mktemp("crosswalk_media")
    video_path = tmp_dir / "clip_crosswalk.mp4"
    cmd = [
        "ffmpeg", "-y", "-hide_banner",
        "-f", "lavfi", "-i", "testsrc=duration=1.0:size=320x240:rate=24",
        "-f", "lavfi", "-i", "aevalsrc=sin(440*2*PI*t):s=44100:d=1.0",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac",
        str(video_path),
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert res.returncode == 0
    return video_path


@pytest.fixture
def base_project_doc():
    """Initial canonical project document."""
    return {
        "version": 1,
        "aspect_ratio": "9:16",
        "tracks": [
            {
                "id": "trk_v1",
                "name": "Main Video",
                "type": "video",
                "clips": [
                    {
                        "id": "c_orig_1",
                        "name": "Original Take",
                        "start": 0.0,
                        "duration": 4.0,
                        "in_point": 0.0,
                        "out_point": 4.0,
                    }
                ],
            }
        ],
    }


# ─── 30-Feature Executable Crosswalk Tests ─────────────────────────────────

def test_30_feature_crosswalk_completeness():
    """Verify all 30 features have complete 8-dimension specifications in the registry."""
    all_specs = MotionCapabilitiesRegistry.list_all()
    assert len(all_specs) == 30

    for spec in all_specs:
        # 1. Main Agent capability ID
        assert spec.id is not None and len(spec.id) > 0
        # 2. Native Motion UI gesture / Entrypoint
        assert spec.motion_entrypoint is not None and len(spec.motion_entrypoint) > 0
        # 3. Legacy implementation source
        assert spec.legacy_source is not None and len(spec.legacy_source) > 0
        # 4. Actual service / FFmpeg backend action
        assert spec.backend_action is not None and len(spec.backend_action) > 0
        # 5. Validator / Parity tier
        assert spec.parity_tier in (ParityTier.VERIFIED_REAL, ParityTier.FUNCTIONAL_WITH_LIMITS)
        # 6. Description & Semantics
        assert spec.description is not None and len(spec.description) > 0
        # 7. Parameters schema
        assert isinstance(spec.parameters_schema, dict)
        # 8. Dispatchable alias or direct handler
        assert MotionCapabilitiesRegistry.get(spec.id) is not None


# ─── Media Tool Timeline Attachment & Project Mutation Tests ──────────────

@pytest.mark.asyncio
async def test_tool_execution_attaches_output_to_project_timeline(small_video_fixture, base_project_doc, tmp_path):
    """Verify deterministic media tool execution places output clip directly into project document timeline."""
    res = await MotionCapabilityDispatcher.dispatch(
        capability_id="trim",
        input_path=small_video_fixture,
        params={"start": 0.0, "end": 0.5, "duration": 0.5},
        project_doc=base_project_doc,
        output_dir=tmp_path,
    )
    assert res.status == "SUCCESS"
    assert res.output_path is not None
    assert "project_doc" in res.output_data

    # Check that mutated document contains the new clip attached to the video track
    mutated_doc = res.output_data["project_doc"]
    video_track = next(t for t in mutated_doc["tracks"] if t["type"] == "video")
    assert len(video_track["clips"]) == 2

    new_clip = video_track["clips"][1]
    assert new_clip["id"] == res.output_data["attached_clip_id"]
    assert new_clip["source_path"] == res.output_path
    assert new_clip["duration"] == 0.5
    # Spliced right after previous 4.0s clip
    assert new_clip["start"] == 4.0


@pytest.mark.asyncio
async def test_audio_tool_attaches_to_audio_track(small_video_fixture, base_project_doc, tmp_path):
    """Verify audio tool execution attaches to audio track, creating it if needed."""
    res = await MotionCapabilityDispatcher.dispatch(
        capability_id="extract-audio",
        input_path=small_video_fixture,
        project_doc=base_project_doc,
        output_dir=tmp_path,
    )
    assert res.status == "SUCCESS"
    mutated_doc = res.output_data["project_doc"]
    audio_track = next((t for t in mutated_doc["tracks"] if t["type"] == "audio"), None)
    assert audio_track is not None
    assert len(audio_track["clips"]) == 1
    assert audio_track["clips"][0]["source_path"] == res.output_path


# ─── CAS Revision Concurrency & Mutation Tests ─────────────────────────────

@pytest.mark.asyncio
async def test_cas_revision_stale_mismatch_raises_409(small_video_fixture, tmp_path):
    """Verify MotionToolRunnerAdapter rejects stale revisions with HTTP 409."""
    proj = await ProjectService.create_project(
        name="CAS Test Project",
        aspect_ratio="9:16",
        initial_document={"version": 1, "tracks": []},
        user_id="local_tester",
    )
    current_rev = proj.revision
    stale_rev = current_rev + 5  # Deliberately mismatched revision

    with pytest.raises(HTTPException) as exc_info:
        await MotionToolRunnerAdapter.execute_tool_with_cas_revision(
            project_id=proj.id,
            expected_revision=stale_rev,
            tool_name="trim",
            input_path=small_video_fixture,
            params={"start": 0.0, "end": 0.5},
        )
    assert exc_info.value.status_code == 409
    assert "Stale revision conflict" in exc_info.value.detail


@pytest.mark.asyncio
async def test_cas_revision_successful_mutation(small_video_fixture, tmp_path):
    """Verify MotionToolRunnerAdapter successfully mutates document and increments revision."""
    proj = await ProjectService.create_project(
        name="CAS Success Project",
        aspect_ratio="9:16",
        initial_document={"version": 1, "tracks": []},
        user_id="local_tester",
    )
    orig_rev = proj.revision

    outcome = await MotionToolRunnerAdapter.execute_tool_with_cas_revision(
        project_id=proj.id,
        expected_revision=orig_rev,
        tool_name="trim",
        input_path=small_video_fixture,
        params={"start": 0.0, "end": 0.5},
    )
    assert outcome["success"] is True
    assert outcome["status"] == "SUCCESS"
    assert outcome["previous_revision"] == orig_rev
    assert outcome["current_revision"] > orig_rev

    # Verify reloading project from DB reflects the mutated state
    reloaded = await ProjectService.get_project(proj.id)
    assert reloaded.revision == outcome["current_revision"]
    doc = json.loads(reloaded.document_json) if isinstance(reloaded.document_json, str) else reloaded.document_json
    assert "tracks" in doc


# ─── Local AI / Ollama Provider Truthfulness ───────────────────────────────

@pytest.mark.asyncio
async def test_ai_tool_truthful_offline_blocked_when_unconfigured():
    """Verify AI text tools return BLOCKED when neither local Ollama nor BYOK API key is configured."""
    orig_openai = os.environ.pop("OPENAI_API_KEY", None)
    orig_anthropic = os.environ.pop("ANTHROPIC_API_KEY", None)
    orig_ollama = os.environ.pop("OLLAMA_BASE_URL", None)
    # Point to a dead port to simulate offline Ollama
    os.environ["OLLAMA_BASE_URL"] = "http://127.0.0.1:9999"

    try:
        res = await MotionCapabilityDispatcher.dispatch(capability_id="hook-analysis")
        assert res.status == "BLOCKED"
        assert res.error_detail == "AI_PROVIDER_UNAVAILABLE"
        assert "Local Ollama provider and BYOK AI keys are unavailable" in res.message
    finally:
        if orig_openai:
            os.environ["OPENAI_API_KEY"] = orig_openai
        if orig_anthropic:
            os.environ["ANTHROPIC_API_KEY"] = orig_anthropic
        if orig_ollama:
            os.environ["OLLAMA_BASE_URL"] = orig_ollama
        else:
            os.environ.pop("OLLAMA_BASE_URL", None)
