# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 7 test suite: Real FFmpeg multi-track export, Catalog export consumer, and Main Agent CAS capability dispatch."""

import asyncio
import json
import os
import subprocess
from pathlib import Path
import pytest
from fastapi import HTTPException

from backend.database import init_db
from backend.media_pipeline.clip_renderer import build_framing_filter, render_manifest_to_mp4
from backend.media_pipeline.media_inspector import probe_physical_media
from backend.motion_capabilities import (
    MotionCapabilitiesRegistry,
    MotionToolRunnerAdapter,
    execute_motion_capability,
)
from backend.motion_render_bridge import (
    CatalogExportConsumer,
    CatalogExportConsumptionResult,
    build_render_manifest,
)
from backend.services.project_service import ProjectService


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Ensure database schema is created for test execution."""
    await init_db()


@pytest.fixture(scope="module")
def sample_video_mp4(tmp_path_factory) -> Path:
    """Generate a real short 1.0-second 1920x1080 MP4 test video with audio using FFmpeg."""
    tmp_dir = tmp_path_factory.mktemp("wave7_media")
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


@pytest.fixture(scope="module")
def sample_alpha_overlay_png(tmp_path_factory) -> Path:
    """Generate a real transparent 1080x1920 PNG overlay with alpha channel."""
    tmp_dir = tmp_path_factory.mktemp("wave7_overlay")
    overlay_path = tmp_dir / "sample_overlay.png"
    # Create an RGBA image with a colored box and transparent background
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=color=red@0.0:size=1080x1920,drawbox=x=100:y=100:w=400:h=200:color=yellow@0.8:t=fill",
        "-frames:v", "1",
        str(overlay_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert res.returncode == 0, f"FFmpeg overlay generation failed: {res.stderr}"
    assert overlay_path.exists()
    return overlay_path


# ─── 1. Catalog Export Consumer ─────────────────────────────────────────────

def test_catalog_export_consumer_valid_manifest():
    """Verify CatalogExportConsumer parses a CatalogExportContract manifest correctly."""
    manifest = {
        "schema_version": "1.0.0",
        "contract_type": "MOTION_BLOCK_EXPORT_MANIFEST",
        "block_id": "lower_third_minimal",
        "instance_id": "inst_lt_001",
        "aspect_ratio": "9:16",
        "viewport": {"width": 1080, "height": 1920, "aspect_ratio_decimal": 0.5625},
        "timeline_parameters": {
            "duration_seconds": 3.0,
            "fps": 30,
            "total_frames": 90,
            "frame_step_seconds": 0.033333,
        },
        "rendering_channel": {
            "alpha_channel_required": True,
            "pixel_format_target": "yuva420p",
            "recommended_codec": "png",
            "stage_background_color": "transparent",
        },
    }

    result = CatalogExportConsumer.consume(manifest, canvas_width=1080, canvas_height=1920)
    assert isinstance(result, CatalogExportConsumptionResult)
    assert result.block_id == "lower_third_minimal"
    assert result.alpha_channel_required is True
    assert result.target_pixel_format == "yuva420p"
    assert result.mp4_parity_status == "NOT_TESTED"
    assert "overlay=" in result.overlay_filter_expression
    assert "format=auto" in result.overlay_filter_expression


def test_catalog_export_consumer_invalid_manifest():
    """Verify CatalogExportConsumer rejects invalid or corrupted manifest data."""
    with pytest.raises(Exception):
        CatalogExportConsumer.consume({"contract_type": "WRONG_CONTRACT"})


# ─── 2. Real FFmpeg Multi-Track Export ───────────────────────────────────────

@pytest.mark.asyncio
async def test_render_manifest_to_mp4_center_crop(sample_video_mp4, tmp_path):
    """Verify render_manifest_to_mp4 produces valid 9:16 MP4 using center_crop."""
    out_file = tmp_path / "rendered_center_crop.mp4"
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
                            "speed_multiplier": 1.0,
                            "framing_preset": "center_crop",
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
    assert probe.duration_seconds >= 0.4
    assert probe.video_codec in ("h264", "libx264")


@pytest.mark.asyncio
async def test_render_manifest_to_mp4_gameplay_reticle(sample_video_mp4, tmp_path):
    """Verify render_manifest_to_mp4 applies gameplay_reticle framing preset."""
    out_file = tmp_path / "rendered_reticle.mp4"
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
                            "framing_preset": "gameplay_reticle",
                        }
                    ],
                }
            ],
        },
    }
    manifest = build_render_manifest(timeline_doc)
    res_path, probe, warnings = await render_manifest_to_mp4(manifest, out_file)
    assert res_path.exists()
    assert probe.width == 1080
    assert probe.height == 1920


@pytest.mark.asyncio
async def test_render_manifest_to_mp4_hud_aware_blur(sample_video_mp4, tmp_path):
    """Verify render_manifest_to_mp4 applies complex hud_aware_blur filter graph."""
    out_file = tmp_path / "rendered_hud_blur.mp4"
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
                            "framing_preset": "hud_aware_blur",
                        }
                    ],
                }
            ],
        },
    }
    manifest = build_render_manifest(timeline_doc)
    res_path, probe, warnings = await render_manifest_to_mp4(manifest, out_file)
    assert res_path.exists()
    assert probe.width == 1080
    assert probe.height == 1920


@pytest.mark.asyncio
async def test_render_manifest_to_mp4_speed_retime(sample_video_mp4, tmp_path):
    """Verify speed_multiplier modifies playback duration via PTS and atempo."""
    out_file = tmp_path / "rendered_speed_2x.mp4"
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
                            "speed_multiplier": 2.0,
                            "framing_preset": "center_crop",
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
    # At 2.0x speed, 0.5s segment renders in ~0.25s
    assert probe.duration_seconds <= 0.45


@pytest.mark.asyncio
async def test_render_manifest_to_mp4_audio_mute_isolation(sample_video_mp4, tmp_path):
    """Verify muting track results in an MP4 without audio stream."""
    out_file = tmp_path / "rendered_muted.mp4"
    timeline_doc = {
        "schema_version": 2,
        "aspect_ratio": "9:16",
        "timeline": {
            "fps": 30,
            "tracks": [
                {
                    "id": "track_v1",
                    "type": "video",
                    "muted": True,
                    "clips": [
                        {
                            "id": "clip_v1",
                            "source_path": str(sample_video_mp4),
                            "source_trim_start": 0.0,
                            "timeline_duration_seconds": 0.5,
                            "framing_preset": "center_crop",
                        }
                    ],
                }
            ],
        },
    }
    manifest = build_render_manifest(timeline_doc)
    res_path, probe, warnings = await render_manifest_to_mp4(manifest, out_file)
    assert res_path.exists()
    assert probe.audio_codec in (None, "none")


@pytest.mark.asyncio
async def test_render_manifest_with_catalog_overlay(sample_video_mp4, sample_alpha_overlay_png, tmp_path):
    """Verify render_manifest_to_mp4 composites alpha catalog overlay onto base video."""
    out_file = tmp_path / "rendered_with_overlay.mp4"
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
                        }
                    ],
                }
            ],
        },
    }
    manifest = build_render_manifest(timeline_doc)
    catalog_manifest = {
        "schema_version": "1.0.0",
        "contract_type": "MOTION_BLOCK_EXPORT_MANIFEST",
        "block_id": "test_box_overlay",
        "aspect_ratio": "9:16",
        "viewport": {"width": 1080, "height": 1920},
        "timeline_parameters": {"duration_seconds": 0.5, "fps": 30},
        "rendering_channel": {
            "alpha_channel_required": True,
            "pixel_format_target": "yuva420p",
        },
    }

    res_path, probe, warnings = await render_manifest_to_mp4(
        manifest_data=manifest,
        output_path=out_file,
        catalog_overlay_path=sample_alpha_overlay_png,
        catalog_overlay_manifest=catalog_manifest,
    )
    assert res_path.exists()
    assert probe.width == 1080
    assert probe.height == 1920


# ─── 3. Main Agent / Planner Capability Dispatch ───────────────────────────

@pytest.mark.asyncio
async def test_execute_motion_capability_cas_concurrency(sample_video_mp4):
    """Verify execute_motion_capability raises HTTPException 409 on stale revision and mutates revision on match."""
    proj = await ProjectService.create_project(
        name="Planner Dispatch Test",
        aspect_ratio="9:16",
        initial_document={"version": 1, "tracks": []},
        user_id="planner_test",
    )
    current_rev = proj.revision

    # 1. Stale revision mismatch -> raises 409
    with pytest.raises(HTTPException) as exc_info:
        await execute_motion_capability(
            project_id=proj.id,
            expected_revision=current_rev + 999,
            capability_id="trim",
            params={"start": 0.0, "end": 0.5},
            input_path=sample_video_mp4,
        )
    assert exc_info.value.status_code == 409
    assert "Stale revision conflict" in exc_info.value.detail

    # 2. Matching revision -> executes and increments revision
    outcome = await execute_motion_capability(
        project_id=proj.id,
        expected_revision=current_rev,
        capability_id="trim",
        params={"start": 0.0, "end": 0.5},
        input_path=sample_video_mp4,
    )
    assert outcome["success"] is True
    assert outcome["status"] == "SUCCESS"
    assert outcome["previous_revision"] == current_rev
    assert outcome["current_revision"] == current_rev + 1

    # Verify project reloaded from database reflects mutated revision and attached clip
    reloaded = await ProjectService.get_project(proj.id)
    assert reloaded.revision == current_rev + 1
    doc = json.loads(reloaded.document_json) if isinstance(reloaded.document_json, str) else reloaded.document_json
    assert "tracks" in doc


# ─── 4. Adversarial Mock Audit ──────────────────────────────────────────────

def test_wave7_adversarial_mock_scan():
    """Verify production code in Role 2 owned modules does not contain test doubles or synthetic mocks."""
    production_dirs = [
        Path("backend/motion_capabilities"),
        Path("backend/motion_render_bridge"),
    ]
    forbidden_tokens = ["unittest.mock", "MagicMock", "AsyncMock"]

    for p_dir in production_dirs:
        for py_file in p_dir.glob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                assert token not in content, f"Forbidden mock token '{token}' detected in production file {py_file}."

    # Check clip_renderer.py
    clip_renderer_content = Path("backend/media_pipeline/clip_renderer.py").read_text(encoding="utf-8")
    for token in forbidden_tokens:
        assert token not in clip_renderer_content, f"Forbidden mock token '{token}' in clip_renderer.py."
