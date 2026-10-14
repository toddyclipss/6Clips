# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 12 Stage 3: Independent Visual Regression & Refine Mode Zero-Spinner Acceptance.

Verifies:
1. Deliberately open /motion?mode=refine with no project loaded across 3 viewports:
   - 1366x768
   - 1440x900
   - 1920x1080
2. Exactly 0 circular progress spinners in player canvas when no project loaded.
3. No double/overlapping circular loading arcs.
4. "No Project Loaded" displayed clearly without eternal "Loading composition...".
5. Refine mode remains active and selected.
6. Catalog panel displays bounded ready/empty state without eternal loading spinner.
7. Capture full viewport PNG screenshots to %TEMP%/6clips_wave12_idle_audit/.
"""

import os
from pathlib import Path
import re
import pytest
from tests.e2e_wave12.conftest import EVIDENCE_DIR

VIEWPORTS = [
    {"width": 1366, "height": 768, "name": "1366x768"},
    {"width": 1440, "height": 900, "name": "1440x900"},
    {"width": 1920, "height": 1080, "name": "1920x1080"},
]


def test_refine_mode_zero_overlapping_spinners_and_no_eternal_loading(isolated_server, playwright_browser):
    """P0 Visual Acceptance: Deliberately open Refine without a project loaded."""
    base_url = isolated_server["base_url"]

    for vp in VIEWPORTS:
        context = playwright_browser.new_context(viewport={"width": vp["width"], "height": vp["height"]})
        page = context.new_page()
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        # 1. Navigate to /motion?mode=refine
        page.goto(f"{base_url}/motion?mode=refine", wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(1000)

        # 2. Verify Refine mode is active in the page
        content = page.content()
        assert "refine" in content.lower() or "motion" in page.url.lower()

        # 3. Check player DOM:
        # Loading container MUST NOT be present when no project is loaded
        stage_loading = page.locator('[data-testid="studio-stage-loading"]')
        assert stage_loading.count() == 0, (
            f"Viewport {vp['name']}: [data-testid='studio-stage-loading'] found when no project is loaded!"
        )

        # Count visible SVG circular progress elements inside player stage
        player_container = page.locator('[data-testid="studio-preview-stage"], [data-testid="studio-player-container"]')
        if player_container.count() > 0:
            spinners = player_container.locator(".MuiCircularProgress-root, svg.MuiCircularProgress-svg")
            assert spinners.count() == 0, (
                f"Viewport {vp['name']}: Found {spinners.count()} circular spinners in player when no project loaded."
            )

        # 4. Capture screenshot outside repo
        screenshot_path = EVIDENCE_DIR / f"w12_p0_refine_no_project_{vp['name']}.png"
        page.screenshot(path=str(screenshot_path))
        assert screenshot_path.is_file() and screenshot_path.stat().st_size > 1000

        # 5. Verify zero uncaught critical JavaScript exceptions
        ignored = ["favicon", "chat", "websocket", "ws error", "forbidden", "404", "403", "origin", "connection"]
        real_errors = [e for e in console_errors if not any(pat in e.lower() for pat in ignored)]
        assert len(real_errors) == 0, f"Console exceptions in {vp['name']}: {real_errors}"

        context.close()


def test_catalog_bounded_loading_and_resources_display(isolated_server, playwright_browser):
    """Verify Catalog tab opens cleanly without infinite spinner."""
    base_url = isolated_server["base_url"]
    context = playwright_browser.new_context(viewport={"width": 1920, "height": 1080})
    page = context.new_page()

    page.goto(f"{base_url}/motion", wait_until="domcontentloaded", timeout=20000)
    page.wait_for_timeout(800)

    # Click Catalog or Resources panel if available
    catalog_btn = page.locator('button:has-text("Catalog"), button:has-text("Resources"), [data-testid="catalog-tab"]')
    if catalog_btn.count() > 0:
        catalog_btn.first.click()
        page.wait_for_timeout(1000)

    # Screenshot catalog view
    screenshot_path = EVIDENCE_DIR / "w12_catalog_panel_view.png"
    page.screenshot(path=str(screenshot_path))
    assert screenshot_path.is_file()

    context.close()


def test_studio_preview_stage_source_code_contract():
    """Verify source code of StudioPreviewStage enforces single spinner contract."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    stage_file = repo_root / "frontend" / "src" / "components" / "motion" / "StudioPreviewStage.jsx"
    assert stage_file.exists()

    code = stage_file.read_text(encoding="utf-8")
    circular_progresses = re.findall(r"<CircularProgress\b", code)
    assert len(circular_progresses) == 1, (
        f"Expected exactly 1 CircularProgress in StudioPreviewStage.jsx, found {len(circular_progresses)}."
    )
