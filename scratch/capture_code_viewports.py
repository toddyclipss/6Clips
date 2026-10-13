# SPDX-License-Identifier: AGPL-3.0-only
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

BASE_DIR = Path("c:/Users/toddy/Desktop/ViralMint")
EVIDENCE_DIR = BASE_DIR / "tests" / "visual_evidence"
PROJECT_ID = "6169c61a-9805-43fa-9230-7806f4ed922b"
PORT = 16889
BASE_URL = f"http://127.0.0.1:{PORT}"

VIEWPORTS = [
    {"name": "1920x1080", "width": 1920, "height": 1080},
    {"name": "1440x900", "width": 1440, "height": 900},
    {"name": "1366x768", "width": 1366, "height": 768},
]

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for vp in VIEWPORTS:
            print(f"Capturing CodeMirror 6 in Refine mode at {vp['name']}...")
            c = await browser.new_context(viewport={"width": vp["width"], "height": vp["height"]})
            pg = await c.new_page()
            await pg.goto(f"{BASE_URL}/motion?projectId={PROJECT_ID}&mode=refine", wait_until="networkidle")
            await pg.wait_for_selector("text='Gaming Highlight Short'", timeout=10000)

            code_btn = pg.locator("[data-testid='studio-toolbar-code-btn']")
            if await code_btn.count() > 0:
                await code_btn.click()
                await pg.wait_for_selector(".cm-editor, .cm-content", timeout=10000)
                await asyncio.sleep(1)

                shot_path = EVIDENCE_DIR / f"refine_code_{vp['name']}.png"
                await pg.screenshot(path=str(shot_path), full_page=True)
                print(f"Saved: {shot_path.name}")
            else:
                print("Code button not found at", vp["name"])
            await c.close()
        await browser.close()
    print("CodeMirror captures completed!")

if __name__ == "__main__":
    asyncio.run(main())
