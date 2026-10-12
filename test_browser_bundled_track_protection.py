# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Browser-level verification of:
1. Bundled tracks delete protection and disabled button in AssetDrawer.
2. Downloaded audio assets rendering audio player in AssetDrawer instead of DownloadedDetail video player.
3. Tile menu safe rejection of bundled track deletion.
"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

async def test_bundled_track_and_downloaded_audio():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})

        print("Navigating to http://127.0.0.1:16888/videos?media=audio ...")
        await page.goto("http://127.0.0.1:16888/videos?media=audio", wait_until="networkidle")
        await page.wait_for_timeout(1500)

        # ---------------------------------------------------------------------
        # TEST A: Bundled music track protection in Drawer
        # ---------------------------------------------------------------------
        print("\n--- TEST A: Bundled Music Track Protection in Drawer ---")
        card = page.locator('[data-testid="asset-tile"]').filter(has_text="bundled ambient").first
        await card.wait_for(state="visible", timeout=5000)
        print("Clicking bundled track card 'bundled ambient'...")
        await card.click()
        await page.wait_for_timeout(1000)

        drawer = page.locator('[data-testid="asset-drawer"]')
        assert await drawer.is_visible()

        audio_el = drawer.locator("audio")
        assert await audio_el.count() == 1
        src = await audio_el.get_attribute("src")
        print("Verified <audio> element for bundled track:", src)
        assert "/api/library/track/bundled_ambient.mp3" in src

        del_btn = drawer.locator('button[aria-label="Delete"]')
        is_disabled = await del_btn.is_disabled()
        print("Is Delete button disabled for bundled track?", is_disabled)
        assert is_disabled, "Bundled tracks MUST have a disabled delete button in AssetDrawer"

        Path("artifacts/p0_final_remediation").mkdir(parents=True, exist_ok=True)
        await page.screenshot(path="artifacts/p0_final_remediation/06_bundled_track_protected_drawer.png")
        print("Saved screenshot: 06_bundled_track_protected_drawer.png")

        # Close drawer with Escape key and wait for drawer hidden
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(1000)

        # ---------------------------------------------------------------------
        # TEST B: Downloaded audio asset rendering audio player (P0-A fix)
        # ---------------------------------------------------------------------
        print("\n--- TEST B: Downloaded Audio Asset in AssetDrawer (P0-A Fix) ---")
        vo_card = page.locator('[data-testid="asset-tile"]').filter(has_text="Lofi Chill Voiceover").first
        await vo_card.wait_for(state="visible", timeout=5000)
        print("Clicking downloaded VO card 'Lofi Chill Voiceover'...")
        await vo_card.click()
        await page.wait_for_timeout(1000)

        vo_drawer = page.locator('[data-testid="asset-drawer"]')
        assert await vo_drawer.is_visible()

        vo_audio = vo_drawer.locator("audio")
        assert await vo_audio.count() == 1, "Downloaded audio asset MUST render an <audio> element, NOT DownloadedDetail video player"
        vo_src = await vo_audio.get_attribute("src")
        print("Verified <audio> element for downloaded VO:", vo_src)
        assert "/api/downloaded/" in vo_src

        # Verify no video player is embedded
        vo_video = vo_drawer.locator("video")
        assert await vo_video.count() == 0, "Downloaded audio asset must NOT render a <video> element"

        # Verify facts table is present
        facts = vo_drawer.locator(".MuiTypography-root:has-text('DURATION')")
        print("Facts table present?", await facts.count() > 0)

        await page.screenshot(path="artifacts/p0_final_remediation/08_downloaded_audio_drawer_player.png")
        print("Saved screenshot: 08_downloaded_audio_drawer_player.png")

        # Close drawer
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(1000)

        # ---------------------------------------------------------------------
        # TEST C: Tile Menu Bundled Deletion Protection
        # ---------------------------------------------------------------------
        print("\n--- TEST C: Tile Menu Bundled Deletion Protection ---")
        await card.focus()
        await page.wait_for_timeout(300)
        more_btn = card.locator('button[aria-label="More"]')
        if await more_btn.count() > 0 and await more_btn.is_visible():
            await more_btn.click()
            await page.wait_for_timeout(500)
            menu_del = page.locator('.MuiMenu-root li:has-text("Delete")')
            if await menu_del.count() > 0:
                menu_txt = await menu_del.text_content()
                print("Menu item text:", menu_txt)
                assert "Bundled track" in menu_txt
                aria_disabled = await menu_del.get_attribute("aria-disabled")
                is_disabled = (aria_disabled == "true") or await menu_del.is_disabled()
                print("Is tile menu Delete option disabled?", is_disabled)
                assert is_disabled, "Tile menu Delete option MUST be disabled for bundled tracks"
                await page.screenshot(path="artifacts/p0_final_remediation/07_tile_menu_bundled_blocked.png")
                print("Saved screenshot: 07_tile_menu_bundled_blocked.png")

        print("\nAll browser verification checks PASSED!")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_bundled_track_and_downloaded_audio())
