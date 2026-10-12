"""
Gate 1 & Gate 2 Proof:
- Live Motion Preview animation verification (both Play and Seek)
- Responsive 9:16 Typography & Placement reflow verification
- User-adjustable positioning & scale contract
"""

import asyncio
import json
import os
from pathlib import Path
import httpx
from playwright.async_api import async_playwright

BASE_URL = "http://127.0.0.1:16888"
OUT_DIR = Path("artifacts/remediation_final/gate1_gate2_proofs")
OUT_DIR.mkdir(parents=True, exist_ok=True)

async def run_gate1_gate2_proof():
    print("=" * 60)
    print("RUNNING GATE 1 & GATE 2 PREVIEW ANIMATION & RESPONSIVE PROOF")
    print("=" * 60)

    # 1. Create 9:16 project
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        res = await client.post("/api/projects", json={
            "name": "Gate 1 & 2 Acceptance Project",
            "aspect_ratio": "9:16"
        })
        p = res.json()
        pid = p["id"]
        rev = p["revision"]
        print(f"[Setup] Created project {pid} at rev {rev}")

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
        assert res_b.status_code == 200, f"add_block failed: {res_b.text}"
        doc = res_b.json()["document"]
        all_clips = [c for tr in doc["timeline"]["tracks"] for c in tr["clips"]]
        block_clip = next(c for c in all_clips if c.get("block_id"))
        cid = block_clip["id"]
        rev = res_b.json()["revision"]
        print(f"[Setup] Added weight-wave block clip {cid} at rev {rev}")

    # 2. Launch browser
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})

        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))

        await page.goto(f"{BASE_URL}/motion?projectId={pid}", wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # Outer preview iframe
        outer_frame_loc = page.locator("#studio-preview-iframe")
        await outer_frame_loc.wait_for(state="attached", timeout=5000)
        outer_frame = await (await outer_frame_loc.element_handle()).content_frame()
        assert outer_frame is not None, "Outer preview frame must be loaded"

        # Inner subcomp iframe
        inner_frame_loc = outer_frame.locator("iframe.subcomp-frame")
        await inner_frame_loc.wait_for(state="attached", timeout=5000)
        inner_frame = await (await inner_frame_loc.element_handle()).content_frame()
        assert inner_frame is not None, "Inner subcomp frame must be loaded"

        # Check initial t=0 state
        init_metrics = await inner_frame.evaluate("""() => {
            const spans = Array.from(document.querySelectorAll('.ww-ch'));
            const line = document.getElementById('ww-line');
            const root = document.getElementById('ww-root');
            const stage = document.getElementById('ww-stage');
            return {
                charCount: spans.length,
                rootW: root?.offsetWidth,
                rootH: root?.offsetHeight,
                lineW: line?.offsetWidth,
                lineH: line?.offsetHeight,
                fontSize: window.getComputedStyle(line).fontSize,
                whiteSpace: window.getComputedStyle(line).whiteSpace,
                stageTransform: stage?.style.transform,
                spansInitialFvs: spans.slice(0, 5).map(s => ({ char: s.textContent, fvs: s.style.fontVariationSettings }))
            };
        }""")
        print("[Gate 2 Reflow] Initial metrics:", json.dumps(init_metrics, indent=2))

        # Gate 2 Assertions: Responsive 9:16 reflow
        assert init_metrics["charCount"] > 0, "Characters must be rendered"
        assert init_metrics["lineW"] <= 920, f"Line width {init_metrics['lineW']} must fit vertical max 920px"
        assert "pre-wrap" in init_metrics["whiteSpace"], f"whiteSpace must be pre-wrap, got {init_metrics['whiteSpace']}"
        assert init_metrics["lineH"] > 100, f"Line must wrap across multiple lines (height {init_metrics['lineH']}px > 100px)"
        assert "-160px" in init_metrics["stageTransform"], f"Stage must be elevated to upper-hero area (-160px): {init_metrics['stageTransform']}"
        print("[Gate 2 PASS] Responsive 9:16 typography wrapped cleanly into upper-hero area!")

        # Gate 1: Test Seek across timestamps
        seek_results = {}
        for t in [0.5, 1.0, 1.5, 2.5]:
            print(f"[Gate 1 Seek] Seeking to t={t}s via postMessage...")
            await outer_frame.evaluate(f"""() => {{
                window.postMessage({{ source: 'vm-parent', action: 'seek', time: {t} }}, '*');
            }}""")
            await page.wait_for_timeout(350)

            active = await inner_frame.evaluate("""() => {
                return Array.from(document.querySelectorAll('.ww-ch')).map(s => ({
                    char: s.textContent,
                    fvs: s.style.fontVariationSettings
                })).filter(x => x.fvs && !x.fvs.includes('400'));
            }""")
            print(f"[Gate 1 Seek t={t}s] Active animated glyphs: {len(active)}", active[:3])
            assert len(active) > 0, f"At t={t}s, variable font axes must be actively deformed (non-400)"
            seek_results[f"t_{t}"] = active

            # Screenshot preview stage
            snap_path = OUT_DIR / f"preview_seek_{t}s.png"
            await page.locator("#studio-preview-iframe").screenshot(path=str(snap_path))
            print(f"[Evidence] Saved seek snapshot: {snap_path}")

        # Gate 1: Test Playback
        print("[Gate 1 Play] Triggering playback...")
        await outer_frame.evaluate("""() => {
            window.postMessage({ source: 'vm-parent', action: 'play' }, '*');
        }""")
        await page.wait_for_timeout(800)

        playing_active = await inner_frame.evaluate("""() => {
            return Array.from(document.querySelectorAll('.ww-ch')).map(s => ({
                char: s.textContent,
                fvs: s.style.fontVariationSettings
            })).filter(x => x.fvs && !x.fvs.includes('400'));
        }""")
        print(f"[Gate 1 Play] Active animated glyphs during live play: {len(playing_active)}", playing_active[:3])
        assert len(playing_active) > 0, "During live play, variable font axes must be actively animating"

        play_snap_path = OUT_DIR / "preview_live_playback.png"
        await page.locator("#studio-preview-iframe").screenshot(path=str(play_snap_path))
        print(f"[Evidence] Saved live playback snapshot: {play_snap_path}")

        # Pause playback
        await outer_frame.evaluate("""() => {
            window.postMessage({ source: 'vm-parent', action: 'pause' }, '*');
        }""")
        await page.wait_for_timeout(300)

        # Gate 2: Test User-adjustable positioning & scale
        print("[Gate 2 Positioning] Updating clip with custom offset_y and scale...")
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
            res_upd = await client.post(f"/api/projects/{pid}/operations", json={
                "expected_revision": rev,
                "operation_type": "update_clip",
                "payload": {
                    "clip_id": cid,
                    "offset_y": -40,
                    "scale": 1.15
                }
            })
            assert res_upd.status_code == 200, f"update_clip failed: {res_upd.text}"

        # Reload preview
        await page.goto(f"{BASE_URL}/motion?projectId={pid}", wait_until="networkidle")
        await page.wait_for_timeout(2000)

        outer_frame2 = await (await page.locator("#studio-preview-iframe").element_handle()).content_frame()
        comp_block_style = await outer_frame2.evaluate(f"""() => {{
            const el = document.getElementById('{cid}');
            return el ? el.style.transform : null;
        }}""")
        print(f"[Gate 2 Positioning] Component block transform: {comp_block_style}")
        assert "translate" in comp_block_style and "scale(1.15)" in comp_block_style, \
            f"Expected translate and scale in component transform, got {comp_block_style}"
        print("[Gate 2 PASS] User-adjustable positioning and scale verified in preview stage!")

        # Save results manifest
        manifest = {
            "project_id": pid,
            "clip_id": cid,
            "reflow_metrics": init_metrics,
            "seeks_tested": [0.5, 1.0, 1.5, 2.5],
            "play_verified": True,
            "positioning_and_scale_verified": True,
            "console_logs_count": len(console_logs)
        }
        (OUT_DIR / "gate1_gate2_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print("[Gate 1 & Gate 2 SUCCESS] All assertions passed!")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_gate1_gate2_proof())
