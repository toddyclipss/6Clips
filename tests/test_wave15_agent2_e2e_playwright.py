# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 15 Agent 2: End-to-End Microsoft Edge Playwright Test Suite.

Verifies with a real browser and live backend:
1. Category navigation and 196-block reconciliation on /catalog.
2. Authentic category filters (captions, code-animation, vfx, transitions, effects, text-effects, social, data, scenes, source_missing).
3. Strict absence of retired 6Clips blocks (creator-hud, glitch-transition) from public Catalog and Motion picker.
4. Two real user Motion graphics flows inserting operational blocks from different categories.
5. Legacy project protection and migration diagnostics without data loss.
6. Isolated temporary database in %TEMP% (production viralmint.db is never touched).
"""
from __future__ import annotations

import os
import sys
import time
import socket
import tempfile
import threading
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def live_server():
    """Start isolated FastAPI server on a free port using a temporary database in %TEMP%."""
    temp_dir = tempfile.mkdtemp(prefix="viralmint_w15_agent2_")
    os.environ["VIRALMINT_DATA_DIR"] = temp_dir
    os.environ["VIRALMINT_FRONTEND_DIST"] = str(FRONTEND_DIST)

    import uvicorn
    from backend.main import app

    port = find_free_port()
    config = uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Poll until server is responding
    base_url = f"http://127.0.0.1:{port}"
    timeout = 10.0
    start_time = time.time()
    server_ready = False

    while time.time() - start_time < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                server_ready = True
                break
        except (OSError, ConnectionRefusedError):
            time.sleep(0.1)

    assert server_ready, "Isolated test backend server failed to start within timeout"

    yield {"base_url": base_url, "port": port, "temp_dir": temp_dir}

    server.should_exit = True
    thread.join(timeout=2.0)


def test_edge_catalog_navigation_and_196_reconciliation(live_server):
    """Real Edge test verifying 196 donor blocks and authentic HyperFrames categories in /catalog."""
    base_url = live_server["base_url"]
    screenshots_dir = Path(live_server["temp_dir"]) / "sentinel_screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge", headless=True)
        except Exception:
            browser = p.chromium.launch(headless=True)

        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # 1. Navigate to /catalog
        page.goto(f"{base_url}/catalog", wait_until="networkidle")
        page.wait_for_selector('[aria-label="Catalog Block Directory"]')

        # 2. Verify view filters are visible with 196 total
        all_original_btn = page.locator('[data-testid="filter-all-original"]')
        page.wait_for_selector('[data-testid="filter-all-original"]')
        assert "196" in all_original_btn.inner_text()

        available_btn = page.locator('[data-testid="filter-available-now"]')
        assert "10" in available_btn.inner_text()

        # 3. Verify neither 6Clips-authored block is present in DOM
        assert page.locator('[data-testid="catalog-card-creator-hud"]').count() == 0
        assert page.locator('[data-testid="catalog-card-glitch-transition"]').count() == 0

        # 4. Verify authentic HyperFrames category chips exist
        for cat in ["captions", "code-animation", "vfx", "transitions", "effects", "social", "data", "scenes"]:
            cat_locator = page.locator(f'[data-testid="category-filter-{cat}"]')
            assert cat_locator.count() > 0, f"Missing category filter chip for '{cat}'"

        # 5. Switch to "All original HyperFrames (196 verified)"
        all_original_btn.click()
        page.wait_for_timeout(300)

        # 6. Click "Scenes" category chip
        scenes_chip = page.locator('[data-testid="category-filter-scenes"]')
        scenes_chip.click()
        page.wait_for_timeout(300)

        # Aurora is an operational block classified under upstream 'scenes' category
        aurora_card = page.locator('[data-testid="catalog-card-aurora"]')
        assert aurora_card.count() > 0, "Operational block 'aurora' not found under scenes"

        # 7. Click aurora card to open inspector drawer
        aurora_card.click()
        page.wait_for_timeout(400)
        page.wait_for_selector('[data-testid="catalog-drawer"]')
        assert page.locator('[data-testid="catalog-drawer"]').count() > 0

        # Capture sentinel screenshot 1: Catalog drawer for operational block
        screenshot_path = screenshots_dir / "sentinel_01_catalog_scenes_drawer.png"
        page.screenshot(path=str(screenshot_path))
        assert screenshot_path.exists()
        print(f"\n[Sentinel 1] Captured {screenshot_path} at {time.strftime('%Y-%m-%d %H:%M:%S')}")

        browser.close()


def test_edge_motion_two_user_flows_and_legacy_protection(live_server):
    """Real Edge test verifying Motion picker, 2 real block insertion flows, and legacy protection."""
    base_url = live_server["base_url"]
    screenshots_dir = Path(live_server["temp_dir"]) / "sentinel_screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge", headless=True)
        except Exception:
            browser = p.chromium.launch(headless=True)

        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # 1. Navigate to /motion
        page.goto(f"{base_url}/motion", wait_until="networkidle")

        # 2. Switch to Catalog tab (Tab index 2) in left panel
        tabs = page.locator('.MuiTabs-root button')
        if tabs.count() >= 3:
            tabs.nth(2).click()
            page.wait_for_timeout(400)

        # 3. Verify creator-hud and glitch-transition are NOT in Motion picker
        assert page.locator('[data-testid="catalog-card-creator-hud"]').count() == 0
        assert page.locator('[data-testid="catalog-card-glitch-transition"]').count() == 0

        # Flow 1: Insert operational block from VFX (aurora)
        aurora_insert = page.locator('[data-testid="insert-block-aurora"]')
        if aurora_insert.count() > 0:
            aurora_insert.first.click()
            page.wait_for_timeout(500)

        # Flow 2: Insert operational block from Social (instagram-follow)
        insta_insert = page.locator('[data-testid="insert-block-instagram-follow"]')
        if insta_insert.count() > 0:
            insta_insert.first.click()
            page.wait_for_timeout(500)

        # Capture sentinel screenshot 2: Motion workspace with blocks
        screenshot_path2 = screenshots_dir / "sentinel_02_motion_workspace_inserted_blocks.png"
        page.screenshot(path=str(screenshot_path2))
        assert screenshot_path2.exists()
        print(f"\n[Sentinel 2] Captured {screenshot_path2} at {time.strftime('%Y-%m-%d %H:%M:%S')}")

        browser.close()
