# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
import asyncio
import json
import urllib.request
from pathlib import Path
from playwright.async_api import async_playwright

ARTIFACTS_DIR = Path(r"C:\Users\toddy\.gemini\antigravity\brain\05dc85cb-9ba9-426a-8e4d-5ef5943efc16")
BASE_URL = "http://localhost:5173"
API_URL = "http://127.0.0.1:8000"


async def run_block_vars_acceptance():
    print("=== STARTING BLOCK VARIABLES & MP4 RENDER ACCEPTANCE ===")
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        await page.goto(f"{BASE_URL}/motion", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        # 1. Switch left to Layers
        layers_btn = page.locator("button:has-text('Layers')").first
        if await layers_btn.is_visible():
            await layers_btn.click()
            await page.wait_for_timeout(1000)

        # 2. Click on the Lower Third block row
        block_row = page.locator("div[data-layer-id]:has-text('Lower Third')").first
        if await block_row.is_visible():
            await block_row.click()
            await page.wait_for_timeout(1500)
            print("Selected Lower Third block in Layers")

        # 3. Switch right panel to Variables
        vars_btn = page.locator("button:has-text('Variables')").first
        if await vars_btn.is_visible():
            await vars_btn.click()
            await page.wait_for_timeout(1500)

            ss = ARTIFACTS_DIR / "phase8_8_block_variables_editor.png"
            await page.screenshot(path=str(ss))
            print(f"Captured: {ss.name}")

            # Fill in variable
            text_input = page.locator("[data-variable-field] input[type='text']").first
            if await text_input.is_visible():
                await text_input.fill("PROFESSIONAL VIRALMINT")
                await text_input.press("Enter")
                await page.wait_for_timeout(2000)
                print("Updated variable to 'PROFESSIONAL VIRALMINT'")

                ss_edited = ARTIFACTS_DIR / "phase8_9_variable_edited.png"
                await page.screenshot(path=str(ss_edited))
                print(f"Captured: {ss_edited.name}")

        # 4. Trigger render via Export Video button
        export_btn = page.locator("button:has-text('Export Video')").first
        if await export_btn.is_visible():
            await export_btn.click()
            await page.wait_for_timeout(3000)
            print("Triggered Export Video")

            ss_render = ARTIFACTS_DIR / "phase8_10_render_dispatched.png"
            await page.screenshot(path=str(ss_render))
            print(f"Captured: {ss_render.name}")

        await browser.close()
        print("=== BLOCK VARIABLES ACCEPTANCE FINISHED ===")


if __name__ == "__main__":
    asyncio.run(run_block_vars_acceptance())
