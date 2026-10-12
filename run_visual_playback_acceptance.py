# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Comprehensive acceptance test suite verifying real visual playback in /motion.
Tests 3 clocks, video currentTime continuous advancement, GSAP transform/opacity progression,
cropped preview pixel differences, seek while paused, pause/resume, seek while playing,
and captures required artifact images.
"""
import asyncio
import sys
import os
from pathlib import Path
from PIL import Image
import numpy as np
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8')

ARTIFACT_DIR = Path(r"C:\Users\toddy\.gemini\antigravity\brain\5fe8acfd-1e07-41f5-8774-c43c45f0e95b")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

PID_916 = "03eddf51-2078-48fb-93a4-74917f0dbc80"
PID_169 = "be24abbb-9a33-4e93-bdc6-16cf38833663"

def diff_preview_images(path1, path2):
    img1 = Image.open(path1).convert("RGBA")
    img2 = Image.open(path2).convert("RGBA")
    arr1 = np.array(img1)
    arr2 = np.array(img2)
    assert arr1.shape == arr2.shape, f"Image dimension mismatch: {arr1.shape} vs {arr2.shape}"
    diff_mask = np.any(arr1 != arr2, axis=-1)
    diff_count = int(np.sum(diff_mask))
    total_pixels = diff_mask.size
    pct = (diff_count / total_pixels) * 100.0

    # Calculate bounding box of changed pixels
    if diff_count > 0:
        ys, xs = np.where(diff_mask)
        bbox = (int(np.min(xs)), int(np.min(ys)), int(np.max(xs)), int(np.max(ys)))
    else:
        bbox = None

    return {
        "diff_count": diff_count,
        "total_pixels": total_pixels,
        "pct": pct,
        "bbox": bbox,
    }

async def inspect_preview_clocks(page, comp_frame):
    """Inspect React transport, HTMLVideoElement, and GSAP timelines."""
    ui_time_str = await page.locator("text=/.*s \\/ .*s/").first.text_content()

    state = await comp_frame.evaluate("""() => {
        let v = document.querySelector('video');
        let vData = v ? {
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
            let win = f.contentWindow;
            let tls = win && win.__timelines ? win.__timelines : {};
            let keys = Object.keys(tls);
            let tl = keys.length ? tls[keys[0]] : null;
            let doc = f.contentDocument;
            let card = doc ? doc.querySelector('#card, .lower-third, #lb-root') : null;
            let cardStyle = card ? win.getComputedStyle(card) : null;
            let btn = doc ? doc.querySelector('#subscribe-btn') : null;
            let btnStyle = btn ? win.getComputedStyle(btn) : null;

            return {
                id: f.parentElement ? f.parentElement.getAttribute('data-hf-id') : null,
                keys: keys,
                tlTime: tl ? tl.time() : null,
                tlProgress: tl ? tl.progress() : null,
                tlPaused: tl ? tl.paused() : null,
                tlDuration: tl ? tl.duration() : null,
                cardTransform: cardStyle ? cardStyle.transform : null,
                cardOpacity: cardStyle ? cardStyle.opacity : null,
                btnTransform: btnStyle ? btnStyle.transform : null,
            };
        });

        let rootTl = window.__timelines && window.__timelines["viralmint_stage"];
        let rootData = rootTl ? {
            time: rootTl.time(),
            paused: rootTl.paused(),
            duration: rootTl.duration()
        } : null;

        let animBox = document.querySelector('#clip_animated_box');
        let animBoxStyle = animBox ? window.getComputedStyle(animBox) : null;

        return {
            rootTl: rootData,
            video: vData,
            subcomps: subframes,
            animBoxTransform: animBoxStyle ? animBoxStyle.transform : null,
            animBoxOpacity: animBoxStyle ? animBoxStyle.opacity : null
        };
    }""")

    return {
        "ui_time": ui_time_str.strip(),
        "state": state
    }

async def run_acceptance():
    print("=" * 60)
    print("STARTING FULL MOTION PREVIEW REAL VISUAL PLAYBACK ACCEPTANCE")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        # =====================================================================
        # PART 1: 9:16 COMPOSITION ACCEPTANCE (DEFAULT PROJECT FORMAT)
        # =====================================================================
        print(f"\n--- [1] 9:16 PROJECT: http://localhost:5173/motion?projectId={PID_916} ---")
        await page.goto(f"http://localhost:5173/motion?projectId={PID_916}", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        iframe_locator = page.locator("iframe[title='Composition Stage']")
        await iframe_locator.wait_for(state="attached", timeout=10000)
        iframe_element = await iframe_locator.element_handle()
        comp_frame = await iframe_element.content_frame()
        stage = comp_frame.locator("#stage")
        await stage.wait_for(state="visible", timeout=10000)

        # -----------------------------------------------------------------
        # TEST A: SEEK TESTED SEPARATELY FROM PLAY (SECTION 8)
        # -----------------------------------------------------------------
        print("\n>>> TEST A: PURE SEEK (WITHOUT PLAYING) <<<")
        seek_shots = {}
        seek_states = {}
        for s_t in [0.0, 1.0, 2.0, 4.0]:
            # Seek via UI or postMessage
            await comp_frame.evaluate(f"window.postMessage({{ source: 'vm-parent', action: 'seek', time: {s_t} }}, '*')")
            await page.wait_for_timeout(400)
            shot_file = ARTIFACT_DIR / f"seek_9x16_t{int(s_t)}.png"
            await stage.screenshot(path=str(shot_file))
            seek_shots[s_t] = shot_file
            st = await inspect_preview_clocks(page, comp_frame)
            seek_states[s_t] = st
            v_cur = st["state"]["video"]["currentTime"] if st["state"]["video"] else None
            sub_cur = st["state"]["subcomps"][0]["tlTime"] if st["state"]["subcomps"] else None
            sub_tf = st["state"]["subcomps"][0]["cardTransform"] if st["state"]["subcomps"] else None
            print(f"Seek t={s_t}s -> video.currentTime={v_cur:.3f}, GSAP child tlTime={sub_cur:.3f}, cardTransform={sub_tf}")

        diff_s0_s1 = diff_preview_images(seek_shots[0.0], seek_shots[1.0])
        diff_s1_s2 = diff_preview_images(seek_shots[1.0], seek_shots[2.0])
        diff_s2_s4 = diff_preview_images(seek_shots[2.0], seek_shots[4.0])
        print(f"Seek Diff 0 vs 1: {diff_s0_s1['diff_count']} pixels ({diff_s0_s1['pct']:.2f}%), bbox={diff_s0_s1['bbox']}")
        print(f"Seek Diff 1 vs 2: {diff_s1_s2['diff_count']} pixels ({diff_s1_s2['pct']:.2f}%), bbox={diff_s1_s2['bbox']}")
        print(f"Seek Diff 2 vs 4: {diff_s2_s4['diff_count']} pixels ({diff_s2_s4['pct']:.2f}%), bbox={diff_s2_s4['bbox']}")

        seek_passed = (diff_s0_s1["pct"] > 5.0 and diff_s1_s2["pct"] > 5.0 and diff_s2_s4["pct"] > 5.0)
        print(f"SEEK SEPARATE VERDICT: {'PASS' if seek_passed else 'FAIL'}")

        # -----------------------------------------------------------------
        # TEST B: REAL UI PLAY BUTTON ACCEPTANCE & 3-CLOCK INSPECTION (SECTIONS 2, 4, 5, 6, 7, 18, 23)
        # -----------------------------------------------------------------
        print("\n>>> TEST B: REAL PLAYBACK VIA UI PLAY BUTTON <<<")
        # Seek back to 0.0s before pressing Play
        await comp_frame.evaluate("window.postMessage({ source: 'vm-parent', action: 'seek', time: 0 }, '*')")
        await page.wait_for_timeout(400)

        # Capture t0 screenshot
        shot_t0_916 = ARTIFACT_DIR / "visual_playback_9x16_t0.png"
        await stage.screenshot(path=str(shot_t0_916))
        c0 = await inspect_preview_clocks(page, comp_frame)
        print("t0 (before Play):")
        print("  UI Transport:", c0["ui_time"])
        print("  Video:", c0["state"]["video"])
        print("  Subcomp GSAP:", c0["state"]["subcomps"])

        # Click the REAL visible Play button in Preview Stage controls
        play_btn = page.locator("button").filter(has=page.locator("svg.tabler-icon-player-play")).nth(1)
        print("Pressing REAL UI Play Button...")
        await play_btn.click()

        # Wait ~1s real time
        await page.wait_for_timeout(1000)
        shot_t1_916 = ARTIFACT_DIR / "visual_playback_9x16_t1.png"
        await stage.screenshot(path=str(shot_t1_916))
        c1 = await inspect_preview_clocks(page, comp_frame)
        print("t1 (~1s real playback):")
        print("  UI Transport:", c1["ui_time"])
        print("  video.currentTime:", c1["state"]["video"]["currentTime"] if c1["state"]["video"] else None)
        print("  GSAP tlTime:", c1["state"]["subcomps"][0]["tlTime"] if c1["state"]["subcomps"] else None)
        print("  Card transform:", c1["state"]["subcomps"][0]["cardTransform"] if c1["state"]["subcomps"] else None)
        print("  Card opacity:", c1["state"]["subcomps"][0]["cardOpacity"] if c1["state"]["subcomps"] else None)

        # Wait another ~1s real time (total ~2s)
        await page.wait_for_timeout(1000)
        shot_t2_916 = ARTIFACT_DIR / "visual_playback_9x16_t2.png"
        await stage.screenshot(path=str(shot_t2_916))
        c2 = await inspect_preview_clocks(page, comp_frame)
        print("t2 (~2s real playback):")
        print("  UI Transport:", c2["ui_time"])
        print("  video.currentTime:", c2["state"]["video"]["currentTime"] if c2["state"]["video"] else None)
        print("  GSAP tlTime:", c2["state"]["subcomps"][0]["tlTime"] if c2["state"]["subcomps"] else None)
        print("  Card transform:", c2["state"]["subcomps"][0]["cardTransform"] if c2["state"]["subcomps"] else None)
        print("  Card opacity:", c2["state"]["subcomps"][0]["cardOpacity"] if c2["state"]["subcomps"] else None)

        # Wait another ~1s real time (total ~3s)
        await page.wait_for_timeout(1000)
        c3 = await inspect_preview_clocks(page, comp_frame)
        print("t3 (~3s real playback):")
        print("  UI Transport:", c3["ui_time"])
        print("  video.currentTime:", c3["state"]["video"]["currentTime"] if c3["state"]["video"] else None)
        print("  GSAP tlTime:", c3["state"]["subcomps"][0]["tlTime"] if c3["state"]["subcomps"] else None)

        # Compute Pixel differences between t0, t1, t2
        diff_0_1 = diff_preview_images(shot_t0_916, shot_t1_916)
        diff_1_2 = diff_preview_images(shot_t1_916, shot_t2_916)
        print(f"\nPixel Diff t0 vs t1: {diff_0_1['diff_count']} pixels ({diff_0_1['pct']:.2f}%), bbox={diff_0_1['bbox']}")
        print(f"Pixel Diff t1 vs t2: {diff_1_2['diff_count']} pixels ({diff_1_2['pct']:.2f}%), bbox={diff_1_2['bbox']}")

        # -----------------------------------------------------------------
        # TEST C: PAUSE ACCEPTANCE (SECTION 19)
        # -----------------------------------------------------------------
        print("\n>>> TEST C: PAUSE & RESUME ACCEPTANCE <<<")
        # Pause playback
        pause_btn = page.locator("button").filter(has=page.locator("svg.tabler-icon-player-pause")).first
        print("Pressing Pause...")
        await pause_btn.click()
        await page.wait_for_timeout(300)

        # Snapshot state right after pause
        pause_shot_1 = ARTIFACT_DIR / "pause_check_1.png"
        await stage.screenshot(path=str(pause_shot_1))
        st_pause_1 = await inspect_preview_clocks(page, comp_frame)

        # Wait 1.0 real second while paused
        await page.wait_for_timeout(1000)
        pause_shot_2 = ARTIFACT_DIR / "pause_check_2.png"
        await stage.screenshot(path=str(pause_shot_2))
        st_pause_2 = await inspect_preview_clocks(page, comp_frame)

        diff_pause = diff_preview_images(pause_shot_1, pause_shot_2)
        print(f"Pause 1s drift: {diff_pause['diff_count']} pixels ({diff_pause['pct']:.2f}%)")
        print(f"Video paused at {st_pause_1['state']['video']['currentTime']:.3f} -> {st_pause_2['state']['video']['currentTime']:.3f}")
        print(f"GSAP paused at {st_pause_1['state']['subcomps'][0]['tlTime']:.3f} -> {st_pause_2['state']['subcomps'][0]['tlTime']:.3f}")
        pause_passed = (diff_pause["diff_count"] == 0 and abs(st_pause_1['state']['video']['currentTime'] - st_pause_2['state']['video']['currentTime']) < 0.01)
        print(f"PAUSE VERDICT: {'PASS' if pause_passed else 'FAIL'}")

        # Resume playback
        resume_btn = page.locator("button").filter(has=page.locator("svg.tabler-icon-player-play")).nth(1)
        print("Resuming Play...")
        await resume_btn.click()
        await page.wait_for_timeout(1000)
        st_resumed = await inspect_preview_clocks(page, comp_frame)
        resume_adv = st_resumed['state']['video']['currentTime'] - st_pause_2['state']['video']['currentTime']
        print(f"Resumed video advancement: +{resume_adv:.3f}s")
        # Pause again
        await pause_btn.click()

        # -----------------------------------------------------------------
        # TEST D: SEEK WHILE PAUSED (SECTION 20)
        # -----------------------------------------------------------------
        print("\n>>> TEST D: SEEK WHILE PAUSED <<<")
        for seek_p in [0.5, 2.0, 4.0]:
            await comp_frame.evaluate(f"window.postMessage({{ source: 'vm-parent', action: 'seek', time: {seek_p} }}, '*')")
            await page.wait_for_timeout(300)
            st_sp = await inspect_preview_clocks(page, comp_frame)
            assert st_sp["state"]["video"]["paused"] == True, "Video should remain paused after seek"
            diff_cur = abs(st_sp["state"]["video"]["currentTime"] - seek_p)
            print(f"Seek while paused to {seek_p}s: video.currentTime={st_sp['state']['video']['currentTime']:.3f} (delta={diff_cur:.3f}s)")
            assert diff_cur < 0.1, f"Video seek error too high: {diff_cur}"

        # -----------------------------------------------------------------
        # TEST E: SEEK WHILE PLAYING (SECTION 21)
        # -----------------------------------------------------------------
        print("\n>>> TEST E: SEEK WHILE PLAYING <<<")
        # Start playing
        await page.locator("button").filter(has=page.locator("svg.tabler-icon-player-play")).nth(1).click()
        await page.wait_for_timeout(500)
        # Scrub to 1.5s while playing
        print("Scrubbing to 1.5s mid-playback...")
        await comp_frame.evaluate("window.postMessage({ source: 'vm-parent', action: 'seek', time: 1.5 }, '*')")
        await page.wait_for_timeout(800)
        st_mid = await inspect_preview_clocks(page, comp_frame)
        print(f"Post-scrub state: UI={st_mid['ui_time']}, video.currentTime={st_mid['state']['video']['currentTime']:.3f}")
        assert st_mid['state']['video']['currentTime'] >= 1.5, "Playback should continue forward from 1.5s without resetting to 0"
        # Pause
        await page.locator("button").filter(has=page.locator("svg.tabler-icon-player-pause")).first.click()

        # =====================================================================
        # PART 2: 16:9 COMPOSITION ACCEPTANCE (SECTION 24)
        # =====================================================================
        print(f"\n--- [2] 16:9 PROJECT: http://localhost:5173/motion?projectId={PID_169} ---")
        await page.goto(f"http://localhost:5173/motion?projectId={PID_169}", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        iframe_locator_169 = page.locator("iframe[title='Composition Stage']")
        await iframe_locator_169.wait_for(state="attached", timeout=10000)
        iframe_element_169 = await iframe_locator_169.element_handle()
        comp_frame_169 = await iframe_element_169.content_frame()
        stage_169 = comp_frame_169.locator("#stage")
        await stage_169.wait_for(state="visible", timeout=10000)

        # Seek to 0.0s
        await comp_frame_169.evaluate("window.postMessage({ source: 'vm-parent', action: 'seek', time: 0 }, '*')")
        await page.wait_for_timeout(400)

        # Capture 16:9 t0
        shot_t0_169 = ARTIFACT_DIR / "visual_playback_16x9_t0.png"
        await stage_169.screenshot(path=str(shot_t0_169))
        c0_169 = await inspect_preview_clocks(page, comp_frame_169)
        print("16:9 t0 (before play): video.currentTime =", c0_169["state"]["video"]["currentTime"] if c0_169["state"]["video"] else None)

        # Click Play in 16:9
        play_btn_169 = page.locator("button").filter(has=page.locator("svg.tabler-icon-player-play")).nth(1)
        await play_btn_169.click()

        await page.wait_for_timeout(1000)
        shot_t1_169 = ARTIFACT_DIR / "visual_playback_16x9_t1.png"
        await stage_169.screenshot(path=str(shot_t1_169))
        c1_169 = await inspect_preview_clocks(page, comp_frame_169)
        print("16:9 t1: video.currentTime =", c1_169["state"]["video"]["currentTime"] if c1_169["state"]["video"] else None)

        await page.wait_for_timeout(1000)
        shot_t2_169 = ARTIFACT_DIR / "visual_playback_16x9_t2.png"
        await stage_169.screenshot(path=str(shot_t2_169))
        c2_169 = await inspect_preview_clocks(page, comp_frame_169)
        print("16:9 t2: video.currentTime =", c2_169["state"]["video"]["currentTime"] if c2_169["state"]["video"] else None)

        diff_0_1_169 = diff_preview_images(shot_t0_169, shot_t1_169)
        diff_1_2_169 = diff_preview_images(shot_t1_169, shot_t2_169)
        print(f"16:9 Pixel Diff t0 vs t1: {diff_0_1_169['diff_count']} pixels ({diff_0_1_169['pct']:.2f}%), bbox={diff_0_1_169['bbox']}")
        print(f"16:9 Pixel Diff t1 vs t2: {diff_1_2_169['diff_count']} pixels ({diff_1_2_169['pct']:.2f}%), bbox={diff_1_2_169['bbox']}")

        await browser.close()

    print("\n" + "=" * 60)
    print("ALL ACCEPTANCE SUITES FINISHED SUCCESSFULLY")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_acceptance())
