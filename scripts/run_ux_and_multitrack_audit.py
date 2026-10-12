# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Evidence-Based UX and Multi-Track Timeline Audit Script
Executes browser automation, API multi-track composition creation, and visual inspection.
Captures real screenshots of the /motion Refine workspace, Timeline, Assets, and Catalog.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

BASE_URL = "http://127.0.0.1:16888"
AUDIT_DIR = Path("artifacts/audit").resolve()
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

audit_results = {}

def log(msg: str):
    print(f"[UX-AUDIT] {msg}", flush=True)

async def run_audit():
    log("Starting comprehensive UX and multi-track architecture audit...")
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        # 1. Health check
        res = await client.get("/api/projects")
        assert res.status_code == 200, "Server not responding on 16888"

        # 2. Create Dense Multi-Track Test Project
        # 3 audio tracks, 2 caption tracks, 3 graphic/block tracks, multiple clips on same track
        p_res = await client.post("/api/projects", json={
            "name": "Audit Multi-Track Dense Project",
            "aspect_ratio": "9:16"
        })
        assert p_res.status_code == 200
        proj = p_res.json()
        pid = proj["id"]
        rev = proj["revision"]
        log(f"Created test project {pid} at revision {rev}")

        # Construct comprehensive multi-track timeline
        tracks = [
            {
                "id": "track_video_main",
                "type": "video",
                "name": "Main Video",
                "visible": True,
                "locked": False,
                "clips": [
                    {
                        "id": "clip_vid_1",
                        "type": "video",
                        "title": "A-Roll Footage 1",
                        "asset_file": "sample_video_1.mp4",
                        "start_seconds": 0.0,
                        "duration_seconds": 4.0,
                        "trim_start": 0.0,
                        "layer_order": 1,
                        "visible": True,
                        "locked": False,
                    },
                    {
                        "id": "clip_vid_2",
                        "type": "video",
                        "title": "A-Roll Footage 2",
                        "asset_file": "sample_video_2.mp4",
                        "start_seconds": 4.0,
                        "duration_seconds": 6.0,
                        "trim_start": 1.0,
                        "layer_order": 2,
                        "visible": True,
                        "locked": False,
                    }
                ]
            },
            {
                "id": "track_audio_bgm",
                "type": "audio",
                "name": "Background Music",
                "visible": True,
                "locked": False,
                "muted": False,
                "clips": [
                    {
                        "id": "clip_bgm_1",
                        "type": "audio",
                        "title": "Lofi Synth Bed",
                        "asset_file": "bgm_loop.mp3",
                        "start_seconds": 0.0,
                        "duration_seconds": 10.0,
                        "trim_start": 0.0,
                        "layer_order": 3,
                        "visible": True,
                        "locked": False,
                    }
                ]
            },
            {
                "id": "track_audio_vo",
                "type": "audio",
                "name": "Voiceover / Speech",
                "visible": True,
                "locked": False,
                "muted": False,
                "clips": [
                    {
                        "id": "clip_vo_1",
                        "type": "audio",
                        "title": "Hook Narration",
                        "asset_file": "hook_voice.mp3",
                        "start_seconds": 0.5,
                        "duration_seconds": 3.0,
                        "trim_start": 0.0,
                        "layer_order": 4,
                        "visible": True,
                        "locked": False,
                    },
                    {
                        "id": "clip_vo_2",
                        "type": "audio",
                        "title": "CTA Narration",
                        "asset_file": "cta_voice.mp3",
                        "start_seconds": 5.0,
                        "duration_seconds": 4.0,
                        "trim_start": 0.0,
                        "layer_order": 5,
                        "visible": True,
                        "locked": False,
                    }
                ]
            },
            {
                "id": "track_audio_sfx",
                "type": "audio",
                "name": "Sound Effects (SFX)",
                "visible": True,
                "locked": False,
                "muted": False,
                "clips": [
                    {
                        "id": "clip_sfx_whoosh",
                        "type": "audio",
                        "title": "Whoosh Hit",
                        "asset_file": "whoosh.wav",
                        "start_seconds": 2.0,
                        "duration_seconds": 1.2,
                        "trim_start": 0.0,
                        "layer_order": 6,
                        "visible": True,
                        "locked": False,
                    },
                    {
                        "id": "clip_sfx_ding",
                        "type": "audio",
                        "title": "Notification Ding",
                        "asset_file": "ding.wav",
                        "start_seconds": 5.0,
                        "duration_seconds": 0.8,
                        "trim_start": 0.0,
                        "layer_order": 7,
                        "visible": True,
                        "locked": False,
                    }
                ]
            },
            {
                "id": "track_caps_primary",
                "type": "captions",
                "name": "Main Subtitles",
                "visible": True,
                "locked": False,
                "clips": [
                    {
                        "id": "cap_1",
                        "type": "captions",
                        "caption_text": "Stop scrolling and check this out",
                        "position": "bottom",
                        "start_seconds": 0.5,
                        "duration_seconds": 2.5,
                        "layer_order": 8,
                        "visible": True,
                        "locked": False,
                    },
                    {
                        "id": "cap_2",
                        "type": "captions",
                        "caption_text": "Here is the exact formula you need",
                        "position": "bottom",
                        "start_seconds": 3.0,
                        "duration_seconds": 3.0,
                        "layer_order": 9,
                        "visible": True,
                        "locked": False,
                    }
                ]
            },
            {
                "id": "track_caps_secondary",
                "type": "captions",
                "name": "Emphasis / Callout Words",
                "visible": True,
                "locked": False,
                "clips": [
                    {
                        "id": "cap_callout_1",
                        "type": "captions",
                        "caption_text": "🔥 300% GROWTH",
                        "position": "top",
                        "start_seconds": 1.5,
                        "duration_seconds": 2.0,
                        "layer_order": 10,
                        "visible": True,
                        "locked": False,
                    }
                ]
            },
            {
                "id": "track_gfx_lower",
                "type": "graphics",
                "name": "Lower Thirds",
                "visible": True,
                "locked": False,
                "clips": [
                    {
                        "id": "elem_lower_third",
                        "type": "block",
                        "block_id": "yt-lower-third",
                        "title": "Creator Name Badge",
                        "start_seconds": 1.0,
                        "duration_seconds": 3.5,
                        "layer_order": 11,
                        "visible": True,
                        "locked": False,
                        "variables": {
                            "name": "ViralMint Studio",
                            "title": "Automated Short Form"
                        },
                        "animations": [
                            {"property": "opacity", "time": 0.0, "value": 0.0, "ease": "power2.out"},
                            {"property": "opacity", "time": 0.5, "value": 1.0, "ease": "none"},
                            {"property": "opacity", "time": 3.0, "value": 1.0, "ease": "none"},
                            {"property": "opacity", "time": 3.5, "value": 0.0, "ease": "power2.in"},
                            {"property": "x", "time": 0.0, "value": -100, "ease": "power2.out"},
                            {"property": "x", "time": 0.5, "value": 0, "ease": "power2.out"},
                        ]
                    }
                ]
            },
            {
                "id": "track_gfx_overlay",
                "type": "graphics",
                "name": "Kinetic Typography",
                "visible": True,
                "locked": False,
                "clips": [
                    {
                        "id": "elem_weight_wave",
                        "type": "block",
                        "block_id": "weight-wave",
                        "title": "Weight Wave Title",
                        "start_seconds": 4.5,
                        "duration_seconds": 4.0,
                        "layer_order": 12,
                        "visible": True,
                        "locked": False,
                        "variables": {
                            "text": "SCALE YOUR AUDIENCE",
                            "color": "#facc15"
                        },
                        "animations": [
                            {"property": "scale", "time": 0.0, "value": 0.8, "ease": "elastic.out"},
                            {"property": "scale", "time": 0.8, "value": 1.2, "ease": "power2.out"},
                            {"property": "scale", "time": 3.5, "value": 1.0, "ease": "none"},
                        ]
                    }
                ]
            },
            {
                "id": "track_gfx_cta",
                "type": "graphics",
                "name": "CTA & End Screen",
                "visible": True,
                "locked": False,
                "clips": [
                    {
                        "id": "elem_tiktok_follow",
                        "type": "block",
                        "block_id": "tiktok-follow",
                        "title": "Follow Button Pop",
                        "start_seconds": 7.0,
                        "duration_seconds": 3.0,
                        "layer_order": 13,
                        "visible": True,
                        "locked": False,
                        "variables": {
                            "username": "@viralmint_app"
                        }
                    }
                ]
            }
        ]

        # Apply update_document to commit the dense multi-track composition
        op_res = await client.post(f"/api/projects/{pid}/operations", json={
            "expected_revision": rev,
            "operation_type": "update_document",
            "payload": {
                "document": {
                    "title": "Audit Multi-Track Dense Project",
                    "aspect_ratio": "9:16",
                    "timeline": {
                        "duration_seconds": 10.0,
                        "fps": 30,
                        "tracks": tracks
                    }
                }
            }
        })
        assert op_res.status_code == 200
        new_rev = op_res.json()["revision"]
        log(f"Committed dense multi-track document at revision {new_rev}")

        # Verify sync studio staging compiles the multi-track composition into HTML
        sync_res = await client.post(f"/api/projects/{pid}/sync-studio", json={"revision": new_rev})
        assert sync_res.status_code == 200
        log(f"Studio sync succeeded: {sync_res.json()}")

        # 3. Launch Playwright to inspect and capture actual UI state
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            # Viewport 1: Desktop 1920x1080
            log("Capturing 1920x1080 desktop layout...")
            page_desktop = await browser.new_page(viewport={"width": 1920, "height": 1080})
            await page_desktop.goto(f"{BASE_URL}/motion?projectId={pid}", wait_until="networkidle")
            await asyncio.sleep(2.0)

            # Ensure Refine mode is active
            refine_btn = page_desktop.locator("button:has-text('Refine')")
            if await refine_btn.count() > 0:
                await refine_btn.first.click()
                await asyncio.sleep(0.5)

            # Screenshot: Full Refine Workspace (1920x1080)
            await page_desktop.screenshot(path=str(AUDIT_DIR / "refine_workspace_1920x1080.png"), full_page=False)
            log("Captured refine_workspace_1920x1080.png")

            # Check Timeline Header label ("Professional Timeline" vs "Timeline")
            header_text_el = page_desktop.locator("text='Professional Timeline'")
            has_prof_label = await header_text_el.count() > 0
            log(f"Header contains 'Professional Timeline': {has_prof_label}")

            # Inspect track headers in UI
            track_headers = await page_desktop.evaluate("""() => {
                const nodes = Array.from(document.querySelectorAll('.MuiTypography-caption'));
                return nodes.map(n => n.textContent).filter(Boolean);
            }""")
            log(f"Visible captions/headers in DOM: {len(track_headers)}")

            # Screenshot: Dense Timeline Section
            timeline_box = page_desktop.locator("[data-testid='studio-timeline-workspace'], .MuiBox-root:has-text('Professional Timeline')").first
            if await timeline_box.count() > 0:
                await timeline_box.screenshot(path=str(AUDIT_DIR / "timeline_multitrack_dense.png"))
                log("Captured timeline_multitrack_dense.png")

            # Expand keyframe lanes on elem_lower_third
            clip_card = page_desktop.locator("[data-clip-id='elem_lower_third']").first
            if await clip_card.count() > 0:
                # Select clip
                await clip_card.click()
                await asyncio.sleep(0.5)

                # Click keyframe diamonds icon to toggle animation lanes
                diamonds_btn = clip_card.locator("button:has([data-tabler-icon='diamonds']), button[aria-label*='Animation'], button[title*='Animation']").first
                if await diamonds_btn.count() == 0:
                    # Find by icon SVG
                    diamonds_btn = clip_card.locator("svg.tabler-icon-diamonds, svg[class*='icon-diamonds']").locator("..").first
                
                if await diamonds_btn.count() > 0:
                    await diamonds_btn.click()
                    await asyncio.sleep(0.5)
                    log("Toggled keyframe property lanes on elem_lower_third")

                # Capture keyframe lanes screenshot
                await page_desktop.screenshot(path=str(AUDIT_DIR / "timeline_keyframe_expanded.png"), full_page=False)
                log("Captured timeline_keyframe_expanded.png")

            # Switch left drawer to "Catalog & Media"
            cat_media_btn = page_desktop.locator("button:has-text('Catalog & Media')").first
            if await cat_media_btn.count() > 0:
                await cat_media_btn.click()
                await asyncio.sleep(0.5)

                # Capture Assets tab
                await page_desktop.screenshot(path=str(AUDIT_DIR / "resource_panel_assets.png"), full_page=False)
                log("Captured resource_panel_assets.png")

                # Click Catalog tab
                cat_tab = page_desktop.locator("button[role='tab']:has-text('Catalog'), div[role='tab']:has-text('Catalog')").first
                if await cat_tab.count() > 0:
                    await cat_tab.click()
                    await asyncio.sleep(1.0)
                    await page_desktop.screenshot(path=str(AUDIT_DIR / "resource_panel_catalog.png"), full_page=False)
                    log("Captured resource_panel_catalog.png")

                # Click Sources tab
                sources_tab = page_desktop.locator("button[role='tab']:has-text('Sources'), div[role='tab']:has-text('Sources')").first
                if await sources_tab.count() > 0:
                    await sources_tab.click()
                    await asyncio.sleep(0.5)
                    await page_desktop.screenshot(path=str(AUDIT_DIR / "resource_panel_sources.png"), full_page=False)
                    log("Captured resource_panel_sources.png")

            # Viewport 2: Laptop 1366x768
            log("Capturing 1366x768 laptop layout...")
            page_laptop = await browser.new_page(viewport={"width": 1366, "height": 768})
            await page_laptop.goto(f"{BASE_URL}/motion?projectId={pid}", wait_until="networkidle")
            await asyncio.sleep(2.0)
            await page_laptop.screenshot(path=str(AUDIT_DIR / "refine_workspace_1366x768.png"), full_page=False)
            log("Captured refine_workspace_1366x768.png")

            # Measure Layout Metrics on 1366x768
            metrics = await page_laptop.evaluate("""() => {
                const previewIframe = document.getElementById('studio-preview-iframe');
                const toolbar = document.querySelector('[data-testid=\"studio-toolbar\"]');
                const timeline = document.querySelector('.MuiBox-root:has(text)');
                const winW = window.innerWidth;
                const winH = window.innerHeight;

                const iframeRect = previewIframe ? previewIframe.getBoundingClientRect() : null;
                const toolbarRect = toolbar ? toolbar.getBoundingClientRect() : null;

                return {
                    window: { width: winW, height: winH },
                    previewStage: iframeRect ? { width: iframeRect.width, height: iframeRect.height, top: iframeRect.top, left: iframeRect.left } : null,
                    toolbar: toolbarRect ? { width: toolbarRect.width, height: toolbarRect.height } : null,
                };
            }""")
            log(f"Laptop layout metrics: {metrics}")

            await browser.close()

        audit_results["project_id"] = pid
        audit_results["revision"] = new_rev
        audit_results["has_professional_timeline_label"] = has_prof_label
        audit_results["tracks_count"] = len(tracks)
        audit_results["laptop_metrics"] = metrics

        out_summary = AUDIT_DIR / "audit_summary.json"
        with open(out_summary, "w") as f:
            json.dump(audit_results, f, indent=2)
        log(f"Audit completed successfully. Results saved to {out_summary}")

if __name__ == "__main__":
    asyncio.run(run_audit())
