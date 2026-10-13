# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 4 / Role 2 Tests: Library Asset Drop Consumer & Deterministic Render Manifest.

Tests:
- application/x-6clips-asset MIME parsing and shape validation
- Rights policy enforcement (permitted_uses containing "timeline_motion")
- Malformed and unpermitted payload rejection
- CAS expected_revision concurrency and conflict handling
- Deterministic render manifest frame calculations (FPS-based timeline and source frames)
- Audio mix mute/solo isolation matrix
- Multiline caption line-break preservation and manual overrides
- Framing presets readiness and unsupported worker flags (gameplay_reticle, hud_aware_blur, split_facecam_gameplay)
- Manifest canonical SHA-256 hash determinism
"""

import copy
import json
import pytest

from backend.motion_render_bridge.manifest import (
    FramingPreset,
    FramingFilterConfig,
    RenderClip,
    RenderTrack,
    RenderAudioMix,
    RenderCaptionSegment,
    RenderManifest,
    WORKER_SUPPORTED_PRESETS,
    build_render_manifest,
)


# --- 1. Library Asset Drop MIME Parsing and Contract Verification ---

def parse_and_validate_motion_asset_drop(payload: dict) -> dict:
    """Simulates client-side / endpoint drop intake validation for application/x-6clips-asset."""
    asset_id = payload.get("asset_id") or payload.get("key") or payload.get("id")
    if not asset_id:
        raise ValueError("Malformed asset drop: missing asset ID or key.")

    media_type = (payload.get("media_type") or payload.get("mediaType") or payload.get("media") or "").lower()
    if media_type not in ("video", "audio", "image", "captions"):
        raise ValueError(f"Invalid media_type '{media_type}'. Must be video, audio, image, or captions.")

    permitted_uses = payload.get("permitted_uses")
    if permitted_uses is not None:
        if not isinstance(permitted_uses, list) or "timeline_motion" not in permitted_uses:
            raise PermissionError("Asset rights policy forbids timeline_motion use.")

    return {
        "asset_id": str(asset_id),
        "key": str(payload.get("key") or asset_id),
        "title": payload.get("title") or "Media Clip",
        "media_type": media_type,
        "stream_url": payload.get("stream_url") or f"/api/library/asset/{asset_id}",
        "duration_seconds": float(payload.get("duration_seconds") or 5.0),
        "aspect_ratio": payload.get("aspect_ratio") or "9:16",
        "source_provenance": payload.get("source_provenance") or "library_user_asset",
        "permitted_uses": permitted_uses or ["timeline_motion"],
        "target_start_time_seconds": max(0.0, float(payload.get("target_start_time_seconds") or 0.0)),
        "file_sha256": payload.get("file_sha256"),
    }


def test_valid_library_asset_drop_decoding():
    """Verify standard application/x-6clips-asset payload is accepted and accurately decoded."""
    raw_payload = {
        "asset_id": "lib_vid_001",
        "key": "raw_footage_gameplay.mp4",
        "title": "Ranked Match Gameplay",
        "media_type": "video",
        "stream_url": "/api/library/asset/lib_vid_001",
        "duration_seconds": 12.5,
        "aspect_ratio": "16:9",
        "source_provenance": "imported:gameplay_recorder",
        "permitted_uses": ["timeline_motion", "derivative_clips", "commercial_creator"],
        "intent_action": "add_track",
        "target_start_time_seconds": 3.0,
        "file_sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
    }
    validated = parse_and_validate_motion_asset_drop(raw_payload)

    assert validated["asset_id"] == "lib_vid_001"
    assert validated["key"] == "raw_footage_gameplay.mp4"
    assert validated["media_type"] == "video"
    assert validated["duration_seconds"] == 12.5
    assert validated["target_start_time_seconds"] == 3.0
    assert "timeline_motion" in validated["permitted_uses"]


def test_malformed_asset_drop_missing_id():
    """Verify asset drop missing asset_id and key is rejected with descriptive error."""
    invalid_payload = {
        "title": "Orphan Asset",
        "media_type": "video",
        "duration_seconds": 5.0,
    }
    with pytest.raises(ValueError, match="Malformed asset drop: missing asset ID or key"):
        parse_and_validate_motion_asset_drop(invalid_payload)


def test_unpermitted_asset_drop_rights_rejection():
    """Verify asset lacking 'timeline_motion' rights is rejected."""
    forbidden_payload = {
        "asset_id": "licensed_music_099",
        "key": "exclusive_audio.mp3",
        "title": "Exclusive Music Track",
        "media_type": "audio",
        "permitted_uses": ["commercial_broadcast_only"],  # timeline_motion NOT included
    }
    with pytest.raises(PermissionError, match="Asset rights policy forbids timeline_motion use"):
        parse_and_validate_motion_asset_drop(forbidden_payload)


# --- 2. Concurrency: CAS expected_revision Operations ---

def simulate_cas_operation(project_state: dict, op_type: str, payload: dict, expected_rev: int) -> dict:
    """Simulates ProjectService CAS revision guard."""
    current_rev = project_state["revision"]
    if expected_rev != current_rev:
        raise ValueError(f"REVISION_CONFLICT: Expected {expected_rev}, but remote is {current_rev}")

    new_state = copy.deepcopy(project_state)
    new_state["revision"] = current_rev + 1
    if op_type == "add_clip":
        track_id = payload["track_id"]
        for t in new_state["document"]["timeline"]["tracks"]:
            if t["id"] == track_id:
                t["clips"].append(payload["clip"])
                break
    return new_state


def test_cas_concurrency_success_and_conflict():
    """Verify CAS revision reconciliation succeeds on matched revision and rejects stale edits."""
    initial_project = {
        "id": "proj_test_cas",
        "revision": 3,
        "document": {
            "timeline": {
                "tracks": [
                    {"id": "v1", "type": "video", "clips": []}
                ]
            }
        }
    }

    # 1. Matching revision succeeds and increments revision
    clip_op = {
        "track_id": "v1",
        "clip": {"id": "c1", "type": "video", "start_seconds": 0.0, "duration_seconds": 4.0}
    }
    updated = simulate_cas_operation(initial_project, "add_clip", clip_op, expected_rev=3)
    assert updated["revision"] == 4
    assert len(updated["document"]["timeline"]["tracks"][0]["clips"]) == 1

    # 2. Stale revision (expected=3, current=4) raises REVISION_CONFLICT
    stale_clip_op = {
        "track_id": "v1",
        "clip": {"id": "c2", "type": "video", "start_seconds": 4.0, "duration_seconds": 4.0}
    }
    with pytest.raises(ValueError, match="REVISION_CONFLICT"):
        simulate_cas_operation(updated, "add_clip", stale_clip_op, expected_rev=3)


# --- 3. Deterministic Render Manifest Generation ---

@pytest.fixture
def complex_timeline_document():
    return {
        "fps": 30.0,
        "aspect_ratio": "9:16",
        "timeline": {
            "tracks": [
                {
                    "id": "track_video_primary",
                    "type": "video",
                    "name": "Main Gameplay",
                    "muted": False,
                    "solo": False,
                    "volume": 1.0,
                    "layer_order": 1,
                    "clips": [
                        {
                            "id": "clip_gameplay_1",
                            "type": "video",
                            "asset_id": "asset_100",
                            "title": "Match Intro",
                            "start_seconds": 0.0,
                            "duration_seconds": 4.0,
                            "trim_start": 2.0,
                            "speed": 1.0,
                            "framing_preset": "center_crop",
                        },
                        {
                            "id": "clip_gameplay_2",
                            "type": "video",
                            "asset_id": "asset_100",
                            "title": "Match Climax (Fast Forward)",
                            "start_seconds": 4.0,
                            "duration_seconds": 2.5,
                            "trim_start": 6.0,
                            "speed": 2.0,  # 2x speed multiplier
                            "framing_preset": "hud_aware_blur",  # Worker unsupported preset
                        },
                    ],
                },
                {
                    "id": "track_audio_bgm",
                    "type": "audio",
                    "name": "Background Music",
                    "muted": True,  # Muted track
                    "solo": False,
                    "volume": 0.8,
                    "clips": [
                        {
                            "id": "clip_bgm_1",
                            "type": "audio",
                            "asset_id": "bgm_chill",
                            "start_seconds": 0.0,
                            "duration_seconds": 6.5,
                            "volume": 1.0,
                        }
                    ],
                },
                {
                    "id": "track_audio_sfx",
                    "type": "audio",
                    "name": "Sound Effects",
                    "muted": False,
                    "solo": False,
                    "volume": 1.0,
                    "clips": [
                        {
                            "id": "clip_sfx_whoosh",
                            "type": "audio",
                            "asset_id": "sfx_whoosh",
                            "start_seconds": 3.8,
                            "duration_seconds": 1.0,
                        }
                    ],
                },
                {
                    "id": "track_captions",
                    "type": "captions",
                    "name": "Subtitles",
                    "clips": [
                        {
                            "id": "caption_intro",
                            "type": "captions",
                            "caption_text": "Welcome to the grand final!\nDon't look away.",
                            "manual_transcript_override": True,
                            "start_seconds": 0.5,
                            "duration_seconds": 3.0,
                        }
                    ],
                },
            ]
        },
    }


def test_build_render_manifest_frame_calculations(complex_timeline_document):
    """Verify build_render_manifest computes exact in/out frames based on FPS and speed multiplier."""
    manifest = build_render_manifest(
        document=complex_timeline_document,
        project_id="proj_alpha",
        revision=5,
    )

    assert manifest.fps == 30.0
    assert manifest.width == 1080
    assert manifest.height == 1920
    assert manifest.aspect_ratio == "9:16"
    assert manifest.total_duration_seconds == 6.5
    assert manifest.total_frames == 195  # 6.5 * 30 = 195 frames

    # Inspect First Video Clip (speed = 1.0)
    v_track = next(t for t in manifest.tracks if t.id == "track_video_primary")
    clip1 = v_track.clips[0]
    assert clip1.timeline_in_frame == 0
    assert clip1.timeline_out_frame == 120  # 4.0s * 30
    assert clip1.source_in_frame == 60     # trim 2.0s * 30
    assert clip1.source_out_frame == 180   # (trim 2.0s + 4.0s) * 30

    # Inspect Second Video Clip (speed = 2.0x)
    clip2 = v_track.clips[1]
    assert clip2.timeline_in_frame == 120   # 4.0s * 30
    assert clip2.timeline_out_frame == 195  # (4.0s + 2.5s) * 30
    assert clip2.source_in_frame == 180    # trim 6.0s * 30
    # At 2.0x speed, 2.5s duration on timeline consumes 5.0s of source window:
    # source_out_frame = (6.0 + 2.5 * 2.0) * 30 = 11.0 * 30 = 330
    assert clip2.source_out_frame == 330


def test_build_render_manifest_audio_mix_mute_isolation(complex_timeline_document):
    """Verify audio mix correctly computes effective active and gain for muted/normal tracks."""
    manifest = build_render_manifest(document=complex_timeline_document)

    bgm_mix = next(m for m in manifest.audio_mix if m.track_id == "track_audio_bgm")
    sfx_mix = next(m for m in manifest.audio_mix if m.track_id == "track_audio_sfx")

    # BGM was muted
    assert bgm_mix.is_muted is True
    assert bgm_mix.effective_active is False
    assert bgm_mix.effective_gain == 0.0

    # SFX was unmuted
    assert sfx_mix.is_muted is False
    assert sfx_mix.effective_active is True
    assert sfx_mix.effective_gain == 1.0


def test_build_render_manifest_audio_mix_solo_isolation(complex_timeline_document):
    """Verify track solo overrides non-solo tracks in the audio mix."""
    doc = copy.deepcopy(complex_timeline_document)
    # Set SFX track to solo=True
    sfx_track = next(t for t in doc["timeline"]["tracks"] if t["id"] == "track_audio_sfx")
    sfx_track["solo"] = True

    manifest = build_render_manifest(document=doc)

    bgm_mix = next(m for m in manifest.audio_mix if m.track_id == "track_audio_bgm")
    sfx_mix = next(m for m in manifest.audio_mix if m.track_id == "track_audio_sfx")

    # SFX is solo -> active
    assert sfx_mix.is_solo is True
    assert sfx_mix.effective_active is True

    # BGM is not solo -> silenced by solo rule
    assert bgm_mix.effective_active is False
    assert bgm_mix.effective_gain == 0.0


def test_build_render_manifest_multiline_captions(complex_timeline_document):
    """Verify multiline captions preserve line breaks and manual override flags."""
    manifest = build_render_manifest(document=complex_timeline_document)

    assert len(manifest.caption_segments) == 1
    seg = manifest.caption_segments[0]
    assert seg.clip_id == "caption_intro"
    assert seg.manual_override is True
    assert len(seg.lines) == 2
    assert seg.lines[0] == "Welcome to the grand final!"
    assert seg.lines[1] == "Don't look away."
    assert seg.start_frame == 15  # 0.5s * 30
    assert seg.end_frame == 105   # 3.5s * 30


def test_build_render_manifest_framing_preset_worker_flags(complex_timeline_document):
    """Verify center_crop is marked supported while hud_aware_blur is flagged unsupported."""
    manifest = build_render_manifest(document=complex_timeline_document)

    v_track = next(t for t in manifest.tracks if t.id == "track_video_primary")
    clip1 = v_track.clips[0]
    clip2 = v_track.clips[1]

    # Clip 1: center_crop is supported by worker
    assert clip1.framing.worker_supported is True
    assert "scale=" in clip1.framing.ffmpeg_filter
    assert clip1.framing.unsupported_reason is None

    # Clip 2: hud_aware_blur is unsupported by current clip_renderer.py
    assert clip2.framing.worker_supported is False
    assert "Worker backend/media_pipeline/clip_renderer.py lacks implementation" in clip2.framing.unsupported_reason

    # Worker compatibility section reflects unsupported features
    assert manifest.worker_compatibility["all_features_worker_ready"] is False
    assert manifest.worker_compatibility["requires_integration_request"] is True
    assert any("framing:hud_aware_blur" in f for f in manifest.worker_compatibility["unsupported_features_detected"])


def test_deterministic_manifest_hash(complex_timeline_document):
    """Verify manifest hash is 100% deterministic and sensitive to changes."""
    manifest1 = build_render_manifest(document=complex_timeline_document, revision=1)
    manifest2 = build_render_manifest(document=complex_timeline_document, revision=1)

    assert manifest1.manifest_hash != ""
    assert manifest1.manifest_hash == manifest2.manifest_hash

    # Mutating a timing property changes the hash
    doc_mod = copy.deepcopy(complex_timeline_document)
    doc_mod["timeline"]["tracks"][0]["clips"][0]["start_seconds"] = 0.5
    manifest_mod = build_render_manifest(document=doc_mod, revision=1)

    assert manifest_mod.manifest_hash != manifest1.manifest_hash
