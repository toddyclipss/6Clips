# language: Python, file: scripts/capture_viewports_and_aspect_ratios.py, target: Windows 11, playwright
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path("artifacts/sources_assets_catalog_acceptance")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def log(msg):
    print(msg, flush=True)

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        viewports = [
            ("1366x768", 1366, 768),
            ("1440x900", 1440, 900),
            ("1920x1080", 1920, 1080),
        ]

        for name, w, h in viewports:
            log(f"Testing viewport {name} ({w}x{h})...")
            context = browser.new_context(viewport={"width": w, "height": h})
            page = context.new_page()
            page.goto("http://127.0.0.1:16888/motion", wait_until="domcontentloaded", timeout=20000)
            time.sleep(2)

            # Switch to Catalog & Media
            cat_btn = page.locator("button:has-text('Catalog & Media')")
            if cat_btn.is_visible():
                cat_btn.click()
                time.sleep(1)

            # Click Catalog tab
            cat_tab = page.locator("button.MuiTab-root:has-text('Catalog')")
            if cat_tab.is_visible():
                cat_tab.click()
                time.sleep(1)

            # Hover first card for ghost preview
            cards = page.locator("div[data-testid^='catalog-card-']")
            if cards.count() > 0:
                cards.first.hover()
                time.sleep(0.8)

            page.screenshot(path=str(OUTPUT_DIR / f"layout_{name}_catalog_ghost.png"))
            log(f"[OK] Captured layout_{name}_catalog_ghost.png")
            context.close()

        # Test 16:9 aspect ratio
        log("Testing 16:9 aspect ratio preview...")
        ctx_169 = browser.new_context(viewport={"width": 1600, "height": 950})
        page_169 = ctx_169.new_page()
        page_169.goto("http://127.0.0.1:16888/motion", wait_until="domcontentloaded", timeout=20000)
        time.sleep(2)

        # Switch aspect ratio if selector exists or pass query param
        aspect_btn = page_169.locator("button:has-text('16:9'), div[role='button']:has-text('16:9')")
        if aspect_btn.is_visible():
            aspect_btn.click()
            time.sleep(1)

        # Open catalog and hover
        cat_btn = page_169.locator("button:has-text('Catalog & Media')")
        if cat_btn.is_visible():
            cat_btn.click()
            time.sleep(1)

        cat_tab = page_169.locator("button.MuiTab-root:has-text('Catalog')")
        if cat_tab.is_visible():
            cat_tab.click()
            time.sleep(1)

        cards = page_169.locator("div[data-testid^='catalog-card-']")
        if cards.count() > 0:
            cards.first.hover()
            time.sleep(0.8)

        page_169.screenshot(path=str(OUTPUT_DIR / "layout_16_9_ghost_preview.png"))
        log("[OK] Captured layout_16_9_ghost_preview.png")
        ctx_169.close()
        browser.close()

if __name__ == "__main__":
    run()
