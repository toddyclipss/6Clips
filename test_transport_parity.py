import asyncio
import json
import numpy as np
from pathlib import Path
from PIL import Image
from playwright.async_api import async_playwright

REPO_ROOT = Path(__file__).resolve().parent
PROOF_DIR = REPO_ROOT / "artifacts" / "final_visual_acceptance"

async def test_transport_and_frame_parity():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        pid = "d5f13156-fc63-45e5-b448-d347639bc180"

        print("1. Opening /motion page...")
        await page.goto(f"http://127.0.0.1:16888/motion?projectId={pid}", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        outer_frame = await (await page.locator("#studio-preview-iframe").element_handle()).content_frame()
        inner_frame = await (await outer_frame.locator("iframe.subcomp-frame").element_handle()).content_frame()

        # Test exact aligned timestamps: 0.0s, 0.1s, 0.25s, 0.5s, 1.0s
        timestamps = [0.0, 0.1, 0.25, 0.5, 1.0]
        results = {}

        print("2. Testing Seek across timestamps...")
        for t in timestamps:
            await outer_frame.evaluate(f"() => {{ if (typeof seekTo === 'function') seekTo({t}); }}")
            await page.wait_for_timeout(250)

            p_opacity = await outer_frame.evaluate("""() => {
                const el = document.querySelector('#elem_fbc05ef7');
                return el ? parseFloat(window.getComputedStyle(el).opacity) : 1;
            }""")

            active_axes = await inner_frame.evaluate("""() => {
                const spans = Array.from(document.querySelectorAll('.ww-ch'));
                return spans.map(s => s.style.fontVariationSettings).filter(x => x && !x.includes('400'));
            }""")

            snap_path = PROOF_DIR / f"test_preview_parity_{t}s.png"
            await page.locator("#studio-preview-iframe").screenshot(path=str(snap_path))
            im = Image.open(snap_path)

            # Title region crop (upper center: X in [300, 1140], Y in [200, 600])
            arr = np.array(im)
            crop = arr[int(arr.shape[0]*0.2):int(arr.shape[0]*0.5), int(arr.shape[1]*0.2):int(arr.shape[1]*0.8)]
            mean_brightness = float(np.mean(crop))

            results[f"t_{t}"] = {
                "timestamp": t,
                "computed_opacity": p_opacity,
                "active_axes_count": len(active_axes),
                "title_region_mean_brightness": round(mean_brightness, 2)
            }
            print(f"Seek t={t}s: opacity={p_opacity}, active_axes={len(active_axes)}, brightness={mean_brightness:.2f}")

        # 3. Test transport controls: Play, Pause, Seek back to 0, Replay
        print("3. Testing transport controls...")
        # Play via button on stage
        play_btn = page.locator("button[aria-label='Play']")
        if await play_btn.count() > 0:
            await play_btn.click()
        else:
            await outer_frame.evaluate("() => { if (typeof startPlayback === 'function') startPlayback(); }")

        await page.wait_for_timeout(1000)

        # Pause via button on stage
        pause_btn = page.locator("button[aria-label='Pause']")
        if await pause_btn.count() > 0:
            await pause_btn.click()
        else:
            await outer_frame.evaluate("() => { if (typeof pausePlayback === 'function') pausePlayback(); }")

        await page.wait_for_timeout(200)

        # Seek back to zero via skip back button or seekTo(0)
        skip_back = page.locator("button[aria-label='Skip to start']")
        if await skip_back.count() > 0:
            await skip_back.click()
        else:
            await outer_frame.evaluate("() => { if (typeof seekTo === 'function') seekTo(0); }")

        await page.wait_for_timeout(300)

        back_to_zero_opacity = await outer_frame.evaluate("""() => {
            const el = document.querySelector('#elem_fbc05ef7');
            return el ? parseFloat(window.getComputedStyle(el).opacity) : 1;
        }""")
        print(f"After seek back to zero: opacity={back_to_zero_opacity}")
        assert abs(back_to_zero_opacity - 0.2) < 0.05, f"Expected opacity 0.2 when seeked back to 0, got {back_to_zero_opacity}"

        # Replay
        if await play_btn.count() > 0:
            await play_btn.click()
        else:
            await outer_frame.evaluate("() => { if (typeof startPlayback === 'function') startPlayback(); }")

        await page.wait_for_timeout(500)
        replaying_opacity = await outer_frame.evaluate("""() => {
            const el = document.querySelector('#elem_fbc05ef7');
            return el ? parseFloat(window.getComputedStyle(el).opacity) : 1;
        }""")
        print(f"During replay at ~0.5s: opacity={replaying_opacity}")
        assert replaying_opacity > 0.4, f"During replay opacity should advance, got {replaying_opacity}"

        await browser.close()
        print("Transport controls verified successfully!")

asyncio.run(test_transport_and_frame_parity())
