# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 21 Agent 5: Native Motion Spec Compliance Tests for all 15 Legacy Slugs."""

import json
import pytest

from backend.knowledge_migration.converter import LegacyProjectConverter
from backend.knowledge_migration.detector import LegacyBlockDetector
from backend.native_motion.schema import NativeMotionSpec

ALL_SLUGS = [
    "ai-answer-rank",
    "apple-money-count",
    "aurora",
    "bar-chart-race",
    "carousel-text-circle-1",
    "closure-test-block",
    "creator-hud",
    "glass-hero",
    "glitch-transition",
    "hw-path-text",
    "lower-third-bild",
    "minimal-title",
    "notification-cascade",
    "spotify-card",
    "tiktok-follow",
    "weight-wave",
    "yt-lower-third",
]


@pytest.mark.parametrize("slug", ALL_SLUGS)
def test_all_slugs_convert_to_valid_native_motion_spec(slug):
    converter = LegacyProjectConverter()
    doc = {
        "schema_version": 1,
        "title": f"Test Project for {slug}",
        "aspect_ratio": "9:16",
        "timeline": {
            "fps": 30,
            "duration_seconds": 4.0,
            "tracks": [
                {
                    "id": "track_video",
                    "type": "video",
                    "clips": [
                        {"id": "bg_cut", "type": "video", "asset_file": "bg.mp4", "start_seconds": 0.0, "duration_seconds": 4.0}
                    ]
                },
                {
                    "id": "track_graphics",
                    "type": "graphics",
                    "clips": [
                        {
                            "id": f"clip_{slug}",
                            "type": "block",
                            "block_id": slug,
                            "start_seconds": 0.5,
                            "duration_seconds": 3.0,
                            "variables": {
                                "TXT_MAIN_1_Line": f"Headline for {slug}",
                                "TXT_SUB": "Subheadline text"
                            }
                        }
                    ]
                }
            ]
        }
    }

    migrated_doc, count = converter.convert_project_doc(doc, project_id=f"proj_{slug}")
    assert count == 1
    assert migrated_doc["schema_version"] == 2

    # Zero legacy blocks remaining
    assert len(LegacyBlockDetector.detect_in_project_doc(migrated_doc)) == 0

    # Video track preserved
    video_track = next(t for t in migrated_doc["timeline"]["tracks"] if t["id"] == "track_video")
    assert len(video_track["clips"]) == 1
    assert video_track["clips"][0]["id"] == "bg_cut"

    # Native spec present in code.files and validates with NativeMotionSpec
    spec_file = next(f for f in migrated_doc["code"]["files"] if f["path"] == "native_motion/spec.json")
    spec_data = json.loads(spec_file["content"])
    spec = NativeMotionSpec.model_validate(spec_data)

    assert spec.schema_version == "native_motion_v1"
    assert spec.width == 1080
    assert spec.height == 1920
    assert len(spec.scenes) >= 1
    assert len(spec.scenes[0].elements) >= 1
    assert len(spec.knowledge_refs) >= 1
    assert spec.knowledge_refs[0].doc_id is not None
