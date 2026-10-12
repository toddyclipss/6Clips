import asyncio
import json
import httpx
from playwright.async_api import async_playwright

BASE_URL = "http://127.0.0.1:16888"

async def diagnose():
    # 1. Create a 9:16 project with weight-wave
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        res = await client.post("/api/projects", json={
            "name": "Gate 1 Animation Diagnosis",
            "aspect_ratio": "9:16"
        })
        p = res.json()
        pid = p["id"]
        rev = p["revision"]
        print(f"Created project {pid} at rev {rev}")

        res_b = await client.post(f"/api/projects/{pid}/operations", json={
            "expected_revision": rev,
            "operation_type": "add_block",
            "payload": {
                "block_id": "weight-wave",
                "start_seconds": 0.0,
                "duration_seconds": 6.0,
                "variables": {
                    "text": "PRESSURE MOVES THROUGH TYPE",
                    "color": "#f5f5f7"
                }
            }
        })
        print("add_block status:", res_b.status_code)
        doc = res_b.json()["document"]
        all_clips = [c for tr in doc["timeline"]["tracks"] for c in tr["clips"]]
        block_clip = next(c for c in all_clips if c.get("block_id"))
        cid = block_clip["id"]
        print(f"Block clip id: {cid}")

    # 2. Open in Playwright and inspect frames, console logs, and animation values
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: console_logs.append(f"[PAGEERROR] {err}"))

        await page.goto(f"{BASE_URL}/motion?projectId={pid}", wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # Locate outer preview iframe
        outer_frame_loc = page.locator("#studio-preview-iframe")
        await outer_frame_loc.wait_for(state="attached", timeout=5000)
        outer_frame = await (await outer_frame_loc.element_handle()).content_frame()
        print("Outer frame loaded:", outer_frame is not None)

        if outer_frame:
            # Check inner subcomp iframe inside outer frame
            inner_frame_loc = outer_frame.locator(f"iframe[title='{cid}']")
            count = await inner_frame_loc.count()
            print(f"Inner frame count: {count}")

            if count > 0:
                inner_frame = await (await inner_frame_loc.element_handle()).content_frame()
                print("Inner frame loaded:", inner_frame is not None)

                # Read initial text and span styles in inner frame
                initial_styles = await inner_frame.evaluate("""() => {
                    const spans = document.querySelectorAll(".ww-ch");
                    return Array.from(spans).slice(0, 8).map(s => ({
                        text: s.textContent,
                        fvs: s.style.fontVariationSettings,
                        computed: window.getComputedStyle(s).fontVariationSettings
                    }));
                }""")
                print("Initial styles (t=0):", json.dumps(initial_styles, indent=2))

                # Test seeks across multiple timestamps and check all spans
                for t in [0.5, 1.0, 1.5, 2.5]:
                    await outer_frame.evaluate(f"() => {{ if (typeof seekTo === 'function') seekTo({t}); }}")
                    await page.wait_for_timeout(400)
                    active_spans = await inner_frame.evaluate("""() => {
                        const spans = document.querySelectorAll(".ww-ch");
                        return Array.from(spans).map((s, idx) => ({
                            idx: idx,
                            char: s.textContent,
                            fvs: s.style.fontVariationSettings,
                            computed: window.getComputedStyle(s).fontVariationSettings
                        })).filter(x => x.fvs && !x.fvs.includes("400"));
                    }""")
                    print(f"Active animated glyphs at t={t}s: count={len(active_spans)}, sample={active_spans[:3]}")

                # Test startPlayback
                print("Testing startPlayback()...")
                await outer_frame.evaluate("() => { if (typeof startPlayback === 'function') startPlayback(); }")
                await page.wait_for_timeout(1000)

                playing_spans = await inner_frame.evaluate("""() => {
                    const spans = document.querySelectorAll(".ww-ch");
                    return Array.from(spans).map((s, idx) => ({
                        idx: idx,
                        char: s.textContent,
                        fvs: s.style.fontVariationSettings,
                        computed: window.getComputedStyle(s).fontVariationSettings
                    })).filter(x => x.fvs && !x.fvs.includes("400"));
                }""")
                print(f"Active animated glyphs during live playback: count={len(playing_spans)}, sample={playing_spans[:3]}")

                # Check window.__timelines in inner frame
                tls_check = await inner_frame.evaluate("""() => {
                    return {
                        timelines: Object.keys(window.__timelines || {}),
                        hasTl: !!window.tl,
                        rootDims: {
                            w: document.getElementById('ww-root')?.offsetWidth,
                            h: document.getElementById('ww-root')?.offsetHeight
                        },
                        lineDims: {
                            w: document.getElementById('ww-line')?.offsetWidth,
                            h: document.getElementById('ww-line')?.offsetHeight,
                            font: document.getElementById('ww-line')?.style.fontSize
                        }
                    };
                }""")
                print("Inner frame debug info:", json.dumps(tls_check, indent=2))

        await browser.close()
        print("\nConsole logs from page:")
        for log in console_logs[-20:]:
            print(" ", log)

if __name__ == "__main__":
    asyncio.run(diagnose())
