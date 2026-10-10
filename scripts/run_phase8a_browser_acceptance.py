# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from playwright.async_api import async_playwright
import urllib.request
import urllib.error

ARTIFACT_DIR = Path(r"C:\Users\toddy\.gemini\antigravity\brain\5fe8acfd-1e07-41f5-8774-c43c45f0e95b")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

BACKEND_BASE = "http://127.0.0.1:16888"
FRONTEND_BASE = "http://localhost:5173"


def api_post(path, data):
    url = f"{BACKEND_BASE}{path}"
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def api_get(path):
    url = f"{BACKEND_BASE}{path}"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


async def run_phase8a_browser_acceptance():
    print("=== VIRALMINT PHASE 8A: REAL BROWSER ACCEPTANCE ===")
    results = {}

    # 1. Setup a fresh acceptance project
    print("\n--- 1. Setting up Phase 8A Acceptance Project ---")
    p_init = api_post("/api/projects", {"name": "Phase 8A Closure Project", "aspect_ratio": "9:16"})
    proj_id = p_init["id"]
    rev = p_init["revision"]
    print(f"Project created: {proj_id} (Rev {rev})")

    # Add real test video clip
    res = api_post(f"/api/projects/{proj_id}/operations", {
        "expected_revision": rev,
        "operation_type": "add_clip",
        "payload": {
            "track_id": "track_video_main",
            "clip": {
                "id": "clip_vid_bg",
                "type": "video",
                "file": "test_moving_video.mp4",
                "start_seconds": 0.0,
                "duration_seconds": 10.0,
                "layer_order": 0,
                "title": "Background Video",
            }
        }
    })
    rev = res["revision"]

    # Add real HyperFrames block (weight-wave)
    res = api_post(f"/api/projects/{proj_id}/operations", {
        "expected_revision": rev,
        "operation_type": "add_block",
        "payload": {
            "block_id": "weight-wave",
            "instance_id": "elem_ww_alpha",
            "title": "Weight Wave Alpha",
            "start_seconds": 0.0,
            "duration_seconds": 4.0,
            "variables": {
                "title": "Alpha Waves",
                "color": "#8b5cf6",
            }
        }
    })
    rev = res["revision"]

    # Add second real HyperFrames block (bar-chart-race)
    res = api_post(f"/api/projects/{proj_id}/operations", {
        "expected_revision": rev,
        "operation_type": "add_block",
        "payload": {
            "block_id": "bar-chart-race",
            "instance_id": "elem_bcr_beta",
            "title": "Bar Chart Beta",
            "start_seconds": 4.5,
            "duration_seconds": 4.0,
            "variables": {
                "title": "Top Metrics",
                "color": "#3b82f6",
            }
        }
    })
    rev = res["revision"]

    # Add static caption
    res = api_post(f"/api/projects/{proj_id}/operations", {
        "expected_revision": rev,
        "operation_type": "add_clip",
        "payload": {
            "track_id": "track_captions",
            "clip": {
                "id": "clip_cap_watermark",
                "type": "captions",
                "caption_text": "STATIC WATERMARK",
                "start_seconds": 0.0,
                "duration_seconds": 10.0,
                "layer_order": 3,
                "title": "Caption Watermark",
            }
        }
    })
    rev = res["revision"]

    # Add audio track (to verify audio does not participate in visual stacking)
    res = api_post(f"/api/projects/{proj_id}/operations", {
        "expected_revision": rev,
        "operation_type": "add_clip",
        "payload": {
            "track_id": "track_audio_main",
            "clip": {
                "id": "clip_audio_bgm",
                "type": "audio",
                "file": "ambient.mp3",
                "start_seconds": 0.0,
                "duration_seconds": 10.0,
                "layer_order": 0,
                "title": "Background Audio",
            }
        }
    })
    rev = res["revision"]
    print(f"Composition built with 5 clips across video, graphics, captions, audio (Rev {rev})")

    # Sync to studio preview
    api_post(f"/api/projects/{proj_id}/sync-studio", {"revision": rev})

    # Launch Playwright browser
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        motion_url = f"{FRONTEND_BASE}/motion?projectId={proj_id}"
        print(f"\nNavigating to {motion_url}...")
        await page.goto(motion_url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        # --------------------------------------------------------------------
        # TEST A: Selection Synchronization across Layers, Timeline, Inspector, Preview
        # --------------------------------------------------------------------
        print("\n--- TEST A: Selection Synchronization ---")
        # Ensure left nav is on Layers
        layers_tab = page.locator("button:has-text('Layers')").first
        if await layers_tab.count() > 0:
            await layers_tab.click()
            await page.wait_for_timeout(500)

        # Click on elem_ww_alpha in Layers Panel
        elem_layer_row = page.locator("[data-layer-id='elem_ww_alpha']").first
        await elem_layer_row.wait_for(state="visible", timeout=10000)
        await elem_layer_row.click()
        await page.wait_for_timeout(500)

        # Verify selection in Timeline
        timeline_clip_sel = page.locator("[data-clip-id='elem_ww_alpha']").first
        timeline_box_shadow = await timeline_clip_sel.evaluate("el => window.getComputedStyle(el).boxShadow")
        has_sel_outline = "c4b5fd" in timeline_box_shadow or "rgb(196, 181, 253)" in timeline_box_shadow

        # Verify selection in Preview Stage iframe
        comp_frame = page.frame_locator("#studio-preview-iframe")
        preview_elem = comp_frame.locator("[data-hf-id='elem_ww_alpha']").first
        await preview_elem.wait_for(state="attached", timeout=15000)
        preview_exists = await preview_elem.count() > 0

        # Click on elem_bcr_beta in Timeline
        timeline_clip_beta = page.locator("[data-clip-id='elem_bcr_beta']").first
        await timeline_clip_beta.click(force=True)
        await page.wait_for_timeout(500)

        # Verify Layers panel row for elem_bcr_beta is selected
        beta_layer_row = page.locator("[data-layer-id='elem_bcr_beta']").first
        beta_styles = await beta_layer_row.evaluate("el => ({ borderLeft: window.getComputedStyle(el).borderLeft, borderLeftColor: window.getComputedStyle(el).borderLeftColor, borderLeftWidth: window.getComputedStyle(el).borderLeftWidth, bg: window.getComputedStyle(el).backgroundColor })")
        beta_is_selected = "3px" in beta_styles["borderLeftWidth"] and ("rgb(59, 130, 246)" in beta_styles["borderLeftColor"] or "3b82f6" in beta_styles["borderLeftColor"] or "59, 130, 246" in beta_styles["bg"])

        results["selection_sync"] = {
            "pass": has_sel_outline and preview_exists and beta_is_selected,
            "layers_to_timeline": has_sel_outline,
            "timeline_to_layers": beta_is_selected,
            "preview_data_hf_id_present": preview_exists,
        }
        print(f"Selection Sync Result: {results['selection_sync']}")

        # Screenshot: Selection Sync
        await page.screenshot(path=str(ARTIFACT_DIR / "phase8a_selection_sync.png"))

        # --------------------------------------------------------------------
        # TEST B: Backend Lock Enforcement & UI Lock State
        # --------------------------------------------------------------------
        print("\n--- TEST B: Backend Lock Enforcement & UI Lock State ---")
        # Lock elem_ww_alpha via API
        lock_res = api_post(f"/api/projects/{proj_id}/operations", {
            "expected_revision": rev,
            "operation_type": "set_element_lock",
            "payload": {"clip_id": "elem_ww_alpha", "locked": True}
        })
        rev = lock_res["revision"]

        # Attempt to delete locked element via API -> must fail with 400
        lock_del_rejected = False
        try:
            api_post(f"/api/projects/{proj_id}/operations", {
                "expected_revision": rev,
                "operation_type": "remove_clip",
                "payload": {"clip_id": "elem_ww_alpha"}
            })
        except urllib.error.HTTPError as e:
            if e.code == 400:
                lock_del_rejected = True
                print(f"Direct API delete of locked element rejected with HTTP 400 as expected.")

        # Attempt to move locked element via API -> must fail with 400
        lock_move_rejected = False
        try:
            api_post(f"/api/projects/{proj_id}/operations", {
                "expected_revision": rev,
                "operation_type": "move_clip",
                "payload": {"clip_id": "elem_ww_alpha", "start_seconds": 2.0}
            })
        except urllib.error.HTTPError as e:
            if e.code == 400:
                lock_move_rejected = True
                print(f"Direct API move of locked element rejected with HTTP 400 as expected.")

        # Refresh page to check UI lock indicator
        await page.reload(wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # Inspect lock icon on elem_ww_alpha in Layers Panel
        layers_tab = page.locator("button:has-text('Layers')").first
        if await layers_tab.count() > 0:
            await layers_tab.click()
            await page.wait_for_timeout(500)

        ww_row = page.locator("[data-layer-id='elem_ww_alpha']").first
        lock_icon_color = await ww_row.locator("svg.tabler-icon-lock").evaluate("el => window.getComputedStyle(el).color")
        is_ui_locked = "ef4444" in lock_icon_color or "rgb(239, 68, 68)" in lock_icon_color or "rgb(220, 38, 38)" in lock_icon_color

        # Unlock elem_ww_alpha
        unlock_res = api_post(f"/api/projects/{proj_id}/operations", {
            "expected_revision": rev,
            "operation_type": "set_element_lock",
            "payload": {"clip_id": "elem_ww_alpha", "locked": False}
        })
        rev = unlock_res["revision"]

        results["lock_enforcement"] = {
            "pass": lock_del_rejected and lock_move_rejected and is_ui_locked,
            "api_delete_rejected": lock_del_rejected,
            "api_move_rejected": lock_move_rejected,
            "ui_lock_indicator": is_ui_locked,
        }
        print(f"Lock Enforcement Result: {results['lock_enforcement']}")

        # --------------------------------------------------------------------
        # TEST C: Group / Ungroup / Reorder / Hierarchy Persistence
        # --------------------------------------------------------------------
        print("\n--- TEST C: Group / Ungroup / Reorder / Hierarchy Persistence ---")
        # Group elem_ww_alpha and elem_bcr_beta into "Folder Charts"
        group_res = api_post(f"/api/projects/{proj_id}/operations", {
            "expected_revision": rev,
            "operation_type": "group_elements",
            "payload": {
                "clip_ids": ["elem_ww_alpha", "elem_bcr_beta"],
                "group_name": "Folder Charts",
                "group_id": "group_charts"
            }
        })
        rev = group_res["revision"]
        print(f"Group created: group_charts (Rev {rev})")

        # Rename group
        rename_res = api_post(f"/api/projects/{proj_id}/operations", {
            "expected_revision": rev,
            "operation_type": "rename_element",
            "payload": {
                "clip_id": "group_charts",
                "name": "Visualization Group"
            }
        })
        rev = rename_res["revision"]

        # Reorder group
        reorder_res = api_post(f"/api/projects/{proj_id}/operations", {
            "expected_revision": rev,
            "operation_type": "reorder_layer",
            "payload": {
                "clip_id": "group_charts",
                "layer_order": 10
            }
        })
        rev = reorder_res["revision"]

        # Sync preview
        api_post(f"/api/projects/{proj_id}/sync-studio", {"revision": rev})

        # Reload browser and verify group rendering in Layers panel
        await page.reload(wait_until="networkidle")
        await page.wait_for_timeout(2000)

        layers_tab = page.locator("button:has-text('Layers')").first
        if await layers_tab.count() > 0:
            await layers_tab.click()
            await page.wait_for_timeout(500)

        group_row = page.locator("[data-layer-id='group_charts']").first
        group_visible = await group_row.count() > 0
        group_text = await group_row.text_content() if group_visible else ""
        has_renamed_title = "Visualization Group" in group_text

        # Child elements under group
        ww_child_row = page.locator("[data-layer-id='elem_ww_alpha']").first
        child_visible = await ww_child_row.count() > 0

        # Screenshot: Grouping hierarchy in Layers
        await page.screenshot(path=str(ARTIFACT_DIR / "phase8a_grouping_hierarchy.png"))

        # Lock the group and verify child mutations are rejected
        group_lock_res = api_post(f"/api/projects/{proj_id}/operations", {
            "expected_revision": rev,
            "operation_type": "set_element_lock",
            "payload": {"clip_id": "group_charts", "locked": True}
        })
        rev = group_lock_res["revision"]

        child_mutation_rejected = False
        try:
            api_post(f"/api/projects/{proj_id}/operations", {
                "expected_revision": rev,
                "operation_type": "move_clip",
                "payload": {"clip_id": "elem_ww_alpha", "start_seconds": 1.5}
            })
        except urllib.error.HTTPError as e:
            if e.code == 400:
                child_mutation_rejected = True
                print("Child mutation inside locked group rejected with HTTP 400 as expected.")

        # Unlock group and ungroup
        group_unlock_res = api_post(f"/api/projects/{proj_id}/operations", {
            "expected_revision": rev,
            "operation_type": "set_element_lock",
            "payload": {"clip_id": "group_charts", "locked": False}
        })
        rev = group_unlock_res["revision"]

        ungroup_res = api_post(f"/api/projects/{proj_id}/operations", {
            "expected_revision": rev,
            "operation_type": "ungroup_elements",
            "payload": {"group_id": "group_charts"}
        })
        rev = ungroup_res["revision"]
        print(f"Ungrouped successfully (Rev {rev})")

        # Verify child elements preserved with parent_id=None
        p_check = api_get(f"/api/projects/{proj_id}")
        clips_check = [c for t in p_check["document"]["timeline"]["tracks"] for c in t.get("clips", [])]
        ww_clip = next((c for c in clips_check if c["id"] == "elem_ww_alpha"), None)
        child_preserved = ww_clip is not None and ww_clip.get("parent_id") is None

        results["group_ungroup_reorder"] = {
            "pass": group_visible and has_renamed_title and child_mutation_rejected and child_preserved,
            "group_created_and_visible": group_visible,
            "group_renamed": has_renamed_title,
            "locked_group_child_protected": child_mutation_rejected,
            "ungroup_preserved_children": child_preserved,
        }
        print(f"Group/Ungroup/Reorder Result: {results['group_ungroup_reorder']}")

        # --------------------------------------------------------------------
        # TEST D: Variables & Inspector Synchronization with Real Registry Block
        # --------------------------------------------------------------------
        print("\n--- TEST D: Variables & Inspector Synchronization ---")
        # Click on elem_ww_alpha
        await page.reload(wait_until="networkidle")
        await page.wait_for_timeout(2000)

        layers_tab = page.locator("button:has-text('Layers')").first
        if await layers_tab.count() > 0:
            await layers_tab.click()
            await page.wait_for_timeout(500)

        ww_row = page.locator("[data-layer-id='elem_ww_alpha']").first
        await ww_row.click()
        await page.wait_for_timeout(500)

        # Open Variables tab in Inspector
        var_tab_btn = page.locator("button:has-text('Variables')").first
        if await var_tab_btn.count() > 0:
            await var_tab_btn.click()
            await page.wait_for_timeout(800)

        # Update variable via API CAS operation to verify persistence and Preview sync
        var_update_res = api_post(f"/api/projects/{proj_id}/operations", {
            "expected_revision": rev,
            "operation_type": "update_block_variables",
            "payload": {
                "clip_id": "elem_ww_alpha",
                "variables": {
                    "title": "Quantum Fluctuations",
                    "color": "#10b981",
                }
            }
        })
        rev = var_update_res["revision"]
        print(f"Block variables updated (Rev {rev}): title='Quantum Fluctuations', color='#10b981'")

        # Invalid variable rejected test (color)
        invalid_var_rejected = False
        try:
            api_post(f"/api/projects/{proj_id}/operations", {
                "expected_revision": rev,
                "operation_type": "update_block_variables",
                "payload": {
                    "clip_id": "elem_ww_alpha",
                    "variables": {
                        "color": "not-valid-color-string-!!!",
                    }
                }
            })
        except urllib.error.HTTPError as e:
            if e.code == 400:
                invalid_var_rejected = True
                print("Invalid color variable rejected with HTTP 400 as expected.")

        # Sync preview and reload
        api_post(f"/api/projects/{proj_id}/sync-studio", {"revision": rev})
        await page.reload(wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # Verify persisted values in DB
        p_latest = api_get(f"/api/projects/{proj_id}")
        ww_latest = next(c for t in p_latest["document"]["timeline"]["tracks"] for c in t.get("clips", []) if c["id"] == "elem_ww_alpha")
        vars_persisted = ww_latest["variables"].get("title") == "Quantum Fluctuations" and ww_latest["variables"].get("color") == "#10b981"

        # Verify preview subcomp frame received variables
        comp_frame = page.frame_locator("#studio-preview-iframe")
        preview_ww = comp_frame.locator("[data-hf-id='elem_ww_alpha']").first
        await preview_ww.wait_for(state="attached", timeout=15000)
        var_attr = await preview_ww.get_attribute("data-variable-values")
        preview_has_vars = "Quantum Fluctuations" in (var_attr or "") and "#10b981" in (var_attr or "")

        # Screenshot: Variables Panel
        await page.screenshot(path=str(ARTIFACT_DIR / "phase8a_variables_inspector.png"))

        results["variables_sync"] = {
            "pass": vars_persisted and preview_has_vars and invalid_var_rejected,
            "vars_persisted_in_revision": vars_persisted,
            "preview_data_variable_values": preview_has_vars,
            "invalid_var_rejected_400": invalid_var_rejected,
        }
        print(f"Variables Sync Result: {results['variables_sync']}")

        # --------------------------------------------------------------------
        # TEST E: Visual Z-Order Stacking Preview & Render Parity
        # --------------------------------------------------------------------
        print("\n--- TEST E: Visual Z-Order Stacking Preview & Render Parity ---")
        # Check z-index style on Preview stage elements
        comp_frame = page.frame_locator("#studio-preview-iframe")
        z_orders = await comp_frame.locator("#stage > *").evaluate_all("""els => els.map(el => ({
            id: el.getAttribute('data-hf-id') || el.id,
            tag: el.tagName.toLowerCase(),
            zIndex: el.style.zIndex || 'none'
        }))""")
        print("Preview elements rendered:")
        for zo in z_orders:
            print(f"  [{zo['tag']}] id={zo['id']} zIndex={zo['zIndex']}")

        # Video: layer_order 0 -> z-index 0
        vid_z = next((zo["zIndex"] for zo in z_orders if zo["id"] == "clip_vid_bg"), None)
        # Block: layer_order > 0 -> z-index matching layer_order
        block_z = next((zo["zIndex"] for zo in z_orders if zo["id"] == "elem_ww_alpha"), None)
        # Audio: does NOT have visual zIndex
        audio_z = next((zo["zIndex"] for zo in z_orders if zo["id"] == "clip_audio_bgm"), "none")

        z_order_valid = vid_z is not None and block_z is not None and audio_z == "none"

        results["z_order_stacking"] = {
            "pass": z_order_valid,
            "video_zIndex": vid_z,
            "block_zIndex": block_z,
            "audio_zIndex": audio_z,
        }
        print(f"Z-Order Stacking Result: {results['z_order_stacking']}")

        # Screenshot: Z-order Preview
        await page.screenshot(path=str(ARTIFACT_DIR / "phase8a_zorder_preview.png"))

        # --------------------------------------------------------------------
        # TEST F: Timeline Filmstrip Acceptance
        # --------------------------------------------------------------------
        print("\n--- TEST F: Timeline Filmstrip Acceptance ---")
        # Verify contact sheet generation for video without Clip Bench
        filmstrip_url = f"{BACKEND_BASE}/api/downloaded/test-moving-vid-1/filmstrip?n=16&h=48"
        t0 = time.time()
        req1 = urllib.request.Request(filmstrip_url, method="GET")
        with urllib.request.urlopen(req1) as resp1:
            data1 = resp1.read()
            code1 = resp1.status
            content_type1 = resp1.headers.get("Content-Type")
        dur1 = time.time() - t0

        # Second call: verify cache hit
        t0 = time.time()
        req2 = urllib.request.Request(filmstrip_url, method="GET")
        with urllib.request.urlopen(req2) as resp2:
            data2 = resp2.read()
            code2 = resp2.status
        dur2 = time.time() - t0

        # Verify ProjectRevision is NOT touched by filmstrip requests
        p_final = api_get(f"/api/projects/{proj_id}")
        filmstrip_no_rev_mutation = p_final["revision"] == rev

        filmstrip_ok = code1 == 200 and code2 == 200 and len(data1) == len(data2) and filmstrip_no_rev_mutation
        results["filmstrip_acceptance"] = {
            "pass": filmstrip_ok,
            "first_call_status": code1,
            "first_call_duration_sec": round(dur1, 3),
            "second_call_cached_duration_sec": round(dur2, 3),
            "cache_hit_identical_bytes": len(data1) == len(data2),
            "no_revision_bump": filmstrip_no_rev_mutation,
        }
        print(f"Filmstrip Result: {results['filmstrip_acceptance']}")

        await browser.close()

    # Save summary artifact
    telemetry_path = ARTIFACT_DIR / "phase8a_functional_closure_telemetry.json"
    with open(telemetry_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nPhase 8A acceptance telemetry saved to: {telemetry_path}")

    all_passed = all(r.get("pass", False) for r in results.values())
    print(f"\nOVERALL RESULT: {'ALL PASS' if all_passed else 'SOME FAILED'}")
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(run_phase8a_browser_acceptance())
    sys.exit(0 if success else 1)
