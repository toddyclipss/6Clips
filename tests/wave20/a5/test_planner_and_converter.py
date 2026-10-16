# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for Wave 20 Agent 5: Migration Planner and Converter."""

import json
import pytest
from backend.knowledge_migration.converter import LegacyProjectConverter
from backend.knowledge_migration.detector import LegacyBlockDetector
from backend.knowledge_migration.models import MigrationStatus, RiskLevel
from backend.knowledge_migration.planner import ProjectMigrationPlanner


@pytest.fixture
def sample_legacy_project():
    return {
        "schema_version": 1,
        "title": "Corporate Lower Third Demo",
        "aspect_ratio": "9:16",
        "timeline": {
            "fps": 30,
            "duration_seconds": 6.0,
            "tracks": [
                {
                    "id": "track_video_main",
                    "type": "video",
                    "clips": [
                        {"id": "cut_1", "type": "video", "asset_file": "speaker.mp4", "start_seconds": 0.0, "duration_seconds": 6.0}
                    ]
                },
                {
                    "id": "track_graphics_main",
                    "type": "graphics",
                    "clips": [
                        {
                            "id": "elem_legacy_1",
                            "type": "block",
                            "block_id": "lower-third-bild",
                            "start_seconds": 1.0,
                            "duration_seconds": 3.0,
                            "variables": {
                                "TXT_MAIN_1_Line": "DR. JANE DOE",
                                "TXT_SUB": "CHIEF SCIENTIST"
                            }
                        }
                    ]
                }
            ]
        }
    }


def test_planner_assess_readiness(sample_legacy_project):
    planner = ProjectMigrationPlanner()
    readiness = planner.assess_project_readiness(
        project_id="proj_123",
        project_name="Corporate Lower Third Demo",
        revision=1,
        document_doc=sample_legacy_project
    )
    assert readiness.has_legacy_blocks is True
    assert readiness.legacy_block_count == 1
    assert readiness.legacy_slugs == ["lower-third-bild"]
    assert readiness.risk_level == RiskLevel.LOW
    assert readiness.status == MigrationStatus.READY


def test_converter_transforms_to_native_motion_v1(sample_legacy_project):
    converter = LegacyProjectConverter()
    migrated_doc, count = converter.convert_project_doc(sample_legacy_project, project_id="proj_123")

    assert count == 1
    assert migrated_doc["schema_version"] == 2

    # Verify zero legacy blocks in migrated doc
    legacy_refs = LegacyBlockDetector.detect_in_project_doc(migrated_doc)
    assert len(legacy_refs) == 0

    # Verify video track was preserved untouched
    tracks = migrated_doc["timeline"]["tracks"]
    video_track = next(t for t in tracks if t["id"] == "track_video_main")
    assert len(video_track["clips"]) == 1
    assert video_track["clips"][0]["id"] == "cut_1"

    # Verify graphics track has native_motion clip
    gfx_track = next(t for t in tracks if t["id"] == "track_graphics_main")
    assert len(gfx_track["clips"]) == 1
    clip = gfx_track["clips"][0]
    assert clip["type"] == "native_motion"
    assert clip["native_motion"]["headline"] == "DR. JANE DOE"
    assert clip["native_motion"]["subtext"] == "CHIEF SCIENTIST"
    assert clip["native_motion"]["schema_version"] == "native_motion_v1"

    # Verify code.files contains native_motion/spec.json
    files = migrated_doc.get("code", {}).get("files", [])
    spec_file = next((f for f in files if f.get("path") == "native_motion/spec.json"), None)
    assert spec_file is not None
    spec_data = json.loads(spec_file["content"])
    assert spec_data["schema_version"] == "native_motion_v1"
    assert len(spec_data["scenes"]) >= 1
    assert any(elem.get("type") == "text" for s in spec_data["scenes"] for elem in s.get("elements", []))


def test_converter_preserves_clean_native_projects():
    converter = LegacyProjectConverter()
    clean_doc = {
        "schema_version": 2,
        "title": "Already Native Project",
        "timeline": {
            "fps": 30,
            "duration_seconds": 5.0,
            "tracks": [
                {"id": "t1", "type": "video", "clips": [{"id": "c1", "type": "video", "duration_seconds": 5.0}]}
            ]
        }
    }
    migrated_doc, count = converter.convert_project_doc(clean_doc)
    assert count == 0
    assert migrated_doc == clean_doc
