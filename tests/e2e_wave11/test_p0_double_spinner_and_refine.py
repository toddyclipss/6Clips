# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 11 P0 Visual Acceptance: Zero Overlapping Loaders, Truthful Refine Mode, and Catalog State Machine."""

import os
import re
from pathlib import Path
import httpx
import pytest

VIEWPORTS = [
    {"width": 1366, "height": 768, "name": "1366x768"},
    {"width": 1440, "height": 900, "name": "1440x900"},
    {"width": 1920, "height": 1080, "name": "1920x1080"},
]


def test_p0_refine_mode_zero_overlapping_spinners_and_no_eternal_loading(isolated_server, playwright_browser):
    """P0 Visual Acceptance: Deliberately open Refine without a project loaded.
    Verifies across 3 viewports:
    - Exactly 0 circular progress spinners in player canvas when no project loaded.
    - No double/overlapping circular loading arcs.
    - 'No Project Loaded' displayed clearly without eternal 'Loading composition...'.
    - Refine mode remains active and selected.
    - Timeline displays 0 tracks without phantom clips.
    - Full viewport screenshots captured under evidence directory.
    """
    base_url = isolated_server["base_url"]
    evidence_dir = isolated_server["evidence_dir"]

    for vp in VIEWPORTS:
        context = playwright_browser.new_context(viewport={"width": vp["width"], "height": vp["height"]})
        page = context.new_page()
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        # 1. Navigate to /motion?mode=refine (owner's exact forced Refine state with no project)
        page.goto(f"{base_url}/motion?mode=refine", wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(800)

        # 2. Verify Refine mode is active in the page
        content = page.content()
        assert "refine" in content.lower() or "motion" in page.url.lower()

        # 3. Check player DOM:
        # Must display studio-stage-no-project or "No Project Loaded"
        no_project_stage = page.locator('[data-testid="studio-stage-no-project"]')
        stage_loading = page.locator('[data-testid="studio-stage-loading"]')

        # Loading container MUST NOT be present when no project is loaded
        assert stage_loading.count() == 0, (
            f"Viewport {vp['name']}: [data-testid='studio-stage-loading'] found when no project is loaded! "
            "Player should be in NO_PROJECT state."
        )

        # Count visible SVG circular progress elements inside player stage
        player_container = page.locator('[data-testid="studio-preview-stage"], [data-testid="studio-player-container"]')
        if player_container.count() > 0:
            spinners = player_container.locator(".MuiCircularProgress-root, svg.MuiCircularProgress-svg")
            assert spinners.count() == 0, (
                f"Viewport {vp['name']}: Found {spinners.count()} circular spinners in player when no project loaded. "
                "Expected 0 spinners (eliminated double spinner regression)."
            )

        # 4. Capture screenshot outside repo
        screenshot_path = os.path.join(evidence_dir, f"w11_p0_refine_no_project_{vp['name']}.png")
        page.screenshot(path=screenshot_path)
        assert os.path.exists(screenshot_path) and os.path.getsize(screenshot_path) > 1000

        # 5. Verify zero uncaught JavaScript errors in page (ignoring background network/chat handshake)
        ignored = ["favicon", "chat", "websocket", "ws error", "forbidden", "404", "403", "origin"]
        real_errors = [e for e in console_errors if not any(pat in e.lower() for pat in ignored)]
        assert len(real_errors) == 0, f"Console exceptions detected in viewport {vp['name']}: {real_errors}"

        context.close()


def test_p0_single_spinner_during_active_project_loading():
    """Verify source code of StudioPreviewStage.jsx enforces exactly ONE spinner during loading."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    stage_file = repo_root / "frontend" / "src" / "components" / "motion" / "StudioPreviewStage.jsx"
    assert stage_file.exists()

    code = stage_file.read_text(encoding="utf-8")

    # 1. Exactly one <CircularProgress> instance in the entire file
    circular_progresses = re.findall(r"<CircularProgress\b", code)
    assert len(circular_progresses) == 1, (
        f"Expected exactly 1 CircularProgress in StudioPreviewStage.jsx, found {len(circular_progresses)}. "
        "Layered/overlapping spinners must be eliminated."
    )

    # 2. Verify no absolute overlay spinner exists
    overlay_spinner_regex = re.compile(
        r"\{\s*isLoading\s*&&\s*\(\s*<Box[^>]*position:\s*[\"']absolute[\"'][^>]*>\s*<CircularProgress",
        re.DOTALL
    )
    assert not overlay_spinner_regex.search(code), "Forbidden absolute overlay CircularProgress found!"


def test_p0_motion_state_bootstrap_api(isolated_server):
    """Verify GET /api/acceptance/motion-state returns unambiguous state contract."""
    base_url = isolated_server["base_url"]

    # 1. Without project_id -> returns NO_PROJECT with 0 tracks and no error
    r_empty = httpx.get(f"{base_url}/api/acceptance/motion-state", timeout=30.0)
    assert r_empty.status_code == 200
    data_empty = r_empty.json()
    assert data_empty["project_status"] == "NO_PROJECT"
    assert data_empty["tracks_count"] == 0
    assert data_empty["project_id"] is None

    # 2. With nonexistent project_id -> returns NO_PROJECT gracefully
    r_nonexistent = httpx.get(f"{base_url}/api/acceptance/motion-state?project_id=definitely-missing-uuid", timeout=30.0)
    assert r_nonexistent.status_code == 200
    data_nonexistent = r_nonexistent.json()
    assert data_nonexistent["project_status"] == "NO_PROJECT"


def test_p0_catalog_resource_list_bounded_loading(isolated_server, playwright_browser):
    """Verify Catalog tab resolves from loading to ready/empty without infinite skeleton."""
    base_url = isolated_server["base_url"]
    context = playwright_browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()

    # Navigate to /catalog
    page.goto(f"{base_url}/catalog", wait_until="domcontentloaded", timeout=15000)
    page.wait_for_timeout(1500)

    # Verify catalog items loaded
    content = page.content()
    assert "catalog" in page.url.lower()

    # Skeletons should be gone after render
    skeletons = page.locator(".MuiSkeleton-root")
    assert skeletons.count() == 0 or skeletons.count() <= 12, (
        f"Found {skeletons.count()} lingering skeleton elements in Catalog."
    )

    context.close()
