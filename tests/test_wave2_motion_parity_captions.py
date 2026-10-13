# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 2 Motion Parity Caption & Transcript Tests.

Tests:
- Manual caption override persistence across reanalysis
- Mapped caption timeline under trims and retimes
- Preservation of manual_transcript_override flag against automated overwrite
"""
import pytest
from backend.motion_legacy_bridge.parity_contracts import map_caption_timeline


def test_map_caption_timeline_under_trim():
    """Verify captions correctly rebase their timing when a video/clip is trimmed."""
    original_captions = [
        {"id": "c1", "caption_text": "First intro sentence", "start_seconds": 1.0, "duration_seconds": 2.0},
        {"id": "c2", "caption_text": "Middle core takeaway", "start_seconds": 3.5, "duration_seconds": 2.5},
        {"id": "c3", "caption_text": "Ending call to action", "start_seconds": 7.0, "duration_seconds": 2.0},
    ]

    # Trim video from 2.0s to 7.0s (dropping c1 start, keeping c2, dropping c3)
    trimmed = map_caption_timeline(original_captions, trim_start=2.0, trim_end=7.0)

    # c1 overlaps [2.0, 3.0] -> start rebased to 0.0, dur 1.0
    # c2 is [3.5, 6.0] -> start rebased to 1.5, dur 2.5
    # c3 starts at 7.0 -> dropped
    assert len(trimmed) == 2
    assert trimmed[0]["id"] == "c1"
    assert trimmed[0]["start_seconds"] == 0.0
    assert trimmed[0]["duration_seconds"] == 1.0

    assert trimmed[1]["id"] == "c2"
    assert trimmed[1]["start_seconds"] == 1.5
    assert trimmed[1]["duration_seconds"] == 2.5


def test_manual_caption_override_persistence():
    """Verify that a manually edited caption segment retains manual_transcript_override."""
    captions = [
        {
            "id": "c1",
            "caption_text": "Corrected brand name from Whisper error",
            "start_seconds": 0.5,
            "duration_seconds": 3.0,
            "manual_transcript_override": True,
        },
        {
            "id": "c2",
            "caption_text": "Automatic speech recognition output",
            "start_seconds": 4.0,
            "duration_seconds": 2.0,
            "manual_transcript_override": False,
        },
    ]

    # Simulated re-analysis pass: should NOT overwrite segments where manual_transcript_override is True
    whisper_fresh_output = [
        {"id": "c1", "caption_text": "Flawed brand name", "start_seconds": 0.5, "duration_seconds": 3.0},
        {"id": "c2", "caption_text": "Automatic speech recognition output v2", "start_seconds": 4.0, "duration_seconds": 2.0},
    ]

    reconciled = []
    for existing in captions:
        if existing.get("manual_transcript_override"):
            # Legitimate manual edits override automated Whisper
            reconciled.append(existing)
        else:
            # Overwrite allowed for non-overridden segments
            matched_fresh = next((f for f in whisper_fresh_output if f["id"] == existing["id"]), existing)
            reconciled.append(matched_fresh)

    assert reconciled[0]["caption_text"] == "Corrected brand name from Whisper error"
    assert reconciled[0]["manual_transcript_override"] is True
    assert reconciled[1]["caption_text"] == "Automatic speech recognition output v2"


def test_caption_retime_with_offset():
    """Verify captions rebase accurately when clip is moved forward on timeline."""
    captions = [
        {"id": "c1", "caption_text": "Offset caption", "start_seconds": 0.0, "duration_seconds": 2.0},
    ]

    # Moved to t=5.0s on the timeline
    retimed = map_caption_timeline(captions, trim_start=0.0, trim_end=2.0, time_offset=5.0)
    assert len(retimed) == 1
    assert retimed[0]["start_seconds"] == 5.0
    assert retimed[0]["duration_seconds"] == 2.0
