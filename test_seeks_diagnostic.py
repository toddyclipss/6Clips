# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright
from PIL import Image
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

PROJ_ID = "f4778d1c-cf1a-442d-b8d2-ca27bae29a31"

async def test_seeks():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print(f"Navigating to http://localhost:5173/motion?projectId={PROJ_ID}...")
        await page.goto(f"http://localhost:5173/motion?projectId={PROJ_ID}", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        iframe_locator = page.locator("iframe[title='Composition Stage']")
        iframe_element = await iframe_locator.element_handle()
        comp_frame = await iframe_element.content_frame()
        stage = comp_frame.locator("#stage")

        shots = {}
        for t in [0.0, 1.0, 2.0, 4.0]:
            print(f"Seeking to {t}s via postMessage...")
            await comp_frame.evaluate(f"""() => {{
                window.postMessage({{ source: "vm-parent", action: "seek", time: {t} }}, "*");
            }}""")
            await page.wait_for_timeout(500)
            img_path = f"test_seek_{t}.png"
            await stage.screenshot(path=img_path)
            v_time = await comp_frame.evaluate("""() => {
                let v = document.querySelector('video');
                let tl = window.__timelines && window.__timelines['viralmint_stage'];
                return {
                    videoCurrentTime: v ? v.currentTime : null,
                    masterTime: tl ? tl.time() : null
                };
            }""")
            print(f"Seek {t}s: state={v_time}")
            shots[t] = img_path

        def diff(p1, p2):
            i1 = np.array(Image.open(p1).convert("RGBA"))
            i2 = np.array(Image.open(p2).convert("RGBA"))
            diff_count = int(np.sum(np.any(i1 != i2, axis=-1)))
            pct = (diff_count / (i1.shape[0] * i1.shape[1])) * 100
            return diff_count, pct

        d01 = diff(shots[0.0], shots[1.0])
        d12 = diff(shots[1.0], shots[2.0])
        d24 = diff(shots[2.0], shots[4.0])
        print(f"Diff 0 vs 1: {d01[0]} pixels ({d01[1]:.2f}%)")
        print(f"Diff 1 vs 2: {d12[0]} pixels ({d12[1]:.2f}%)")
        print(f"Diff 2 vs 4: {d24[0]} pixels ({d24[1]:.2f}%)")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_seeks())
