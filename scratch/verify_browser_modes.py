import os
import sys
import time
import urllib.request
import json
import asyncio
import subprocess
from pathlib import Path
from playwright.async_api import async_playwright

ISOLATED_DIR = Path("c:/Users/toddy/Desktop/ViralMint/tmp_isolated_test")
PROJECT_ID = "6169c61a-9805-43fa-9230-7806f4ed922b"
PORT = 16889
BASE_URL = f"http://127.0.0.1:{PORT}"

env = os.environ.copy()
env["VIRALMINT_DATA_DIR"] = str(ISOLATED_DIR)
env["PORT"] = str(PORT)

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
    env=env,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

async def run_checks():
    try:
        # Wait for backend
        ready = False
        for _ in range(25):
            try:
                with urllib.request.urlopen(f"{BASE_URL}/api/config", timeout=1) as resp:
                    ready = True
                    break
            except Exception:
                time.sleep(0.5)

        if not ready:
            print("ERROR: Backend failed to start on port", PORT)
            return False

        print(f"Backend live on {BASE_URL}. Launching Chromium...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            # ── Check 1: Review Mode ──────────────────────────────────────────
            print("\n--- CHECK 1: REVIEW MODE ---")
            page_rev = await browser.new_page(viewport={"width": 1920, "height": 1080})
            page_rev.on("console", lambda m: print(f"[REV CONSOLE {m.type}] {m.text}") if m.type in ("error", "warning") else None)

            url_rev = f"{BASE_URL}/motion?projectId={PROJECT_ID}&mode=review"
            print("Navigating to:", url_rev)
            await page_rev.goto(url_rev, wait_until="networkidle")
            
            # Authoritative wait: wait for project name or video player
            await page_rev.wait_for_selector("text='Gaming Highlight Short'", timeout=10000)
            print("FOUND: Project title 'Gaming Highlight Short'")

            # Check review button active
            review_btn = page_rev.locator("button:has-text('Review')")
            print("Review button count:", await review_btn.count())

            # Check video tag
            video_el = page_rev.locator("#studio-rendered-video, video")
            print("Video element count:", await video_el.count())
            if await video_el.count() > 0:
                src = await video_el.first.get_attribute("src")
                print("Video src:", src)

            # Check review header badge
            badge = page_rev.locator("[data-testid='studio-review-header']")
            print("Review header badge count:", await badge.count())

            # Seek video to 4.0s
            await page_rev.evaluate("""() => {
                const v = document.querySelector('#studio-rendered-video') || document.querySelector('video');
                if (v) v.currentTime = 4.0;
            }""")
            await asyncio.sleep(1)

            # Capture review screenshot
            shot_rev = "scratch/test_review_1920x1080.png"
            await page_rev.screenshot(path=shot_rev, full_page=True)
            print("Saved review screenshot:", shot_rev)
            await page_rev.close()

            # ── Check 2: Refine Mode ──────────────────────────────────────────
            print("\n--- CHECK 2: REFINE MODE ---")
            page_ref = await browser.new_page(viewport={"width": 1920, "height": 1080})
            page_ref.on("console", lambda m: print(f"[REF CONSOLE {m.type}] {m.text}") if m.type in ("error", "warning") else None)

            url_ref = f"{BASE_URL}/motion?projectId={PROJECT_ID}&mode=refine"
            print("Navigating to:", url_ref)
            await page_ref.goto(url_ref, wait_until="networkidle")

            # Wait for project name and timeline
            await page_ref.wait_for_selector("text='Gaming Highlight Short'", timeout=10000)
            print("FOUND: Project title in Refine mode")

            # Check tracks
            tracks_el = page_ref.locator("text='Main Video'")
            print("Track 'Main Video' count:", await tracks_el.count())
            caps_el = page_ref.locator("text='Captions'")
            print("Track 'Captions' count:", await caps_el.count())
            gfx_el = page_ref.locator("text='Graphics & Blocks'")
            print("Track 'Graphics & Blocks' count:", await gfx_el.count())

            # Check layers
            layers_btn = page_ref.locator("button:has-text('Layers')")
            print("Layers tab count:", await layers_btn.count())

            # Capture refine screenshot
            shot_ref = "scratch/test_refine_1920x1080.png"
            await page_ref.screenshot(path=shot_ref, full_page=True)
            print("Saved refine screenshot:", shot_ref)

            # ── Check 3: CodeMirror 6 in Refine Mode ───────────────────────────
            print("\n--- CHECK 3: CODEMIRROR 6 IN REFINE MODE ---")
            code_btn = page_ref.locator("[data-testid='studio-toolbar-code-btn']")
            print("Code button count:", await code_btn.count())
            if await code_btn.count() > 0:
                await code_btn.click()
                await asyncio.sleep(1.5)
                cm_el = page_ref.locator(".cm-editor, .cm-content")
                print("CodeMirror editor count:", await cm_el.count())
                shot_code = "scratch/test_refine_code_1920x1080.png"
                await page_ref.screenshot(path=shot_code, full_page=True)
                print("Saved CodeMirror screenshot:", shot_code)

            await page_ref.close()
            await browser.close()
            print("\nALL BROWSER CHECKS COMPLETED!")
            return True
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

asyncio.run(run_checks())
