# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print("Navigating to http://localhost:5173/motion...")
        await page.goto("http://localhost:5173/motion", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        iframe_locator = page.locator("iframe[title='Composition Stage']")
        iframe_element = await iframe_locator.element_handle()
        comp_frame = await iframe_element.content_frame()

        # Let's see what happens if we postMessage directly inside comp_frame
        res = await comp_frame.evaluate("""() => {
            return {
                hasGsap: !!window.gsap,
                timelinesKeys: window.__timelines ? Object.keys(window.__timelines) : [],
                viralmint_stage: window.__timelines && window.__timelines["viralmint_stage"] ? {
                    duration: window.__timelines["viralmint_stage"].duration(),
                    totalDuration: window.__timelines["viralmint_stage"].totalDuration(),
                    paused: window.__timelines["viralmint_stage"].paused(),
                    time: window.__timelines["viralmint_stage"].time()
                } : null
            };
        }""")
        print("Initial comp_frame state:", res)

        # Now send play message to comp_frame
        await comp_frame.evaluate("""() => {
            window.postMessage({ source: "vm-parent", action: "play" }, "*");
        }""")

        for i in range(5):
            await page.wait_for_timeout(500)
            state = await comp_frame.evaluate("""() => {
                let vm = window.__timelines && window.__timelines["viralmint_stage"];
                let subcomps = Array.from(document.querySelectorAll('iframe.subcomp-frame')).map(f => {
                    let win = f.contentWindow;
                    let keys = win && win.__timelines ? Object.keys(win.__timelines) : [];
                    let tl = keys.length ? win.__timelines[keys[0]] : null;
                    return {
                        id: f.parentElement ? f.parentElement.id : null,
                        keys: keys,
                        time: tl ? tl.time() : null,
                        paused: tl ? tl.paused() : null
                    };
                });
                return {
                    vmTime: vm ? vm.time() : null,
                    vmPaused: vm ? vm.paused() : null,
                    subcomps: subcomps
                };
            }""")
            print(f"Step {i} (+{(i+1)*0.5}s):", state)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
