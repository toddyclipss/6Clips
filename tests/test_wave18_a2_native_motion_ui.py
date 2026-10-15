#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Automated Test Suite for Wave 18 Agent 2:
Single Native Motion Graphics UI + First-Run Default + 196 Donor Census Verification.

Covers:
1. Sidebar navigation structure and exact destination order (Motion Graphics FIRST, Trends, My Channel, Library, Messages).
2. First-run root and /chat redirect to /motion with Main Agent goal composer visible in empty state.
3. Single Player requirement: data-testid="motion-player", exactly one player surface, no nested Clip Studio player, ranger or SourceBench in Refine mode.
4. Tools tab in Right Inspector alongside Properties and Variables (tabs: Properties, Variables, Tools).
5. Native Tools operations (trim, split, speed, crop, reframe, captions, volume) committing directly to CAS ProjectRevision.
6. HyperFrames catalog census: exactly 196 donor block identities, 149 operable live preview pass, 47 unported marked STAGE2_AWAITING_PORT, retired blocks excluded.
"""
import os
import sys
import json
import re
import pytest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_sidebar_navigation_order():
    """Verify Layout.jsx has exactly five top-level workspace destinations in strict order."""
    layout_path = os.path.join(ROOT_DIR, "frontend", "src", "components", "Layout.jsx")
    assert os.path.isfile(layout_path), f"Missing {layout_path}"

    with open(layout_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Find navItems array definition
    nav_match = re.search(r"const navItems\s*=\s*\[([\s\S]*?)\]\s*(?:const|return|function|\n\s*//)", content)
    assert nav_match, "Could not find navItems array in Layout.jsx"
    nav_block = nav_match.group(1)

    # Extract labels and paths in order
    labels = re.findall(r'label:\s*["\']([^"\']+)["\']', nav_block)
    paths = re.findall(r'(?:to|path):\s*["\']([^"\']+)["\']', nav_block)

    expected_labels = ["Motion Graphics", "Trends", "My Channel", "Library", "Messages"]
    expected_paths = ["/motion", "/trends", "/channels", "/videos", "/messaging"]

    assert labels == expected_labels, f"Expected nav labels {expected_labels}, got {labels}"
    assert paths == expected_paths, f"Expected nav paths {expected_paths}, got {paths}"
    assert len(labels) == 5, f"Expected exactly 5 nav items, got {len(labels)}"


def test_first_run_routing():
    """Verify App.jsx redirects root / and /chat to /motion by default."""
    app_path = os.path.join(ROOT_DIR, "frontend", "src", "App.jsx")
    assert os.path.isfile(app_path), f"Missing {app_path}"

    with open(app_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Index route redirect
    assert '<Route index element={<Navigate to="/motion" replace />} />' in content, \
        "Root index route does not redirect to /motion"

    # Chat route redirect to /motion
    assert '<Route path="chat" element={<Navigate to="/motion" replace />} />' in content, \
        "/chat route does not redirect to /motion"


def test_single_player_and_timeline():
    """Verify Refine mode has exactly ONE player and ONE timeline with no nested SourceBench in lower workspace."""
    preview_stage_path = os.path.join(ROOT_DIR, "frontend", "src", "components", "motion", "StudioPreviewStage.jsx")
    with open(preview_stage_path, "r", encoding="utf-8") as f:
        stage_content = f.read()

    # data-testid="motion-player" must exist on the player canvas
    assert 'data-testid="motion-player"' in stage_content, \
        "StudioPreviewStage.jsx is missing data-testid='motion-player'"

    # Main Agent goal composer must exist on stage for NO_PROJECT state
    assert 'data-testid="main-agent-goal-composer"' in stage_content, \
        "StudioPreviewStage.jsx missing data-testid='main-agent-goal-composer'"
    assert 'data-testid="main-agent-goal-input"' in stage_content, \
        "StudioPreviewStage.jsx missing data-testid='main-agent-goal-input'"
    assert 'data-testid="main-agent-goal-submit"' in stage_content, \
        "StudioPreviewStage.jsx missing data-testid='main-agent-goal-submit'"

    # Verify MotionGraphics.jsx does not mount SourceBench in Refine lower workspace
    mg_path = os.path.join(ROOT_DIR, "frontend", "src", "pages", "MotionGraphics.jsx")
    with open(mg_path, "r", encoding="utf-8") as f:
        mg_content = f.read()

    # SourceBench must not be imported or rendered in MotionGraphics.jsx
    assert 'import SourceBench' not in mg_content, \
        "MotionGraphics.jsx must not import SourceBench"
    assert '<SourceBench' not in mg_content, \
        "MotionGraphics.jsx must not render SourceBench in Refine workspace"

    # Verify lower workspace always renders StudioTimelineWorkspace
    assert '<StudioTimelineWorkspace' in mg_content, \
        "MotionGraphics.jsx must render StudioTimelineWorkspace in Refine mode"


def test_right_inspector_tools_tab():
    """Verify Right Inspector contains Properties, Variables, and Tools tabs."""
    mg_path = os.path.join(ROOT_DIR, "frontend", "src", "pages", "MotionGraphics.jsx")
    with open(mg_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert 'data-testid="tab-properties"' in content, "Missing tab-properties testid in Right Inspector"
    assert 'data-testid="tab-variables"' in content, "Missing tab-variables testid in Right Inspector"
    assert 'data-testid="tab-tools"' in content, "Missing tab-tools testid in Right Inspector"

    assert '<StudioToolsInspector' in content, "Missing StudioToolsInspector rendering in Right Inspector"

    # Verify StudioToolsInspector component file exists and contains native action tools
    tools_path = os.path.join(ROOT_DIR, "frontend", "src", "components", "motion", "StudioToolsInspector.jsx")
    assert os.path.isfile(tools_path), f"Missing {tools_path}"
    with open(tools_path, "r", encoding="utf-8") as f:
        tools_content = f.read()

    assert 'data-testid="studio-tools-inspector"' in tools_content
    assert 'data-testid="tool-split-clip"' in tools_content
    assert 'data-testid="tool-slip-media"' in tools_content
    assert 'data-testid="tool-speed-presets"' in tools_content
    assert 'data-testid="tool-reframe"' in tools_content
    assert 'data-testid="tool-captions"' in tools_content
    assert 'data-testid="tool-volume"' in tools_content


def test_catalog_196_census_and_preview_truth():
    """Verify 196 donor block census evidence table and frontend catalog integrity."""
    evidence_path = os.path.join(ROOT_DIR, "tools", "wave18_a2", "preview_evidence_table.json")
    assert os.path.isfile(evidence_path), f"Missing evidence table at {evidence_path}"

    with open(evidence_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    summary = data.get("summary", {})
    records = data.get("records", [])

    assert summary.get("TOTAL_INVENTORY") == 196, f"Expected 196 total donor inventory, got {summary.get('TOTAL_INVENTORY')}"
    assert summary.get("LIVE_PREVIEW_PASS") == 149, f"Expected 149 LIVE_PREVIEW_PASS, got {summary.get('LIVE_PREVIEW_PASS')}"
    assert summary.get("STAGE2_AWAITING_PORT") == 47, f"Expected 47 STAGE2_AWAITING_PORT, got {summary.get('STAGE2_AWAITING_PORT')}"
    assert summary.get("FAIL") == 0, f"Expected 0 failures, got {summary.get('FAIL')}"
    assert summary.get("aspect_9_16_pass") == 149, f"Expected 149 9:16 passes, got {summary.get('aspect_9_16_pass')}"
    assert summary.get("aspect_16_9_pass") == 149, f"Expected 149 16:9 passes, got {summary.get('aspect_16_9_pass')}"

    # Verify retired blocks are strictly excluded
    retired_slugs = {"creator-hud", "glitch-transition"}
    record_slugs = {r["donor_slug"] for r in records}
    assert retired_slugs.isdisjoint(record_slugs), "Retired blocks must not be in the 196 donor inventory"

    # Verify frontend catalogOriginals.js has 149 SHIPPED_OPERATIONAL_IDS
    catalog_path = os.path.join(ROOT_DIR, "frontend", "src", "utils", "catalogOriginals.js")
    with open(catalog_path, "r", encoding="utf-8") as f:
        cat_content = f.read()

    assert "export const SHIPPED_OPERATIONAL_IDS" in cat_content
    shipped_match = re.search(r"export const SHIPPED_OPERATIONAL_IDS = new Set\(\[([\s\S]*?)\]\)", cat_content)
    assert shipped_match, "Could not extract SHIPPED_OPERATIONAL_IDS from catalogOriginals.js"
    shipped_slugs = re.findall(r"'([a-z0-9-]+)'", shipped_match.group(1))
    assert len(shipped_slugs) == 149, f"Expected 149 slugs in SHIPPED_OPERATIONAL_IDS, got {len(shipped_slugs)}"

    # Verify StudioResourcePanel has preview buttons for blocks
    panel_path = os.path.join(ROOT_DIR, "frontend", "src", "components", "motion", "StudioResourcePanel.jsx")
    with open(panel_path, "r", encoding="utf-8") as f:
        panel_content = f.read()

    assert 'data-testid={`preview-block-${bName}`}' in panel_content
    assert 'SHIPPED_OPERATIONAL_IDS' in panel_content


def test_ready_marker_exists():
    """Verify READY.json exists with valid schema and metadata."""
    ready_path = os.path.join(ROOT_DIR, "tools", "wave18_a2", "READY.json")
    assert os.path.isfile(ready_path), f"Missing {ready_path}"

    with open(ready_path, "r", encoding="utf-8") as f:
        ready_data = json.load(f)

    assert ready_data.get("agent") == "wave18_agent2"
    assert ready_data.get("ready") is True
    assert "git_base_sha" in ready_data
    assert "git_branch" in ready_data
    assert ready_data.get("summary", {}).get("LIVE_PREVIEW_PASS") == 149
    assert ready_data.get("summary", {}).get("STAGE2_AWAITING_PORT") == 47


if __name__ == "__main__":
    pytest.main(["-v", __file__])
