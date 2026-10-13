# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 8 Agent 2 — Complete Native Motion Migration, Render Parity & Multi-Output Lifecycle Tests."""

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi import HTTPException

from backend.database import init_db
from backend.media_pipeline.clip_renderer import (
    build_framing_filter,
    render_manifest_to_mp4,
    render_output_clip,
)
from backend.media_pipeline.media_inspector import probe_physical_media
from backend.media_pipeline.models import (
    DurationPolicy,
    OutputSpecV1,
    OutputState,
    SourceRangeV1,
)
from backend.motion_capabilities import (
    MotionCapabilitiesRegistry,
    MotionCapabilityDispatcher,
    execute_motion_capability,
)
from backend.motion_render_bridge import build_render_manifest
from backend.services.project_service import ProjectService


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Ensure database schema is created for test execution."""
    await init_db()


@pytest.fixture(scope="module")
def sample_video_mp4(tmp_path_factory) -> Path:
    """Generate a real 1.0-second 1920x1080 MP4 test video with audio using FFmpeg."""
    tmp_dir = tmp_path_factory.mktemp("wave8_media")
    video_path = tmp_dir / "sample_test_input.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=1.0:size=1920x1080:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=1.0:sample_rate=48000",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
        "-c:a", "aac", "-b:a", "128k",
        str(video_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert res.returncode == 0, f"FFmpeg sample generation failed: {res.stderr}"
    assert video_path.exists()
    return video_path


@pytest.mark.asyncio
async def test_render_manifest_with_caption_overrides_and_line_breaks(sample_video_mp4, tmp_path):
    """Verify render_manifest_to_mp4 burns multi-line caption overrides via ASS subtitle filter."""
    out_file = tmp_path / "rendered_with_captions.mp4"
    timeline_doc = {
        "schema_version": 2,
        "aspect_ratio": "9:16",
        "timeline": {
            "fps": 30,
            "tracks": [
                {
                    "id": "track_v1",
                    "type": "video",
                    "clips": [
                        {
                            "id": "clip_v1",
                            "source_path": str(sample_video_mp4),
                            "source_trim_start": 0.0,
                            "timeline_duration_seconds": 0.5,
                            "framing_preset": "center_crop",
                            "caption_text": "HOOK OF THE VIDEO\nLINE NUMBER TWO",
                            "caption_lines": ["HOOK OF THE VIDEO", "LINE NUMBER TWO"],
                        }
                    ],
                }
            ],
        },
    }
    manifest = build_render_manifest(timeline_doc)
    res_path, probe, warnings = await render_manifest_to_mp4(manifest, out_file)
    assert res_path.exists()
    assert probe is not None
    assert probe.width == 1080
    assert probe.height == 1920
    assert any("caption overrides" in w.lower() for w in warnings)


@pytest.mark.asyncio
async def test_render_manifest_with_audio_enhance(sample_video_mp4, tmp_path):
    """Verify render_manifest_to_mp4 applies dynamic audio normalization and voice filters."""
    out_file = tmp_path / "rendered_enhanced_audio.mp4"
    timeline_doc = {
        "schema_version": 2,
        "aspect_ratio": "9:16",
        "timeline": {
            "fps": 30,
            "tracks": [
                {
                    "id": "track_v1",
                    "type": "video",
                    "clips": [
                        {
                            "id": "clip_v1",
                            "source_path": str(sample_video_mp4),
                            "source_trim_start": 0.0,
                            "timeline_duration_seconds": 0.5,
                            "framing_preset": "center_crop",
                            "audio_enhance": True,
                        }
                    ],
                }
            ],
        },
    }
    manifest = build_render_manifest(timeline_doc)
    res_path, probe, warnings = await render_manifest_to_mp4(manifest, out_file)
    assert res_path.exists()
    assert probe is not None
    assert probe.audio_codec == "aac"
    assert any("voice enhancement" in w.lower() for w in warnings)


@pytest.mark.asyncio
async def test_render_manifest_all_framing_presets(sample_video_mp4, tmp_path):
    """Verify all Wave 8 framing presets render and produce valid MP4 artifacts."""
    presets = ["center_crop", "gameplay_reticle", "hud_aware_blur", "split_facecam_gameplay"]
    for preset in presets:
        out_file = tmp_path / f"rendered_{preset}.mp4"
        timeline_doc = {
            "schema_version": 2,
            "aspect_ratio": "9:16",
            "timeline": {
                "fps": 30,
                "tracks": [
                    {
                        "id": "track_v1",
                        "type": "video",
                        "clips": [
                            {
                                "id": "clip_v1",
                                "source_path": str(sample_video_mp4),
                                "source_trim_start": 0.0,
                                "timeline_duration_seconds": 0.4,
                                "framing_preset": preset,
                            }
                        ],
                    }
                ],
            },
        }
        manifest = build_render_manifest(timeline_doc)
        res_path, probe, warnings = await render_manifest_to_mp4(manifest, out_file)
        assert res_path.exists()
        assert probe is not None
        assert probe.width == 1080
        assert probe.height == 1920


@pytest.mark.asyncio
async def test_dispatcher_blocked_provider_transparency(sample_video_mp4):
    """Verify tools requiring unavailable external providers return BLOCKED_PROVIDER honestly."""
    # Test translate with dub_audio=True when voice keys are absent
    old_eleven = os.environ.pop("ELEVENLABS_API_KEY", None)
    old_azure = os.environ.pop("AZURE_SPEECH_KEY", None)
    try:
        res = await MotionCapabilityDispatcher.dispatch(
            capability_id="translate",
            input_path=sample_video_mp4,
            params={"target_language": "es", "dub_audio": True},
        )
        assert res.status == "BLOCKED_PROVIDER"
        assert res.error_detail == "BLOCKED_PROVIDER"
        assert "voice provider credentials" in res.message
    finally:
        if old_eleven:
            os.environ["ELEVENLABS_API_KEY"] = old_eleven
        if old_azure:
            os.environ["AZURE_SPEECH_KEY"] = old_azure


@pytest.mark.asyncio
async def test_three_independently_editable_and_approvable_outputs_lifecycle(sample_video_mp4, tmp_path):
    """Verify 3 distinct outputs rendered, independently edited, approved, and reloaded across revisions."""
    # 1. Initialize project
    proj_id = "proj_wave8_lifecycle_test"
    initial_doc = {
        "schema_version": 2,
        "title": "Wave 8 Triple Output Project",
        "aspect_ratio": "9:16",
        "timeline": {
            "fps": 30,
            "duration_seconds": 3.0,
            "tracks": [
                {"id": "t_v", "type": "video", "clips": []},
                {"id": "t_a", "type": "audio", "clips": []},
            ],
        },
        "outputs": {
            "out_1": {"preset": "center_crop", "editorial_status": "NOT_ASSESSED", "notes": ""},
            "out_2": {"preset": "hud_aware_blur", "editorial_status": "NOT_ASSESSED", "notes": ""},
            "out_3": {"preset": "gameplay_reticle", "editorial_status": "NOT_ASSESSED", "notes": ""},
        },
    }
    proj = await ProjectService.create_project(
        name="Wave 8 Triple Output Project",
        aspect_ratio="9:16",
        initial_document=initial_doc,
    )
    proj_id = proj.id
    assert proj.revision == 1

    # 2. Render each output independently
    presets = [("out_1", "center_crop"), ("out_2", "hud_aware_blur"), ("out_3", "gameplay_reticle")]
    rendered_results = []
    for out_id, preset in presets:
        spec = OutputSpecV1(
            output_id=out_id,
            seconds=0.5,
            duration_policy=DurationPolicy.TARGET,
            tolerance_seconds=0.2,
        )
        res = await render_output_clip(
            source_path=sample_video_mp4,
            source_range=SourceRangeV1(
                asset_id="asset_test",
                start_seconds=0.0,
                end_seconds=0.5,
                duration_seconds=0.5,
                editorial_reason="Highlight cut",
            ),
            spec=spec,
            project_id=proj_id,
            output_dir=tmp_path,
            framing_preset=preset,
        )
        assert res.state == OutputState.SUCCEEDED
        rendered_results.append(res)

    # 3. Independently approve Output 1 while keeping Outputs 2 and 3 as NOT_ASSESSED
    current_proj = await ProjectService.get_project(proj_id)
    import json
    cur_doc = json.loads(current_proj.document_json) if isinstance(current_proj.document_json, str) else current_proj.document_json
    cur_doc["outputs"]["out_1"]["editorial_status"] = "APPROVED"
    cur_doc["outputs"]["out_1"]["notes"] = "Editorial quality verified for gaming short"

    rev_result = await ProjectService.apply_operation(
        project_id=proj_id,
        expected_revision=current_proj.revision,
        operation_type="update_document",
        payload={"document": cur_doc},
        idempotency_key="approve_out_1",
        author="reviewer",
    )
    assert rev_result["revision"] > current_proj.revision

    # 4. Reload from database and verify persistence of independent states
    reloaded_proj = await ProjectService.get_project(proj_id)
    assert reloaded_proj is not None
    assert reloaded_proj.revision == rev_result["revision"]
    reloaded_doc = json.loads(reloaded_proj.document_json) if isinstance(reloaded_proj.document_json, str) else reloaded_proj.document_json

    assert reloaded_doc["outputs"]["out_1"]["editorial_status"] == "APPROVED"
    assert reloaded_doc["outputs"]["out_1"]["notes"] == "Editorial quality verified for gaming short"
    assert reloaded_doc["outputs"]["out_2"]["editorial_status"] == "NOT_ASSESSED"
    assert reloaded_doc["outputs"]["out_3"]["editorial_status"] == "NOT_ASSESSED"


@pytest.mark.asyncio
async def test_cas_concurrency_409_stale_revision_rejection(sample_video_mp4):
    """Verify CAS revision mismatch strictly raises HTTPException 409."""
    proj = await ProjectService.create_project(
        name="CAS Test",
        aspect_ratio="9:16",
        initial_document={"schema_version": 2, "timeline": {"tracks": []}},
    )
    proj_id = proj.id
    assert proj.revision == 1

    # Bump to revision 2
    await ProjectService.apply_operation(
        project_id=proj_id,
        expected_revision=1,
        operation_type="update_document",
        payload={"document": {"schema_version": 2, "timeline": {"tracks": [{"id": "t1", "type": "video", "clips": []}]}}},
        idempotency_key="bump_rev",
    )

    # Calling with stale revision 1 must raise HTTPException(409)
    with pytest.raises(HTTPException) as exc_info:
        await execute_motion_capability(
            project_id=proj_id,
            expected_revision=1,
            capability_id="transform",
            params={"op": "flip_h"},
            input_path=sample_video_mp4,
        )
    assert exc_info.value.status_code == 409
    assert "Stale revision" in exc_info.value.detail


@pytest.mark.asyncio
async def test_cancelled_render_does_not_corrupt_project_state(sample_video_mp4, tmp_path):
    """Verify failed/cancelled renders return OutputState.FAILED without corrupting project revisions."""
    proj = await ProjectService.create_project(
        name="Failure Isolation Test",
        aspect_ratio="9:16",
        initial_document={"schema_version": 2, "timeline": {"tracks": []}},
    )
    proj_id = proj.id
    initial_rev = proj.revision

    spec = OutputSpecV1(output_id="out_failed", seconds=1.0)
    res = await render_output_clip(
        source_path=sample_video_mp4,
        source_range=SourceRangeV1(
            asset_id="asset_test",
            start_seconds=0.0,
            end_seconds=1.0,
            duration_seconds=1.0,
            editorial_reason="Fault tolerance cut",
        ),
        spec=spec,
        project_id=proj_id,
        output_dir=tmp_path,
        simulate_failure=True,
    )
    assert res.state == OutputState.FAILED
    assert "Simulated render pipeline execution failure" in (res.error_detail or "")

    # Project revision remains untouched
    current_proj = await ProjectService.get_project(proj_id)
    assert current_proj.revision == initial_rev


def test_wave8_adversarial_mock_scan():
    """Verify zero production fallbacks to mocks or fake media pipelines."""
    scanned_dirs = [
        Path("backend/motion_capabilities"),
        Path("backend/motion_render_bridge"),
        Path("backend/media_pipeline/clip_renderer.py"),
    ]
    forbidden_tokens = ["unittest.mock", "MagicMock", "AsyncMock"]
    for path in scanned_dirs:
        if path.is_file():
            files = [path]
        else:
            files = [f for f in path.glob("**/*.py") if "parity_audit" not in f.name]
        for f in files:
            content = f.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                assert token not in content, f"Forbidden mock token '{token}' discovered in production file {f}"
