# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for Wave 20 Agent 5: Legacy Block Detector & Inventory Ledger."""

import pytest
from backend.knowledge_migration.detector import LegacyBlockDetector
from backend.knowledge_migration.inventory import DonorInventoryLedger, LEGACY_TO_NATIVE_MAPPING


def test_detector_identifies_legacy_blocks():
    clip = {
        "id": "clip_1",
        "block_id": "lower-third-bild",
        "start_seconds": 1.0,
        "duration_seconds": 2.5,
        "variables": {"TXT_MAIN_1_Line": "Hello World", "TXT_SUB": "Sub text"}
    }
    ref = LegacyBlockDetector.detect_in_clip(clip, track_id="track_gfx")
    assert ref is not None
    assert ref.block_id == "lower-third-bild"
    assert ref.clip_id == "clip_1"
    assert ref.track_id == "track_gfx"
    assert ref.start_seconds == 1.0
    assert ref.duration_seconds == 2.5
    assert ref.variables["TXT_MAIN_1_Line"] == "Hello World"
    assert ref.is_retired_custom is False


def test_detector_identifies_retired_custom_blocks():
    clip_hud = {"id": "clip_hud", "block_id": "creator-hud", "duration_seconds": 3.0}
    clip_glitch = {"id": "clip_glitch", "block_id": "glitch-transition", "duration_seconds": 1.0}

    ref_hud = LegacyBlockDetector.detect_in_clip(clip_hud)
    ref_glitch = LegacyBlockDetector.detect_in_clip(clip_glitch)

    assert ref_hud is not None and ref_hud.is_retired_custom is True
    assert ref_glitch is not None and ref_glitch.is_retired_custom is True


def test_detector_ignores_clean_native_clips():
    clip = {
        "id": "clip_video_1",
        "type": "video",
        "asset_file": "media/video1.mp4",
        "start_seconds": 0.0,
        "duration_seconds": 5.0
    }
    ref = LegacyBlockDetector.detect_in_clip(clip)
    assert ref is None


def test_detector_extracts_shipped_blocks_from_asset_path():
    clip = {
        "id": "clip_path",
        "asset_file": "backend/catalog/shipped_blocks/weight-wave/weight-wave.html",
        "duration_seconds": 3.0
    }
    ref = LegacyBlockDetector.detect_in_clip(clip)
    assert ref is not None
    assert ref.block_id == "weight-wave"


def test_detector_project_document_scan():
    doc = {
        "title": "Test Multi-Block Project",
        "timeline": {
            "fps": 30,
            "duration_seconds": 10.0,
            "tracks": [
                {
                    "id": "track_video",
                    "type": "video",
                    "clips": [{"id": "c1", "type": "video", "asset_file": "v.mp4"}]
                },
                {
                    "id": "track_gfx",
                    "type": "graphics",
                    "clips": [
                        {"id": "b1", "block_id": "weight-wave", "start_seconds": 0.0, "duration_seconds": 2.0},
                        {"id": "b2", "block_id": "bar-chart-race", "start_seconds": 2.5, "duration_seconds": 3.0}
                    ]
                }
            ]
        }
    }
    refs = LegacyBlockDetector.detect_in_project_doc(doc)
    assert len(refs) == 2
    assert [r.block_id for r in refs] == ["weight-wave", "bar-chart-race"]


def test_inventory_ledger_mappings_and_fallbacks():
    ledger = DonorInventoryLedger()
    assert ledger.total_shipped_bundles >= 156

    # Test mapped slug
    m_lower = ledger.get_native_mapping("lower-third-bild")
    assert m_lower["capability_family"] == "typography_kinetic"
    assert m_lower["technique"] == "lower_third_bar"

    # Test unknown slug fallback
    m_unknown = ledger.get_native_mapping("non-existent-fantasy-block")
    assert m_unknown["capability_family"] == "typography_kinetic"
    assert "default_fill" in m_unknown
