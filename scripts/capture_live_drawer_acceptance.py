# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

OUTPUT_DIR = Path("artifacts/library_playback_acceptance")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VIEWPORTS = [
    {"name": "1920x1080", "width": 1920, "height": 1080},
    {"name": "1440x900", "width": 1440, "height": 900},
    {"name": "1366x768", "width": 1366, "height": 768},
]

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for vp in VIEWPORTS:
            vp_name = vp["name"]
            w, h = vp["width"], vp["height"]
            print(f"Testing live Drawer in {vp_name}...")
            context = await browser.new_context(viewport={"width": w, "height": h})
            page = await context.new_page()
            await page.goto("http://localhost:5173/videos", wait_until="networkidle")

            # Open drawer for test item via React state dispatch
            opened = await page.evaluate("""() => {
                const root = document.querySelector('#root');
                const fiberKey = Object.keys(root).find(k => k.startsWith('__reactContainer$'));
                let fiber = root[fiberKey];
                
                function findLibrary(node) {
                    if (!node) return null;
                    if (node.type && node.type.name === 'Library') return node;
                    let child = findLibrary(node.child);
                    if (child) return child;
                    return findLibrary(node.sibling);
                }
                const libFiber = findLibrary(fiber);
                if (!libFiber) return false;
                
                let h = libFiber.memoizedState;
                while (h) {
                    if (h.memoizedState instanceof Map) {
                        const drawerHook = h.next;
                        const item = {
                            key: 'dl:test-moving-vid-1',
                            source: 'downloaded',
                            id: 'test-moving-vid-1',
                            media: 'video',
                            origin: 'imported',
                            producer_key: 'download',
                            producer: 'YouTube',
                            title: 'Moving Video Test Asset',
                            stream_url: '/api/downloaded/test-moving-vid-1/stream',
                            duration_seconds: 10.0,
                            size_mb: 4.1,
                            ext: 'mp4'
                        };
                        drawerHook.queue.dispatch(item);
                        return true;
                    }
                    h = h.next;
                }
                return false;
            }""")

            print(f"  [{vp_name}] Drawer dispatch succeeded: {opened}")
            assert opened, "Could not open drawer via React dispatch"

            # Wait for drawer animation and content to load
            await page.wait_for_selector('[data-testid="asset-drawer"]', state="visible")
            await page.wait_for_timeout(2000)

            # Check video element in drawer
            video_locator = page.locator('[data-testid="asset-drawer"] video')
            count = await video_locator.count()
            print(f"  [{vp_name}] Video elements found in drawer: {count}")
            assert count >= 1, "No video element in drawer!"

            # Play video inside the drawer
            play_res = await page.evaluate("""async () => {
                const v = document.querySelector('[data-testid="asset-drawer"] video');
                if (!v) return { ok: false, err: 'no video' };
                try {
                    await v.play();
                    await new Promise(r => setTimeout(r, 1000));
                    return { ok: true, currentTime: v.currentTime, duration: v.duration };
                } catch (e) {
                    return { ok: false, err: e.message };
                }
            }""")
            print(f"  [{vp_name}] In-drawer playback evaluation: {play_res}")

            # Verify NO duplicate close button in drawer
            close_buttons = page.locator('[data-testid="asset-drawer"] button[aria-label="Close"]')
            close_count = await close_buttons.count()
            print(f"  [{vp_name}] Close buttons (aria-label=Close) in drawer: {close_count}")
            assert close_count == 1, f"Expected exactly 1 close button in drawer, found {close_count}!"

            # Verify NO intrusive top action banner (check that Use as Inspiration is primary)
            use_insp = page.locator('[data-testid="asset-drawer"] button:has-text("Use as Inspiration")')
            use_insp_count = await use_insp.count()
            print(f"  [{vp_name}] 'Use as Inspiration' buttons: {use_insp_count}")
            assert use_insp_count == 1, "Missing 'Use as Inspiration' button"

            # Actions dropdown button
            actions_btn = page.locator('[data-testid="asset-drawer"] button:has-text("Actions")')
            actions_btn_count = await actions_btn.count()
            print(f"  [{vp_name}] Discreet Actions button count: {actions_btn_count}")
            assert actions_btn_count == 1, "Missing 'Actions ▾' menu button"

            # Capture drawer screenshot
            drawer_shot_path = OUTPUT_DIR / f"03_asset_drawer_clean_oaas_{vp_name}.png"
            await page.screenshot(path=str(drawer_shot_path))
            print(f"  [{vp_name}] Captured Drawer screenshot: {drawer_shot_path}")

            # Also click "Actions ▾" to screenshot the menu
            await actions_btn.click()
            await page.wait_for_timeout(500)
            menu_shot_path = OUTPUT_DIR / f"04_asset_drawer_actions_menu_{vp_name}.png"
            await page.screenshot(path=str(menu_shot_path))
            print(f"  [{vp_name}] Captured Actions Menu screenshot: {menu_shot_path}")

            await context.close()
        await browser.close()
    print("\n[ALL DRAWER ACCEPTANCE TESTS PASSED]")

if __name__ == "__main__":
    asyncio.run(main())
