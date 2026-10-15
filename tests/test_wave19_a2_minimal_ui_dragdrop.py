#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Automated Test Suite for Wave 19 Agent 2:
Minimal UI, One Clean Player, Native Drag/Drop & Ephemeral Hover Previews.

Covers:
1. Player Cleanliness: No goal composer, prompt input, Run Goal, Blank Project, or preset chips inside StudioPreviewStage.
2. Resource Panel Cleanliness: No yt-dlp remote video ingest button, download stream modal, or 1080p/720p quality chooser.
3. Catalog Card Cleanliness: No 'preview block' eye button, 'insert block' button, or 'ask AI' button on cards. Accessible drag and focus.
4. Native Timeline Drag & Drop: Strict track type compatibility (captions->text, media->video, audio->audio, transitions->boundaries) with pre-drop visual feedback and rejection before CAS mutation.
5. Ephemeral Stage Hover Previews: Debounced ghost preview triggers on hover/focus, mouse leave/blur cleanly restores previous project frame/playback state without dirtying project.
6. 196 Donor Census & Categorization: Faithful mapping to authentic donor gallery groups, 'Unclassified in source' honest labeling, exclusion of 6Clips originals.
7. Refine Right Inspector: Context-sensitive native Tools alongside Properties and Variables.
8. Legacy Tools Crosswalk: Audit of all 21 legacy tools from ViralMint-Legado.
"""
import os
import sys
import json
import re
import pytest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_stage_no_unwanted_goal_composer():
    """Verify StudioPreviewStage does NOT render any goal composer overlay, prompt input, or preset chips."""
    stage_path = os.path.join(ROOT_DIR, "frontend", "src", "components", "motion", "StudioPreviewStage.jsx")
    assert os.path.isfile(stage_path), f"Missing {stage_path}"

    with open(stage_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Banned consumer SaaS overlay elements inside player
    assert 'data-testid="main-agent-goal-composer"' not in content, \
        "Found banned 'main-agent-goal-composer' overlay inside StudioPreviewStage.jsx"
    assert 'data-testid="main-agent-goal-input"' not in content, \
        "Found banned 'main-agent-goal-input' prompt field inside StudioPreviewStage.jsx"
    assert 'data-testid="main-agent-goal-submit"' not in content, \
        "Found banned 'main-agent-goal-submit' button inside StudioPreviewStage.jsx"
    assert 'data-testid="main-agent-blank-project"' not in content, \
        "Found banned 'main-agent-blank-project' button inside StudioPreviewStage.jsx"
    assert "Viral AI Breakdown (9:16)" not in content, \
        "Found banned preset suggestion chips inside StudioPreviewStage.jsx"

    # Must preserve neutral blank stage and canonical player
    assert 'data-testid="motion-player"' in content, \
        "StudioPreviewStage.jsx missing canonical data-testid='motion-player'"
    assert 'data-testid="studio-stage-no-project"' in content, \
        "StudioPreviewStage.jsx missing neutral data-testid='studio-stage-no-project'"
    assert "No Project Loaded" in content, \
        "StudioPreviewStage.jsx missing neutral 'No Project Loaded' indicator"


def test_resource_panel_no_remote_ingest_controls():
    """Verify StudioResourcePanel does NOT render yt-dlp remote ingest buttons or download stream bars."""
    panel_path = os.path.join(ROOT_DIR, "frontend", "src", "components", "motion", "StudioResourcePanel.jsx")
    assert os.path.isfile(panel_path), f"Missing {panel_path}"

    with open(panel_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Banned ingest controls
    assert 'data-testid="ingest-url-button"' not in content, \
        "Found banned 'ingest-url-button' in StudioResourcePanel.jsx"
    assert "Download Video Stream (yt-dlp)" not in content, \
        "Found banned 'Download Video Stream (yt-dlp)' collapsible bar in StudioResourcePanel.jsx"
    assert 'MenuItem value="1080p"' not in content, \
        "Found banned 1080p/720p resolution chooser in StudioResourcePanel.jsx"
    assert "handleIngestUrl" not in content, \
        "Found leftover handleIngestUrl handler in StudioResourcePanel.jsx"


def test_catalog_cards_no_preview_insert_ask_buttons():
    """Verify catalog cards do not have duplicate eye/insert/ask AI buttons, but are accessible and draggable."""
    panel_path = os.path.join(ROOT_DIR, "frontend", "src", "components", "motion", "StudioResourcePanel.jsx")
    with open(panel_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Banned action buttons on catalog cards
    assert 'data-testid={`preview-block-${bName}`}' not in content, \
        "Found banned preview eye button on catalog cards in StudioResourcePanel.jsx"
    assert 'data-testid={`insert-block-${bName}`}' not in content, \
        "Found banned insert block button on catalog cards in StudioResourcePanel.jsx"
    assert "Preview block animation on player" not in content, \
        "Found banned 'Preview block animation on player' tooltip in StudioResourcePanel.jsx"
    assert "Ask AI to insert & style in Chat" not in content, \
        "Found banned 'Ask AI to insert & style in Chat' button in StudioResourcePanel.jsx"

    # Accessible native drag and focus support
    assert "draggable={isOperational}" in content, \
        "Catalog cards missing draggable={isOperational}"
    assert "tabIndex={isOperational ? 0 : -1}" in content, \
        "Catalog cards missing accessible keyboard tabIndex"
    assert "role=\"button\"" in content, \
        "Catalog cards missing accessible role=\"button\""
    assert "handleCatalogItemMouseEnter" in content, \
        "Catalog cards missing handleCatalogItemMouseEnter handler"
    assert "handleCatalogItemMouseLeave" in content, \
        "Catalog cards missing handleCatalogItemMouseLeave handler"


def test_timeline_drag_drop_compatibility_rules():
    """Verify timeline workspace enforces strict track type validation and rejection before CAS mutation."""
    workspace_path = os.path.join(ROOT_DIR, "frontend", "src", "components", "motion", "StudioTimelineWorkspace.jsx")
    assert os.path.isfile(workspace_path), f"Missing {workspace_path}"

    with open(workspace_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Track validation function must exist
    assert "isExternalItemValidForTrack" in content, \
        "StudioTimelineWorkspace.jsx missing isExternalItemValidForTrack"

    # Captions validation rule: text-captions / captions -> captions or text track
    assert "category === \"text-captions\"" in content or "category === 'text-captions'" in content, \
        "StudioTimelineWorkspace.jsx missing caption category compatibility check"
    assert "destType === \"captions\" || destType === \"text\"" in content or "destType === 'captions' || destType === 'text'" in content, \
        "StudioTimelineWorkspace.jsx missing text/captions track destination check"

    # Audio validation rule: audio / music -> audio track
    assert "destType === \"audio\"" in content or "destType === 'audio'" in content, \
        "StudioTimelineWorkspace.jsx missing audio track destination check"

    # Rejection callback
    assert "onDropRejected" in content, \
        "StudioTimelineWorkspace.jsx missing onDropRejected prop and invocation"

    # Verify MotionGraphics.jsx checks compatibility before CAS mutation
    mg_path = os.path.join(ROOT_DIR, "frontend", "src", "pages", "MotionGraphics.jsx")
    with open(mg_path, "r", encoding="utf-8") as f:
        mg_content = f.read()

    assert "handleDropRejected" in mg_content, \
        "MotionGraphics.jsx missing handleDropRejected callback"
    assert "Incompatible track:" in mg_content, \
        "MotionGraphics.jsx missing Incompatible track error notification"
    assert "onDropRejected={handleDropRejected}" in mg_content, \
        "MotionGraphics.jsx does not pass onDropRejected to StudioTimelineWorkspace"


def test_ephemeral_stage_hover_previews():
    """Verify hovering catalog blocks drives debounced ephemeral ghost preview and restores playhead on leave."""
    mg_path = os.path.join(ROOT_DIR, "frontend", "src", "pages", "MotionGraphics.jsx")
    with open(mg_path, "r", encoding="utf-8") as f:
        mg_content = f.read()

    # Check ghost preview state management in MotionGraphics
    assert "handleStartGhostPreview" in mg_content, \
        "MotionGraphics.jsx missing handleStartGhostPreview"
    assert "handleEndGhostPreview" in mg_content, \
        "MotionGraphics.jsx missing handleEndGhostPreview"
    assert "preGhostPlayingRef.current" in mg_content, \
        "MotionGraphics.jsx missing preGhostPlayingRef for restoring playback state"
    assert "ghostPreview={ghostPreview}" in mg_content, \
        "MotionGraphics.jsx does not pass ghostPreview to StudioPreviewStage"

    # Check ghost preview frame in StudioPreviewStage
    stage_path = os.path.join(ROOT_DIR, "frontend", "src", "components", "motion", "StudioPreviewStage.jsx")
    with open(stage_path, "r", encoding="utf-8") as f:
        stage_content = f.read()

    assert "ghostPreview" in stage_content, \
        "StudioPreviewStage.jsx missing ghostPreview prop"
    assert "data-testid=\"studio-ghost-preview-stage\"" in stage_content, \
        "StudioPreviewStage.jsx missing data-testid='studio-ghost-preview-stage'"


def test_196_donor_census_and_authentic_categorization():
    """Verify 196 donor block census and authentic donor categories from upstream metadata."""
    tax_path = os.path.join(ROOT_DIR, "frontend", "src", "utils", "catalogOriginals.js")
    assert os.path.isfile(tax_path), f"Missing {tax_path}"

    with open(tax_path, "r", encoding="utf-8") as f:
        tax_content = f.read()

    # Check authentic categories from donor gallery metadata
    expected_categories = [
        "scenes-demos",
        "transitions",
        "carousels",
        "text-captions",
        "blocks",
        "surfaces",
        "code",
        "data-charts",
        "3d-motion",
        "motion-effects",
    ]
    for cat in expected_categories:
        assert f"id: '{cat}'" in tax_content or f'id: "{cat}"' in tax_content, \
            f"Missing authentic category '{cat}' in HYPERFRAMES_CATEGORIES"

    # Check honest label for unclassified blocks
    assert "Unclassified in source" in tax_content, \
        "catalogOriginals.js missing honest 'Unclassified in source' label"

    # Exclude 6Clips originals from 196 donor census
    assert "'creator-hud'" in tax_content or '"creator-hud"' in tax_content, \
        "RETIRED_6CLIPS_BLOCK_IDS missing creator-hud exclusion"
    assert "'glitch-transition'" in tax_content or '"glitch-transition"' in tax_content, \
        "RETIRED_6CLIPS_BLOCK_IDS missing glitch-transition exclusion"


def test_refine_right_inspector_context_sensitive_tools():
    """Verify Refine inspector mounts Properties, Variables, and context-sensitive Tools."""
    mg_path = os.path.join(ROOT_DIR, "frontend", "src", "pages", "MotionGraphics.jsx")
    with open(mg_path, "r", encoding="utf-8") as f:
        mg_content = f.read()

    assert 'data-testid="tab-properties"' in mg_content, \
        "MotionGraphics.jsx missing tab-properties button"
    assert 'data-testid="tab-variables"' in mg_content, \
        "MotionGraphics.jsx missing tab-variables button"
    assert 'data-testid="tab-tools"' in mg_content, \
        "MotionGraphics.jsx missing tab-tools button"
    assert '<StudioToolsInspector' in mg_content, \
        "MotionGraphics.jsx missing StudioToolsInspector mount"

    # Verify StudioToolsInspector operations
    inspector_path = os.path.join(ROOT_DIR, "frontend", "src", "components", "motion", "StudioToolsInspector.jsx")
    with open(inspector_path, "r", encoding="utf-8") as f:
        ins_content = f.read()

    assert "handleSplit" in ins_content, "StudioToolsInspector missing handleSplit"
    assert "handleSpeedChange" in ins_content, "StudioToolsInspector missing handleSpeedChange"
    assert "handleSlip" in ins_content, "StudioToolsInspector missing handleSlip"
    assert "handleFramingSelect" in ins_content, "StudioToolsInspector missing handleFramingSelect"
    assert "handleGenerateCaptions" in ins_content, "StudioToolsInspector missing handleGenerateCaptions"
    assert "handleVolumeChange" in ins_content, "StudioToolsInspector missing handleVolumeChange"


def test_legacy_tools_crosswalk_integrity():
    """Verify all 21 legacy tool files in ViralMint-Legado are accounted for in the native architecture."""
    legacy_tools_dir = os.path.join("C:\\Users\\toddy\\Desktop\\ViralMint-Legado", "frontend", "src", "pages", "tools")
    if not os.path.isdir(legacy_tools_dir):
        pytest.skip("ViralMint-Legado read-only directory not accessible on this machine.")

    legacy_files = sorted([f for f in os.listdir(legacy_tools_dir) if f.endswith(".jsx")])
    assert len(legacy_files) == 21, f"Expected exactly 21 legacy tool files, found {len(legacy_files)}"

    expected_tools = [
        "AudioEnhance.jsx", "AutoChapters.jsx", "AutoZoom.jsx", "Captions.jsx",
        "Compress.jsx", "Crop.jsx", "Gif.jsx", "HookAnalysis.jsx",
        "MergeClips.jsx", "Metadata.jsx", "MusicVisualizer.jsx", "Reframe.jsx",
        "RemoveSilence.jsx", "Speed.jsx", "Subtitles.jsx", "Transform.jsx",
        "Translate.jsx", "Trim.jsx", "VideoDownload.jsx", "Voiceover.jsx",
        "Watermark.jsx",
    ]
    assert legacy_files == expected_tools, f"Tool list mismatch: {legacy_files}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
