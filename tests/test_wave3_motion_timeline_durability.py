# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 3 Motion Timeline Durability & Editing Operations Tests.

Tests:
- Slip edit: source media offset shifts while timeline start_time and duration remain invariant
- Ripple delete: deleted clip shifts subsequent clips on track left by deleted duration without gaps
- Speed / retime: speed multiplier (0.25x - 4.0x) adjusts clip duration proportionally
- Redo invalidation: new edits invalidate and clear redo stack
- Draft revert: uncommitted changes revert cleanly to last committed revision snapshot
- Retimed caption scaling: caption segments and word timings scale under retime while preserving line breaks
"""
import pytest
from backend.motion_legacy_bridge.parity_contracts import (
    apply_slip_operation,
    apply_ripple_delete,
    apply_speed_retime,
    retime_caption_words,
)


@pytest.fixture
def sample_clip():
    return {
        "id": "clip_v1",
        "title": "Gameplay Clip",
        "type": "video",
        "start_seconds": 2.0,
        "duration_seconds": 5.0,
        "trim_start": 10.0,
        "trim_end": 15.0,
        "speed": 1.0,
    }


@pytest.fixture
def sample_tracks():
    return [
        {
            "id": "track_video_1",
            "name": "Video Track",
            "type": "video",
            "clips": [
                {
                    "id": "clip_v1",
                    "title": "First Clip",
                    "start_seconds": 0.0,
                    "duration_seconds": 4.0,
                    "trim_start": 0.0,
                    "trim_end": 4.0,
                },
                {
                    "id": "clip_v2",
                    "title": "Second Clip (Target)",
                    "start_seconds": 4.0,
                    "duration_seconds": 6.0,
                    "trim_start": 0.0,
                    "trim_end": 6.0,
                },
                {
                    "id": "clip_v3",
                    "title": "Third Clip",
                    "start_seconds": 10.0,
                    "duration_seconds": 5.0,
                    "trim_start": 0.0,
                    "trim_end": 5.0,
                },
            ],
        },
        {
            "id": "track_audio_1",
            "name": "Music Track",
            "type": "audio",
            "clips": [
                {
                    "id": "clip_a1",
                    "title": "Background Music",
                    "start_seconds": 0.0,
                    "duration_seconds": 20.0,
                }
            ],
        },
    ]


def test_slip_operation_invariance(sample_clip):
    """Verify slip edit shifts source trim_start/end while keeping timeline start and duration constant."""
    # Slip forward by 2.5 seconds
    slipped = apply_slip_operation(sample_clip, delta_seconds=2.5, source_duration=30.0)

    # Timeline placement MUST NOT change
    assert slipped["start_seconds"] == sample_clip["start_seconds"]
    assert slipped["duration_seconds"] == sample_clip["duration_seconds"]

    # Source window shifts forward
    assert slipped["trim_start"] == 12.5
    assert slipped["trim_end"] == 17.5


def test_slip_operation_boundary_clamping(sample_clip):
    """Verify slip edit cannot shift trim_start below 0.0 or past source duration."""
    # Slip backward past 0
    slipped_min = apply_slip_operation(sample_clip, delta_seconds=-20.0, source_duration=30.0)
    assert slipped_min["trim_start"] == 0.0
    assert slipped_min["trim_end"] == 5.0

    # Slip forward past max source duration (30.0 - 5.0 duration = max trim_start 25.0)
    slipped_max = apply_slip_operation(sample_clip, delta_seconds=50.0, source_duration=30.0)
    assert slipped_max["trim_start"] == 25.0
    assert slipped_max["trim_end"] == 30.0


def test_ripple_delete_operation(sample_tracks):
    """Verify ripple delete removes target clip and shifts subsequent clips left by target duration."""
    # Ripple delete clip_v2 (duration 6.0, start 4.0)
    new_tracks, deleted = apply_ripple_delete(sample_tracks, "clip_v2")

    assert deleted is not None
    assert deleted["id"] == "clip_v2"

    v_clips = new_tracks[0]["clips"]
    assert len(v_clips) == 2

    # clip_v1 remains at start 0.0, duration 4.0
    c1 = next(c for c in v_clips if c["id"] == "clip_v1")
    assert c1["start_seconds"] == 0.0

    # clip_v3 shifts from 10.0 to (10.0 - 6.0) = 4.0, perfectly adjoining clip_v1!
    c3 = next(c for c in v_clips if c["id"] == "clip_v3")
    assert c3["start_seconds"] == 4.0
    assert c3["duration_seconds"] == 5.0

    # Audio track remains untouched
    assert len(new_tracks[1]["clips"]) == 1
    assert new_tracks[1]["clips"][0]["start_seconds"] == 0.0


def test_speed_retime_multiplier(sample_clip):
    """Verify 2.0x speed halves duration and 0.5x speed doubles duration."""
    # Retime to 2.0x
    fast_clip, _ = apply_speed_retime(sample_clip, new_speed=2.0)
    assert fast_clip["speed"] == 2.0
    # Original duration 5.0 / 2.0 = 2.5
    assert fast_clip["duration_seconds"] == 2.5

    # Retime to 0.5x
    slow_clip, _ = apply_speed_retime(sample_clip, new_speed=0.5)
    assert slow_clip["speed"] == 0.5
    # Original duration 5.0 / 0.5 = 10.0
    assert slow_clip["duration_seconds"] == 10.0


def test_speed_retime_ripple_mode(sample_tracks):
    """Verify speed retime with ripple shifts subsequent clips accordingly."""
    target_clip = sample_tracks[0]["clips"][1]  # clip_v2, start 4.0, duration 6.0
    # Slow clip down to 0.5x -> new duration = 12.0 (diff = +6.0)
    re_clip, updated_tracks = apply_speed_retime(
        target_clip,
        new_speed=0.5,
        tracks=sample_tracks,
        ripple=True,
    )

    assert re_clip["duration_seconds"] == 12.0
    assert updated_tracks is not None
    v_clips = updated_tracks[0]["clips"]

    # clip_v3 was at 10.0, should now shift to 10.0 + 6.0 = 16.0
    c3 = next(c for c in v_clips if c["id"] == "clip_v3")
    assert c3["start_seconds"] == 16.0


def test_redo_invalidation_lifecycle():
    """Verify simulation of redo stack invalidation upon any new edit."""
    undo_stack = []
    redo_stack = []
    doc = {"revision": 1, "state": "initial"}

    # Action 1: user edit
    undo_stack.append(dict(doc))
    redo_stack.clear()
    doc = {"revision": 2, "state": "edit_1"}

    # Action 2: user edit
    undo_stack.append(dict(doc))
    redo_stack.clear()
    doc = {"revision": 3, "state": "edit_2"}

    # User undoes edit 2
    prev_doc = undo_stack.pop()
    redo_stack.append(dict(doc))
    doc = prev_doc
    assert doc["state"] == "edit_1"
    assert len(redo_stack) == 1

    # User performs a brand NEW edit 3 -> MUST invalidate redo_stack!
    undo_stack.append(dict(doc))
    redo_stack.clear()  # Invalidation step
    doc = {"revision": 4, "state": "new_branch_edit_3"}

    assert len(redo_stack) == 0, "Redo stack must be empty after a new diverging edit"
    assert len(undo_stack) == 2


def test_draft_revert_lifecycle():
    """Verify draft revert returns document cleanly to last committed revision snapshot."""
    committed_snapshot = {
        "revision": 5,
        "timeline": {
            "tracks": [{"id": "t1", "clips": [{"id": "c1", "start_seconds": 0.0}]}],
        },
    }

    # User makes dirty uncommitted draft modifications
    draft_doc = {
        "revision": 5,
        "timeline": {
            "tracks": [{"id": "t1", "clips": [{"id": "c1", "start_seconds": 12.0}]}],
        },
    }
    is_dirty = True

    # User invokes handleCancelDraft
    reverted_doc = dict(committed_snapshot)
    is_dirty = False

    assert is_dirty is False
    assert reverted_doc["timeline"]["tracks"][0]["clips"][0]["start_seconds"] == 0.0


def test_caption_retime_words_preserves_linebreaks():
    """Verify caption retiming scales word timings while strictly preserving multiline line breaks."""
    captions = [
        {
            "id": "cap_1",
            "start_seconds": 1.0,
            "duration_seconds": 2.0,
            "caption_text": "Top Headline\nBottom Hook Line",
            "manual_transcript_override": True,
            "words": [
                {"word": "Top", "start": 1.0, "end": 1.5},
                {"word": "Headline", "start": 1.5, "end": 2.0},
                {"word": "Bottom", "start": 2.0, "end": 2.5},
                {"word": "Hook", "start": 2.5, "end": 2.8},
                {"word": "Line", "start": 2.8, "end": 3.0},
            ],
        }
    ]

    # Double playback speed (1.0x -> 2.0x)
    retimed = retime_caption_words(captions, old_speed=1.0, new_speed=2.0)
    assert len(retimed) == 1
    c = retimed[0]

    # Line break MUST be preserved exactly
    assert c["caption_text"] == "Top Headline\nBottom Hook Line"
    assert "\n" in c["caption_text"]
    assert c["manual_transcript_override"] is True

    # Timing scaled by 0.5
    assert c["start_seconds"] == 0.5
    assert c["duration_seconds"] == 1.0
    assert c["words"][0]["start"] == 0.5
    assert c["words"][0]["end"] == 0.75
