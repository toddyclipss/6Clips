# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Acceptance test suite for B4 & B5 — Preview & Render Parity for 16:9 -> 9:16 Media Production.

Tests:
1. Reframe geometry parity: 16:9 input produces verified 9:16 (1080x1920) output.
2. Audio stream synchronization and non-synthetic preservation.
3. Caption offset retiming: subtitles align with trimmed start time (relative t=0).
4. Full database isolation.
"""

import hashlib
import json
import subprocess
from pathlib import Path
import pytest

from backend.media_pipeline.clip_renderer import _build_reframe_filter, render_output_clip
from backend.media_pipeline.media_inspector import probe_physical_media
from backend.media_pipeline.models import (
    DurationPolicy,
    OutputSpecV1,
    OutputState,
    SourceRangeV1,
)

PROD_DB_PATH = Path("c:/Users/toddy/Desktop/ViralMint/viralmint.db")


def get_file_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().upper()


@pytest.fixture(autouse=True)
def verify_production_db_isolation():
    assert PROD_DB_PATH.exists(), "Production DB must exist"
    pre_hash = get_file_sha256(PROD_DB_PATH)
    yield
    post_hash = get_file_sha256(PROD_DB_PATH)
    assert pre_hash == post_hash, f"Production DB modified! Pre: {pre_hash}, Post: {post_hash}"


def create_16x9_test_source(target_path: Path, duration_s: int = 20) -> Path:
    """Create a 16:9 1920x1080 video with distinct visuals and stereo tone."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={duration_s}:size=1920x1080:rate=30",
        "-f", "lavfi", "-i", f"sine=frequency=523:duration={duration_s}",
        "-vf", "drawbox=x=860:y=440:w=200:h=200:color=yellow@0.8:t=fill,drawbox=x=950:y=530:w=20:h=20:color=white@0.9:t=fill",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        str(target_path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)
    return target_path


@pytest.mark.asyncio
async def test_reframe_filter_geometry():
    """B4 — Filter geometry calculation: 16:9 produces 1080:1920 crop-center filter."""
    vf_169 = _build_reframe_filter(1920, 1080, 1080, 1920)
    assert "scale=1080:1920" in vf_169
    assert "crop=1080:1920" in vf_169

    vf_916 = _build_reframe_filter(1080, 1920, 1080, 1920)
    assert vf_916 == "scale=1080:1920"


@pytest.mark.asyncio
async def test_preview_render_parity_execution(tmp_path):
    """B4 & B5 — Rendered output has exact 9:16 dimension parity and audible audio."""
    src_path = tmp_path / "source_16x9.mp4"
    create_16x9_test_source(src_path, duration_s=15)

    source_range = SourceRangeV1(
        asset_id="src_16x9",
        start_seconds=2.0,
        end_seconds=10.0,
        duration_seconds=8.0,
        editorial_reason="Central engagement highlight",
        relevance_score=9.2,
    )
    spec = OutputSpecV1(
        output_id="parity_clip_1",
        aspect_ratio="9:16",
        seconds=8.0,
        duration_policy=DurationPolicy.EXACT,
    )

    out_dir = tmp_path / "renders"
    out_dir.mkdir(parents=True, exist_ok=True)

    result = await render_output_clip(
        source_path=src_path,
        source_range=source_range,
        spec=spec,
        project_id="proj_parity_test",
        output_dir=out_dir,
    )

    assert result.state == OutputState.SUCCEEDED
    assert result.checks.technical == "PASS"
    assert result.checks.contract == "PASS"

    probe = result.media_probe
    assert probe is not None
    assert probe.width == 1080
    assert probe.height == 1920
    assert 7.5 <= probe.duration_seconds <= 8.5
    assert probe.audio_codec == "aac"
    assert probe.is_silent is False


def test_caption_offset_retiming_logic():
    """B4 — Captions alignment retiming: transcript segments offset relative to clip start."""
    from backend.services.clip_extractor import _filter_and_offset_segments

    raw_segments = [
        {"start": 1.0, "end": 3.0, "text": "intro before clip"},
        {"start": 5.0, "end": 8.0, "text": "watch this play"},
        {"start": 9.0, "end": 12.0, "text": "squad defeated"},
        {"start": 16.0, "end": 18.0, "text": "after clip"},
    ]

    # Clip starts at 5.0 and ends at 13.0
    clip_start = 5.0
    clip_end = 13.0
    retimed = _filter_and_offset_segments(raw_segments, clip_start, clip_end)

    assert len(retimed) == 2
    # First segment: was 5.0-8.0 -> becomes 0.0-3.0
    assert retimed[0]["start"] == 0.0
    assert retimed[0]["end"] == 3.0
    assert retimed[0]["text"] == "watch this play"

    # Second segment: was 9.0-12.0 -> becomes 4.0-7.0
    assert retimed[1]["start"] == 4.0
    assert retimed[1]["end"] == 7.0
    assert retimed[1]["text"] == "squad defeated"
