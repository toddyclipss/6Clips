# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 6 test suite: Deterministic FFmpeg framing filter chains and clip renderer execution."""

import asyncio
import subprocess
from pathlib import Path
import pytest

from backend.database import init_db
from backend.media_pipeline.clip_renderer import build_framing_filter, render_output_clip
from backend.media_pipeline.media_inspector import probe_physical_media
from backend.media_pipeline.models import (
    DurationPolicy,
    OutputResultV1,
    OutputSpecV1,
    OutputState,
    SourceRangeV1,
)


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Ensure database schema exists for ProjectService."""
    await init_db()


@pytest.fixture(scope="module")
def real_16x9_fixture(tmp_path_factory):
    """Generate a real 1-second 1280x720 (16:9) MP4 media fixture with audio using local FFmpeg."""
    tmp_dir = tmp_path_factory.mktemp("framing_media")
    video_path = tmp_dir / "sample_16x9.mp4"
    cmd = [
        "ffmpeg", "-y", "-hide_banner",
        "-f", "lavfi", "-i", "testsrc=duration=1.0:size=1280x720:rate=24",
        "-f", "lavfi", "-i", "aevalsrc=sin(440*2*PI*t):s=44100:d=1.0",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac",
        str(video_path),
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert res.returncode == 0, f"FFmpeg fixture generation failed: {res.stderr}"
    assert video_path.exists() and video_path.stat().st_size > 0
    return video_path


# ─── Framing Filter Chain Formulation Tests ────────────────────────────────

def test_build_framing_filter_center_crop():
    """Verify center_crop builds standard 9:16 crop filter."""
    expr, warnings, is_complex = build_framing_filter(1920, 1080, 1080, 1920, "center_crop")
    assert is_complex is False
    assert "crop=1080:1920" in expr
    assert any("Center crop 9:16 applied" in w for w in warnings)


def test_build_framing_filter_hud_aware_blur():
    """Verify hud_aware_blur builds complex filter with boxblur and centered crisp overlay."""
    expr, warnings, is_complex = build_framing_filter(1920, 1080, 1080, 1920, "hud_aware_blur")
    assert is_complex is True
    assert "boxblur=" in expr
    assert "overlay=0:(H-h)/2" in expr
    assert any("hud_aware_blur applied" in w for w in warnings)


def test_build_framing_filter_gameplay_reticle():
    """Verify gameplay_reticle preserves HUD radar and crosshair safe zones."""
    expr, warnings, is_complex = build_framing_filter(1920, 1080, 1080, 1920, "gameplay_reticle")
    assert is_complex is False
    assert "scale=1080:1920" in expr
    assert any("gameplay_reticle applied" in w for w in warnings)


def test_build_framing_filter_split_facecam_gameplay():
    """Verify split_facecam_gameplay builds vertical stacked layout."""
    expr, warnings, is_complex = build_framing_filter(1920, 1080, 1080, 1920, "split_facecam_gameplay")
    assert is_complex is True
    assert "vstack=inputs=2" in expr
    assert any("split_facecam_gameplay applied" in w for w in warnings)


def test_build_framing_filter_insufficient_geometry_fallback():
    """Verify split_facecam_gameplay falls back to center crop on low resolution source."""
    expr, warnings, is_complex = build_framing_filter(320, 240, 1080, 1920, "split_facecam_gameplay")
    assert is_complex is False  # Fell back to simple crop
    assert any("insufficient" in w.lower() for w in warnings)


def test_build_framing_filter_unsupported_preset_fallback():
    """Verify unsupported preset falls back to center crop with truthful warning."""
    expr, warnings, is_complex = build_framing_filter(1920, 1080, 1080, 1920, "nonexistent_preset_xyz")
    assert is_complex is False
    assert any("Unsupported framing preset" in w for w in warnings)


# ─── Real Media Clip Renderer Execution Tests ──────────────────────────────

@pytest.mark.asyncio
async def test_render_output_clip_center_crop(real_16x9_fixture, tmp_path):
    """Verify real render of center_crop produces verified 1080x1920 MP4."""
    spec = OutputSpecV1(output_id="out_test_center", seconds=1.0, duration_policy=DurationPolicy.TARGET)
    srange = SourceRangeV1(asset_id="test_asset", start_seconds=0.0, end_seconds=1.0, duration_seconds=1.0, editorial_reason="Hook scene")

    res = await render_output_clip(
        source_path=real_16x9_fixture,
        source_range=srange,
        spec=spec,
        project_id="test_proj_1",
        output_dir=tmp_path,
        framing_preset="center_crop",
    )
    assert res.state == OutputState.SUCCEEDED
    assert res.media_probe is not None
    assert res.media_probe.width == 1080
    assert res.media_probe.height == 1920
    assert res.media_probe.video_codec in ("h264", "avc1")
    assert res.checks.technical == "PASS"


@pytest.mark.asyncio
async def test_render_output_clip_hud_aware_blur(real_16x9_fixture, tmp_path):
    """Verify real render of hud_aware_blur produces 1080x1920 MP4 with blurred background."""
    spec = OutputSpecV1(output_id="out_test_blur", seconds=1.0, duration_policy=DurationPolicy.TARGET)
    srange = SourceRangeV1(asset_id="test_asset", start_seconds=0.0, end_seconds=1.0, duration_seconds=1.0, editorial_reason="Gameplay HUD")

    res = await render_output_clip(
        source_path=real_16x9_fixture,
        source_range=srange,
        spec=spec,
        project_id="test_proj_2",
        output_dir=tmp_path,
        framing_preset="hud_aware_blur",
    )
    assert res.state == OutputState.SUCCEEDED
    assert res.media_probe.width == 1080
    assert res.media_probe.height == 1920
    assert any("hud_aware_blur" in w for w in res.warnings)


@pytest.mark.asyncio
async def test_render_output_clip_split_facecam(real_16x9_fixture, tmp_path):
    """Verify real render of split_facecam_gameplay produces 1080x1920 stacked MP4."""
    spec = OutputSpecV1(output_id="out_test_split", seconds=1.0, duration_policy=DurationPolicy.TARGET)
    srange = SourceRangeV1(asset_id="test_asset", start_seconds=0.0, end_seconds=1.0, duration_seconds=1.0, editorial_reason="Facecam reaction")

    res = await render_output_clip(
        source_path=real_16x9_fixture,
        source_range=srange,
        spec=spec,
        project_id="test_proj_3",
        output_dir=tmp_path,
        framing_preset="split_facecam_gameplay",
    )
    assert res.state == OutputState.SUCCEEDED
    assert res.media_probe.width == 1080
    assert res.media_probe.height == 1920
    assert any("split_facecam_gameplay" in w for w in res.warnings)


@pytest.mark.asyncio
async def test_render_output_clip_simulate_failure(real_16x9_fixture, tmp_path):
    """Verify simulate_failure gracefully returns FAILED status with error detail."""
    spec = OutputSpecV1(output_id="out_test_fail", seconds=1.0)
    srange = SourceRangeV1(asset_id="test_asset", start_seconds=0.0, end_seconds=1.0, duration_seconds=1.0, editorial_reason="Failure test")

    res = await render_output_clip(
        source_path=real_16x9_fixture,
        source_range=srange,
        spec=spec,
        project_id="test_proj_4",
        output_dir=tmp_path,
        simulate_failure=True,
    )
    assert res.state == OutputState.FAILED
    assert res.checks.technical == "FAIL"
    assert "Simulated render pipeline execution failure" in res.error_detail
