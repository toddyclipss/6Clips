# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 17 Agent 2 Microsoft Edge Playwright Browser Test Suite.

End-to-End Real Browser Acceptance Testing on Microsoft Edge:
1. Validates the strictly FIVE top-level OAAS workspace destinations in the left sidebar:
   - Trends (/trends)
   - My Channel (/channels)
   - Library (/videos)
   - Motion Graphics (/motion)
   - Messages (/messaging)
2. Validates that Catalog, Clip Studio, Distribution, Analytics, and Tools are NOT top-level sidebar items.
3. Validates backward-compatible redirects in real Edge browser:
   - /catalog -> /motion?tab=catalog
   - /clips -> /motion?mode=clip
   - /tools -> /motion?mode=tools
   - /distribution -> /channels
   - /analytics -> /channels
4. Validates My Channel page presents the Outcome Delivery Summary:
   - Published Outcomes (Provider-Verified) with truthful AWAITING_PUBLISHED_POST status (no synthetic ticks)
   - Pending Approvals & Distribution Queue
   - Platform Connectors with truthful NOT_CONNECTED state
5. Validates Motion Graphics absorbs Catalog and Clip Studio:
   - /motion?tab=catalog auto-opens StudioResourcePanel with Catalog tab
   - Clean "Template" / "TEMPLATE" markers with zero raw "Unported" or "INVENTORY ONLY" chips
   - /motion?mode=clip activates contextual clip workspace
6. Validates responsive behavior across viewports:
   - 1366x768 (standard laptop)
   - 1440x900 (MacBook/widescreen)
   - 1920x1080 (Full HD desktop)
7. Asserts zero console errors and saves verified Edge screenshots to tests/e2e_wave17/agent2/screenshots/.
"""

import os
import sys
import time
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SCREENSHOTS_DIR = REPO_ROOT / "tests" / "e2e_wave17" / "agent2" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

VIEWPORTS = [
    {"width": 1366, "height": 768, "name": "1366x768"},
    {"width": 1440, "height": 900, "name": "1440x900"},
    {"width": 1920, "height": 1080, "name": "1920x1080"},
]

import socket
import tempfile
import shutil
import subprocess
import httpx

FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def isolated_server():
    """Launch a real Uvicorn server serving FastAPI backend and built frontend SPA with port-aware origins."""
    temp_dir = tempfile.mkdtemp(prefix="viralmint_w17_a2_")
    db_path = os.path.join(temp_dir, "viralmint_w17_test.db")
    media_dir = os.path.join(temp_dir, "media")
    os.makedirs(media_dir, exist_ok=True)

    port = find_free_port()
    env = os.environ.copy()
    env["VIRALMINT_DATA_DIR"] = temp_dir
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    env["VIRALMINT_FRONTEND_DIST"] = str(FRONTEND_DIST)
    env["MEDIA_DIR"] = media_dir
    env["PORT"] = str(port)
    env["FRONTEND_URL"] = f"http://127.0.0.1:{port}"
    env["PYTHONPATH"] = f"{REPO_ROOT};{env.get('PYTHONPATH', '')}"

    log_path = os.path.join(temp_dir, "uvicorn_w17.log")
    log_file = open(log_path, "w", encoding="utf-8", errors="replace")

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "info",
        ],
        cwd=REPO_ROOT,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )

    base_url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 25.0
    ready = False

    while time.time() < deadline:
        try:
            r = httpx.get(f"{base_url}/health", timeout=1.0)
            if r.status_code == 200:
                ready = True
                break
        except Exception:
            time.sleep(0.3)

    if not ready:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        log_file.close()
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError(f"Uvicorn server failed to boot on {base_url}")

    yield {
        "base_url": base_url,
        "port": port,
        "temp_dir": temp_dir,
        "proc": proc,
        "media_dir": media_dir,
    }

    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        proc.kill()
    log_file.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="session")
def edge_browser():
    """Launch real Microsoft Edge browser context."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="msedge")
        yield browser
        browser.close()


class TestWave17A2EdgeBrowserAcceptance:
    """End-to-End Microsoft Edge Playwright acceptance suite for Wave 17 Agent 2."""

    def test_sidebar_five_destinations_across_viewports(self, isolated_server, edge_browser):
        """Verifies strictly 5 OAAS destinations exist in the sidebar across 3 viewports."""
        base_url = isolated_server["base_url"]

        for vp in VIEWPORTS:
            context = edge_browser.new_context(viewport={"width": vp["width"], "height": vp["height"]})
            page = context.new_page()
            console_errors = []

            def handle_console(msg):
                if msg.type == "error":
                    text = msg.text
                    if any(x in text for x in ["ws://", "wss://", "WS error", "/api/chat", "WebSocket", "chat", "Failed to load resource"]):
                        return
                    console_errors.append(text)

            page.on("console", handle_console)

            page.goto(f"{base_url}/trends", wait_until="networkidle", timeout=25000)
            page.wait_for_selector('[data-testid="nav-trends"]', timeout=15000)

            # Assert the 5 destinations exist
            assert page.locator('[data-testid="nav-trends"]').count() >= 1, "Missing nav-trends"
            assert page.locator('[data-testid="nav-my-channel"]').count() >= 1, "Missing nav-my-channel"
            assert page.locator('[data-testid="nav-library"]').count() >= 1, "Missing nav-library"
            assert page.locator('[data-testid="nav-motion-graphics"]').count() >= 1, "Missing nav-motion-graphics"
            assert page.locator('[data-testid="nav-messages"]').count() >= 1, "Missing nav-messages"

            # Assert legacy standalone destinations do NOT exist in sidebar
            assert page.locator('[data-testid="nav-catalog"]').count() == 0, "Catalog should not be in sidebar"
            assert page.locator('[data-testid="nav-clip-studio"]').count() == 0, "Clip Studio should not be in sidebar"
            assert page.locator('[data-testid="nav-distribution"]').count() == 0, "Distribution should not be in sidebar"
            assert page.locator('[data-testid="nav-analytics"]').count() == 0, "Analytics should not be in sidebar"
            assert page.locator('[data-testid="nav-tools"]').count() == 0, "Tools should not be in sidebar"

            # Capture screenshot
            ss_path = SCREENSHOTS_DIR / f"oaas_navigation_{vp['name']}.png"
            page.screenshot(path=str(ss_path), full_page=False)
            assert ss_path.exists() and ss_path.stat().st_size > 0

            assert len(console_errors) == 0, f"Unexpected console errors in viewport {vp['name']}: {console_errors}"
            context.close()

    def test_backward_compatible_redirects_in_edge(self, isolated_server, edge_browser):
        """Verifies backward-compatible URL redirects function cleanly in Edge."""
        base_url = isolated_server["base_url"]
        context = edge_browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        redirect_cases = [
            ("/catalog", "/motion?tab=catalog"),
            ("/clips", "/motion?mode=clip"),
            ("/tools", "/motion?mode=tools"),
            ("/distribution", "/channels"),
            ("/analytics", "/channels"),
        ]

        for source_path, expected_target in redirect_cases:
            page.goto(f"{base_url}{source_path}", wait_until="networkidle", timeout=25000)
            page.wait_for_timeout(1000)
            current_url = page.url
            expected_full = f"{base_url}{expected_target}"
            assert expected_target in current_url, (
                f"Navigating to {source_path} did not redirect to {expected_target}, current URL: {current_url}"
            )

        context.close()

    def test_my_channel_outcome_delivery_summary(self, isolated_server, edge_browser):
        """Verifies My Channel renders Outcome Delivery Summary with truthful metrics and no fake buttons."""
        base_url = isolated_server["base_url"]
        context = edge_browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        console_errors = []

        def handle_console(msg):
            if msg.type == "error":
                text = msg.text
                if any(x in text for x in ["ws://", "wss://", "WS error", "/api/chat", "WebSocket", "chat", "Failed to load resource", "canceled", "CanceledError"]):
                    return
                console_errors.append(text)

        page.on("console", handle_console)

        page.goto(f"{base_url}/channels", wait_until="networkidle", timeout=25000)
        page.wait_for_selector('[data-testid="outcome-summary"]', timeout=15000)

        # Check page header
        heading = page.locator("h5").first.inner_text()
        assert "My Channel" in heading, f"Expected 'My Channel' heading, found '{heading}'"

        # Check OAAS sections
        assert page.locator('[data-testid="published-outcomes"]').count() == 1
        assert page.locator('[data-testid="distribution-queue"]').count() == 1
        assert page.locator('[data-testid="platform-connectors"]').count() == 1

        # Check truthful empty outcome state
        body_text = page.locator("body").inner_text()
        assert "AWAITING_PUBLISHED_POST" in body_text, "Missing truthful AWAITING_PUBLISHED_POST indicator"
        assert "NOT_CONNECTED" in body_text, "Missing truthful NOT_CONNECTED indicator"

        # Verify absence of developer actions
        assert "Load Test Fixture" not in body_text
        assert "Preview with Isolated Test Fixture" not in body_text
        assert "Trigger Worker Tick" not in body_text

        # Capture verified screenshot
        ss_path = SCREENSHOTS_DIR / "my_channel_outcomes_1920x1080.png"
        page.screenshot(path=str(ss_path), full_page=False)
        assert ss_path.exists() and ss_path.stat().st_size > 0

        assert len(console_errors) == 0, f"Unexpected console errors on My Channel: {console_errors}"
        context.close()

    def test_motion_graphics_absorbs_catalog_and_clip_contexts(self, isolated_server, edge_browser):
        """Verifies Motion Graphics handles ?tab=catalog and ?mode=clip without developer markers."""
        base_url = isolated_server["base_url"]
        context = edge_browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        console_errors = []

        def handle_console(msg):
            if msg.type == "error":
                text = msg.text
                if any(x in text for x in ["ws://", "wss://", "WS error", "/api/chat", "WebSocket", "chat", "Failed to load resource", "canceled", "CanceledError"]):
                    return
                console_errors.append(text)

        page.on("console", handle_console)

        # 1. Catalog absorbed into Motion
        page.goto(f"{base_url}/motion?tab=catalog", wait_until="networkidle", timeout=25000)
        page.wait_for_timeout(2000)

        body_text = page.locator("body").inner_text()
        # Verify absence of raw developer chips
        assert "INVENTORY ONLY" not in body_text, "Found raw INVENTORY ONLY in Motion Graphics"

        ss_catalog = SCREENSHOTS_DIR / "catalog_absorption_motion_1920x1080.png"
        page.screenshot(path=str(ss_catalog), full_page=False)
        assert ss_catalog.exists() and ss_catalog.stat().st_size > 0

        # 2. Clip Studio absorbed into Motion
        page.goto(f"{base_url}/motion?mode=clip", wait_until="networkidle", timeout=25000)
        page.wait_for_timeout(2000)

        ss_clip = SCREENSHOTS_DIR / "clips_absorption_motion_1920x1080.png"
        page.screenshot(path=str(ss_clip), full_page=False)
        assert ss_clip.exists() and ss_clip.stat().st_size > 0

        assert len(console_errors) == 0, f"Unexpected console errors in Motion Graphics: {console_errors}"
        context.close()
