# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
import asyncio
import json
import os
from pathlib import Path
from playwright.async_api import async_playwright

ARTIFACT_DIR = Path(r"C:\Users\toddy\.gemini\antigravity\brain\05dc85cb-9ba9-426a-8e4d-5ef5943efc16")

async def test_acceptance_browser():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        # ----------------------------------------------------
        # 1. TEST 9:16 PROJECT (DEFAULT)
        # ----------------------------------------------------
        proj_916_id = "f395afb3-14a8-469f-8352-f47994d6d95f"
        print(f"Navigating to 9:16 project: http://localhost:5173/motion?projectId={proj_916_id}")
        await page.goto(f"http://localhost:5173/motion?projectId={proj_916_id}", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        # Locate preview iframe
        iframe_locator = page.locator("iframe[title='Composition Stage']")
        await iframe_locator.wait_for(state="attached", timeout=10000)
        iframe_element = await iframe_locator.element_handle()
        comp_frame = await iframe_element.content_frame()
        assert comp_frame is not None, "Failed to get content frame for 9:16 composition stage"

        # Wait for stage in iframe
        await comp_frame.wait_for_selector("#stage", timeout=10000)
        # Wait for subcomposition iframe inside stage
        subcomp_frame_locator = comp_frame.locator("iframe.subcomp-frame")
        await subcomp_frame_locator.wait_for(state="attached", timeout=10000)
        subcomp_el = await subcomp_frame_locator.element_handle()
        subcomp_frame = await subcomp_el.content_frame()
        assert subcomp_frame is not None, "Failed to get subcomp frame"

        # Wait for block element inside subcomp frame
        await subcomp_frame.wait_for_selector("#lb-root", timeout=10000)
        main_text_el = await subcomp_frame.wait_for_selector("#lb-main-text", timeout=10000)
        main_text = await main_text_el.text_content()
        print("9:16 Block Text:", main_text)

        # Check caption in main stage
        caption_el = await comp_frame.wait_for_selector(".caption-block", timeout=10000)
        caption_text = await caption_el.text_content()
        print("9:16 Caption Text:", caption_text)

        # Check bounding box and scale of stage
        stage_box = await comp_frame.locator("#stage").bounding_box()
        subcomp_box = await subcomp_frame.locator("#lb-root").bounding_box()
        print("9:16 Stage Bounding Box:", stage_box)
        print("9:16 Subcomp Root Bounding Box:", subcomp_box)

        assert stage_box is not None and stage_box["width"] > 0 and stage_box["height"] > 0
        assert subcomp_box is not None and subcomp_box["width"] > 0 and subcomp_box["height"] > 0

        # Capture INITIAL 9:16 screenshot
        shot_initial_916 = ARTIFACT_DIR / "preview_fixed_initial_9x16.png"
        await page.screenshot(path=str(shot_initial_916))
        print("Saved:", shot_initial_916)

        # Click Play button
        play_btn = page.locator("button[aria-label='Play'], button:has([data-tabler-icon='player-play']), button:has-text('Play')").first
        if await play_btn.count() == 0:
            # Fallback locator for play button
            play_btn = page.locator("button").filter(has=page.locator("svg.tabler-icon-player-play")).first
        print("Play button count:", await play_btn.count())
        await play_btn.click()
        await page.wait_for_timeout(1500)

        # Capture PLAYING 9:16 screenshot
        shot_playing_916 = ARTIFACT_DIR / "preview_fixed_playing_9x16.png"
        await page.screenshot(path=str(shot_playing_916))
        print("Saved:", shot_playing_916)

        # ----------------------------------------------------
        # 2. TEST 16:9 PROJECT (SUPPORTED)
        # ----------------------------------------------------
        proj_169_id = "60659b90-de43-4c7c-a7fa-f048c9e373e5"
        print(f"Navigating to 16:9 project: http://localhost:5173/motion?projectId={proj_169_id}")
        await page.goto(f"http://localhost:5173/motion?projectId={proj_169_id}", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        iframe_locator_169 = page.locator("iframe[title='Composition Stage']")
        await iframe_locator_169.wait_for(state="attached", timeout=10000)
        iframe_element_169 = await iframe_locator_169.element_handle()
        comp_frame_169 = await iframe_element_169.content_frame()
        assert comp_frame_169 is not None

        await comp_frame_169.wait_for_selector("#stage", timeout=10000)
        subcomp_frame_loc_169 = comp_frame_169.locator("iframe.subcomp-frame")
        await subcomp_frame_loc_169.wait_for(state="attached", timeout=10000)
        subcomp_el_169 = await subcomp_frame_loc_169.element_handle()
        subcomp_frame_169 = await subcomp_el_169.content_frame()
        assert subcomp_frame_169 is not None

        await subcomp_frame_169.wait_for_selector("#lb-root", timeout=10000)
        main_text_el_169 = await subcomp_frame_169.wait_for_selector("#lb-main-text", timeout=10000)
        main_text_169 = await main_text_el_169.text_content()
        print("16:9 Block Text:", main_text_169)

        caption_el_169 = await comp_frame_169.wait_for_selector(".caption-block", timeout=10000)
        caption_text_169 = await caption_el_169.text_content()
        print("16:9 Caption Text:", caption_text_169)

        stage_box_169 = await comp_frame_169.locator("#stage").bounding_box()
        subcomp_box_169 = await subcomp_frame_169.locator("#lb-root").bounding_box()
        print("16:9 Stage Bounding Box:", stage_box_169)
        print("16:9 Subcomp Root Bounding Box:", subcomp_box_169)

        assert stage_box_169 is not None and stage_box_169["width"] > 0 and stage_box_169["height"] > 0
        assert subcomp_box_169 is not None and subcomp_box_169["width"] > 0 and subcomp_box_169["height"] > 0

        # Capture INITIAL 16:9 screenshot
        shot_initial_169 = ARTIFACT_DIR / "preview_fixed_initial_16x9.png"
        await page.screenshot(path=str(shot_initial_169))
        print("Saved:", shot_initial_169)

        # Click Play button
        play_btn_169 = page.locator("button").filter(has=page.locator("svg.tabler-icon-player-play")).first
        if await play_btn_169.count() > 0:
            await play_btn_169.click()
            await page.wait_for_timeout(1500)

        # Capture PLAYING 16:9 screenshot
        shot_playing_169 = ARTIFACT_DIR / "preview_fixed_playing_16x9.png"
        await page.screenshot(path=str(shot_playing_169))
        print("Saved:", shot_playing_169)

        await browser.close()
        print("ALL BROWSER ACCEPTANCE CHECKS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_acceptance_browser())
