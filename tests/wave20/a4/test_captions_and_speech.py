# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for NativeCaptionEngine: authentic word timestamps, honest PENDING, and safe-zone anchoring."""

import pytest
from backend.native_motion.captions import (
    CaptionSpeechUnavailableError,
    NativeCaptionEngine,
)
from backend.native_motion.schema import CreativeBrief, SafeZoneSpec


def test_captions_fails_with_honest_pending_on_missing_audio():
    # Never fabricate word timestamps when authentic audio is absent
    with pytest.raises(CaptionSpeechUnavailableError) as exc:
        NativeCaptionEngine.load_authentic_words(audio_path="nonexistent_audio_file.wav")
    assert exc.value.status == "PENDING_SPEECH_AUDIO"


def test_captions_compose_safe_zone_anchoring():
    transcript = [
        {"word": "ViralMint", "start": 0.1, "end": 0.8},
        {"word": "powers", "start": 0.8, "end": 1.4},
        {"word": "motion", "start": 1.4, "end": 2.0},
    ]
    words = NativeCaptionEngine.load_authentic_words(transcript_data=transcript)
    assert len(words) == 3

    brief = CreativeBrief(topic="Caption Test", intent="explain", tone="punchy")
    sz = SafeZoneSpec(top=0.12, bottom=0.20, left=0.08, right=0.08)

    elem = NativeCaptionEngine.compose_caption_element(
        words=words,
        width=1080,
        height=1920,
        safe_zones=sz,
        brief=brief,
        duration=3.0,
    )

    # Element must be anchored within bottom safe zone
    assert elem.type == "captions"
    assert elem.captions_config.safe_zone_anchor == "bottom"
    assert elem.transform.y < 1920 * (1.0 - sz.bottom)  # Fully inside bottom margin
    assert elem.captions_config.background_veil is True
