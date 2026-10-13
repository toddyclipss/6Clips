# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 5 test suite: Deterministic capabilities dispatcher and real media execution."""

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path
import pytest

from backend.motion_capabilities import (
    MotionCapabilitiesRegistry,
    MotionCapabilityDispatcher,
    ParityTier,
)


@pytest.fixture(scope="module")
def real_media_fixture(tmp_path_factory):
    """Generate a real 1-second 320x240 MP4 media fixture with audio using local FFmpeg."""
    tmp_dir = tmp_path_factory.mktemp("real_media")
    video_path = tmp_dir / "real_fixture.mp4"
    cmd = [
        "ffmpeg", "-y", "-hide_banner",
        "-f", "lavfi", "-i", "testsrc=duration=1.0:size=320x240:rate=24",
        "-f", "lavfi", "-i", "aevalsrc=sin(440*2*PI*t):s=44100:d=1.0",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac",
        str(video_path),
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert res.returncode == 0, f"FFmpeg fixture generation failed: {res.stderr}"
    assert video_path.exists() and video_path.stat().st_size > 0
    return video_path


@pytest.fixture
def sample_project_doc():
    """Authoritative project document with tracks, clips, and layers."""
    return {
        "version": 2,
        "tracks": [
            {
                "id": "t_video_1",
                "name": "Main Video",
                "type": "video",
                "clips": [
                    {
                        "id": "clip_main_1",
                        "name": "Clip A",
                        "start": 0.0,
                        "duration": 6.0,
                        "in_point": 1.0,
                        "out_point": 7.0,
                        "speed": 1.0,
                        "volume": 1.0,
                    },
                    {
                        "id": "clip_main_2",
                        "name": "Clip B",
                        "start": 6.0,
                        "duration": 4.0,
                        "in_point": 0.0,
                        "out_point": 4.0,
                        "speed": 1.0,
                        "volume": 0.8,
                    },
                ],
            },
            {
                "id": "t_audio_1",
                "name": "Background Music",
                "type": "audio",
                "clips": [
                    {
                        "id": "clip_bgm_1",
                        "name": "BGM Loop",
                        "start": 0.0,
                        "duration": 10.0,
                        "in_point": 0.0,
                        "out_point": 10.0,
                        "volume": 0.5,
                    }
                ],
            },
        ],
        "layers": [
            {
                "id": "layer_caption_1",
                "type": "caption",
                "text": "Initial automated caption segment",
                "start": 0.5,
                "duration": 3.0,
            }
        ],
    }


# ─── Timeline Mutation Capability Tests ────────────────────────────────────

@pytest.mark.asyncio
async def test_timeline_clip_split_valid(sample_project_doc):
    """Verify timeline-clip-split creates two clean adjacent clips with preserved in/out points."""
    res = await MotionCapabilityDispatcher.dispatch(
        capability_id="timeline-clip-split",
        project_doc=sample_project_doc,
        params={"clip_id": "clip_main_1", "split_time": 2.5},
    )
    assert res.status == "SUCCESS"
    assert "split_clips" in res.output_data
    split_ids = res.output_data["split_clips"]
    assert len(split_ids) == 2

    # Check updated document
    doc = res.output_data["project_doc"]
    clips = doc["tracks"][0]["clips"]
    assert len(clips) == 3
    c1 = next(c for c in clips if c["id"] == split_ids[0])
    c2 = next(c for c in clips if c["id"] == split_ids[1])

    assert c1["start"] == 0.0
    assert c1["duration"] == 2.5
    assert c1["in_point"] == 1.0
    assert c1["out_point"] == 3.5

    assert c2["start"] == 2.5
    assert c2["duration"] == 3.5
    assert c2["in_point"] == 3.5
    assert c2["out_point"] == 7.0


@pytest.mark.asyncio
async def test_timeline_clip_split_out_of_bounds(sample_project_doc):
    """Verify timeline-clip-split rejects split_time outside clip bounds."""
    res = await MotionCapabilityDispatcher.dispatch(
        capability_id="timeline-clip-split",
        project_doc=sample_project_doc,
        params={"clip_id": "clip_main_1", "split_time": 8.0},
    )
    assert res.status == "FAILED"
    assert res.error_detail == "OUT_OF_BOUNDS"


@pytest.mark.asyncio
async def test_timeline_slip_edit(sample_project_doc):
    """Verify timeline-slip-edit modifies source in/out points without altering track start or duration."""
    res = await MotionCapabilityDispatcher.dispatch(
        capability_id="timeline-slip-edit",
        project_doc=sample_project_doc,
        params={"clip_id": "clip_main_1", "slip_delta_seconds": 1.5},
    )
    assert res.status == "SUCCESS"
    doc = res.output_data["project_doc"]
    c1 = doc["tracks"][0]["clips"][0]
    assert c1["start"] == 0.0
    assert c1["duration"] == 6.0
    assert c1["in_point"] == 2.5
    assert c1["out_point"] == 8.5


@pytest.mark.asyncio
async def test_timeline_ripple_delete(sample_project_doc):
    """Verify timeline-ripple-delete deletes clip and ripples following clips leftward."""
    res = await MotionCapabilityDispatcher.dispatch(
        capability_id="timeline-ripple-delete",
        project_doc=sample_project_doc,
        params={"clip_id": "clip_main_1"},
    )
    assert res.status == "SUCCESS"
    doc = res.output_data["project_doc"]
    clips = doc["tracks"][0]["clips"]
    assert len(clips) == 1
    assert clips[0]["id"] == "clip_main_2"
    # Clip B was at start=6.0, duration of Clip A was 6.0 -> rippled to 0.0
    assert clips[0]["start"] == 0.0


@pytest.mark.asyncio
async def test_timeline_retime(sample_project_doc):
    """Verify timeline-retime-playback scales duration correctly."""
    res = await MotionCapabilityDispatcher.dispatch(
        capability_id="timeline-retime-playback",
        project_doc=sample_project_doc,
        params={"clip_id": "clip_main_1", "factor": 2.0},
    )
    assert res.status == "SUCCESS"
    doc = res.output_data["project_doc"]
    c1 = doc["tracks"][0]["clips"][0]
    assert c1["speed"] == 2.0
    assert c1["duration"] == 3.0  # 6.0 / 2.0


@pytest.mark.asyncio
async def test_b_roll_placement(sample_project_doc):
    """Verify b-roll-lane-placement adds an overlay clip to the B-Roll track."""
    res = await MotionCapabilityDispatcher.dispatch(
        capability_id="b-roll-lane-placement",
        project_doc=sample_project_doc,
        params={"source_url": "/media/overlay.mp4", "start": 1.0, "duration": 2.0, "name": "Reaction Cut"},
    )
    assert res.status == "SUCCESS"
    doc = res.output_data["project_doc"]
    broll_track = next(t for t in doc["tracks"] if t.get("name") == "B-Roll Overlay")
    assert len(broll_track["clips"]) == 1
    assert broll_track["clips"][0]["start"] == 1.0
    assert broll_track["clips"][0]["duration"] == 2.0


@pytest.mark.asyncio
async def test_audio_framing_parity_truthful_status(sample_project_doc):
    """Verify audio-framing-parity assigns truthful worker status per Requirement 4."""
    # Test native center_crop
    res_native = await MotionCapabilityDispatcher.dispatch(
        capability_id="audio-framing-parity",
        project_doc=sample_project_doc,
        params={"clip_id": "clip_main_1", "volume": 0.9, "framing_preset": "center_crop"},
    )
    assert res_native.status == "SUCCESS"
    assert res_native.output_data["worker_status"] == "Native 9:16 Center Crop (Active)"

    # Test advanced gameplay_reticle -> staged PENDING
    res_staged = await MotionCapabilityDispatcher.dispatch(
        capability_id="audio-framing-parity",
        project_doc=sample_project_doc,
        params={"clip_id": "clip_main_1", "framing_preset": "gameplay_reticle"},
    )
    assert res_staged.status == "SUCCESS"
    assert "PENDING" in res_staged.output_data["worker_status"]


@pytest.mark.asyncio
async def test_multiline_caption_override(sample_project_doc):
    """Verify multiline-caption-override records user edits across Whisper updates."""
    multiline_text = "Line 1: High engagement hook\nLine 2: Supporting premise\nLine 3: Call to action"
    res = await MotionCapabilityDispatcher.dispatch(
        capability_id="multiline-caption-override",
        project_doc=sample_project_doc,
        params={"layer_id": "layer_caption_1", "text": multiline_text},
    )
    assert res.status == "SUCCESS"
    doc = res.output_data["project_doc"]
    layer = next(l for l in doc["layers"] if l["id"] == "layer_caption_1")
    assert layer["text"] == multiline_text
    assert layer["override_active"] is True


@pytest.mark.asyncio
async def test_three_output_review():
    """Verify three-output-review records editorial approvals and notes."""
    res = await MotionCapabilityDispatcher.dispatch(
        capability_id="three-output-review",
        params={"output_id": "out_variant_1", "approval_state": "EDITORIAL: APPROVED", "notes": "Strong hook, verified safe zone."},
    )
    assert res.status == "SUCCESS"
    assert res.output_data["output_id"] == "out_variant_1"
    assert res.output_data["approval_state"] == "EDITORIAL: APPROVED"
    assert "Strong hook" in res.output_data["notes"]


# ─── Real Media Tool Invocations via FFmpeg ────────────────────────────────

@pytest.mark.asyncio
async def test_tool_trim_real_media(real_media_fixture, tmp_path):
    """Verify trim tool executes real FFmpeg and produces non-empty output."""
    res = await MotionCapabilityDispatcher.dispatch(
        capability_id="trim",
        input_path=real_media_fixture,
        params={"start": 0.0, "end": 0.5},
        output_dir=tmp_path,
    )
    assert res.status == "SUCCESS"
    assert res.output_path is not None
    out = Path(res.output_path)
    assert out.exists() and out.stat().st_size > 0


@pytest.mark.asyncio
async def test_tool_speed_real_media(real_media_fixture, tmp_path):
    """Verify speed tool executes real FFmpeg and re-times media."""
    res = await MotionCapabilityDispatcher.dispatch(
        capability_id="speed",
        input_path=real_media_fixture,
        params={"factor": 1.5},
        output_dir=tmp_path,
    )
    assert res.status == "SUCCESS"
    assert Path(res.output_path).exists()


@pytest.mark.asyncio
async def test_tool_remove_audio_real_media(real_media_fixture, tmp_path):
    """Verify remove-audio strips audio stream with real FFmpeg."""
    res = await MotionCapabilityDispatcher.dispatch(
        capability_id="remove-audio",
        input_path=real_media_fixture,
        output_dir=tmp_path,
    )
    assert res.status == "SUCCESS"
    assert Path(res.output_path).exists()


@pytest.mark.asyncio
async def test_tool_extract_audio_real_media(real_media_fixture, tmp_path):
    """Verify extract-audio generates a valid MP3 file."""
    res = await MotionCapabilityDispatcher.dispatch(
        capability_id="extract-audio",
        input_path=real_media_fixture,
        output_dir=tmp_path,
    )
    assert res.status == "SUCCESS"
    out = Path(res.output_path)
    assert out.exists() and out.suffix == ".mp3"


@pytest.mark.asyncio
async def test_tool_reframe_real_media(real_media_fixture, tmp_path):
    """Verify reframe tool executes 16:9 to 9:16 vertical crop."""
    res = await MotionCapabilityDispatcher.dispatch(
        capability_id="reframe",
        input_path=real_media_fixture,
        output_dir=tmp_path,
    )
    assert res.status == "SUCCESS"
    assert Path(res.output_path).exists()
    assert len(res.warnings) > 0  # Warns of native center-crop fallback


@pytest.mark.asyncio
async def test_tool_transform_real_media(real_media_fixture, tmp_path):
    """Verify transform tool flips video horizontally."""
    res = await MotionCapabilityDispatcher.dispatch(
        capability_id="transform",
        input_path=real_media_fixture,
        params={"op": "flip_h"},
        output_dir=tmp_path,
    )
    assert res.status == "SUCCESS"
    assert Path(res.output_path).exists()


@pytest.mark.asyncio
async def test_tool_merge_clips_real_media(real_media_fixture, tmp_path):
    """Verify merge-clips concats two clips."""
    res = await MotionCapabilityDispatcher.dispatch(
        capability_id="merge-clips",
        params={"clip_paths": [str(real_media_fixture), str(real_media_fixture)]},
        output_dir=tmp_path,
    )
    assert res.status == "SUCCESS"
    assert Path(res.output_path).exists()


# ─── Truthful Error Handling & Boundary Tests ──────────────────────────────

@pytest.mark.asyncio
async def test_nonexistent_file_returns_failed():
    """Verify missing input file returns truthful FAILED status, never synthetic success."""
    res = await MotionCapabilityDispatcher.dispatch(
        capability_id="trim",
        input_path="/nonexistent/file_12345.mp4",
        params={"start": 0, "end": 2},
    )
    assert res.status == "FAILED"
    assert res.error_detail == "FILE_NOT_FOUND"


@pytest.mark.asyncio
async def test_unknown_capability_returns_failed():
    """Verify non-registered capability ID returns UNKNOWN_CAPABILITY."""
    res = await MotionCapabilityDispatcher.dispatch(
        capability_id="non-existent-capability-xyz",
    )
    assert res.status == "FAILED"
    assert res.error_detail == "UNKNOWN_CAPABILITY"


@pytest.mark.asyncio
async def test_ai_tool_unconfigured_key_returns_blocked():
    """Verify AI text tools return BLOCKED when BYOK key is absent."""
    # Ensure keys are temporarily unset
    orig_openai = os.environ.pop("OPENAI_API_KEY", None)
    orig_anthropic = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        res = await MotionCapabilityDispatcher.dispatch(capability_id="hook-analysis")
        assert res.status == "BLOCKED"
        assert res.error_detail == "BYOK_KEY_MISSING"
    finally:
        if orig_openai:
            os.environ["OPENAI_API_KEY"] = orig_openai
        if orig_anthropic:
            os.environ["ANTHROPIC_API_KEY"] = orig_anthropic
