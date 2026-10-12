# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
import asyncio
import sys
import os
from pathlib import Path
from playwright.async_api import async_playwright

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

ARTIFACT_DIR = Path(r"C:\Users\toddy\.gemini\antigravity\brain\5fe8acfd-1e07-41f5-8774-c43c45f0e95b")

async def run():
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        print("Navigating to http://localhost:5173/motion...")
        await page.goto("http://localhost:5173/motion", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        # Locate preview iframe
        iframe_locator = page.locator("iframe[title='Composition Stage']")
        await iframe_locator.wait_for(state="attached", timeout=10000)
        iframe_element = await iframe_locator.element_handle()
        comp_frame = await iframe_element.content_frame()
        assert comp_frame is not None, "Could not find composition stage iframe"

        # Locate stage element
        stage = comp_frame.locator("#stage")
        await stage.wait_for(state="visible", timeout=10000)

        # Capture t0 (before play)
        t0_path = ARTIFACT_DIR / "playback_frozen_t0.png"
        await stage.screenshot(path=str(t0_path))
        print("Captured t0:", t0_path)

        # Locate the Preview Stage Play Button (in the bottom bar of preview stage)
        # It's an IconButton with IconPlayerPlay inside StudioPreviewStage
        preview_play_btn = page.locator("button").filter(has=page.locator("svg.tabler-icon-player-play")).nth(1)
        btn_box = await preview_play_btn.bounding_box()
        print(f"Targeting Play button at {btn_box}...")

        # Read t0 clocks
        t0_ui_time = await page.locator("text=/.*s \\/ .*s/").first.text_content()
        t0_runtime_state = await comp_frame.evaluate("""() => {
            const vids = Array.from(document.querySelectorAll('video')).map(v => ({
                id: v.id,
                currentTime: v.currentTime,
                paused: v.paused,
                readyState: v.readyState
            }));
            const iframes = Array.from(document.querySelectorAll('iframe.subcomp-frame')).map(f => {
                let win = f.contentWindow;
                let keys = win && win.__timelines ? Object.keys(win.__timelines) : [];
                let tl = keys.length ? win.__timelines[keys[0]] : null;
                return {
                    id: f.parentElement ? f.parentElement.id : null,
                    timelineKeys: keys,
                    tlTime: tl ? tl.time() : null,
                    tlProgress: tl ? tl.progress() : null,
                    tlPaused: tl ? tl.paused() : null
                };
            });
            let rootTl = window.__timelines && window.__timelines["viralmint_stage"];
            return {
                rootTime: rootTl ? rootTl.time() : null,
                videos: vids,
                subcomps: iframes
            };
        }""")
        print(f"t0: UI='{t0_ui_time}', state={t0_runtime_state}")

        # Click real UI Play button
        print("Clicking Play button...")
        await preview_play_btn.click()

        # Wait 2 seconds
        await page.wait_for_timeout(2000)

        # Capture t2
        t2_path = ARTIFACT_DIR / "playback_frozen_t2.png"
        await stage.screenshot(path=str(t2_path))
        print("Captured t2:", t2_path)

        t2_ui_time = await page.locator("text=/.*s \\/ .*s/").first.text_content()
        t2_runtime_state = await comp_frame.evaluate("""() => {
            const vids = Array.from(document.querySelectorAll('video')).map(v => ({
                id: v.id,
                currentTime: v.currentTime,
                paused: v.paused,
                readyState: v.readyState
            }));
            const iframes = Array.from(document.querySelectorAll('iframe.subcomp-frame')).map(f => {
                let win = f.contentWindow;
                let keys = win && win.__timelines ? Object.keys(win.__timelines) : [];
                let tl = keys.length ? win.__timelines[keys[0]] : null;
                return {
                    id: f.parentElement ? f.parentElement.id : null,
                    timelineKeys: keys,
                    tlTime: tl ? tl.time() : null,
                    tlProgress: tl ? tl.progress() : null,
                    tlPaused: tl ? tl.paused() : null
                };
            });
            let rootTl = window.__timelines && window.__timelines["viralmint_stage"];
            return {
                rootTime: rootTl ? rootTl.time() : null,
                videos: vids,
                subcomps: iframes
            };
        }""")
        print(f"t2: UI='{t2_ui_time}', state={t2_runtime_state}")

        # Wait another 2 seconds (total 4s)
        await page.wait_for_timeout(2000)

        # Capture t4
        t4_path = ARTIFACT_DIR / "playback_frozen_t4.png"
        await stage.screenshot(path=str(t4_path))
        print("Captured t4:", t4_path)

        t4_ui_time = await page.locator("text=/.*s \\/ .*s/").first.text_content()
        t4_runtime_state = await comp_frame.evaluate("""() => {
            const vids = Array.from(document.querySelectorAll('video')).map(v => ({
                id: v.id,
                currentTime: v.currentTime,
                paused: v.paused,
                readyState: v.readyState
            }));
            const iframes = Array.from(document.querySelectorAll('iframe.subcomp-frame')).map(f => {
                let win = f.contentWindow;
                let keys = win && win.__timelines ? Object.keys(win.__timelines) : [];
                let tl = keys.length ? win.__timelines[keys[0]] : null;
                return {
                    id: f.parentElement ? f.parentElement.id : null,
                    timelineKeys: keys,
                    tlTime: tl ? tl.time() : null,
                    tlProgress: tl ? tl.progress() : null,
                    tlPaused: tl ? tl.paused() : null
                };
            });
            let rootTl = window.__timelines && window.__timelines["viralmint_stage"];
            return {
                rootTime: rootTl ? rootTl.time() : null,
                videos: vids,
                subcomps: iframes
            };
        }""")
        print(f"t4: UI='{t4_ui_time}', state={t4_runtime_state}")

        # Compare screenshots
        from PIL import Image
        import numpy as np

        def diff_images(p1, p2):
            img1 = Image.open(p1).convert("RGBA")
            img2 = Image.open(p2).convert("RGBA")
            arr1 = np.array(img1)
            arr2 = np.array(img2)
            if arr1.shape != arr2.shape:
                return -1, 0
            diff = np.any(arr1 != arr2, axis=-1)
            diff_count = int(np.sum(diff))
            total = diff.size
            pct = (diff_count / total) * 100
            return diff_count, pct

        d02_cnt, d02_pct = diff_images(t0_path, t2_path)
        d24_cnt, d24_pct = diff_images(t2_path, t4_path)
        print(f"Diff t0 vs t2: {d02_cnt} pixels ({d02_pct:.2f}%)")
        print(f"Diff t2 vs t4: {d24_cnt} pixels ({d24_pct:.2f}%)")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
