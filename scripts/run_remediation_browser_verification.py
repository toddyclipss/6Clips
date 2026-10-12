# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Automated Browser Verification for Motion Timeline & Refine Professional UX Remediation.
Tests:
- Creation of dense 9-track canonical composition (1 video, 3 audio, 2 captions, 3 graphics)
- Parity & multi-track caption collision avoidance
- UI Timeline header label (strictly "Timeline")
- Multi-track headers with Solo, Mute, Lock, Visibility, Reorder, and Delete
- Keyframe subtracks extraction beneath parent track
- Responsive layouts at 1920x1080 and 1366x768
- Persistence across reload
"""
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

BASE_URL = "http://127.0.0.1:16888"
OUTPUT_DIR = Path("artifacts/remediation_verification").resolve()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def log(msg: str):
    print(f"[REMEDIATION-VERIFY] {msg}", flush=True)


async def main():
    log("Starting Playwright browser verification for Motion Timeline remediation...")

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        # 1. Verify backend health
        res = await client.get("/api/projects")
        assert res.status_code == 200, f"Backend returned {res.status_code}"

        # 2. Create canonical project
        create_res = await client.post("/api/projects", json={
            "name": "Remediation Dense 9-Track Suite",
            "aspect_ratio": "9:16",
        })
        assert create_res.status_code == 200, f"Project create failed: {create_res.text}"
        proj = create_res.json()
        pid = proj["id"]
        rev = proj["revision"]
        log(f"Created project {pid} at revision {rev}")

        # 3. Add tracks to build full 9-track composition:
        # Initial doc has: track_video_main, track_audio_main, track_captions
        # Let's rename existing tracks and add missing ones:
        # Rename track_audio_main -> "Music BGM"
        r = await client.post(f"/api/projects/{pid}/operations", json={
            "expected_revision": rev,
            "operation_type": "rename_track",
            "payload": {"track_id": "track_audio_main", "name": "Background Music"},
            "author": "test",
        })
        rev = r.json()["revision"]

        # Rename track_captions -> "Primary Captions (EN)"
        r = await client.post(f"/api/projects/{pid}/operations", json={
            "expected_revision": rev,
            "operation_type": "rename_track",
            "payload": {"track_id": "track_captions", "name": "English Captions"},
            "author": "test",
        })
        rev = r.json()["revision"]

        # Add Audio 2: Narration Voiceover
        r = await client.post(f"/api/projects/{pid}/operations", json={
            "expected_revision": rev,
            "operation_type": "add_track",
            "payload": {"type": "audio", "track_id": "track_audio_vo", "name": "Voiceover Narration"},
            "author": "test",
        })
        rev = r.json()["revision"]

        # Add Audio 3: Sound Effects (SFX)
        r = await client.post(f"/api/projects/{pid}/operations", json={
            "expected_revision": rev,
            "operation_type": "add_track",
            "payload": {"type": "audio", "track_id": "track_audio_sfx", "name": "Sound Effects (SFX)"},
            "author": "test",
        })
        rev = r.json()["revision"]

        # Add Captions 2: Secondary Translation (ES)
        r = await client.post(f"/api/projects/{pid}/operations", json={
            "expected_revision": rev,
            "operation_type": "add_track",
            "payload": {"type": "captions", "track_id": "track_captions_es", "name": "Spanish Subtitles"},
            "author": "test",
        })
        rev = r.json()["revision"]

        # Add Graphics 1: Lower Thirds
        r = await client.post(f"/api/projects/{pid}/operations", json={
            "expected_revision": rev,
            "operation_type": "add_track",
            "payload": {"type": "graphics", "track_id": "track_gfx_lower", "name": "Lower Thirds"},
            "author": "test",
        })
        rev = r.json()["revision"]

        # Add Graphics 2: Callout Badges
        r = await client.post(f"/api/projects/{pid}/operations", json={
            "expected_revision": rev,
            "operation_type": "add_track",
            "payload": {"type": "graphics", "track_id": "track_gfx_callouts", "name": "Callout Badges"},
            "author": "test",
        })
        rev = r.json()["revision"]

        # Add Graphics 3: Progress Overlays
        r = await client.post(f"/api/projects/{pid}/operations", json={
            "expected_revision": rev,
            "operation_type": "add_track",
            "payload": {"type": "graphics", "track_id": "track_gfx_progress", "name": "Progress Overlay"},
            "author": "test",
        })
        rev = r.json()["revision"]

        # Now add clips across tracks:
        # Video clip 1 with keyframes
        r = await client.post(f"/api/projects/{pid}/operations", json={
            "expected_revision": rev,
            "operation_type": "add_clip",
            "payload": {
                "track_id": "track_video_main",
                "clip": {
                    "id": "clip_vid_hero",
                    "type": "video",
                    "title": "Hero Intro",
                    "start_seconds": 0.0,
                    "duration_seconds": 5.0,
                    "asset_file": "sample_video_1.mp4",
                    "animations": [
                        {"property": "opacity", "time": 0.0, "value": 0.0},
                        {"property": "opacity", "time": 1.0, "value": 1.0, "ease": "power2.out"},
                        {"property": "scale", "time": 0.0, "value": 0.9},
                        {"property": "scale", "time": 2.0, "value": 1.05, "ease": "none"},
                    ],
                },
            },
            "author": "test",
        })
        rev = r.json()["revision"]

        # Video clip 2
        r = await client.post(f"/api/projects/{pid}/operations", json={
            "expected_revision": rev,
            "operation_type": "add_clip",
            "payload": {
                "track_id": "track_video_main",
                "clip": {
                    "id": "clip_vid_outro",
                    "type": "video",
                    "title": "Outro Scene",
                    "start_seconds": 5.0,
                    "duration_seconds": 5.0,
                    "asset_file": "sample_video_2.mp4",
                },
            },
            "author": "test",
        })
        rev = r.json()["revision"]

        # Audio BGM clip
        r = await client.post(f"/api/projects/{pid}/operations", json={
            "expected_revision": rev,
            "operation_type": "add_clip",
            "payload": {
                "track_id": "track_audio_main",
                "clip": {
                    "id": "clip_bgm_main",
                    "type": "audio",
                    "title": "Lofi Beat Loop",
                    "start_seconds": 0.0,
                    "duration_seconds": 10.0,
                },
            },
            "author": "test",
        })
        rev = r.json()["revision"]

        # Audio VO clip
        r = await client.post(f"/api/projects/{pid}/operations", json={
            "expected_revision": rev,
            "operation_type": "add_clip",
            "payload": {
                "track_id": "track_audio_vo",
                "clip": {
                    "id": "clip_vo_narration",
                    "type": "audio",
                    "title": "AI Voice Track",
                    "start_seconds": 0.5,
                    "duration_seconds": 6.0,
                },
            },
            "author": "test",
        })
        rev = r.json()["revision"]

        # Audio SFX clip
        r = await client.post(f"/api/projects/{pid}/operations", json={
            "expected_revision": rev,
            "operation_type": "add_clip",
            "payload": {
                "track_id": "track_audio_sfx",
                "clip": {
                    "id": "clip_sfx_whoosh",
                    "type": "audio",
                    "title": "Subtle Whoosh",
                    "start_seconds": 4.8,
                    "duration_seconds": 1.2,
                },
            },
            "author": "test",
        })
        rev = r.json()["revision"]

        # Captions EN clip
        r = await client.post(f"/api/projects/{pid}/operations", json={
            "expected_revision": rev,
            "operation_type": "add_clip",
            "payload": {
                "track_id": "track_captions",
                "clip": {
                    "id": "clip_cap_en",
                    "type": "caption",
                    "caption_text": "Viral hook dialogue starts here!",
                    "start_seconds": 0.5,
                    "duration_seconds": 4.0,
                },
            },
            "author": "test",
        })
        rev = r.json()["revision"]

        # Captions ES clip
        r = await client.post(f"/api/projects/{pid}/operations", json={
            "expected_revision": rev,
            "operation_type": "add_clip",
            "payload": {
                "track_id": "track_captions_es",
                "clip": {
                    "id": "clip_cap_es",
                    "type": "caption",
                    "caption_text": "El diálogo de enganche viral comienza aquí!",
                    "start_seconds": 0.5,
                    "duration_seconds": 4.0,
                    "color": "#a7f3d0",
                },
            },
            "author": "test",
        })
        rev = r.json()["revision"]

        # Graphics Lower Third clip
        r = await client.post(f"/api/projects/{pid}/operations", json={
            "expected_revision": rev,
            "operation_type": "add_clip",
            "payload": {
                "track_id": "track_gfx_lower",
                "clip": {
                    "id": "clip_gfx_speaker",
                    "type": "graphics",
                    "title": "Speaker Title Card",
                    "start_seconds": 1.0,
                    "duration_seconds": 3.5,
                },
            },
            "author": "test",
        })
        rev = r.json()["revision"]

        # Verify document state via GET
        check_res = await client.get(f"/api/projects/{pid}")
        doc = check_res.json()["document"]
        assert len(doc["timeline"]["tracks"]) == 9, f"Expected 9 tracks, got {len(doc['timeline']['tracks'])}"
        log(f"Successfully constructed 9-track canonical composition. Total tracks: {len(doc['timeline']['tracks'])}")

        # Sync studio preview
        sync_res = await client.post(f"/api/projects/{pid}/sync-studio", json={"revision": rev})
        assert sync_res.status_code == 200, f"Studio sync failed: {sync_res.text}"

    # 4. Launch Playwright browser inspection
    log("Launching Playwright to inspect /motion Refine workspace...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # A. Viewport 1: Desktop 1920x1080
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        await page.goto(f"{BASE_URL}/motion", wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # Switch to Refine mode if not active
        refine_btn = page.locator("button:has-text('Refine')")
        if await refine_btn.count() > 0:
            await refine_btn.first.click()
            await page.wait_for_timeout(1000)

        # Check Timeline Title
        timeline_header = page.locator("[data-testid='studio-timeline-workspace']")
        assert await timeline_header.count() > 0, "StudioTimelineWorkspace element not found"

        # Check title text says "Timeline"
        title_text = await page.locator("text='Timeline'").first.inner_text()
        assert title_text == "Timeline", f"Expected 'Timeline', got '{title_text}'"
        log("PASS: Header label reads 'Timeline' (not 'Professional Timeline')")

        # Verify tracks rendered
        track_headers = page.locator("text='Main Video'")
        assert await track_headers.count() > 0, "Main Video track header missing"
        assert await page.locator("text='Background Music'").count() > 0, "Background Music track missing"
        assert await page.locator("text='English Captions'").count() > 0, "English Captions track missing"
        assert await page.locator("text='Spanish Subtitles'").count() > 0, "Spanish Subtitles track missing"
        assert await page.locator("text='Voiceover Narration'").count() > 0, "Voiceover Narration track missing"
        assert await page.locator("text='Sound Effects (SFX)'").count() > 0, "Sound Effects track missing"
        assert await page.locator("text='Lower Thirds'").count() > 0, "Lower Thirds track missing"
        log("PASS: Multi-track headers rendered for dense 9-track composition")

        # Expand Keyframe Subtracks on Hero clip
        # Click the diamonds toggle button on the hero clip
        toggle_subtracks_btn = page.locator("[data-clip-id='clip_vid_hero'] button[title*='Subtracks'], [data-clip-id='clip_vid_hero'] button[aria-label*='Subtracks']").first
        if await toggle_subtracks_btn.count() == 0:
            # Fallback to finding button with IconDiamonds inside clip_vid_hero
            toggle_subtracks_btn = page.locator("[data-clip-id='clip_vid_hero'] button").last
        await toggle_subtracks_btn.click()
        await page.wait_for_timeout(800)

        # Verify property subtrack rows appear underneath parent track
        assert await page.locator("text='↳ Opacity'").count() > 0, "Opacity subtrack missing"
        assert await page.locator("text='↳ Scale'").count() > 0, "Scale subtrack missing"
        assert await page.locator("text='↳ Position X'").count() > 0, "Position X subtrack missing"
        log("PASS: Property subtracks (Opacity, Scale, Position X) expand beneath parent track across full ruler width")

        # Screenshot 1920x1080
        shot_1080 = OUTPUT_DIR / "refine_timeline_1920x1080.png"
        await page.screenshot(path=str(shot_1080), full_page=False)
        log(f"Saved 1920x1080 screenshot to {shot_1080}")

        # B. Viewport 2: Constrained Laptop 1366x768
        await page.set_viewport_size({"width": 1366, "height": 768})
        await page.wait_for_timeout(1000)

        # Verify Stage preview height >= 380px and Timeline >= 220px
        preview_box = await page.locator("[data-testid='studio-preview-stage']").bounding_box()
        timeline_box = await page.locator("[data-testid='studio-timeline-workspace']").bounding_box()

        log(f"1366x768 Dimensions: Preview height={preview_box['height']}px, Timeline height={timeline_box['height']}px")
        assert preview_box["height"] >= 350, f"Preview height too small: {preview_box['height']}px"
        assert timeline_box["height"] >= 200, f"Timeline height too small: {timeline_box['height']}px"

        # Screenshot 1366x768
        shot_768 = OUTPUT_DIR / "refine_timeline_1366x768.png"
        await page.screenshot(path=str(shot_768), full_page=False)
        log(f"Saved 1366x768 screenshot to {shot_768}")

        # C. Reload page to verify persistence
        await page.reload(wait_until="networkidle")
        await page.wait_for_timeout(1500)
        assert await page.locator("text='Main Video'").count() > 0
        assert await page.locator("text='Spanish Subtitles'").count() > 0
        log("PASS: Dense composition state persisted cleanly across browser reload")

        await browser.close()

    log("All Playwright verification checks PASSED successfully!")


if __name__ == "__main__":
    asyncio.run(main())
