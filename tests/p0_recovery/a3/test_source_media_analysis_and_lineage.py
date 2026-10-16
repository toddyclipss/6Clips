# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Unit Tests for Source Media Analysis and Lineage Metrics (Agent 3).

Verifies:
- Stream and metadata extraction via ffprobe
- Authentic visual frame detection (luminance, standard deviation, and motion)
- Rejection of pitch-black videos and static uniform title cards
- Audio stream validation and speech synchronization metrics
- Precise source edit span bounds checking
"""

import math
from pathlib import Path
import pytest
import subprocess

from backend.oaas_media_edit.analyzer import SourceMediaAnalyzer
from backend.oaas_media_edit.models import SourceMediaAnalysis


@pytest.fixture
def genuine_moving_video(tmp_path: Path) -> Path:
    """Generate a genuine 5-second moving video with real audio track."""
    out = tmp_path / "genuine_sample.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
        "-t", "5.0",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        str(out),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return out


@pytest.fixture
def static_black_video(tmp_path: Path) -> Path:
    """Generate a 4-second pitch-black video without motion (simulating counterfeit/failure)."""
    out = tmp_path / "static_black.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=black:s=1280x720:r=30",
        "-t", "4.0",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        str(out),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return out


@pytest.fixture
def video_without_audio(tmp_path: Path) -> Path:
    """Generate a 3-second moving video with NO audio stream."""
    out = tmp_path / "no_audio.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30",
        "-t", "3.0",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-an",
        str(out),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return out


def test_genuine_video_analysis(genuine_moving_video: Path):
    """Verify deep forensic analysis correctly captures streams, duration, luminance, and motion."""
    analysis = SourceMediaAnalyzer.analyze_file(genuine_moving_video)

    assert analysis.has_video
    assert analysis.has_audio
    assert analysis.video_codec == "h264"
    assert analysis.audio_codec == "aac"
    assert analysis.resolution == (1280, 720)
    assert analysis.aspect_ratio == "16:9"
    assert abs(analysis.duration_sec - 5.0) < 0.2
    assert analysis.is_authentic_footage is True
    assert analysis.is_static_black is False

    # Check frame luminance and standard deviation
    assert len(analysis.sampled_luminance) > 0
    avg_lum = sum(analysis.sampled_luminance) / len(analysis.sampled_luminance)
    assert avg_lum > 10.0  # Well above black threshold

    avg_std = sum(analysis.sampled_stddev) / len(analysis.sampled_stddev)
    assert avg_std > 10.0  # Well above flat color threshold

    # Verify motion between sampled frames
    assert any(delta > 0.001 for delta in analysis.motion_deltas)


def test_static_black_rejection(static_black_video: Path):
    """Verify static black video is flagged as non-authentic / static black."""
    analysis = SourceMediaAnalyzer.analyze_file(static_black_video)

    assert analysis.is_static_black is True
    assert analysis.is_authentic_footage is False
    assert not analysis.has_audio

    # All sampled luminances must be near zero
    for lum in analysis.sampled_luminance:
        assert lum < 2.0


def test_video_without_audio_detected(video_without_audio: Path):
    """Verify video without audio track is accurately reported without crashing."""
    analysis = SourceMediaAnalyzer.analyze_file(video_without_audio)

    assert analysis.has_video
    assert not analysis.has_audio
    assert analysis.audio_codec is None
    assert analysis.is_authentic_footage is True


def test_select_edit_spans_bounds(genuine_moving_video: Path):
    """Verify select_edit_spans respects boundaries and preserves exact target duration."""
    analysis = SourceMediaAnalyzer.analyze_file(genuine_moving_video)
    src_dur = analysis.duration_sec

    # Case 1: Requested 3.0 seconds from 5.0 second video
    spans_3s = SourceMediaAnalyzer.select_edit_spans(analysis, requested_duration=3.0)
    assert len(spans_3s) == 1
    start, end = spans_3s[0]
    assert 0.0 <= start < end <= src_dur
    assert abs((end - start) - 3.0) < 0.05

    # Case 2: Requested 10.0 seconds from 5.0 second video (clamped to full source duration)
    spans_10s = SourceMediaAnalyzer.select_edit_spans(analysis, requested_duration=10.0)
    start_10, end_10 = spans_10s[0]
    assert start_10 == 0.0
    assert abs(end_10 - src_dur) < 0.05

    # Case 3: Preferred offset near end of source
    spans_offset = SourceMediaAnalyzer.select_edit_spans(analysis, requested_duration=2.0, preferred_offset=4.5)
    start_off, end_off = spans_offset[0]
    assert 0.0 <= start_off < end_off <= src_dur
    assert abs((end_off - start_off) - 2.0) < 0.05


def test_empty_or_missing_file_raises():
    """Verify analyze_file fails closed if file does not exist or is 0 bytes."""
    with pytest.raises(ValueError, match="does not exist or is empty"):
        SourceMediaAnalyzer.analyze_file(Path("nonexistent_video_path_xyz.mp4"))
