# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Reproduction script for Blocker Mission: Motion Preview Player Runtime Failure
Captures live browser state, DOM nodes, computed dimensions, console logs, network errors,
and saves failure screenshots.
"""
import asyncio
import json
from pathlib import Path
import httpx
from playwright.async_api import async_playwright

ARTIFACTS_DIR = Path(r"C:\Users\toddy\.gemini\antigravity\brain\05dc85cb-9ba9-426a-8e4d-5ef5943efc16")


async def reproduce():
    print("=== STEP 2: REPRODUCING PREVIEW FAILURE IN LIVE /motion ===")
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. First, create a 9:16 test project with real objects:
    # - 1 video or background
    # - 1 HyperFrames block
    # - 1 caption/text
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
        # Create 9:16 project
        res = await client.post("/api/projects", json={
            "name": "Live 9:16 Preview Test",
            "aspect_ratio": "9:16"
        })
        assert res.status_code == 200, res.text
        proj = res.json()
        pid = proj["id"]
        rev = proj["revision"]
        print(f"Created Project: {pid} (aspect: {proj['aspect_ratio']}, rev: {rev})")

        # Add block instance (lower-third-bild or notification-cascade)
        res_block = await client.post(f"/api/projects/{pid}/operations", json={
            "expected_revision": rev,
            "operation_type": "add_block",
            "payload": {
                "block_id": "lower-third-bild",
                "variables": {
                    "TXT_MAIN_1_Line": "LIVE PREVIEW TEST",
                    "TXT_SUB": "VIRALMINT 9:16 COMPOSITION"
                },
                "start_seconds": 0.0,
                "duration_seconds": 5.0
            }
        })
        assert res_block.status_code == 200, res_block.text
        rev = res_block.json()["revision"]
        print(f"Added block, rev={rev}")

        # Add caption
        res_cap = await client.post(f"/api/projects/{pid}/operations", json={
            "expected_revision": rev,
            "operation_type": "add_clip",
            "payload": {
                "track_id": "track_captions_main",
                "clip": {
                    "id": "caption_hero",
                    "type": "captions",
                    "caption_text": "VISIBLE CAPTION TEST",
                    "start_seconds": 0.5,
                    "duration_seconds": 4.0,
                    "layer_order": 5,
                    "visible": True,
                    "locked": False
                }
            }
        })
        assert res_cap.status_code == 200, res_cap.text
        rev = res_cap.json()["revision"]
        print(f"Added caption, rev={rev}")

        # Also test sync-studio / preview endpoint response
        res_prev = await client.get(f"/api/projects/{pid}/preview")
        print(f"Backend GET /preview status: {res_prev.status_code}, HTML length: {len(res_prev.text)}")
        preview_html = res_prev.text

    # 2. Open Playwright Chromium browser and navigate to /motion
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: console_logs.append(f"[pageerror] {err}"))

        network_errors = []
        page.on("requestfailed", lambda req: network_errors.append(f"{req.method} {req.url} -> {req.failure}"))

        print(f"Navigating to http://localhost:5173/motion?project_id={pid}...")
        await page.goto(f"http://localhost:5173/motion?project_id={pid}", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        # 3. Inspect Preview Stage geometry & DOM
        # Outer container
        stage_outer = page.locator("div:has(> iframe[title='Composition Stage'])").first
        outer_box = await stage_outer.bounding_box() if await stage_outer.count() > 0 else None
        print(f"Outer stage container bbox: {outer_box}")

        iframe_locator = page.locator("iframe[title='Composition Stage']")
        iframe_count = await iframe_locator.count()
        print(f"Iframe count: {iframe_count}")

        iframe_box = None
        iframe_src = None
        if iframe_count > 0:
            iframe_box = await iframe_locator.bounding_box()
            iframe_src = await iframe_locator.get_attribute("src")
            print(f"Iframe bbox: {iframe_box}, src: {iframe_src}")

        # Capture initial screenshot BEFORE any changes
        fail_ss_path = ARTIFACTS_DIR / "preview_failure_before_fix_9x16.png"
        await page.screenshot(path=str(fail_ss_path), full_page=True)
        print(f"Captured failure screenshot: {fail_ss_path}")

        # Check inside iframe frame
        frame = page.frame(name=None, url=lambda u: f"/api/projects/{pid}/preview" in u)
        if not frame:
            # Try to get frame from element handle
            iframe_el = await iframe_locator.element_handle()
            frame = await iframe_el.content_frame() if iframe_el else None

        frame_info = {}
        if frame:
            print("Found composition iframe frame!")
            frame_title = await frame.title()
            stage_el = frame.locator("#stage")
            stage_count = await stage_el.count()
            stage_bbox = await stage_el.bounding_box() if stage_count > 0 else None
            stage_style = await stage_el.evaluate("el => ({ width: el.style.width, height: el.style.height, computedWidth: window.getComputedStyle(el).width, computedHeight: window.getComputedStyle(el).height, transform: window.getComputedStyle(el).transform })") if stage_count > 0 else {}
            
            blocks = frame.locator(".component-block")
            block_count = await blocks.count()
            block_children = await frame.locator(".component-block > *").count() if block_count > 0 else 0
            block_text = await frame.locator(".component-block").inner_text() if block_count > 0 else ""
            
            captions = frame.locator(".caption-block")
            caption_count = await captions.count()
            caption_bbox = await captions.bounding_box() if caption_count > 0 else None
            caption_text = await captions.inner_text() if caption_count > 0 else ""

            frame_info = {
                "title": frame_title,
                "stage_count": stage_count,
                "stage_bbox": stage_bbox,
                "stage_style": stage_style,
                "block_count": block_count,
                "block_children": block_children,
                "block_text": block_text,
                "caption_count": caption_count,
                "caption_bbox": caption_bbox,
                "caption_text": caption_text,
            }
            print(f"Frame details: {json.dumps(frame_info, indent=2)}")

        # Save diagnostic report
        diag = {
            "project_id": pid,
            "revision": rev,
            "aspect_ratio": "9:16",
            "outer_box": outer_box,
            "iframe_box": iframe_box,
            "iframe_src": iframe_src,
            "frame_info": frame_info,
            "console_logs": console_logs,
            "network_errors": network_errors,
            "preview_html_snippet": preview_html[:1000]
        }
        (ARTIFACTS_DIR / "preview_diagnostic_reproduction.json").write_text(json.dumps(diag, indent=2), encoding="utf-8")
        print("Diagnostic report saved to preview_diagnostic_reproduction.json")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(reproduce())
