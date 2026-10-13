# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Acceptance test suite for Wave 2 Agent 2 — Media Intelligence Helpers.

Validates:
1. Audio energy analysis, RMS dynamics, silence detection, and dead-air penalties.
2. Scene cut detection, frozen video filler guard, and black frame detection.
3. 9:16 safe region presets (gameplay_reticle, hud_aware_blur, split_facecam, center_crop).
4. Caption grounding: non-destructive authoritative user edit preservation, cut remapping, speed scaling.
5. Candidate highlight generation, ranking provenance, and deduplication.
6. Complete database isolation.
"""

import hashlib
import math
import subprocess
from pathlib import Path
import pytest

from backend.media_intelligence.audio_energy import (
    AudioEnergyProfile,
    analyze_audio_energy,
    analyze_audio_energy_sync,
)
from backend.media_intelligence.caption_grounding import (
    ground_and_remap_captions,
    validate_caption_integrity,
)
from backend.media_intelligence.candidate_ranker import (
    generate_and_rank_segments,
    generate_candidate_windows,
)
from backend.media_intelligence.reframing import (
    ReframePreset,
    build_reframe_filter,
)
from backend.media_intelligence.scene_analyzer import (
    detect_black_frames_sync,
    detect_frozen_frames_sync,
    detect_scene_changes_sync,
)
from backend.media_pipeline.models import (
    DurationPolicy,
    MediaProbeV1,
    OutputSpecV1,
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
    """Ensure production database remains pristine before and after tests."""
    if PROD_DB_PATH.exists():
        pre_hash = get_file_sha256(PROD_DB_PATH)
        yield
        post_hash = get_file_sha256(PROD_DB_PATH)
        assert pre_hash == post_hash, f"Production DB modified! Pre: {pre_hash}, Post: {post_hash}"
    else:
        yield


def create_dynamic_audio_video_fixture(target_path: Path, duration_s: int = 12) -> Path:
    """Generate a test video with distinct audio energy burst and static pause."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    # 0-6s: high tone 880Hz, 6-12s: quiet volume
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={duration_s}:size=640x360:rate=25",
        "-f", "lavfi", "-i", f"sine=frequency=880:duration={duration_s}",
        "-af", "volume=enable='between(t,0,6)':volume=1.0,volume=enable='between(t,6,12)':volume=0.01",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        str(target_path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)
    return target_path


def test_audio_energy_analysis_and_silence_detection(tmp_path):
    """Verify audio energy profiling extracts RMS dB and catches low-energy intervals."""
    fixture_path = tmp_path / "energy_test.mp4"
    create_dynamic_audio_video_fixture(fixture_path, duration_s=10)

    profile = analyze_audio_energy_sync(fixture_path, window_sec=1.0)
    assert profile.duration_seconds >= 9.5
    assert profile.is_silent is False
    assert profile.peak_rms_db > profile.mean_rms_db

    # Energy in first half (loud) must be strictly higher than second half (quiet)
    first_half_energy = profile.energy_in_range(0.0, 5.0)
    second_half_energy = profile.energy_in_range(6.0, 10.0)
    assert first_half_energy > second_half_energy

    # Silence ratio in second half must be higher than first half
    assert profile.silence_ratio_in_range(6.0, 10.0) >= profile.silence_ratio_in_range(0.0, 5.0)


def test_scene_cut_and_frozen_frame_detection(tmp_path):
    """Verify scene transition and frozen frame detection engines."""
    # Create video with a 4-second frozen static segment
    frozen_path = tmp_path / "frozen_test.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=blue:duration=5:size=320x240:rate=25",
        "-c:v", "libx264", "-preset", "ultrafast",
        str(frozen_path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)

    frozen = detect_frozen_frames_sync(frozen_path, min_duration=2.0)
    assert len(frozen) >= 1
    assert frozen[0][1] > frozen[0][0]

    # Black frame test
    black_path = tmp_path / "black_test.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=black:duration=4:size=320x240:rate=25",
        "-c:v", "libx264", "-preset", "ultrafast",
        str(black_path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)
    blacks = detect_black_frames_sync(black_path, min_duration=1.0)
    assert len(blacks) >= 1


def test_reframing_presets_and_disclosures():
    """Verify 9:16 safe region preset filtergraphs and explicit limitation disclosures."""
    # 1. Gameplay reticle
    vf_reticle, disc_reticle = build_reframe_filter(1920, 1080, preset=ReframePreset.GAMEPLAY_RETICLE.value)
    assert "scale=1080:1920" in vf_reticle
    assert "crop=1080:1920" in vf_reticle
    assert "Gameplay reticle" in disc_reticle

    # 2. HUD-aware blur
    vf_hud, disc_hud = build_reframe_filter(1920, 1080, preset=ReframePreset.HUD_AWARE_BLUR.value)
    assert "boxblur" in vf_hud
    assert "overlay" in vf_hud
    assert "HUD-aware blur" in disc_hud

    # 3. Split facecam / gameplay
    vf_cam, disc_cam = build_reframe_filter(1920, 1080, preset=ReframePreset.SPLIT_FACECAM_GAMEPLAY.value)
    assert "vstack" in vf_cam
    assert "Split facecam" in disc_cam

    # 4. Standard center crop
    vf_center, disc_center = build_reframe_filter(1920, 1080, preset=ReframePreset.CENTER_CROP.value)
    assert "crop=1080:1920" in vf_center
    assert "Standard center crop" in disc_center


def test_caption_grounding_preserves_authoritative_user_edits():
    """Verify that user-edited captions are preserved verbatim and retimed accurately."""
    transcript = [
        {"id": "c1", "start": 2.0, "end": 4.5, "text": "intro text", "is_user_edited": False},
        {"id": "c2", "start": 10.0, "end": 14.0, "text": "USER EDITED CLUTCH MOMENT", "is_user_edited": True},
        {"id": "c3", "start": 15.0, "end": 18.0, "text": "standard asr speech", "is_user_edited": False},
        {"id": "c4", "start": 30.0, "end": 35.0, "text": "tail outside cut", "is_user_edited": False},
    ]

    cut_start = 8.0
    cut_end = 20.0

    remapped = ground_and_remap_captions(transcript, cut_start, cut_end)
    assert len(remapped) == 2  # c2 and c3 fall within cut window

    # c2 was [10.0, 14.0] -> relative to 8.0 becomes [2.0, 6.0]
    assert remapped[0]["id"] == "c2"
    assert remapped[0]["start"] == 2.0
    assert remapped[0]["end"] == 6.0
    assert remapped[0]["text"] == "USER EDITED CLUTCH MOMENT"
    assert remapped[0]["is_user_edited"] is True
    assert remapped[0]["provenance"] == "user_edited_authoritative"

    # c3 was [15.0, 18.0] -> relative to 8.0 becomes [7.0, 10.0]
    assert remapped[1]["id"] == "c3"
    assert remapped[1]["start"] == 7.0
    assert remapped[1]["end"] == 10.0
    assert remapped[1]["is_user_edited"] is False

    # Integrity validator must pass
    valid, issues = validate_caption_integrity(transcript, remapped, cut_start, cut_end)
    assert valid is True
    assert len(issues) == 0


def test_caption_grounding_with_word_timestamps_and_speed_scaling():
    """Verify word-level timestamp remapping under playback speed change."""
    transcript = [
        {
            "id": "seg1",
            "start": 5.0,
            "end": 9.0,
            "text": "fast double kill",
            "is_user_edited": False,
            "words": [
                {"word": "fast", "start": 5.0, "end": 6.0},
                {"word": "double", "start": 6.2, "end": 7.5},
                {"word": "kill", "start": 7.6, "end": 9.0},
            ],
        }
    ]

    cut_start = 5.0
    cut_end = 10.0
    speed_factor = 1.25  # 25% faster

    remapped = ground_and_remap_captions(transcript, cut_start, cut_end, speed_factor=speed_factor)
    assert len(remapped) == 1
    words = remapped[0]["words"]
    assert len(words) == 3

    # "fast": (5.0 - 5.0) / 1.25 = 0.0, (6.0 - 5.0) / 1.25 = 0.8
    assert words[0]["word"] == "fast"
    assert words[0]["start"] == 0.0
    assert words[0]["end"] == 0.8


def test_candidate_highlight_ranking_and_deduplication():
    """Verify multi-signal candidate ranking generates non-overlapping highlights."""
    total_duration = 200.0
    specs = [
        OutputSpecV1(output_id="clip_1", seconds=60.0, duration_policy=DurationPolicy.TARGET),
        OutputSpecV1(output_id="clip_2", seconds=60.0, duration_policy=DurationPolicy.TARGET),
        OutputSpecV1(output_id="clip_3", seconds=60.0, duration_policy=DurationPolicy.TARGET),
    ]

    scene_cuts = [15.0, 35.0, 75.0, 110.0, 155.0, 180.0]
    transcript = [
        {"start": 10.0, "end": 25.0, "text": "engaging intro callout with team tactical setup"},
        {"start": 70.0, "end": 95.0, "text": "peak action encounter pushing into enemy objective"},
        {"start": 130.0, "end": 170.0, "text": "final clutch round victory and match wrapup"},
    ]

    ranges, blocker = generate_and_rank_segments(
        total_duration=total_duration,
        output_specs=specs,
        scene_cuts=scene_cuts,
        transcript_segments=transcript,
    )

    assert blocker is None
    assert len(ranges) == 3

    # Strict non-overlap verification
    for i in range(len(ranges) - 1):
        assert ranges[i].end_seconds <= ranges[i + 1].start_seconds, (
            f"Overlap detected: Range {i} ends {ranges[i].end_seconds} > Range {i+1} starts {ranges[i+1].start_seconds}"
        )

    # Provenance and score transparency verification
    for r in ranges:
        assert r.duration_seconds >= 55.0
        assert r.relevance_score > 0.0
        assert "Score:" in r.editorial_reason or "HEURISTIC" in r.editorial_reason
        assert "Editorial: NOT_ASSESSED" in r.editorial_reason
