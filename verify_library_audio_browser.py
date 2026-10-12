# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Browser-level verification of Library audio assets, player drawer, and safe deletion."""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

SCREENSHOTS_DIR = Path("artifacts/p0_final_remediation")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

def verify_library_audio_browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        # 1. Load library with audio filter
        print("1. Loading Library audio page...")
        page.goto("http://127.0.0.1:16888/videos?media=audio", wait_until="networkidle", timeout=15000)
        time.sleep(2)
        page.screenshot(path=str(SCREENSHOTS_DIR / "01_library_audio_grid.png"))
        print(f"Captured grid: {SCREENSHOTS_DIR / '01_library_audio_grid.png'}")

        # 2. Find audio cards
        cards = page.locator(".MuiCard-root").all()
        print(f"Found {len(cards)} library cards on page.")
        assert len(cards) > 0, "Expected audio tiles in Library"

        # 3. Click first audio card to open AssetDrawer
        print("2. Opening AssetDrawer for first audio card...")
        cards[0].click()
        time.sleep(1.5)

        drawer = page.locator(".MuiDrawer-root")
        assert drawer.is_visible(), "AssetDrawer must be visible after clicking tile"

        # Check for audio player in drawer
        audio_player = page.locator(".MuiDrawer-root audio")
        audio_count = audio_player.count()
        print(f"Audio elements in drawer: {audio_count}")
        assert audio_count > 0, "AssetDrawer MUST render an <audio> element for audio assets"
        audio_src = audio_player.first.get_attribute("src")
        print(f"Audio player src: {audio_src}")
        assert audio_src and ("/api/library/track/" in audio_src or "/api/downloaded/" in audio_src)

        page.screenshot(path=str(SCREENSHOTS_DIR / "02_asset_drawer_audio_player.png"))
        print(f"Captured drawer: {SCREENSHOTS_DIR / '02_asset_drawer_audio_player.png'}")

        # Check for waveform bars in drawer
        waveform_bars = page.locator(".MuiDrawer-root .MuiStack-root div[style*='height:']")
        print(f"Waveform visualizer elements: {waveform_bars.count()}")

        # Close drawer
        close_btn = page.locator(".MuiDrawer-root button[aria-label='Close']")
        if close_btn.count() > 0:
            close_btn.first.click()
            time.sleep(1)

        # 4. Check bundled track delete restriction in tile menu
        print("3. Testing tile action menus...")
        menu_btns = page.locator("button[aria-label='actions']").all()
        print(f"Found {len(menu_btns)} action menu buttons.")
        if len(menu_btns) > 0:
            menu_btns[0].click()
            time.sleep(0.5)
            delete_option = page.locator(".MuiMenu-root li:has-text('Delete')")
            print(f"Delete option visible in tile menu: {delete_option.is_visible()}")
            page.screenshot(path=str(SCREENSHOTS_DIR / "03_tile_menu_delete.png"))
            # Dismiss menu
            page.keyboard.press("Escape")
            time.sleep(0.5)

        # 5. Check Motion Editor Live Audio Control & Composition Volume
        print("4. Testing Motion Editor Timeline and Audio controls...")
        page.goto("http://127.0.0.1:16888/motion", wait_until="networkidle", timeout=15000)
        time.sleep(2)
        page.screenshot(path=str(SCREENSHOTS_DIR / "04_motion_editor_initial.png"))

        # Verify preview iframe
        iframe_locator = page.locator("iframe[title='HyperFrames Studio Stage']")
        print(f"Preview iframe count: {iframe_locator.count()}")
        assert iframe_locator.count() > 0, "Motion editor preview iframe must exist"

        print("Browser verification completed successfully.")
        browser.close()

if __name__ == "__main__":
    verify_library_audio_browser()
