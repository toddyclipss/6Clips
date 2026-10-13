# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for Wave 3 Motion Contract: DTO, permitted uses, and drag payload serialization."""
import json
import pytest

from backend.library_workflows.motion_contract import (
    MotionAssetIntent,
    MIME_MOTION_ASSET,
)


def test_motion_intent_video_track():
    intent = MotionAssetIntent(
        asset_id="clip1",
        key="gv:clip1",
        title="Vertical Hook Intro",
        media_type="video",
        stream_url="/api/videos/clip1/stream",
        duration_seconds=12.5,
        aspect_ratio="9:16",
        permitted_uses=["timeline_motion", "derivative_clips"],
        intent_action="add_track",
        target_track="video_1",
    )

    assert intent.target_track == "video_1"
    assert "timeline_motion" in intent.permitted_uses

    dnd_str = intent.to_dnd_json()
    data = json.loads(dnd_str)
    assert data["key"] == "gv:clip1"
    assert data["title"] == "Vertical Hook Intro"
    assert data["media_type"] == "video"
    assert data["stream_url"] == "/api/videos/clip1/stream"
    assert data["aspect_ratio"] == "9:16"
    assert data["duration_seconds"] == 12.5
    assert data["target_track"] == "video_1"

    # Verify MIME constant
    assert MIME_MOTION_ASSET == "application/x-6clips-asset"


def test_motion_intent_audio_track():
    intent = MotionAssetIntent(
        asset_id="synth_beat",
        key="music:synth_beat",
        title="Synth Beat",
        media_type="audio",
        stream_url="/api/music/synth_beat/stream",
        duration_seconds=45.0,
        permitted_uses=["timeline_motion"],
        intent_action="audio_bed",
        target_track="audio_1",
    )

    assert intent.target_track == "audio_1"
    assert intent.media_type == "audio"
    d = intent.to_dict()
    assert d["intent_action"] == "audio_bed"


def test_motion_intent_roundtrip_deserialization():
    raw = {
        "asset_id": "badge_1",
        "key": "img:badge_1",
        "title": "Verified Badge",
        "media_type": "image",
        "stream_url": "/api/images/badge_1/stream",
        "duration_seconds": 0.0,
        "aspect_ratio": "1:1",
        "source_provenance": "library_user_asset",
        "permitted_uses": ["timeline_motion"],
        "intent_action": "broll_overlay",
        "target_track": "overlay_1",
        "target_start_time_seconds": 2.5,
        "file_sha256": "abc123def456",
    }
    intent = MotionAssetIntent.from_dict(raw)
    assert intent.asset_id == "badge_1"
    assert intent.key == "img:badge_1"
    assert intent.aspect_ratio == "1:1"
    assert intent.target_start_time_seconds == 2.5
    assert intent.to_dict() == raw
