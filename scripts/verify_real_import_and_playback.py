# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Authentic User Playback Acceptance Script:
1. Imports a real video using the standard POST /api/downloaded/import user flow.
2. Navigates to /videos in a real Playwright browser.
3. Finds the visible card in the Library grid and performs an authentic user click.
4. Asserts AssetDrawer opens naturally (zero React Fiber manipulation).
5. Verifies video player renders, plays, advances currentTime, and seeks cleanly.
6. Tests the Actions menu layout in the Details drawer.
7. Captures multi-viewport screenshots (1920x1080, 1440x900, 1366x768).
8. Cleans up the imported video via standard DELETE /api/downloaded/{id}.
"""
import asyncio
from pathlib import Path
import httpx
from playwright.async_api import async_playwright

EVIDENCE_DIR = Path("artifacts/p0_media_security_isolation_closure")
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

BACKEND_BASE = "http://127.0.0.1:16888"
FRONTEND_BASE = "http://localhost:5173"
TEST_VIDEO_PATH = Path("motion/studio/test_moving_video.mp4").resolve()


async def main():
    assert TEST_VIDEO_PATH.is_file(), f"Test video not found: {TEST_VIDEO_PATH}"

    imported_id = None
    imported_title = "Genuine Imported Video Demo"

    print("Step 1: Importing video via user-facing endpoint POST /api/downloaded/import...")
    async with httpx.AsyncClient(base_url=BACKEND_BASE, timeout=30.0) as client:
        with open(TEST_VIDEO_PATH, "rb") as f:
            files = {"file": ("test_moving_video.mp4", f, "video/mp4")}
            data = {"title": imported_title}
            res = await client.post("/api/downloaded/import", files=files, data=data)
        assert res.status_code == 200, f"Import failed: {res.status_code} {res.text}"
        imported_id = res.json()["id"]
        print(f"  Successfully imported video id={imported_id}")

    try:
        viewports = [
            ("1920x1080", 1920, 1080),
            ("1440x900", 1440, 900),
            ("1366x768", 1366, 768),
        ]

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)

            for vp_name, width, height in viewports:
                print(f"\nStep 2: Testing authentic UI interaction at viewport {vp_name}...")
                page = await browser.new_page(viewport={"width": width, "height": height})

                # Navigate to Library
                await page.goto(f"{FRONTEND_BASE}/videos", wait_until="networkidle")
                await page.wait_for_timeout(1000)

                # Locate the newly imported card in the grid
                card_title_locator = page.locator(f"text='{imported_title}'").first
                await card_title_locator.wait_for(state="visible", timeout=10000)
                print(f"  Found visible Library card with title '{imported_title}'")

                # Capture Library grid screenshot
                tile_screenshot_path = EVIDENCE_DIR / f"01_library_imported_tile_{vp_name}.png"
                await page.screenshot(path=str(tile_screenshot_path))
                print(f"  Captured grid screenshot: {tile_screenshot_path}")

                # Perform authentic user click on the card
                print("  Performing authentic user click on card...")
                await card_title_locator.click()

                # Verify AssetDrawer opens naturally
                drawer_locator = page.locator('[data-testid="asset-drawer"]').first
                await drawer_locator.wait_for(state="visible", timeout=8000)
                print("  AssetDrawer opened naturally!")

                # Locate the video player inside AssetDrawer
                video_locator = drawer_locator.locator("video").first
                await video_locator.wait_for(state="attached", timeout=8000)
                print("  Located video element inside AssetDrawer")

                # Wait for video readyState >= 1 (metadata loaded)
                ready_state = await video_locator.evaluate("""async (v) => {
                    if (v.readyState >= 1) return v.readyState;
                    return new Promise((resolve) => {
                        v.addEventListener('loadedmetadata', () => resolve(v.readyState), { once: true });
                        setTimeout(() => resolve(v.readyState), 5000);
                    });
                }""")
                print(f"  Video readyState: {ready_state}")

                # Start playback
                print("  Initiating video.play()...")
                play_res = await video_locator.evaluate("""async (v) => {
                    try {
                        await v.play();
                        return { ok: true, paused: v.paused, currentTime: v.currentTime };
                    } catch (e) {
                        return { ok: false, error: String(e) };
                    }
                }""")
                print(f"  Play result: {play_res}")

                # Let video play for 1.8 seconds
                await page.wait_for_timeout(1800)

                # Measure playback progression
                time_after_play = await video_locator.evaluate("(v) => ({ paused: v.paused, currentTime: v.currentTime })")
                print(f"  State after playing: {time_after_play}")
                assert time_after_play["currentTime"] > 1.0, f"Video did not advance: {time_after_play}"
                assert not time_after_play["paused"], "Video is unexpectedly paused"

                # Capture playing screenshot
                playing_screenshot_path = EVIDENCE_DIR / f"02_drawer_video_playback_{vp_name}.png"
                await page.screenshot(path=str(playing_screenshot_path))
                print(f"  Captured playing screenshot: {playing_screenshot_path}")

                # Test seeking
                print("  Testing seeking to 4.5 seconds...")
                seek_res = await video_locator.evaluate("""(v) => {
                    v.currentTime = 4.5;
                    return v.currentTime;
                }""")
                await page.wait_for_timeout(600)
                time_after_seek = await video_locator.evaluate("(v) => v.currentTime")
                print(f"  CurrentTime after seek: {time_after_seek}")
                assert time_after_seek >= 4.0, f"Seek failed: {time_after_seek}"

                # Test Actions menu
                actions_btn = drawer_locator.locator("button:has-text('Actions')").first
                if await actions_btn.is_visible():
                    print("  Clicking Actions dropdown button...")
                    await actions_btn.click()
                    await page.wait_for_timeout(400)
                    actions_screenshot_path = EVIDENCE_DIR / f"03_drawer_actions_menu_{vp_name}.png"
                    await page.screenshot(path=str(actions_screenshot_path))
                    print(f"  Captured actions menu screenshot: {actions_screenshot_path}")
                    # Close menu by pressing Escape
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(200)

                # Close drawer using standard close button
                close_btn = drawer_locator.locator("button[aria-label='Close']").first
                await close_btn.click()
                await drawer_locator.wait_for(state="hidden", timeout=5000)
                print("  AssetDrawer closed cleanly.")

                await page.close()

            await browser.close()

    finally:
        if imported_id:
            print("\nStep 3: Cleaning up imported test video via DELETE /api/downloaded/{id}...")
            async with httpx.AsyncClient(base_url=BACKEND_BASE, timeout=10.0) as client:
                del_res = await client.delete(f"/api/downloaded/{imported_id}")
                print(f"  Cleanup response: {del_res.status_code} {del_res.text}")


if __name__ == "__main__":
    asyncio.run(main())
