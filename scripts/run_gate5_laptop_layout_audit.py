"""
Gate 5 Acceptance Script:
- Refine Workspace Responsive Layout Audit at 1366x768, 1440x900, 1920x1080.
- Measures preview stage canvas dimensions, container ratios, and unclipped toolbar controls.
- Confirms "Timeline" header naming and responsive panel behavior.
- Captures full-page screenshots as product-owner visual evidence.
"""

import asyncio
import json
from pathlib import Path
import httpx
from playwright.async_api import async_playwright

BASE_URL = "http://127.0.0.1:16888"
OUT_DIR = Path("artifacts/remediation_final/gate5_proofs")
OUT_DIR.mkdir(parents=True, exist_ok=True)

VIEWPORTS = [
    {"name": "1366x768_laptop", "width": 1366, "height": 768},
    {"name": "1440x900_macbook", "width": 1440, "height": 900},
    {"name": "1920x1080_desktop", "width": 1920, "height": 1080},
]

async def run_gate5_audit():
    print("=" * 60)
    print("STARTING GATE 5: RESPONSIVE LAPTOP LAYOUT & REFINE UX AUDIT")
    print("=" * 60)

    # 1. Create a project with rich timeline tracks
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        res = await client.post("/api/projects", json={
            "name": "Gate 5 Layout Audit Project",
            "aspect_ratio": "9:16"
        })
        p = res.json()
        pid = p["id"]
        rev = p["revision"]
        print(f"[Setup] Created project {pid} at rev {rev}")

        # Add block
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
        rev = res_b.json()["revision"]

        # Add BGM track
        res_t = await client.post(f"/api/projects/{pid}/operations", json={
            "expected_revision": rev,
            "operation_type": "add_track",
            "payload": {"type": "audio", "name": "BGM Music"}
        })
        rev = res_t.json()["revision"]

    manifest_data = {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)

        for vp in VIEWPORTS:
            v_name = vp["name"]
            w = vp["width"]
            h = vp["height"]
            print(f"\n[Audit Viewport] Testing {v_name} ({w}x{h})...")

            page = await browser.new_page(viewport={"width": w, "height": h})
            await page.goto(f"{BASE_URL}/motion?projectId={pid}", wait_until="networkidle")
            await page.wait_for_timeout(2000)

            # 1. Audit Toolbar Controls
            toolbar_info = await page.evaluate("""() => {
                const tb = document.querySelector('[data-testid=\"studio-toolbar\"]');
                if (!tb) return null;
                const rect = tb.getBoundingClientRect();
                const saveBtn = Array.from(tb.querySelectorAll('button')).find(b => b.innerText.includes('Save'));
                const exportBtn = Array.from(tb.querySelectorAll('button')).find(b => b.innerText.includes('Export'));
                return {
                    width: rect.width,
                    height: rect.height,
                    saveVisible: !!saveBtn && saveBtn.offsetWidth > 0,
                    exportVisible: !!exportBtn && exportBtn.offsetWidth > 0,
                    exportText: exportBtn ? exportBtn.innerText.trim() : null
                };
            }""")
            print(f"[{v_name}] Toolbar:", json.dumps(toolbar_info))
            assert toolbar_info["saveVisible"], f"Save button must be visible at {v_name}"
            assert toolbar_info["exportVisible"], f"Export button must be visible at {v_name}"

            # 2. Audit Timeline Workspace & Header
            timeline_info = await page.evaluate("""() => {
                const tl = document.querySelector('[data-testid=\"studio-timeline-workspace\"]');
                if (!tl) return null;
                const rect = tl.getBoundingClientRect();
                const titleEl = tl.querySelector('span, p');
                const tracks = tl.querySelectorAll('[data-track-id]');
                return {
                    width: rect.width,
                    height: rect.height,
                    headerText: titleEl ? titleEl.innerText.trim() : null,
                    renderedTracksCount: tracks.length
                };
            }""")
            print(f"[{v_name}] Timeline Workspace:", json.dumps(timeline_info))
            assert timeline_info is not None, f"Timeline workspace must be present at {v_name}"
            assert timeline_info["height"] >= 180, f"Timeline workspace height {timeline_info['height']}px must be >= 180px"
            assert "Timeline" in timeline_info["headerText"], f"Timeline header must read 'Timeline', got {timeline_info['headerText']}"

            # 3. Audit Preview Stage and Canvas Box
            stage_info = await page.evaluate("""() => {
                const stage = document.querySelector('[data-testid=\"studio-preview-stage\"]');
                const iframe = document.getElementById('studio-preview-iframe');
                if (!stage || !iframe) return null;
                const sRect = stage.getBoundingClientRect();
                const iRect = iframe.getBoundingClientRect();
                return {
                    containerWidth: sRect.width,
                    containerHeight: sRect.height,
                    canvasWidth: iRect.width,
                    canvasHeight: iRect.height,
                    canvasAspectRatio: (iRect.width / iRect.height).toFixed(3)
                };
            }""")
            print(f"[{v_name}] Preview Stage:", json.dumps(stage_info))
            assert stage_info is not None, f"Preview stage must be present at {v_name}"
            assert stage_info["canvasWidth"] >= 150, f"Canvas width {stage_info['canvasWidth']} must not be squished (<150px)"
            assert stage_info["canvasHeight"] >= 280, f"Canvas height {stage_info['canvasHeight']} must not be squished (<280px)"
            expected_aspect = 9 / 16
            actual_aspect = float(stage_info["canvasAspectRatio"])
            assert abs(actual_aspect - expected_aspect) < 0.05, f"Canvas aspect {actual_aspect} must match 9:16 (~0.563)"

            # Capture full-page screenshot
            shot_path = OUT_DIR / f"motion_refine_layout_{v_name}.png"
            await page.screenshot(path=str(shot_path), full_page=True)
            print(f"[{v_name}] Screenshot saved: {shot_path.name}")

            manifest_data[v_name] = {
                "viewport": {"width": w, "height": h},
                "toolbar": toolbar_info,
                "timeline": timeline_info,
                "stage": stage_info,
                "screenshot": str(shot_path.name)
            }

            await page.close()

        await browser.close()

    # Save manifest
    manifest_file = OUT_DIR / "gate5_manifest.json"
    manifest_file.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
    print("\n[Gate 5 SUCCESS] Responsive Laptop Layout & Refine UX Audit passed for all viewports!")

if __name__ == "__main__":
    asyncio.run(run_gate5_audit())
