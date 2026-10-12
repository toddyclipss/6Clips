# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Browser-level verification of successful user audio deletion when unreferenced."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

async def test_successful_user_audio_delete():
    # 1. Create temporary unreferenced user track
    target_file = Path("storage/music/test_browser_removable.mp3")
    sample_file = Path("storage/music/lofi_chill.mp3")
    target_file.write_bytes(sample_file.read_bytes())
    assert target_file.exists(), "Target file must exist before test"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})

        print("Navigating to http://127.0.0.1:16888/videos?media=audio ...")
        await page.goto("http://127.0.0.1:16888/videos?media=audio", wait_until="networkidle")
        await page.wait_for_timeout(1500)

        # Locate the card for test_browser_removable
        card = page.locator('[data-testid="asset-tile"]:has-text("test browser removable")')
        await card.wait_for(state="visible", timeout=5000)
        print("Found removable user track tile, clicking to open drawer...")
        await card.click()
        await page.wait_for_timeout(1000)

        # Verify drawer
        drawer = page.locator('[data-testid="asset-drawer"]')
        assert await drawer.is_visible()

        # Verify audio element
        audio_el = drawer.locator("audio")
        assert await audio_el.count() == 1
        print("Verified <audio> element in drawer:", await audio_el.get_attribute("src"))

        # Click Delete in drawer
        del_btn = drawer.locator('button[aria-label="Delete"]')
        assert await del_btn.is_enabled(), "Delete button must be enabled for user track"
        await del_btn.click()
        await page.wait_for_timeout(500)

        # Confirm in dialog
        confirm_dialog = page.get_by_role("dialog", name="Delete this item?")
        assert await confirm_dialog.is_visible()
        confirm_btn = confirm_dialog.locator("button:has-text('Delete')")
        print("Confirming delete in modal...")
        await confirm_btn.click()
        await page.wait_for_timeout(1500)

        # Check snackbar
        snackbar = page.locator(".MuiSnackbar-root, .MuiAlert-root")
        snackbar_text = await snackbar.first.text_content() if await snackbar.count() > 0 else ""
        print("Snackbar message:", snackbar_text)
        assert "Deleted" in snackbar_text

        # Verify file is deleted on disk
        print("File exists on disk after delete?", target_file.exists())
        assert not target_file.exists(), "File must be unlinked from storage/music/"

        # Take screenshot of clean library
        Path("artifacts/p0_final_remediation").mkdir(parents=True, exist_ok=True)
        await page.screenshot(path="artifacts/p0_final_remediation/05_user_audio_deleted_successfully.png")
        print("Screenshot saved to artifacts/p0_final_remediation/05_user_audio_deleted_successfully.png")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_successful_user_audio_delete())
