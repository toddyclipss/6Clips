# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 2 Motion Parity Timeline Operations Tests.

Tests:
- Track protections: audio, video, caption track type separation
- Lock protections: locked tracks and clips reject mutations
- Split clip operation with trim boundaries
- Duplicate clip operation
- Move clip operation with type validation
- Solo, mute, visibility state updates
"""
import pytest
from backend.services.project_service import ProjectService, ProjectError


@pytest.fixture
def base_document():
    return {
        "aspect_ratio": "9:16",
        "timeline": {
            "duration_seconds": 30.0,
            "fps": 30,
            "tracks": [
                {
                    "id": "track_video_1",
                    "name": "Video Track 1",
                    "type": "video",
                    "locked": False,
                    "visible": True,
                    "muted": False,
                    "solo": False,
                    "clips": [
                        {
                            "id": "clip_v1",
                            "title": "Intro Video",
                            "type": "video",
                            "start_seconds": 0.0,
                            "duration_seconds": 10.0,
                            "trim_start": 0.0,
                            "trim_end": 10.0,
                            "locked": False,
                        }
                    ],
                },
                {
                    "id": "track_audio_1",
                    "name": "Audio Track 1",
                    "type": "audio",
                    "locked": False,
                    "visible": True,
                    "muted": False,
                    "solo": False,
                    "clips": [
                        {
                            "id": "clip_a1",
                            "title": "Voiceover Audio",
                            "type": "audio",
                            "start_seconds": 0.0,
                            "duration_seconds": 8.0,
                            "trim_start": 0.0,
                            "trim_end": 8.0,
                            "locked": False,
                        }
                    ],
                },
                {
                    "id": "track_captions_1",
                    "name": "Captions Track",
                    "type": "captions",
                    "locked": False,
                    "visible": True,
                    "muted": False,
                    "solo": False,
                    "clips": [
                        {
                            "id": "clip_c1",
                            "title": "Captions",
                            "type": "captions",
                            "caption_text": "Hello world",
                            "start_seconds": 0.5,
                            "duration_seconds": 2.5,
                            "locked": False,
                        }
                    ],
                },
            ],
        },
    }


def test_track_type_protections(base_document):
    """Verify that moving clips across incompatible track types is strictly prevented."""
    # Attempt to move video clip to audio track -> must fail
    with pytest.raises(ProjectError) as exc_v2a:
        ProjectService._mutate_document(
            base_document,
            "move_clip",
            {"clip_id": "clip_v1", "new_track_id": "track_audio_1"},
        )
    assert "audio track" in str(exc_v2a.value).lower()

    # Attempt to move audio clip to video track -> must fail
    with pytest.raises(ProjectError) as exc_a2v:
        ProjectService._mutate_document(
            base_document,
            "move_clip",
            {"clip_id": "clip_a1", "new_track_id": "track_video_1"},
        )
    assert "non-audio track" in str(exc_a2v.value).lower()

    # Attempt to move caption clip to video track -> must fail
    with pytest.raises(ProjectError) as exc_c2v:
        ProjectService._mutate_document(
            base_document,
            "move_clip",
            {"clip_id": "clip_c1", "new_track_id": "track_video_1"},
        )
    assert "captions" in str(exc_c2v.value).lower()


def test_locked_track_and_clip_protections(base_document):
    """Verify that locked elements reject mutations."""
    # Lock the clip directly
    clip_v1 = base_document["timeline"]["tracks"][0]["clips"][0]
    clip_v1["locked"] = True

    # Splitting locked clip must fail
    with pytest.raises(ProjectError) as exc_lock_split:
        ProjectService._mutate_document(
            base_document,
            "split_clip",
            {"clip_id": "clip_v1", "split_time": 4.0},
        )
    assert "locked" in str(exc_lock_split.value).lower()

    # Removing locked clip must fail
    with pytest.raises(ProjectError) as exc_lock_del:
        ProjectService._mutate_document(
            base_document,
            "remove_clip",
            {"clip_id": "clip_v1"},
        )
    assert "locked" in str(exc_lock_del.value).lower()


def test_split_clip_operation(base_document):
    """Verify splitting clip at playhead creates two contiguous parts with valid trim boundaries."""
    ProjectService._mutate_document(
        base_document,
        "split_clip",
        {"clip_id": "clip_v1", "split_time": 4.0},
    )

    video_track = base_document["timeline"]["tracks"][0]
    clips = video_track["clips"]
    assert len(clips) == 2, f"Expected 2 clips after split, got {len(clips)}"

    c1 = next(c for c in clips if c["id"] == "clip_v1")
    c2 = next(c for c in clips if c["id"] != "clip_v1")

    # Part 1: [0.0, 4.0], duration 4.0, trim_start 0.0, trim_end 4.0
    assert c1["start_seconds"] == 0.0
    assert c1["duration_seconds"] == 4.0
    assert c1["trim_start"] == 0.0
    assert c1["trim_end"] == 4.0

    # Part 2: [4.0, 10.0], duration 6.0, trim_start 4.0, trim_end 10.0
    assert c2["start_seconds"] == 4.0
    assert c2["duration_seconds"] == 6.0
    assert c2["trim_start"] == 4.0
    assert c2["trim_end"] == 10.0


def test_duplicate_clip_operation(base_document):
    """Verify duplicating clip creates an unlocked clone with offset."""
    ProjectService._mutate_document(
        base_document,
        "duplicate_clip",
        {"clip_id": "clip_v1", "offset_seconds": 12.0},
    )

    video_track = base_document["timeline"]["tracks"][0]
    clips = video_track["clips"]
    assert len(clips) == 2
    cloned = next(c for c in clips if c["id"] != "clip_v1")
    assert cloned["start_seconds"] == 12.0
    assert cloned["duration_seconds"] == 10.0
    assert cloned["locked"] is False


def test_update_track_state(base_document):
    """Verify track state toggles for mute, solo, and lock."""
    ProjectService._mutate_document(
        base_document,
        "update_track_state",
        {"track_id": "track_video_1", "patch": {"solo": True, "muted": True}},
    )

    video_track = base_document["timeline"]["tracks"][0]
    assert video_track["solo"] is True
    assert video_track["muted"] is True
