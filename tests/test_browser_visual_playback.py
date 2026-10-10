# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Automated Browser Regression Test: Motion Preview Visual Playback
Asserts:
- UI composition time increases after Play
- <video>.currentTime continuously advances
- GSAP child timeline time & computed transform/opacity advance
- Cropped preview-region pixel difference exceeds meaningful threshold (> 5%)
"""
import asyncio
from pathlib import Path
import httpx
from PIL import Image
import numpy as np
import pytest
from playwright.async_api import async_playwright


def _diff_images(path1, path2):
    img1 = Image.open(path1).convert("RGBA")
    img2 = Image.open(path2).convert("RGBA")
    arr1 = np.array(img1)
    arr2 = np.array(img2)
    assert arr1.shape == arr2.shape
    diff = np.any(arr1 != arr2, axis=-1)
    count = int(np.sum(diff))
    pct = (count / diff.size) * 100.0
    return count, pct


@pytest.mark.asyncio
async def test_motion_preview_visual_playback_regression(tmp_path):
    # 1. Create acceptance project with real video + animated block
    async with httpx.AsyncClient(base_url="http://127.0.0.1:16888") as client:
        res = await client.post("/api/projects", json={
            "name": "Regression Visual Playback Test",
            "aspect_ratio": "9:16"
        })
        assert res.status_code == 200
        p = res.json()
        pid = p["id"]
        rev = p["revision"]

        # Add moving video
        res_v = await client.post(f"/api/projects/{pid}/operations", json={
            "expected_revision": rev,
            "operation_type": "add_clip",
            "payload": {
                "track_id": "track_video_main",
                "clip": {
                    "id": "reg_vid",
                    "type": "video",
                    "asset_id": "test-moving-vid-1",
                    "start_seconds": 0.0,
                    "duration_seconds": 6.0,
                    "layer_order": 1,
                    "visible": True
                }
            }
        })
        assert res_v.status_code == 200
        rev = res_v.json()["revision"]

        # Add animated block
        res_b = await client.post(f"/api/projects/{pid}/operations", json={
            "expected_revision": rev,
            "operation_type": "add_block",
            "payload": {
                "block_id": "yt-lower-third",
                "start_seconds": 0.0,
                "duration_seconds": 5.0
            }
        })
        assert res_b.status_code == 200

    # 2. Open Playwright browser and test live /motion
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})

        await page.goto(f"http://localhost:5173/motion?projectId={pid}", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        iframe_locator = page.locator("iframe[title='Composition Stage']")
        await iframe_locator.wait_for(state="attached", timeout=10000)
        iframe_element = await iframe_locator.element_handle()
        comp_frame = await iframe_element.content_frame()
        assert comp_frame is not None

        stage = comp_frame.locator("#stage")
        await stage.wait_for(state="visible", timeout=10000)

        # Record t0 before Play
        shot_t0 = tmp_path / "t0.png"
        await stage.screenshot(path=str(shot_t0))

        state_t0 = await comp_frame.evaluate("""() => {
            let v = document.querySelector('video');
            let subframe = document.querySelector('iframe.subcomp-frame');
            let w = subframe ? subframe.contentWindow : null;
            let tls = w && w.__timelines ? w.__timelines : {};
            let k = Object.keys(tls);
            let tl = k.length ? tls[k[0]] : null;
            let card = subframe && subframe.contentDocument ? subframe.contentDocument.querySelector('#card') : null;
            let cardStyle = card ? w.getComputedStyle(card) : null;
            return {
                videoTime: v ? v.currentTime : null,
                tlTime: tl ? tl.time() : null,
                cardTransform: cardStyle ? cardStyle.transform : null,
                cardOpacity: cardStyle ? cardStyle.opacity : null
            };
        }""")
        ui_t0_str = await page.locator("text=/.*s \\/ .*s/").first.text_content()

        # Click the real UI play button in preview stage
        play_btn = page.locator("button").filter(has=page.locator("svg.tabler-icon-player-play")).nth(1)
        await play_btn.click()

        # Wait ~2 seconds of real playback
        await page.wait_for_timeout(2000)

        shot_t2 = tmp_path / "t2.png"
        await stage.screenshot(path=str(shot_t2))

        state_t2 = await comp_frame.evaluate("""() => {
            let v = document.querySelector('video');
            let subframe = document.querySelector('iframe.subcomp-frame');
            let w = subframe ? subframe.contentWindow : null;
            let tls = w && w.__timelines ? w.__timelines : {};
            let k = Object.keys(tls);
            let tl = k.length ? tls[k[0]] : null;
            let card = subframe && subframe.contentDocument ? subframe.contentDocument.querySelector('#card') : null;
            let cardStyle = card ? w.getComputedStyle(card) : null;
            return {
                videoTime: v ? v.currentTime : null,
                tlTime: tl ? tl.time() : null,
                cardTransform: cardStyle ? cardStyle.transform : null,
                cardOpacity: cardStyle ? cardStyle.opacity : null
            };
        }""")
        ui_t2_str = await page.locator("text=/.*s \\/ .*s/").first.text_content()

        await browser.close()

    # 3. Assertions
    # A. UI composition time increased
    ui_t0 = float(ui_t0_str.split("/")[0].replace("s", "").strip())
    ui_t2 = float(ui_t2_str.split("/")[0].replace("s", "").strip())
    assert ui_t2 > ui_t0, f"UI time did not advance: {ui_t0} -> {ui_t2}"

    # B. Real video currentTime continuously increased
    assert state_t0["videoTime"] is not None
    assert state_t2["videoTime"] is not None
    assert state_t2["videoTime"] >= state_t0["videoTime"] + 1.2, (
        f"Video currentTime did not advance sufficiently: {state_t0['videoTime']} -> {state_t2['videoTime']}"
    )

    # C. GSAP child timeline time increased
    assert state_t0["tlTime"] is not None
    assert state_t2["tlTime"] is not None
    assert state_t2["tlTime"] >= state_t0["tlTime"] + 1.2, (
        f"GSAP tlTime did not advance sufficiently: {state_t0['tlTime']} -> {state_t2['tlTime']}"
    )

    # D. Block computed transform or opacity changed
    assert (
        state_t0["cardTransform"] != state_t2["cardTransform"]
        or state_t0["cardOpacity"] != state_t2["cardOpacity"]
    ), f"Block visual property did not change: t0={state_t0}, t2={state_t2}"

    # E. Preview pixel diff exceeds meaningful threshold (> 5%)
    diff_count, diff_pct = _diff_images(shot_t0, shot_t2)
    assert diff_pct > 5.0, f"Preview pixels remained static! Changed: {diff_count} ({diff_pct:.2f}%)"
