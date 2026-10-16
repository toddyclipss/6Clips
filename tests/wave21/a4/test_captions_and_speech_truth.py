# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for Captions, Speech Truth, Dead-Air Removal & Audio Ducking (Wave 21 Agent 4)."""

import pytest
from backend.native_motion.captions import (
    CaptionSpeechUnavailableError,
    NativeCaptionEngine,
)
from backend.native_motion.schema import WordTimestampSpec


def test_dead_air_removal_and_shift_calculation():
    """Verify dead-air removal condenses long gaps between spoken words."""
    words = [
        WordTimestampSpec(word="Welcome", start=0.1, end=0.7),
        WordTimestampSpec(word="to", start=0.75, end=0.95),
        # 1.55 second dead air gap here:
        WordTimestampSpec(word="the", start=2.5, end=2.8),
        WordTimestampSpec(word="podcast.", start=2.85, end=3.5),
    ]

    condensed, saved = NativeCaptionEngine.remove_dead_air(words, max_silence_seconds=0.35)
    assert len(condensed) == 4
    assert saved > 1.0, f"Expected saved time > 1.0s, got {saved}"
    # The gap between word 2 and word 3 should now be clamped to max_silence_seconds
    gap_after = condensed[2].start - condensed[1].end
    assert abs(gap_after - 0.35) < 0.01


def test_audio_ducking_interval_calculation():
    """Verify ducking intervals cover all spoken words plus safe padding."""
    words = [
        WordTimestampSpec(word="First", start=1.0, end=1.5),
        WordTimestampSpec(word="sentence.", start=1.6, end=2.2),
        WordTimestampSpec(word="Second", start=6.0, end=6.8),
    ]
    intervals = NativeCaptionEngine.compute_ducking_intervals(words, padding_seconds=0.25)
    assert len(intervals) == 2
    # First interval covers 1.0-0.25 to 2.2+0.25
    assert intervals[0][0] == 0.75
    assert intervals[0][1] == 2.45
    # Second interval covers 6.0-0.25 to 6.8+0.25
    assert intervals[1][0] == 5.75
    assert intervals[1][1] == 7.05


def test_honest_pending_and_blocked_when_human_speech_absent():
    """Verify engine raises honest PENDING status when real speech audio is absent."""
    with pytest.raises(CaptionSpeechUnavailableError) as exc_info:
        NativeCaptionEngine.load_authentic_words(audio_path="nonexistent_human_voice.wav")
    assert exc_info.value.status == "PENDING_SPEECH_AUDIO"
