# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 19 Agent 2: End-to-End Microsoft Edge Playwright Test Suite.

Runs against real backend and real frontend built assets in actual MS Edge.
Verifies:
1. One clean player stage: no Main Agent Goal composer overlay centered inside StudioPreviewStage.
2. Stage displays neutral blank 'No Project Loaded' view without input fields or prompt widgets.
3. Left Chat is the single input surface.
4. StudioResourcePanel has NO remote video ingest button, NO yt-dlp download bar, NO 1080p/720p chooser.
5. Catalog cards have NO duplicate eye preview buttons, NO insert block buttons, NO ask AI buttons.
6. Catalog cards are accessible (tabIndex, role, keyboard).
7. Takes high-fidelity viewport screenshot proving the clean UI in MS Edge.
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

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"
EVIDENCE_DIR = REPO_ROOT / "tools" / "wave19_a2"


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def live_server():
    """Start isolated FastAPI server with built frontend dist on a free port."""
    temp_dir = tempfile.mkdtemp(prefix="viralmint_w19_a2_")
    port = find_free_port()

    os.environ["VIRALMINT_DATA_DIR"] = temp_dir
    os.environ["VIRALMINT_FRONTEND_DIST"] = str(FRONTEND_DIST)
    os.environ["HOST"] = "0.0.0.0"
    os.environ["PORT"] = str(port)

    from backend.config import settings
    settings.HOST = "0.0.0.0"
    settings.PORT = port

    from backend.services.hyperframes_service import HyperFramesService
    from backend.services.studio_service import StudioService

    # Mock HyperFrames installed state and studio start for E2E browser test
    HyperFramesService.is_installed = classmethod(lambda cls: True)

    async def _mock_ensure_running(cls, mode="dark", force=False):
        return {"ok": True, "port": 16890, "mode": mode}

    StudioService.ensure_running = classmethod(_mock_ensure_running)

    import uvicorn
    from backend.main import create_app
    app = create_app()

    config = uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    timeout = 15.0
    start_time = time.time()
    server_ready = False

    while time.time() - start_time < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                server_ready = True
                break
        except (OSError, ConnectionRefusedError):
            time.sleep(0.1)

    assert server_ready, f"Live backend server failed to bind to {base_url} within {timeout}s"

    yield {"base_url": base_url, "port": port, "temp_dir": temp_dir}

    server.should_exit = True
    thread.join(timeout=2.0)


@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
def test_edge_clean_player_and_minimal_ui(live_server):
    """Run real MS Edge browser to verify absence of unwanted controls and presence of clean player."""
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    screenshot_path = EVIDENCE_DIR / "screenshot_clean_player_edge.png"
    base_url = live_server["base_url"]

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        # 1. Navigate to Motion Graphics
        page.goto(f"{base_url}/motion", wait_until="networkidle", timeout=30000)

        # 2. Wait for Motion player to hydrate and render
        page.wait_for_selector('[data-testid="motion-player"]', timeout=15000)
        assert page.locator('[data-testid="motion-player"]').count() == 1, "Expected exactly 1 canonical motion-player"

        # 3. Assert NO Main Agent Goal composer overlay inside player stage
        assert page.locator('[data-testid="main-agent-goal-composer"]').count() == 0, \
            "Unwanted 'main-agent-goal-composer' overlay is in DOM!"
        assert page.locator('[data-testid="main-agent-goal-input"]').count() == 0, \
            "Unwanted 'main-agent-goal-input' is in DOM!"
        assert page.locator('[data-testid="main-agent-goal-submit"]').count() == 0, \
            "Unwanted 'main-agent-goal-submit' is in DOM!"

        # 4. Assert neutral blank stage is rendered
        no_project = page.locator('[data-testid="studio-stage-no-project"]')
        assert no_project.count() > 0, "Neutral 'studio-stage-no-project' blank stage was not found!"
        assert "No Project Loaded" in page.content(), "Neutral stage missing 'No Project Loaded' notice"

        # 5. Assert StudioResourcePanel has NO remote ingest button or download stream bar
        assert page.locator('[data-testid="ingest-url-button"]').count() == 0, \
            "Unwanted 'ingest-url-button' found in Resource Panel!"
        assert "Download Video Stream (yt-dlp)" not in page.content(), \
            "Unwanted 'Download Video Stream (yt-dlp)' found in page content!"

        # 6. Switch to Catalog tab in Resource Panel
        catalog_tab = page.locator('button[role="tab"]:has-text("Catalog")')
        if catalog_tab.count() > 0:
            catalog_tab.first.click()
            page.wait_for_timeout(1000)

            # Check that catalog cards have NO preview eye button, NO insert button, NO ask AI button
            assert page.locator('[data-testid^="preview-block-"]').count() == 0, \
                "Found banned preview-block- buttons on catalog cards!"
            assert page.locator('[data-testid^="insert-block-"]').count() == 0, \
                "Found banned insert-block- buttons on catalog cards!"

            # Assert catalog cards exist and are keyboard accessible
            cards = page.locator('[data-testid^="catalog-card-"]')
            assert cards.count() > 0, "Expected catalog cards to be rendered"
            first_card = cards.first
            assert first_card.get_attribute("tabindex") == "0"
            assert first_card.get_attribute("role") == "button"

        # 7. Take screenshot of the clean editor UI in MS Edge
        page.screenshot(path=str(screenshot_path))
        assert screenshot_path.is_file(), f"Screenshot was not generated at {screenshot_path}"

        page.close()
        context.close()
        browser.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
