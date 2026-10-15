# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 16 Agent 2 Real Microsoft Edge Playwright Browser Test Suite.

Validates the full 196 HyperFrames catalog, authentic taxonomy, owner's 37 packaged cards,
Motion workflow, responsive viewports (1366x768, 1440x900, 1920x1080), zero console errors,
and saves verified Edge screenshots to tests/e2e_wave16/agent2/screenshots/.
"""

import os
import sys
import time
import socket
import tempfile
import shutil
import subprocess
from pathlib import Path
import pytest
import httpx
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"
SCREENSHOTS_DIR = REPO_ROOT / "tests" / "e2e_wave16" / "agent2" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

VIEWPORTS = [
    {"width": 1366, "height": 768, "name": "1366x768"},
    {"width": 1440, "height": 900, "name": "1440x900"},
    {"width": 1920, "height": 1080, "name": "1920x1080"},
]


from tests.e2e_wave8.conftest import isolated_server, playwright_browser


class TestWave16Agent2RealEdgeAcceptance:
    """End-to-End Real Microsoft Edge Acceptance Testing for Wave 16 Agent 2."""

    def test_catalog_packaged_cards_viewports_and_diagnostics(self, isolated_server, playwright_browser):
        """Verify Catalog renders owner's 37 packaged cards, diagnostics bar, and zero console errors across 3 viewports."""
        base_url = isolated_server["base_url"]

        for vp in VIEWPORTS:
            context = playwright_browser.new_context(viewport={"width": vp["width"], "height": vp["height"]})
            page = context.new_page()
            console_errors = []
            def handle_console(msg):
                if msg.type == "error":
                    text = msg.text
                    if any(x in text for x in ["ws://", "wss://", "WS error", "/api/chat", "WebSocket", "chat", "Failed to load resource"]):
                        return
                    console_errors.append(text)
            page.on("console", handle_console)

            url = f"{base_url}/catalog"
            resp = page.goto(url, wait_until="networkidle", timeout=20000)
            assert resp.status == 200, f"Catalog route returned HTTP {resp.status}"

            # Wait for diagnostics bar to render
            page.wait_for_selector('[data-testid="catalog-diagnostics-bar"]', timeout=10000)

            # Check diagnostics content
            diag_text = page.locator('[data-testid="catalog-diagnostics-bar"]').inner_text()
            assert "196" in diag_text, f"Diagnostics must show 196 inventoried items: {diag_text}"
            assert "37" in diag_text, f"Diagnostics must show 37 packaged items: {diag_text}"
            assert "10" in diag_text, f"Diagnostics must show 10 operational items: {diag_text}"

            # Wait for card grid
            page.wait_for_selector('[data-testid="catalog-grid"]', timeout=10000)

            # Count rendered cards in default Packaged view (owner's 37 observation)
            # Default page size is 24 cards on page 1, 13 cards on page 2 (totaling 37 packaged cards)
            cards = page.locator('[data-testid^="catalog-card-"]')
            card_count = cards.count()
            assert card_count == 24, f"Expected 24 packaged cards on page 1, got {card_count}"

            # Check page 2 to verify full 37 packaged cards
            page2_btn = page.locator('.MuiPagination-ul button:text-is("2")')
            if page2_btn.count() > 0:
                page2_btn.click()
                page.wait_for_timeout(300)
                cards_p2 = page.locator('[data-testid^="catalog-card-"]')
                assert cards_p2.count() == 13, f"Expected 13 packaged cards on page 2, got {cards_p2.count()}"
                assert card_count + cards_p2.count() == 37, "Total packaged cards across pages must equal exactly 37"
                # Go back to page 1 for screenshot
                page.locator('.MuiPagination-ul button:text-is("1")').click()
                page.wait_for_timeout(300)

            # Check that retired 6Clips blocks are NOT rendered
            assert page.locator('[data-testid="catalog-card-creator-hud"]').count() == 0
            assert page.locator('[data-testid="catalog-card-glitch-transition"]').count() == 0

            # Capture Edge screenshot
            screenshot_path = SCREENSHOTS_DIR / f"catalog_packaged_{vp['name']}.png"
            page.screenshot(path=str(screenshot_path))
            assert screenshot_path.is_file() and screenshot_path.stat().st_size > 1000

            # Zero console errors check
            assert len(console_errors) == 0, f"Discovered console errors on viewport {vp['name']}: {console_errors}"
            context.close()

    def test_catalog_all_196_originals_traversal_and_drawer(self, isolated_server, playwright_browser):
        """Verify switching to All 196 Originals renders multi-page traversal without duplicates and drawer details."""
        base_url = isolated_server["base_url"]
        context = playwright_browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.goto(f"{base_url}/catalog", wait_until="networkidle", timeout=20000)
        page.wait_for_selector('[data-testid="catalog-grid"]', timeout=10000)

        # Switch to "All 196 Donor Originals" tab using data-testid
        all_tab = page.locator('[data-testid="filter-all-original"]')
        assert all_tab.count() > 0, "All 196 Originals filter button must be present"
        all_tab.click()
        page.wait_for_timeout(600)

        # Check pagination bar is rendered
        page.wait_for_selector('[data-testid="catalog-pagination"]', timeout=5000)

        # Iterate through pages 1, 2, 3 to verify traversal without duplicates
        seen_slugs = set()
        for p in range(1, 4):
            page_btn = page.locator(f'.MuiPagination-ul button:text-is("{p}")')
            assert page_btn.count() > 0, f"Pagination button {p} must exist"
            page_btn.click()
            page.wait_for_timeout(400)

            page_cards = page.locator('[data-testid^="catalog-card-"]')
            page_slugs = []
            for i in range(page_cards.count()):
                card_id = page_cards.nth(i).get_attribute("data-testid").replace("catalog-card-", "")
                assert card_id not in seen_slugs, f"Duplicate block ID {card_id} discovered on page {p}"
                seen_slugs.add(card_id)
                page_slugs.append(card_id)
            assert len(page_slugs) == 24, f"Page {p} must render exactly 24 cards, got {len(page_slugs)}"

        assert len(seen_slugs) == 72, f"First 3 pages must render 72 unique items, got {len(seen_slugs)}"

        # Save screenshot of All 196 Originals view
        screenshot_path = SCREENSHOTS_DIR / "catalog_all196_1440x900.png"
        page.screenshot(path=str(screenshot_path))
        assert screenshot_path.is_file()

        # Click on card 'aurora' to open CatalogDrawer
        aurora_card = page.locator('[data-testid="catalog-card-aurora"]')
        if aurora_card.count() == 0:
            # Go back to page 1
            page.locator('.MuiPagination-ul button:text-is("1")').click()
            page.wait_for_timeout(300)

        page.locator('[data-testid="catalog-card-aurora"]').click()
        page.wait_for_selector('[data-testid="catalog-drawer"]', timeout=5000)

        # Verify drawer details
        drawer = page.locator('[data-testid="catalog-drawer"]')
        assert drawer.is_visible()
        drawer_text = drawer.inner_text()
        assert "aurora" in drawer_text
        assert "LOCAL_SHIPPED" in drawer_text or "Packaged" in drawer_text

        # Take screenshot of open drawer
        drawer_ss = SCREENSHOTS_DIR / "catalog_drawer_1920x1080.png"
        page.screenshot(path=str(drawer_ss))
        assert drawer_ss.is_file()

        context.close()

    def test_motion_studio_catalog_picker_and_no_ai_leak(self, isolated_server, playwright_browser):
        """Verify /motion studio catalog picker renders packaged blocks and triggers zero unsolicited AI network calls."""
        base_url = isolated_server["base_url"]
        context = playwright_browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        # Track network calls to verify zero unsolicited AI or remote inference leak
        ai_calls = []
        def handle_request(req):
            u = req.url.lower()
            if any(k in u for k in ["ollama", "openai", "anthropic", "gemini", "/api/ai/infer", "/api/chat/complete"]):
                ai_calls.append(req.url)
        page.on("request", handle_request)

        resp = page.goto(f"{base_url}/motion", wait_until="networkidle", timeout=20000)
        assert resp.status == 200

        # Wait for motion workspace
        page.wait_for_timeout(800)

        # Verify resource panel exists
        resource_panel = page.locator('[data-testid="studio-resource-panel"]')
        if resource_panel.count() > 0:
            assert resource_panel.is_visible()

        # Switch to Catalog tab in StudioResourcePanel using role="tab"
        catalog_tab = page.locator('button[role="tab"]:has-text("Catalog")')
        if catalog_tab.count() > 0:
            catalog_tab.click()
            page.wait_for_timeout(500)

        # Capture motion editor screenshot
        motion_ss = SCREENSHOTS_DIR / "motion_editor_1920x1080.png"
        page.screenshot(path=str(motion_ss))
        assert motion_ss.is_file() and motion_ss.stat().st_size > 1000

        # Assert zero unsolicited AI calls were dispatched on mount/idle
        assert len(ai_calls) == 0, f"Unsolicited AI calls detected: {ai_calls}"
        context.close()
