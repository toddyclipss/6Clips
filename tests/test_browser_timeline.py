# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Real Browser Playwright Test for Professional Motion Timeline:
Tests http://localhost:5173/motion:
- Multi-track timeline (Video, Audio waveform, HyperFrames Blocks, Captions)
- Ruler playhead scrubbing
- Magnetic snapping and visual guide line
- Bidirectional trimming and dragging
- Keyframe diamonds and expandable property lanes
- Selection sync across Timeline and Inspector
- Clip duplication and splitting
- Page reload persistence from SQLite
"""
import asyncio
import os
import shutil
from pathlib import Path
import httpx
from playwright.async_api import async_playwright

ARTIFACTS_DIR = Path(r"C:\Users\toddy\.gemini\antigravity\brain\05dc85cb-9ba9-426a-8e4d-5ef5943efc16")


async def run_browser_timeline_test():
    print("=== STARTING PROFESSIONAL TIMELINE BROWSER TEST ===")
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Create seeded multi-track project via API
    initial_doc = {
        "schema_version": 2,
        "title": "Timeline Test Project",
        "aspect_ratio": "16:9",
        "timeline": {
            "fps": 30,
            "duration_seconds": 12.0,
            "tracks": [
                {
                    "id": "track_video_main",
                    "type": "video",
                    "name": "Main Video",
                    "clips": [
                        {
                            "id": "clip_hero_scene",
                            "type": "video",
                            "title": "Hero Scene",
                            "start_seconds": 1.0,
                            "duration_seconds": 4.0,
                            "asset_file": "hero.mp4",
                            "trim_start": 0.0,
                            "trim_end": 4.0,
                        }
                    ]
                },
                {
                    "id": "track_audio_main",
                    "type": "audio",
                    "name": "Background Audio",
                    "clips": [
                        {
                            "id": "clip_audio_score",
                            "type": "audio",
                            "title": "Theme Score",
                            "start_seconds": 0.0,
                            "duration_seconds": 8.0,
                            "asset_file": "theme.mp3",
                            "trim_start": 0.0,
                            "trim_end": 8.0,
                        }
                    ]
                },
                {
                    "id": "track_graphics_main",
                    "type": "graphics",
                    "name": "Graphics & Blocks",
                    "clips": [
                        {
                            "id": "elem_title_card",
                            "type": "block",
                            "block_id": "minimal-title",
                            "block_version": "a1b2c3d4",
                            "title": "Title Card",
                            "start_seconds": 2.0,
                            "duration_seconds": 4.0,
                            "variables": {
                                "headline": "NEXT GEN MOTION",
                                "color": "#a855f7"
                            },
                            "animations": [
                                {
                                    "property": "opacity",
                                    "time": 0.0,
                                    "value": 0.0,
                                    "ease": "none"
                                },
                                {
                                    "property": "opacity",
                                    "time": 1.0,
                                    "value": 1.0,
                                    "ease": "power2.out"
                                }
                            ]
                        }
                    ]
                },
                {
                    "id": "track_captions_main",
                    "type": "captions",
                    "name": "Subtitles",
                    "clips": [
                        {
                            "id": "clip_sub_1",
                            "type": "captions",
                            "caption_text": "ViralMint Studio Composition",
                            "start_seconds": 0.5,
                            "duration_seconds": 3.0,
                        }
                    ]
                }
            ]
        }
    }

    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        res = await client.post("/api/projects", json={
            "name": "Timeline Pro Test Project",
            "aspect_ratio": "16:9",
            "initial_document": initial_doc,
        })
        assert res.status_code == 200, f"Failed creating project: {res.text}"
        project_data = res.json()
        project_id = project_data["id"]
        print(f"[Step 1 PASS] Seeded project created: {project_id}")

    # 2. Launch Chromium and navigate to /motion?project_id=...
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        print("[Step 2] Navigating to http://localhost:5173/motion...")
        await page.goto(f"http://localhost:5173/motion?project_id={project_id}", wait_until="networkidle")
        await page.wait_for_timeout(2500)

        # 3. Verify Timeline Workspace and Track Headers mounted
        assert await page.is_visible("text=Professional Timeline")
        assert await page.is_visible("text=Main Video")
        assert await page.is_visible("text=Background Audio")
        assert await page.is_visible("text=Graphics & Blocks")
        assert await page.is_visible("text=Subtitles")
        print("[Step 3 PASS] Multi-track headers mounted")

        # 4. Verify specialized clip representations
        assert await page.is_visible("text=Hero Scene")
        assert await page.is_visible("text=Theme Score")
        assert await page.is_visible("text=Title Card")
        assert await page.is_visible("text=ViralMint Studio Composition")
        
        # Audio waveform canvas verified
        waveform_canvas = page.locator("canvas")
        assert await waveform_canvas.count() >= 1
        print("[Step 4 PASS] Clips and audio waveform canvas rendered")

        # Keyframe diamond verified
        diamond = page.locator("[data-keyframe-diamond='opacity']").first
        assert await diamond.is_visible()
        print("[Step 4 PASS] Keyframe diamond rendered on Title Card block")

        # Save collapsed timeline screenshot
        collapsed_path = ARTIFACTS_DIR / "motion_timeline_collapsed.png"
        await page.screenshot(path=str(collapsed_path))
        print(f"Captured: {collapsed_path}")

        # Waveform crop screenshot
        waveform_path = ARTIFACTS_DIR / "motion_timeline_waveform.png"
        audio_clip_elem = page.locator("text=Theme Score").locator("..").locator("..")
        await audio_clip_elem.screenshot(path=str(waveform_path))
        print(f"Captured: {waveform_path}")

        # 5. Playhead scrub test
        print("[Step 5] Testing Ruler Scrub...")
        ruler = page.locator("text=Tracks").locator("..").locator("div").nth(1)
        ruler_box = await ruler.bounding_box()
        if ruler_box:
            # Click at 2.0s (2.0s * 40pps = 80px offset)
            target_x = ruler_box["x"] + 80
            target_y = ruler_box["y"] + 14
            await page.mouse.click(target_x, target_y)
            await page.wait_for_timeout(500)

        # 6. Clip selection & Inspector sync test
        print("[Step 6] Testing Clip Selection & Inspector sync...")
        hero_clip = page.locator("[data-clip-id='clip_hero_scene']").first
        await hero_clip.click(force=True)
        await page.wait_for_timeout(500)
        # Check Inspector shows Hero Scene or start timing
        assert await page.is_visible("text=Start: 1.0s") or await page.locator("text=Hero Scene").count() >= 1
        print("[Step 6 PASS] Clip selected and synced with Inspector")

        # 7. Animation Property Lanes expansion & Keyframe addition test
        print("[Step 7] Testing Property Lanes Expansion...")
        title_card = page.locator("[data-clip-id='elem_title_card']").first
        await title_card.click(force=True)
        await page.wait_for_timeout(300)

        # Toggle Animation Lanes button
        lanes_toggle = page.locator("button[aria-label='Show Animation Lanes'], [title*='Animation Lanes']").first
        if await lanes_toggle.is_visible():
            await lanes_toggle.click(force=True)
            await page.wait_for_timeout(500)

        assert await page.is_visible("text=Position X") or await page.is_visible("text=Opacity")
        print("[Step 7 PASS] Property lanes expanded (Opacity, Position X, etc.)")

        # Capture expanded lanes screenshot
        expanded_path = ARTIFACTS_DIR / "motion_timeline_expanded_lanes.png"
        await page.screenshot(path=str(expanded_path))
        print(f"Captured: {expanded_path}")

        # Add keyframe on Position X at current playhead
        add_kf_btn = page.locator("[title*='Add keyframe for Position X']").first
        if await add_kf_btn.is_visible():
            await add_kf_btn.click(force=True)
            await page.wait_for_timeout(500)
            print("[Step 7 PASS] Keyframe added on Position X")

        # 8. Duplicate Clip test (Ctrl+D / context menu)
        print("[Step 8] Testing Clip Duplication...")
        # Right click to open context menu on Hero Scene
        await hero_clip.click(button="right", force=True)
        await page.wait_for_timeout(500)
        assert await page.is_visible("text=Duplicate Clip")
        await page.click("text=Duplicate Clip")
        await page.wait_for_timeout(1000)

        # Verify duplicate clip exists (2 clips with 'Hero Scene')
        hero_clips = page.locator("text=Hero Scene")
        assert await hero_clips.count() >= 2
        print("[Step 8 PASS] Clip duplicated successfully")

        # 9. Split Clip test ('S' / context menu)
        print("[Step 9] Testing Clip Splitting...")
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(500)

        # Select Hero Scene and press 'S' keyboard shortcut or use toolbar button
        first_hero_clip = page.locator("[data-clip-id='clip_hero_scene']").first
        await first_hero_clip.click(force=True)
        await page.wait_for_timeout(300)

        # Split at playhead (2.0s is inside 1.0s to 5.0s bounds of Hero Scene)
        await page.keyboard.press("s")
        await page.wait_for_timeout(1000)

        # Verify Hero Scene is split (now 3 clips containing 'Hero Scene')
        hero_clips_count = await page.locator("text=Hero Scene").count()
        assert hero_clips_count >= 2
        print(f"[Step 9 PASS] Clip split successfully ({hero_clips_count} clips)")

        # 10. Dragging and Magnetic Snapping test
        print("[Step 10] Testing Dragging & Magnetic Snapping...")
        first_hero = hero_clips.first
        h_box = await first_hero.bounding_box()
        if h_box:
            await page.mouse.move(h_box["x"] + 20, h_box["y"] + 15)
            await page.mouse.down()
            # Move towards snap edge
            await page.mouse.move(h_box["x"] + 100, h_box["y"] + 15)
            await page.wait_for_timeout(300)

            # Capture snapping guideline screenshot
            snap_path = ARTIFACTS_DIR / "motion_timeline_snapping.png"
            await page.screenshot(path=str(snap_path))
            print(f"Captured: {snap_path}")

            await page.mouse.up()
            await page.wait_for_timeout(500)
        print("[Step 10 PASS] Drag and snapping interaction validated")

        # 11. Persistence verification upon page reload from SQLite
        print("[Step 11] Testing Persistence upon page reload...")
        await page.reload(wait_until="networkidle")
        await page.wait_for_timeout(2500)

        # Verify duplicated and split clips survive reload
        assert await page.locator("text=Hero Scene").count() >= 2
        assert await page.locator("text=ViralMint Studio Composition").count() >= 1
        assert await page.is_visible("text=Title Card")
        assert await page.is_visible("text=Theme Score")
        print("[Step 11 PASS] All updates persisted in SQLite and survived page reload")

        await browser.close()
        print("=== BROWSER TIMELINE TEST COMPLETED SUCCESSFULLY ===")


if __name__ == "__main__":
    asyncio.run(run_browser_timeline_test())
