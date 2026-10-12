# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8')

PROJ_ID = "f4778d1c-cf1a-442d-b8d2-ca27bae29a31"

async def test_clocks():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print(f"Navigating to http://localhost:5173/motion?projectId={PROJ_ID}...")
        await page.goto(f"http://localhost:5173/motion?projectId={PROJ_ID}", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        iframe_locator = page.locator("iframe[title='Composition Stage']")
        await iframe_locator.wait_for(state="attached", timeout=10000)
        iframe_element = await iframe_locator.element_handle()
        comp_frame = await iframe_element.content_frame()

        stage = comp_frame.locator("#stage")
        await stage.wait_for(state="visible", timeout=10000)

        # Inspect initial state
        async def inspect_state():
            ui_time = await page.locator("text=/.*s \\/ .*s/").first.text_content()
            state = await comp_frame.evaluate("""() => {
                let v = document.querySelector('video');
                let vidData = v ? {
                    src: v.src,
                    readyState: v.readyState,
                    networkState: v.networkState,
                    paused: v.paused,
                    currentTime: v.currentTime,
                    duration: v.duration,
                    videoWidth: v.videoWidth,
                    videoHeight: v.videoHeight,
                    playbackRate: v.playbackRate,
                    error: v.error ? v.error.message : null
                } : null;

                let subframes = Array.from(document.querySelectorAll('iframe.subcomp-frame')).map(f => {
                    let w = f.contentWindow;
                    let k = w && w.__timelines ? Object.keys(w.__timelines) : [];
                    let tl = k.length ? w.__timelines[k[0]] : null;
                    let mainText = f.contentDocument ? f.contentDocument.querySelector('#lb-root, #root') : null;
                    let style = mainText ? window.getComputedStyle(mainText) : null;
                    return {
                        id: f.parentElement ? f.parentElement.id : null,
                        keys: k,
                        time: tl ? tl.time() : null,
                        progress: tl ? tl.progress() : null,
                        paused: tl ? tl.paused() : null,
                        transform: style ? style.transform : null,
                        opacity: style ? style.opacity : null
                    };
                });

                let rootTl = window.__timelines && window.__timelines["viralmint_stage"];
                return {
                    rootTime: rootTl ? rootTl.time() : null,
                    video: vidData,
                    subcomps: subframes
                };
            }""")
            return ui_time, state

        print("--- t0 BEFORE PLAY ---")
        ui0, s0 = await inspect_state()
        print("UI:", ui0)
        print("Video:", s0["video"])
        print("Subcomps:", s0["subcomps"])

        # Click Preview Play button
        play_btn = page.locator("button").filter(has=page.locator("svg.tabler-icon-player-play")).nth(1)
        print("Clicking Play...")
        await play_btn.click()

        for t in [1, 2, 3]:
            await page.wait_for_timeout(1000)
            ui, s = await inspect_state()
            print(f"--- t{t} (~{t}s after play) ---")
            print("UI:", ui)
            print("Video:", s["video"])
            print("Subcomps:", s["subcomps"])

        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_clocks())
