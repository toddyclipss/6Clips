# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
import asyncio
import json
from playwright.async_api import async_playwright

async def test_all_tiles():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        
        console_msgs = []
        page.on("console", lambda msg: console_msgs.append(f"[{msg.type}] {msg.text}"))
        
        await page.goto("http://127.0.0.1:16888/videos?media=audio", wait_until="networkidle")
        await page.wait_for_timeout(1000)
        
        tiles = await page.locator('[data-testid="asset-tile"]').all()
        print(f"Total tiles: {len(tiles)}")
        
        for i in range(min(len(tiles), 6)):
            tile = tiles[i]
            title = await tile.text_content()
            print(f"\n--- Inspecting Tile {i}: {title} ---")
            await tile.click()
            await page.wait_for_timeout(1000)
            
            drawer = page.locator('[data-testid="asset-drawer"]')
            audio_el = drawer.locator("audio")
            if await audio_el.count() > 0:
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
                print("  Drawer audio state:", audio_eval)
            else:
                print("  NO audio element in drawer!")
                
            # Close drawer
            close_btn = drawer.locator('button[aria-label="Close"]')
            if await close_btn.count() > 0:
                await close_btn.click()
                await page.wait_for_timeout(500)
                
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_all_tiles())
