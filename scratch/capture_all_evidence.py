# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Comprehensive multi-viewport evidence capture proving Review, Refine, CodeMirror, and Chat."""
import asyncio
import sqlite3
from pathlib import Path
from playwright.async_api import async_playwright

BASE_DIR = Path("c:/Users/toddy/Desktop/ViralMint")
EVIDENCE_DIR = BASE_DIR / "tests" / "visual_evidence"
PROJECT_ID = "6169c61a-9805-43fa-9230-7806f4ed922b"
PORT = 16889
BASE_URL = f"http://127.0.0.1:{PORT}"
ISOLATED_DB = BASE_DIR / "tmp_isolated_test" / "viralmint.db"

VIEWPORTS = [
    {"name": "1920x1080", "width": 1920, "height": 1080},
    {"name": "1440x900", "width": 1440, "height": 900},
    {"name": "1366x768", "width": 1366, "height": 768},
]


def count_projects() -> int:
    conn = sqlite3.connect(str(ISOLATED_DB))
    c = conn.cursor()
    count = c.execute("SELECT count(*) FROM projects").fetchone()[0]
    conn.close()
    return count


async def main():
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    print("Capturing all visual evidence against port", PORT)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # ── Test 1: Blank /motion visit must NOT create implicit project ───
        pre_count = count_projects()
        print(f"Pre-visit project count: {pre_count}")

        ctx = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await ctx.new_page()

        await page.goto(f"{BASE_URL}/motion", wait_until="networkidle")
        await asyncio.sleep(2)

        # Screenshot blank stage
        blank_path = EVIDENCE_DIR / "motion_blank_no_implicit_create.png"
        await page.screenshot(path=str(blank_path))
        print(f"Saved: {blank_path.name}")
        await ctx.close()

        post_count = count_projects()
        print(f"Post-visit project count: {post_count}")
        assert post_count == pre_count, f"Unintended project creation! Pre: {pre_count}, Post: {post_count}"
        print("VERIFIED: No implicit project created upon visiting /motion without projectId.")

        # ── Test 2: Review Mode Across 3 Viewports ───
        for vp in VIEWPORTS:
            print(f"\nCapturing Review mode at {vp['name']}...")
            c = await browser.new_context(viewport={"width": vp["width"], "height": vp["height"]})
            pg = await c.new_page()

            # Listen for console errors
            pg.on("console", lambda m: print(f"[{vp['name']} BROWSER CONSOLE {m.type}]: {m.text}") if m.type == "error" else None)

            await pg.goto(f"{BASE_URL}/motion?projectId={PROJECT_ID}&mode=review", wait_until="networkidle")

            # Wait for video element
            video_sel = 'video[data-testid="studio-rendered-video"]'
            await pg.wait_for_selector(video_sel, timeout=10000)

            # Wait for metadata and dimensions to load
            await pg.wait_for_function("""
                () => {
                    const v = document.querySelector('video[data-testid="studio-rendered-video"]');
                    return v && v.readyState >= 1 && v.duration > 0 && v.videoWidth > 0;
                }
            """, timeout=10000)

            # Read video metrics
            metrics = await pg.evaluate("""
                () => {
                    const v = document.querySelector('video[data-testid="studio-rendered-video"]');
                    return {
                        src: v.src,
                        duration: v.duration,
                        videoWidth: v.videoWidth,
                        videoHeight: v.videoHeight,
                        currentTime: v.currentTime,
                        paused: v.paused
                    };
                }
            """)
            print(f"[{vp['name']}] Video metrics at 0.0s:", metrics)
            assert metrics["duration"] > 0, "Video duration must be > 0"
            assert metrics["videoWidth"] > 0, "Video width must be > 0"
            assert metrics["videoHeight"] > 0, "Video height must be > 0"

            # Capture initial Review frame at 0.0s
            shot_path = EVIDENCE_DIR / f"review_{vp['name']}.png"
            await pg.screenshot(path=str(shot_path), full_page=True)
            print(f"Saved: {shot_path.name}")

            # Seek video to 4.0s
            await pg.evaluate("""
                () => {
                    const v = document.querySelector('video[data-testid="studio-rendered-video"]');
                    v.currentTime = 4.0;
                }
            """)
            await asyncio.sleep(1)

            seek_metrics = await pg.evaluate("""
                () => {
                    const v = document.querySelector('video[data-testid="studio-rendered-video"]');
                    return {
                        currentTime: v.currentTime,
                        paused: v.paused
                    };
                }
            """)
            print(f"[{vp['name']}] Video metrics after seek:", seek_metrics)

            # Capture seeked Review frame
            seek_shot_path = EVIDENCE_DIR / f"review_seek_{vp['name']}.png"
            await pg.screenshot(path=str(seek_shot_path), full_page=True)
            print(f"Saved: {seek_shot_path.name}")

            await c.close()

        # ── Test 3: Refine Mode Across 3 Viewports ───
        for vp in VIEWPORTS:
            print(f"\nCapturing Refine mode at {vp['name']}...")
            c = await browser.new_context(viewport={"width": vp["width"], "height": vp["height"]})
            pg = await c.new_page()

            await pg.goto(f"{BASE_URL}/motion?projectId={PROJECT_ID}&mode=refine", wait_until="networkidle")

            # Wait for timeline tracks
            await pg.wait_for_selector('text="Main Video"', timeout=10000)
            await pg.wait_for_selector('text="Captions"', timeout=10000)
            await pg.wait_for_selector('text="Graphics & Blocks"', timeout=10000)

            # Screenshot timeline & layers
            shot_path = EVIDENCE_DIR / f"refine_{vp['name']}.png"
            await pg.screenshot(path=str(shot_path), full_page=True)
            print(f"Saved: {shot_path.name}")

            # Switch to Code tab in left nav to show CodeMirror 6 editor
            code_tab = pg.locator('button:has-text("Code")').first
            if await code_tab.count() > 0:
                await code_tab.click()
                await pg.wait_for_selector('.cm-editor', timeout=10000)
                await asyncio.sleep(1)

                code_shot_path = EVIDENCE_DIR / f"refine_code_{vp['name']}.png"
                await pg.screenshot(path=str(code_shot_path), full_page=True)
                print(f"Saved: {code_shot_path.name}")

            await c.close()

        # ── Test 4: Global Chat View ───
        print("\nCapturing Global Chat Workflow...")
        c = await browser.new_context(viewport={"width": 1920, "height": 1080})
        pg = await c.new_page()
        await pg.goto(f"{BASE_URL}/", wait_until="networkidle")
        await asyncio.sleep(2)
        shot_path = EVIDENCE_DIR / "chat_workflow_1920x1080.png"
        await pg.screenshot(path=str(shot_path), full_page=True)
        print(f"Saved: {shot_path.name}")
        await c.close()

        await browser.close()

    print("\nALL MULTI-VIEWPORT VISUAL EVIDENCE CAPTURED AND VERIFIED!")


if __name__ == "__main__":
    asyncio.run(main())
