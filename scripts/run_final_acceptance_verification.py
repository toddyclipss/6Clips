import asyncio
import os
import json
import time
from pathlib import Path
from PIL import Image
import numpy as np
from playwright.async_api import async_playwright

ARTIFACT_DIR = Path(r"C:\Users\toddy\.gemini\antigravity\brain\5fe8acfd-1e07-41f5-8774-c43c45f0e95b")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

PROJ_916_ID = "03eddf51-2078-48fb-93a4-74917f0dbc80"
PROJ_169_ID = "be24abbb-9a33-4e93-bdc6-16cf38833663"

def compute_pixel_diff(img1_path, img2_path):
    im1 = Image.open(img1_path).convert("RGBA")
    im2 = Image.open(img2_path).convert("RGBA")
    arr1 = np.array(im1)
    arr2 = np.array(im2)
    min_shape = (min(arr1.shape[0], arr2.shape[0]), min(arr1.shape[1], arr2.shape[1]), 4)
    a1 = arr1[:min_shape[0], :min_shape[1]]
    a2 = arr2[:min_shape[0], :min_shape[1]]
    diff = np.any(a1 != a2, axis=-1)
    changed = int(np.sum(diff))
    total = int(diff.size)
    pct = (changed / total) * 100.0 if total > 0 else 0.0
    ys, xs = np.where(diff)
    bbox = None
    if len(xs) > 0:
        bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
    return changed, total, pct, bbox

async def sample_runtime_state(page, comp_frame):
    # React UI transport time string
    ui_time = "unknown"
    try:
        loc = page.locator("text=/.*s \\/ .*s/").first
        if await loc.count() > 0:
            ui_time = (await loc.text_content()).strip()
    except Exception:
        pass

    # Inside comp_frame: video, gsap, computed properties
    state = await comp_frame.evaluate("""() => {
        var v = document.querySelector('video');
        var vData = null;
        if (v) {
            vData = {
                src: v.src,
                currentTime: v.currentTime,
                duration: v.duration,
                paused: v.paused,
                readyState: v.readyState,
                videoWidth: v.videoWidth,
                videoHeight: v.videoHeight
            };
        }
        var subframe = document.querySelector('iframe.subcomp-frame');
        var gsapData = null;
        if (subframe) {
            var w = subframe.contentWindow;
            var d = subframe.contentDocument;
            var tls = (w && w.__timelines) ? w.__timelines : {};
            var keys = Object.keys(tls);
            var tl = keys.length ? tls[keys[0]] : (w ? w.tl : null);
            var card = d ? (d.querySelector('#card') || d.querySelector('.lower-third') || d.body) : null;
            var cardStyle = (card && w) ? w.getComputedStyle(card) : null;

            gsapData = {
                timelineKey: keys.length ? keys[0] : null,
                tlTime: tl ? tl.time() : null,
                tlProgress: tl ? tl.progress() : null,
                tlDuration: tl ? tl.duration() : null,
                tlPaused: tl ? tl.paused() : null,
                cardTransform: cardStyle ? cardStyle.transform : null,
                cardOpacity: cardStyle ? cardStyle.opacity : null
            };
        }
        return {
            windowCompTime: window.compTime != null ? window.compTime : null,
            windowIsPlaying: window.isPlaying != null ? window.isPlaying : null,
            video: vData,
            gsap: gsapData
        };
    }""")
    return { "ui_transport": ui_time, "runtime": state }

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        results = {}

        # =========================================================================
        # 1. TEST 9:16 ACCEPTANCE PROJECT (03eddf51-2078-48fb-93a4-74917f0dbc80)
        # =========================================================================
        print("\n==================================================")
        print("1. RUNNING 9:16 LIVE ACCEPTANCE VERIFICATION")
        print("==================================================")
        await page.goto(f"http://localhost:5173/motion?projectId={PROJ_916_ID}", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        iframe_locator = page.locator("iframe[title='Composition Stage']")
        await iframe_locator.wait_for(state="attached", timeout=10000)
        iframe_element = await iframe_locator.element_handle()
        comp_frame = await iframe_element.content_frame()
        assert comp_frame is not None, "9:16 comp_frame not available"

        stage = comp_frame.locator("#stage")
        await stage.wait_for(state="visible", timeout=10000)

        # Confirm simultaneous elements
        has_video = await comp_frame.evaluate("() => !!document.querySelector('video')")
        has_block = await comp_frame.evaluate("() => !!document.querySelector('iframe.subcomp-frame')")
        has_caption = await comp_frame.evaluate("() => !!document.querySelector('[data-composition-id=\"clip_static_hud\"], [data-hf-id=\"clip_static_hud\"], .caption-block, [data-layer-type=\"captions\"]') || (document.body.innerText.indexOf('STATIC CAPTION HUD') !== -1)")
        print(f"9:16 Composition contents: Real Video={has_video}, Real Block={has_block}, Static Caption={has_caption}")
        assert has_video and has_block, "Composition missing video or block"

        # Record t0 before Play
        t0_path = ARTIFACT_DIR / "final_9x16_stage_t0.png"
        await stage.screenshot(path=str(t0_path))
        t0_state = await sample_runtime_state(page, comp_frame)
        print("9:16 t0 State:", json.dumps(t0_state, indent=2))

        # Real user click Play button
        play_btn = page.locator("button").filter(has=page.locator("svg.tabler-icon-player-play")).nth(1)
        await play_btn.wait_for(state="visible", timeout=5000)
        print("Clicking UI Play button...")
        await play_btn.click()

        # Sample t1 at ~1.2s
        await page.wait_for_timeout(1200)
        t1_path = ARTIFACT_DIR / "final_9x16_stage_t1.png"
        await stage.screenshot(path=str(t1_path))
        t1_state = await sample_runtime_state(page, comp_frame)
        print("9:16 t1 State:", json.dumps(t1_state, indent=2))

        # Sample t2 at ~2.5s
        await page.wait_for_timeout(1300)
        t2_path = ARTIFACT_DIR / "final_9x16_stage_t2.png"
        await stage.screenshot(path=str(t2_path))
        t2_state = await sample_runtime_state(page, comp_frame)
        print("9:16 t2 State:", json.dumps(t2_state, indent=2))

        # Real UI Pause button click
        pause_btn = page.locator("button").filter(has=page.locator("svg.tabler-icon-player-pause")).first
        print("Clicking UI Pause button...")
        await pause_btn.click()
        await page.wait_for_timeout(200)

        # Pause observation 1
        pause_shot_1 = ARTIFACT_DIR / "final_9x16_pause_obs1.png"
        await stage.screenshot(path=str(pause_shot_1))
        p1_state = await sample_runtime_state(page, comp_frame)

        # Wait 1.0 real second while paused
        print("Waiting 1.0 real second while paused...")
        await page.wait_for_timeout(1000)
        pause_shot_2 = ARTIFACT_DIR / "final_9x16_pause_obs2.png"
        await stage.screenshot(path=str(pause_shot_2))
        p2_state = await sample_runtime_state(page, comp_frame)

        # Pixel drift while paused
        p_ch, p_tot, p_pct, _ = compute_pixel_diff(pause_shot_1, pause_shot_2)
        print(f"9:16 Pause Drift: {p_ch}/{p_tot} pixels ({p_pct:.2f}%)")

        # Resume from same position
        print("Resuming playback from paused position...")
        play_btn = page.locator("button").filter(has=page.locator("svg.tabler-icon-player-play")).nth(1)
        await play_btn.click()
        await page.wait_for_timeout(800)
        resume_state = await sample_runtime_state(page, comp_frame)
        print("9:16 Resume State:", json.dumps(resume_state, indent=2))

        # Pause again for seek tests
        pause_btn = page.locator("button").filter(has=page.locator("svg.tabler-icon-player-pause")).first
        await pause_btn.click()
        await page.wait_for_timeout(200)

        # Discrete Seek while paused
        print("Testing Seek while paused (0.5s, 2.0s, 4.0s)...")
        seek_tests_916 = []
        for s_time in [0.5, 2.0, 4.0]:
            await comp_frame.evaluate(f"() => window.postMessage({{ source: 'vm-parent', action: 'seek', time: {s_time} }}, '*')")
            await page.wait_for_timeout(300)
            s_shot = ARTIFACT_DIR / f"final_9x16_seek_{s_time}.png"
            await stage.screenshot(path=str(s_shot))
            s_state = await sample_runtime_state(page, comp_frame)
            seek_tests_916.append({ "target": s_time, "state": s_state, "shot": str(s_shot) })
            print(f"Seek {s_time}s -> video={s_state['runtime']['video']['currentTime']:.3f}, gsap={s_state['runtime']['gsap']['tlTime']:.3f}, transform={s_state['runtime']['gsap']['cardTransform']}")

        # Seek while playing
        print("Testing Seek while playing...")
        play_btn = page.locator("button").filter(has=page.locator("svg.tabler-icon-player-play")).nth(1)
        await play_btn.click()
        await page.wait_for_timeout(500)
        # Scrub to 1.5s mid-playback
        await comp_frame.evaluate("() => window.postMessage({ source: 'vm-parent', action: 'seek', time: 1.5 }, '*')")
        await page.wait_for_timeout(600)
        mid_seek_state = await sample_runtime_state(page, comp_frame)
        print(f"Seek while playing to 1.5s -> video={mid_seek_state['runtime']['video']['currentTime']:.3f}, playing={not mid_seek_state['runtime']['video']['paused']}")
        assert not mid_seek_state['runtime']['video']['paused'], "Video paused unexpectedly during seek-while-play"
        assert mid_seek_state['runtime']['video']['currentTime'] >= 1.5, "Video did not advance past 1.5s"

        # End of timeline test: seek near end (5.8s), play to duration (6.0s)
        print("Testing End-of-Timeline behavior...")
        await comp_frame.evaluate("() => window.postMessage({ source: 'vm-parent', action: 'seek', time: 5.8 }, '*')")
        await page.wait_for_timeout(600)
        end_state = await sample_runtime_state(page, comp_frame)
        print(f"End-of-Timeline State: time={end_state['runtime']['windowCompTime']}, video.paused={end_state['runtime']['video']['paused']}, gsap.paused={end_state['runtime']['gsap']['tlPaused']}")

        # Compute play diffs
        d01_ch, d01_tot, d01_pct, d01_box = compute_pixel_diff(t0_path, t1_path)
        d12_ch, d12_tot, d12_pct, d12_box = compute_pixel_diff(t1_path, t2_path)
        print(f"9:16 t0 vs t1 Diff: {d01_ch}/{d01_tot} ({d01_pct:.2f}%), box={d01_box}")
        print(f"9:16 t1 vs t2 Diff: {d12_ch}/{d12_tot} ({d12_pct:.2f}%), box={d12_box}")

        results["9x16"] = {
            "project_id": PROJ_916_ID,
            "t0": t0_state,
            "t1": t1_state,
            "t2": t2_state,
            "diff_0_1": { "changed": d01_ch, "total": d01_tot, "pct": d01_pct, "bbox": d01_box },
            "diff_1_2": { "changed": d12_ch, "total": d12_tot, "pct": d12_pct, "bbox": d12_box },
            "pause_diff": { "changed": p_ch, "total": p_tot, "pct": p_pct },
            "resume": resume_state,
            "seek_tests": seek_tests_916,
            "seek_while_playing": mid_seek_state,
            "end_of_timeline": end_state
        }

        # =========================================================================
        # 2. TEST 16:9 ACCEPTANCE PROJECT (be24abbb-9a33-4e93-bdc6-16cf38833663)
        # =========================================================================
        print("\n==================================================")
        print("2. RUNNING 16:9 LIVE ACCEPTANCE VERIFICATION")
        print("==================================================")
        await page.goto(f"http://localhost:5173/motion?projectId={PROJ_169_ID}", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        iframe_locator_169 = page.locator("iframe[title='Composition Stage']")
        await iframe_locator_169.wait_for(state="attached", timeout=10000)
        iframe_element_169 = await iframe_locator_169.element_handle()
        comp_frame_169 = await iframe_element_169.content_frame()
        assert comp_frame_169 is not None, "16:9 comp_frame not available"

        stage_169 = comp_frame_169.locator("#stage")
        await stage_169.wait_for(state="visible", timeout=10000)

        has_video_169 = await comp_frame_169.evaluate("() => !!document.querySelector('video')")
        has_block_169 = await comp_frame_169.evaluate("() => !!document.querySelector('iframe.subcomp-frame')")
        has_caption_169 = await comp_frame_169.evaluate("() => !!document.querySelector('[data-composition-id=\"clip_static_hud_169\"], [data-hf-id=\"clip_static_hud_169\"], .caption-block, [data-layer-type=\"captions\"]') || (document.body.innerText.indexOf('STATIC CAPTION HUD 16:9') !== -1)")
        print(f"16:9 Composition contents: Real Video={has_video_169}, Real Block={has_block_169}, Static Caption={has_caption_169}")

        # Record t0 before Play
        t0_path_169 = ARTIFACT_DIR / "final_16x9_stage_t0.png"
        await stage_169.screenshot(path=str(t0_path_169))
        t0_state_169 = await sample_runtime_state(page, comp_frame_169)
        print("16:9 t0 State:", json.dumps(t0_state_169, indent=2))

        # Real UI Play button click
        play_btn_169 = page.locator("button").filter(has=page.locator("svg.tabler-icon-player-play")).nth(1)
        print("Clicking UI Play button on 16:9...")
        await play_btn_169.click()

        # Sample t1 at ~1.2s
        await page.wait_for_timeout(1200)
        t1_path_169 = ARTIFACT_DIR / "final_16x9_stage_t1.png"
        await stage_169.screenshot(path=str(t1_path_169))
        t1_state_169 = await sample_runtime_state(page, comp_frame_169)
        print("16:9 t1 State:", json.dumps(t1_state_169, indent=2))

        # Sample t2 at ~2.5s
        await page.wait_for_timeout(1300)
        t2_path_169 = ARTIFACT_DIR / "final_16x9_stage_t2.png"
        await stage_169.screenshot(path=str(t2_path_169))
        t2_state_169 = await sample_runtime_state(page, comp_frame_169)
        print("16:9 t2 State:", json.dumps(t2_state_169, indent=2))

        # Real UI Pause button click on 16:9
        pause_btn_169 = page.locator("button").filter(has=page.locator("svg.tabler-icon-player-pause")).first
        print("Clicking UI Pause button on 16:9...")
        await pause_btn_169.click()
        await page.wait_for_timeout(200)

        pause_169_shot1 = ARTIFACT_DIR / "final_16x9_pause_obs1.png"
        await stage_169.screenshot(path=str(pause_169_shot1))
        await page.wait_for_timeout(1000)
        pause_169_shot2 = ARTIFACT_DIR / "final_16x9_pause_obs2.png"
        await stage_169.screenshot(path=str(pause_169_shot2))
        p_ch_169, p_tot_169, p_pct_169, _ = compute_pixel_diff(pause_169_shot1, pause_169_shot2)
        print(f"16:9 Pause Drift: {p_ch_169}/{p_tot_169} pixels ({p_pct_169:.2f}%)")

        # Compute full-stage diffs for 16:9
        d01_ch_169, d01_tot_169, d01_pct_169, d01_box_169 = compute_pixel_diff(t0_path_169, t1_path_169)
        d12_ch_169, d12_tot_169, d12_pct_169, d12_box_169 = compute_pixel_diff(t1_path_169, t2_path_169)
        print(f"16:9 Full Stage t0 vs t1 Diff: {d01_ch_169}/{d01_tot_169} ({d01_pct_169:.2f}%), box={d01_box_169}")
        print(f"16:9 Full Stage t1 vs t2 Diff: {d12_ch_169}/{d12_tot_169} ({d12_pct_169:.2f}%), box={d12_box_169}")

        results["16x9"] = {
            "project_id": PROJ_169_ID,
            "t0": t0_state_169,
            "t1": t1_state_169,
            "t2": t2_state_169,
            "diff_0_1": { "changed": d01_ch_169, "total": d01_tot_169, "pct": d01_pct_169, "bbox": d01_box_169 },
            "diff_1_2": { "changed": d12_ch_169, "total": d12_tot_169, "pct": d12_pct_169, "bbox": d12_box_169 },
            "pause_diff": { "changed": p_ch_169, "total": p_tot_169, "pct": p_pct_169 }
        }

        # =========================================================================
        # 3. TEST RELOAD & REPLAY OF PERSISTED PROJECT
        # =========================================================================
        print("\n==================================================")
        print("3. TESTING RELOAD & REPLAY OF PERSISTED PROJECT")
        print("==================================================")
        await page.reload(wait_until="networkidle")
        await page.wait_for_timeout(3000)

        iframe_locator_rel = page.locator("iframe[title='Composition Stage']")
        await iframe_locator_rel.wait_for(state="attached", timeout=10000)
        comp_frame_rel = await (await iframe_locator_rel.element_handle()).content_frame()
        stage_rel = comp_frame_rel.locator("#stage")
        await stage_rel.wait_for(state="visible", timeout=10000)

        play_btn_rel = page.locator("button").filter(has=page.locator("svg.tabler-icon-player-play")).nth(1)
        rel_t0 = await sample_runtime_state(page, comp_frame_rel)
        print("Reloaded t0 State:", json.dumps(rel_t0, indent=2))

        await play_btn_rel.click()
        await page.wait_for_timeout(1500)
        rel_t1 = await sample_runtime_state(page, comp_frame_rel)
        print("Reloaded t1 State after Play:", json.dumps(rel_t1, indent=2))

        v_rel_time = rel_t1["runtime"]["video"]["currentTime"]
        print(f"Reload verification: video currentTime after play = {v_rel_time:.3f}s")
        assert v_rel_time > 1.0, f"Video did not advance after reload & play (got {v_rel_time})"

        results["reload_test"] = {
            "t0": rel_t0,
            "t1": rel_t1,
            "verified": True
        }

        # Save structured telemetry
        telemetry_file = ARTIFACT_DIR / "final_acceptance_closure_telemetry.json"
        with open(telemetry_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nTelemetry saved to {telemetry_file}")

        await browser.close()
        print("\nALL ACCEPTANCE CRITERIA EXECUTED AND RECORDED SUCCESSFULLY.")

if __name__ == "__main__":
    asyncio.run(run())
