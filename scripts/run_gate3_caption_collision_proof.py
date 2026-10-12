"""
Gate 3 Proof:
- Prevent text-on-text collisions between multi-track captions.
- Staged dynamic heights, multiline text wrapping, safe clearance gaps.
- Verifies DOM bounding boxes do not intersect.
"""

import asyncio
import json
from pathlib import Path
import httpx
from playwright.async_api import async_playwright

BASE_URL = "http://127.0.0.1:16888"
OUT_DIR = Path("artifacts/remediation_final/gate3_proofs")
OUT_DIR.mkdir(parents=True, exist_ok=True)

async def run_gate3_proof():
    print("=" * 60)
    print("RUNNING GATE 3 CAPTION COLLISION PREVENTION PROOF")
    print("=" * 60)

    # 1. Create a 9:16 project
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        res = await client.post("/api/projects", json={
            "name": "Gate 3 Caption Collision Proof",
            "aspect_ratio": "9:16"
        })
        p = res.json()
        pid = p["id"]
        rev = p["revision"]
        print(f"[Setup] Created project {pid} at rev {rev}")

        # Add primary caption track with multiline turquoise caption
        res_t1 = await client.post(f"/api/projects/{pid}/operations", json={
            "expected_revision": rev,
            "operation_type": "add_track",
            "payload": {
                "track_id": "track_cap_primary",
                "type": "captions",
                "name": "Primary Subtitles"
            }
        })
        assert res_t1.status_code == 200, f"add_track 1 failed: {res_t1.text}"
        rev = res_t1.json()["revision"]

        res_c1 = await client.post(f"/api/projects/{pid}/operations", json={
            "expected_revision": rev,
            "operation_type": "add_clip",
            "payload": {
                "track_id": "track_cap_primary",
                "clip": {
                    "id": "cap_primary_1",
                    "type": "caption",
                    "caption_text": "THIS IS THE LOWER SUBTITLE ROW\nCONTAINING TWO LINES OF TURQUOISE TEXT",
                    "color": "#00f0ff",
                    "font_size": 48,
                    "position": "bottom",
                    "start_seconds": 0.0,
                    "duration_seconds": 5.0,
                    "layer_order": 10
                }
            }
        })
        assert res_c1.status_code == 200, f"add_clip 1 failed: {res_c1.text}"
        rev = res_c1.json()["revision"]

        # Add secondary caption track with white caption
        res_t2 = await client.post(f"/api/projects/{pid}/operations", json={
            "expected_revision": rev,
            "operation_type": "add_track",
            "payload": {
                "track_id": "track_cap_secondary",
                "type": "captions",
                "name": "Secondary Callout"
            }
        })
        assert res_t2.status_code == 200, f"add_track 2 failed: {res_t2.text}"
        rev = res_t2.json()["revision"]

        res_c2 = await client.post(f"/api/projects/{pid}/operations", json={
            "expected_revision": rev,
            "operation_type": "add_clip",
            "payload": {
                "track_id": "track_cap_secondary",
                "clip": {
                    "id": "cap_secondary_1",
                    "type": "caption",
                    "caption_text": "UPPER WHITE CALLOUT LAYER\nSTACKED DIRECTLY ABOVE WITHOUT INTERSECTING",
                    "color": "#ffffff",
                    "font_size": 44,
                    "position": "bottom",
                    "start_seconds": 0.0,
                    "duration_seconds": 5.0,
                    "layer_order": 11
                }
            }
        })
        rev = res_c2.json()["revision"]
        print(f"[Setup] Both caption tracks configured at rev {rev}")

    # 2. Inspect preview stage in browser
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        await page.goto(f"{BASE_URL}/motion?projectId={pid}", wait_until="networkidle")
        await page.wait_for_timeout(2000)

        outer_frame = await (await page.locator("#studio-preview-iframe").element_handle()).content_frame()
        assert outer_frame is not None, "Outer preview frame must be present"

        # Evaluate bounding boxes and styling of both caption elements
        caption_rects = await outer_frame.evaluate("""() => {
            const el1 = document.getElementById('cap_primary_1');
            const el2 = document.getElementById('cap_secondary_1');
            if (!el1 || !el2) return null;

            const r1 = el1.getBoundingClientRect();
            const r2 = el2.getBoundingClientRect();

            return {
                primary: {
                    id: el1.id,
                    text: el1.innerText,
                    color: el1.style.color,
                    bottom: el1.style.bottom,
                    rect: { top: r1.top, bottom: r1.bottom, left: r1.left, right: r1.right, height: r1.height }
                },
                secondary: {
                    id: el2.id,
                    text: el2.innerText,
                    color: el2.style.color,
                    bottom: el2.style.bottom,
                    rect: { top: r2.top, bottom: r2.bottom, left: r2.left, right: r2.right, height: r2.height }
                }
            };
        }""")
        print("[Gate 3 Caption Rects]:", json.dumps(caption_rects, indent=2))
        assert caption_rects is not None, "Both caption elements must be rendered in DOM"

        r1 = caption_rects["primary"]["rect"]
        r2 = caption_rects["secondary"]["rect"]

        # Secondary (upper) must be positioned strictly ABOVE primary (lower)
        # In screen coords: top=0 is highest, so secondary.bottom must be <= primary.top (with clear separation)
        vertical_clearance = r1["top"] - r2["bottom"]
        print(f"[Gate 3 Clearance] Primary Top: {r1['top']}px, Secondary Bottom: {r2['bottom']}px -> Clearance: {vertical_clearance}px")

        assert vertical_clearance >= 0, f"Captions collide! Clearance is {vertical_clearance}px (negative means overlap)"
        print(f"[Gate 3 PASS] Safe vertical clearance verified: {vertical_clearance}px between tracks!")

        # Screenshot preview stage showing both non-overlapping captions
        snap_path = OUT_DIR / "captions_stacked_no_collision.png"
        await page.locator("#studio-preview-iframe").screenshot(path=str(snap_path))
        print(f"[Evidence] Saved snapshot: {snap_path}")

        # Save manifest
        (OUT_DIR / "gate3_manifest.json").write_text(json.dumps({
            "project_id": pid,
            "primary": caption_rects["primary"],
            "secondary": caption_rects["secondary"],
            "vertical_clearance_px": vertical_clearance,
            "collision_detected": False
        }, indent=2), encoding="utf-8")

        await browser.close()
        print("[Gate 3 SUCCESS] All caption collision assertions passed!")

if __name__ == "__main__":
    asyncio.run(run_gate3_proof())
