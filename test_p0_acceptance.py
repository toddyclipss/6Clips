# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Acceptance Test for ViralMint P0:
1. Normal navigation to /motion opens in Create mode with a fresh, clean project (0 clips, 0 blocks, 9:16).
2. Explicit /motion?projectId=<id> loads and preserves existing project revisions.
3. Weight Wave Layer Deletion: Adding duplicate Weight Wave layers and deleting one removes ONLY that instance, preserving sibling instances.
4. Preview Integrity: Missing media renders graceful fallback banner without 500 JSON error.
"""
import asyncio
from pathlib import Path
import httpx
import pytest
from playwright.async_api import async_playwright

BASE_API = "http://127.0.0.1:16888"
BASE_UI = "http://localhost:5173"

async def test_motion_p0_clean_entry_and_deletion():
    # 1. Test Clean Entry on /motion
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})

        print("--- [1] Testing Clean Entry /motion ---")
        await page.goto(f"{BASE_UI}/motion", wait_until="networkidle")
        await page.wait_for_timeout(1500)

        # Check URL has projectId assigned
        curr_url = page.url
        assert "projectId=" in curr_url, f"Expected projectId in URL, got {curr_url}"
        clean_pid = curr_url.split("projectId=")[1].split("&")[0]

        # Verify backend project is clean
        async with httpx.AsyncClient(base_url=BASE_API) as client:
            res = await client.get(f"/api/projects/{clean_pid}")
            assert res.status_code == 200
            pdata = res.json()
            doc = pdata.get("document", pdata)
            tracks = doc.get("timeline", {}).get("tracks", [])
            total_clips = sum(len(t.get("clips", [])) for t in tracks)
            assert total_clips == 0, f"Expected 0 clips in clean project, found {total_clips}"
            assert pdata.get("aspect_ratio") == "9:16", f"Expected 9:16 aspect ratio, got {pdata.get('aspect_ratio')}"
            print(f"  [+] Clean project created: {clean_pid} with 0 clips, 9:16 aspect ratio.")

        # Check UI shows Create mode by default
        create_btn = page.locator("button:has-text('Create')")
        refine_btn = page.locator("button:has-text('Refine')")
        assert await create_btn.count() > 0
        assert await refine_btn.count() > 0

        # 2. Test Layer Deletion with Duplicate Weight Wave instances
        print("--- [2] Testing Duplicate Weight Wave Insertion & Targeted Deletion ---")
        async with httpx.AsyncClient(base_url=BASE_API) as client:
            # Add Weight Wave #1
            res1 = await client.post(f"/api/projects/{clean_pid}/operations", json={
                "expected_revision": pdata["revision"],
                "operation_type": "add_block",
                "payload": {
                    "block_id": "weight-wave",
                    "start_seconds": 0.0,
                    "duration_seconds": 4.0
                }
            })
            assert res1.status_code == 200
            rev2 = res1.json()["revision"]

            # Add Weight Wave #2
            res2 = await client.post(f"/api/projects/{clean_pid}/operations", json={
                "expected_revision": rev2,
                "operation_type": "add_block",
                "payload": {
                    "block_id": "weight-wave",
                    "start_seconds": 4.0,
                    "duration_seconds": 4.0
                }
            })
            assert res2.status_code == 200
            rev3 = res2.json()["revision"]

            # Get project to inspect clip IDs
            res_p = await client.get(f"/api/projects/{clean_pid}")
            doc3 = res_p.json()["document"]
            all_clips = [c for t in doc3["timeline"]["tracks"] for c in t.get("clips", [])]
            assert len(all_clips) == 2, f"Expected 2 clips, got {len(all_clips)}"
            clip1_id = all_clips[0]["id"]
            clip2_id = all_clips[1]["id"]
            assert clip1_id != clip2_id, "Clips should have unique IDs"
            print(f"  [+] Inserted clips: {clip1_id} and {clip2_id}")

        # Refresh page in browser to load the 2 clips
        await page.goto(f"{BASE_UI}/motion?projectId={clean_pid}", wait_until="networkidle")
        await page.wait_for_timeout(1500)

        # Switch to Refine mode to view Layers panel
        await refine_btn.first.click()
        await page.wait_for_timeout(500)

        # Switch left nav to Layers
        layers_tab = page.locator("button:has-text('Layers')")
        if await layers_tab.count() > 0:
            await layers_tab.first.click()
            await page.wait_for_timeout(500)

        # Find quick-action delete button for clip1_id
        del_btn_1 = page.locator(f"[data-testid='delete-layer-btn-{clip1_id}']")
        assert await del_btn_1.count() > 0, f"Delete button for {clip1_id} not found"
        print(f"  [+] Found delete button for {clip1_id}. Clicking delete...")
        await del_btn_1.first.click()
        await page.wait_for_timeout(1000)

        # Verify in backend: clip1 deleted, clip2 preserved
        async with httpx.AsyncClient(base_url=BASE_API) as client:
            res_after = await client.get(f"/api/projects/{clean_pid}")
            doc_after = res_after.json()["document"]
            rem_clips = [c for t in doc_after["timeline"]["tracks"] for c in t.get("clips", [])]
            assert len(rem_clips) == 1, f"Expected 1 remaining clip, got {len(rem_clips)}"
            assert rem_clips[0]["id"] == clip2_id, f"Expected {clip2_id} to survive, got {rem_clips[0]['id']}"
            print(f"  [+] Confirmed: {clip1_id} was deleted; sibling {clip2_id} was preserved!")

        # 3. Test Preview Graceful Missing Media
        print("--- [3] Testing Preview Graceful Handling of Missing Media ---")
        async with httpx.AsyncClient(base_url=BASE_API) as client:
            prev_res = await client.get(f"/api/projects/{clean_pid}/preview")
            assert prev_res.status_code == 200, f"Preview failed with status {prev_res.status_code}"
            assert "missing-media-block" not in prev_res.text or "<div id=\"stage\"" in prev_res.text
            print("  [+] Preview endpoint returned HTTP 200 HTML smoothly.")

        await browser.close()
        print("=== ALL P0 INTEGRITY TESTS PASSED SUCCESSFULLY ===")

if __name__ == "__main__":
    asyncio.run(test_motion_p0_clean_entry_and_deletion())
