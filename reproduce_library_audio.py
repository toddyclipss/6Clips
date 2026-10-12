# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
import asyncio
import json
from playwright.async_api import async_playwright

async def test_library_ui():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        
        console_msgs = []
        page.on("console", lambda msg: console_msgs.append(f"[{msg.type}] {msg.text}"))
        
        failed_reqs = []
        page.on("requestfailed", lambda req: failed_reqs.append(f"{req.method} {req.url}: {req.failure}"))
        
        req_responses = []
        page.on("response", lambda resp: req_responses.append(f"{resp.request.method} {resp.url} -> {resp.status}"))
        
        print("Navigating to http://127.0.0.1:16888/videos?media=audio ...")
        await page.goto("http://127.0.0.1:16888/videos?media=audio", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        
        # Check tiles
        tiles = await page.locator('[data-testid="asset-tile"]').all()
        print(f"Found {len(tiles)} asset tiles in Library")
        
        # Get tile texts
        for i, tile in enumerate(tiles[:5]):
            txt = await tile.text_content()
            print(f"Tile {i}: {txt}")
            
        # Click first tile to open AssetDrawer
        if len(tiles) > 0:
            print("Clicking first audio tile...")
            await tiles[0].click()
            await page.wait_for_timeout(1500)
            
            # Check drawer
            drawer = page.locator('[data-testid="asset-drawer"]')
            is_visible = await drawer.is_visible()
            print(f"AssetDrawer visible: {is_visible}")
            
            # Check audio element in drawer
            audio_el = drawer.locator("audio")
            has_audio = await audio_el.count()
            print(f"Audio element in drawer: {has_audio}")
            if has_audio:
                src = await audio_el.get_attribute("src")
                print(f"Audio src: {src}")
                audio_eval = await drawer.evaluate("""el => {
                    const a = el.querySelector('audio');
                    if (!a) return { error: 'no audio' };
                    return {
                        src: a.src,
                        duration: a.duration,
                        paused: a.paused,
                        readyState: a.readyState,
                        networkState: a.networkState,
                        error: a.error ? { code: a.error.code, message: a.error.message } : null
                    };
                }""")
                print("Audio eval in drawer:", audio_eval)
                
            # Now let's test clicking the delete button in the drawer!
            del_btn = drawer.locator('button[aria-label="Delete"], button:has-text("Delete")')
            del_count = await del_btn.count()
            print(f"Delete buttons in drawer: {del_count}")
            if del_count > 0:
                print("Clicking Delete button in AssetDrawer...")
                await del_btn.first.click()
                await page.wait_for_timeout(1000)
                
                # Check for confirm dialog
                confirm_dialog = page.get_by_role("dialog", name="Delete this item?")
                if await confirm_dialog.is_visible():
                    print("Dialog appeared:", await confirm_dialog.text_content())
                    confirm_btn = confirm_dialog.locator("button:has-text('Delete'), button:has-text('Confirm')")
                    if await confirm_btn.count() > 0:
                        print("Clicking confirm delete button...")
                        await confirm_btn.first.click()
                        await page.wait_for_timeout(1500)
                
                # Check snackbar
                snackbar = page.locator(".MuiSnackbar-root, .MuiAlert-root")
                if await snackbar.count() > 0:
                    print("Snackbar text:", await snackbar.first.text_content())
                    
        print("\nConsole errors:", [m for m in console_msgs if "error" in m.lower()])
        print("\nFailed requests:", failed_reqs)
        print("\nRelevant responses:")
        for r in req_responses:
            if "delete" in r.lower() or "audio" in r.lower() or "track" in r.lower() or "asset" in r.lower():
                print("  ", r)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_library_ui())
