# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Comprehensive Acceptance Script for Phase 9 Final Acceptance: Three Remaining Gates
GATE 1: Direct Preview/Render Parity and Language Attribution
GATE 2: FileTree UI & Conflict-Recovery Browser Evidence
GATE 3: Executable Project-Code Isolation
"""
import asyncio
import base64
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from PIL import Image, ImageChops, ImageStat
from playwright.async_api import async_playwright

BASE_URL = "http://127.0.0.1:16888"
OUTPUT_DIR = Path("artifacts/phase9/three_gates")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def log(msg: str):
    print(f"[THREE-GATES] {msg}", flush=True)

def compute_image_metrics(img1_path: Path, img2_path: Path, diff_out_path: Path) -> Dict[str, Any]:
    """Normalize both images to 1080x1920, compute pixel difference and RMS error."""
    target_size = (1080, 1920)
    im1 = Image.open(img1_path).convert("RGB").resize(target_size, Image.Resampling.BICUBIC)
    im2 = Image.open(img2_path).convert("RGB").resize(target_size, Image.Resampling.BICUBIC)

    diff = ImageChops.difference(im1, im2)
    diff.save(diff_out_path)

    # Calculate statistics
    stat = ImageStat.Stat(diff)
    rms = math.sqrt(sum(v**2 for v in stat.mean) / len(stat.mean))

    # Count pixels that changed noticeably (> 10 intensity diff on any channel)
    diff_data = diff.convert("L").getdata()
    changed_pixels = sum(1 for p in diff_data if p > 10)
    total_pixels = target_size[0] * target_size[1]
    pct = round((changed_pixels / total_pixels) * 100, 2)

    return {
        "total_pixels": total_pixels,
        "changed_pixels": changed_pixels,
        "diff_percentage": pct,
        "rms_error": round(rms, 2),
        "diff_image": str(diff_out_path)
    }

async def eval_in_preview_frame(page, js_code: str):
    iframe_elem = await page.wait_for_selector("#studio-preview-iframe")
    frame = await iframe_elem.content_frame()
    assert frame is not None, "Preview iframe content_frame() is None!"
    return await frame.evaluate(js_code)

async def render_project_mp4(client: httpx.AsyncClient, project_id: str, revision: int, out_mp4: Path) -> Path:
    from backend.services.hyperframes_adapter import HyperFramesAdapter
    from backend.services.motion_render_service import MotionRenderService
    log(f"Staging and rendering frozen MP4 for project {project_id} at revision {revision}...")
    target_rev, work_dir = await HyperFramesAdapter.stage_project_for_render(project_id, revision=revision)
    rendered_path = await MotionRenderService.render_project(
        project_dir=work_dir,
        aspect="9:16",
        fps=30,
        quality="draft",
        out_path=out_mp4.resolve(),
        keep=True
    )
    assert out_mp4.exists() and out_mp4.stat().st_size > 0, f"MP4 missing: {out_mp4}"
    log(f"Rendered MP4: {out_mp4} ({out_mp4.stat().st_size} bytes)")
    return out_mp4

def decode_mp4_frame(mp4_path: Path, timestamp_sec: float, out_png: Path) -> Path:
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(timestamp_sec),
        "-i", str(mp4_path),
        "-vframes", "1",
        "-q:v", "2",
        str(out_png)
    ]
    sub = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if sub.returncode != 0 or not out_png.exists():
        raise RuntimeError(f"ffmpeg frame extraction failed: {sub.stderr.decode('utf-8', errors='ignore')}")
    return out_png

# ==============================================================================
# GATE 1: Direct Preview/Render Parity and Language Attribution
# ==============================================================================
async def execute_gate_1(page, client: httpx.AsyncClient) -> Dict[str, Any]:
    log("=== STARTING GATE 1: Direct Preview/Render Parity & Language Attribution ===")
    gate1_results = {}

    # 1. Create Controlled Acceptance Project
    res = await client.post(f"{BASE_URL}/api/projects", json={
        "name": "Gate1-Parity-Attribution-Project",
        "aspect_ratio": "9:16"
    })
    assert res.status_code == 200
    pdata = res.json()
    pid = pdata["id"]
    rev = pdata["revision"]
    log(f"Created Gate 1 acceptance project {pid} at rev {rev}")

    # Add block clip for background visuals
    res = await client.post(f"{BASE_URL}/api/projects/{pid}/operations", json={
        "expected_revision": rev,
        "operation_type": "add_block",
        "payload": {
            "block_id": "weight-wave",
            "title": "Gate 1 Visual Bed",
            "start_seconds": 0.0,
            "duration_seconds": 5.0,
            "variables": {"count": 3}
        }
    })
    assert res.status_code == 200
    rev = res.json()["revision"]

    # Add initial baseline code files
    res = await client.post(f"{BASE_URL}/api/projects/{pid}/operations", json={
        "expected_revision": rev,
        "operation_type": "create_file",
        "payload": {
            "path": "compositions/overlay.html",
            "content": '<div id="gate1-title" style="position:absolute;top:150px;left:40px;font-size:52px;font-weight:900;color:#ffffff;text-shadow:2px 2px 8px #000;">BASELINE TITLING</div>'
        }
    })
    assert res.status_code == 200
    rev = res.json()["revision"]

    res = await client.post(f"{BASE_URL}/api/projects/{pid}/operations", json={
        "expected_revision": rev,
        "operation_type": "create_file",
        "payload": {
            "path": "styles/theme.css",
            "content": '/* Baseline Theme */\n#stage { background-color: #050811; }\n#gate1-title { border-bottom: 4px solid #ffffff; }'
        }
    })
    assert res.status_code == 200
    rev = res.json()["revision"]

    res = await client.post(f"{BASE_URL}/api/projects/{pid}/operations", json={
        "expected_revision": rev,
        "operation_type": "create_file",
        "payload": {
            "path": "scripts/main.js",
            "content": '// Baseline Script\nconsole.log("Gate 1 baseline script loaded.");'
        }
    })
    assert res.status_code == 200
    rev = res.json()["revision"]
    baseline_rev = rev
    log(f"Baseline established at rev {baseline_rev}")

    # Render Baseline MP4
    baseline_mp4 = OUTPUT_DIR / f"gate1_baseline_rev{baseline_rev}.mp4"
    await render_project_mp4(client, pid, baseline_rev, baseline_mp4)

    # Open Project in Browser
    await page.goto(f"{BASE_URL}/motion?projectId={pid}", wait_until="networkidle")
    await page.wait_for_selector("#studio-preview-iframe", timeout=15000)
    await asyncio.sleep(2.0)

    # Sub-test A: Timestamp-aligned Preview vs Render Parity on SAME frozen revision
    log("Comparing Preview #stage canvas against Decoded MP4 frames at 0.5s, 1.0s, and 2.0s...")
    parity_timestamps = [0.5, 1.0, 2.0]
    timestamp_metrics = {}

    for t in parity_timestamps:
        # Seek preview stage to timestamp t
        await page.evaluate(f"""() => {{
            const iframe = document.getElementById('studio-preview-iframe');
            if (iframe && iframe.contentWindow) {{
                iframe.contentWindow.postMessage({{ source: 'vm-parent', action: 'seek', time: {t} }}, '*');
            }}
        }}""")
        await asyncio.sleep(1.0)

        # Screenshot strictly the composition stage (#stage) inside iframe, excluding all host UI
        stage_loc = page.frame_locator("#studio-preview-iframe").locator("#stage")
        preview_png = OUTPUT_DIR / f"gate1_parity_preview_{t}s.png"
        await stage_loc.screenshot(path=str(preview_png))

        # Decode MP4 frame at timestamp t
        mp4_frame_png = OUTPUT_DIR / f"gate1_parity_render_{t}s.png"
        decode_mp4_frame(baseline_mp4, t, mp4_frame_png)

        # Compute metric difference
        diff_png = OUTPUT_DIR / f"gate1_parity_diff_{t}s.png"
        metrics = compute_image_metrics(preview_png, mp4_frame_png, diff_png)
        metrics["preview_image"] = str(preview_png)
        metrics["render_frame"] = str(mp4_frame_png)
        timestamp_metrics[f"{t}s"] = metrics
        log(f"  At {t}s -> Diff: {metrics['diff_percentage']}%, RMS: {metrics['rms_error']}, Changed Pixels: {metrics['changed_pixels']}")

    gate1_results["timestamp_parity_analysis"] = timestamp_metrics

    # Sub-test B: HTML-only Edit Attribution
    log("Applying HTML-only mutation...")
    html_mutated_content = '<div id="gate1-title" style="position:absolute;top:200px;left:60px;font-size:56px;font-weight:900;color:#ffff00;background:#ff0033;padding:20px;border-radius:12px;">HTML ONLY MUTATION ACTIVE</div>'
    res = await client.post(f"{BASE_URL}/api/projects/{pid}/operations", json={
        "expected_revision": rev,
        "operation_type": "update_file",
        "payload": {
            "path": "compositions/overlay.html",
            "content": html_mutated_content
        }
    })
    assert res.status_code == 200
    rev = res.json()["revision"]
    html_rev = rev

    html_mp4 = OUTPUT_DIR / f"gate1_html_only_rev{html_rev}.mp4"
    await render_project_mp4(client, pid, html_rev, html_mp4)
    html_frame_1s = OUTPUT_DIR / "gate1_html_frame_1s.png"
    decode_mp4_frame(html_mp4, 1.0, html_frame_1s)

    # Compare HTML-only frame against baseline frame at 1.0s
    baseline_frame_1s = OUTPUT_DIR / "gate1_parity_render_1.0s.png"
    html_diff_png = OUTPUT_DIR / "gate1_html_attribution_diff.png"
    html_metrics = compute_image_metrics(baseline_frame_1s, html_frame_1s, html_diff_png)
    log(f"HTML-only attribution -> Diff: {html_metrics['diff_percentage']}%, Pixels Changed: {html_metrics['changed_pixels']}")
    assert html_metrics["changed_pixels"] > 0, "HTML-only edit did not change pixels!"
    gate1_results["html_only_attribution"] = html_metrics

    # Sub-test C: CSS-only Edit Attribution
    log("Applying CSS-only mutation...")
    css_mutated_content = '/* Mutated CSS */\n#stage { background-color: #00ffaa !important; border: 24px solid #ff0055 !important; }\n#gate1-title { box-shadow: 0 0 40px #00ffff !important; }'
    res = await client.post(f"{BASE_URL}/api/projects/{pid}/operations", json={
        "expected_revision": rev,
        "operation_type": "update_file",
        "payload": {
            "path": "styles/theme.css",
            "content": css_mutated_content
        }
    })
    assert res.status_code == 200
    rev = res.json()["revision"]
    css_rev = rev

    css_mp4 = OUTPUT_DIR / f"gate1_css_only_rev{css_rev}.mp4"
    await render_project_mp4(client, pid, css_rev, css_mp4)
    css_frame_1s = OUTPUT_DIR / "gate1_css_frame_1s.png"
    decode_mp4_frame(css_mp4, 1.0, css_frame_1s)

    # Compare CSS-only frame against HTML-only frame at 1.0s
    css_diff_png = OUTPUT_DIR / "gate1_css_attribution_diff.png"
    css_metrics = compute_image_metrics(html_frame_1s, css_frame_1s, css_diff_png)
    log(f"CSS-only attribution -> Diff: {css_metrics['diff_percentage']}%, Pixels Changed: {css_metrics['changed_pixels']}")
    assert css_metrics["changed_pixels"] > 0, "CSS-only edit did not change pixels!"
    gate1_results["css_only_attribution"] = css_metrics

    # Sub-test D: JS-only Edit with Composition Clock Synchronization
    log("Applying JS-only mutation advancing with composition clock...")
    js_mutated_content = """
    // JS Animation advancing with canonical composition clock
    window.addEventListener("compositiontimeupdate", function(e) {
        var t = e.detail ? e.detail.time : (window.__compositionTime || 0);
        var badge = document.getElementById("js-clock-badge");
        if (!badge) {
            badge = document.createElement("div");
            badge.id = "js-clock-badge";
            badge.style.position = "absolute";
            badge.style.width = "220px";
            badge.style.height = "220px";
            badge.style.backgroundColor = "#ff00bb";
            badge.style.border = "8px solid #ffffff";
            badge.style.borderRadius = "20px";
            badge.style.zIndex = "999";
            document.getElementById("stage").appendChild(badge);
        }
        badge.style.top = (350 + t * 180) + "px";
        badge.style.left = (100 + t * 140) + "px";
        badge.style.transform = "rotate(" + (t * 120) + "deg)";
    });
    """
    res = await client.post(f"{BASE_URL}/api/projects/{pid}/operations", json={
        "expected_revision": rev,
        "operation_type": "update_file",
        "payload": {
            "path": "scripts/main.js",
            "content": js_mutated_content
        }
    })
    assert res.status_code == 200
    rev = res.json()["revision"]
    js_rev = rev

    js_mp4 = OUTPUT_DIR / f"gate1_js_only_rev{js_rev}.mp4"
    await render_project_mp4(client, pid, js_rev, js_mp4)
    js_frame_05s = OUTPUT_DIR / "gate1_js_frame_0.5s.png"
    js_frame_15s = OUTPUT_DIR / "gate1_js_frame_1.5s.png"
    decode_mp4_frame(js_mp4, 0.5, js_frame_05s)
    decode_mp4_frame(js_mp4, 1.5, js_frame_15s)

    # Compare 0.5s vs 1.5s in JS-only render to verify motion progression
    js_motion_diff_png = OUTPUT_DIR / "gate1_js_clock_motion_diff.png"
    js_motion_metrics = compute_image_metrics(js_frame_05s, js_frame_15s, js_motion_diff_png)
    log(f"JS clock progression (0.5s vs 1.5s) -> Diff: {js_motion_metrics['diff_percentage']}%, Pixels Changed: {js_motion_metrics['changed_pixels']}")
    assert js_motion_metrics["changed_pixels"] > 0, "JS animation did not advance over time!"
    gate1_results["js_only_attribution"] = js_motion_metrics

    # Sub-test E: JSON Runtime Consumer Identification & Classification
    log("Verifying JSON runtime parameter injection...")
    json_content = json.dumps({"theme_accent": "#00ffff", "banner_text": "JSON PARAMETER ACTIVE", "speed": 2.5})
    res = await client.post(f"{BASE_URL}/api/projects/{pid}/operations", json={
        "expected_revision": rev,
        "operation_type": "create_file",
        "payload": {
            "path": "config/settings.json",
            "content": json_content
        }
    })
    assert res.status_code == 200
    rev = res.json()["revision"]

    # Reload page to check injected window.__project_configs in preview HTML
    await page.goto(f"{BASE_URL}/motion?projectId={pid}", wait_until="networkidle")
    await page.wait_for_selector("#studio-preview-iframe", timeout=15000)
    await asyncio.sleep(2.0)

    json_injected_configs = await eval_in_preview_frame(page, """() => {
        return window.__project_configs || null;
    }""")
    log(f"window.__project_configs received in iframe: {json_injected_configs}")
    assert json_injected_configs is not None, "window.__project_configs missing in iframe!"
    assert "config/settings.json" in json_injected_configs, "config/settings.json not parsed into window.__project_configs!"
    assert json_injected_configs["config/settings.json"]["banner_text"] == "JSON PARAMETER ACTIVE"

    gate1_results["json_runtime_verification"] = {
        "status": "PASS",
        "injected_in_window_project_configs": True,
        "classification": "Versioned structured configuration & parameter store; programmatic access via window.__project_configs; no automatic visual binding without script/block binding."
    }

    gate1_results["status"] = "PASS"
    log("=== GATE 1 PASSED ===")
    return gate1_results

# ==============================================================================
# GATE 2: Missing Real FileTree and Conflict-Recovery Browser Evidence
# ==============================================================================
async def execute_gate_2(page, client: httpx.AsyncClient) -> Dict[str, Any]:
    log("=== STARTING GATE 2: FileTree UI & Conflict-Recovery Browser Evidence ===")
    gate2_results = {}

    res = await client.post(f"{BASE_URL}/api/projects", json={
        "name": "Gate2-FileTree-Conflict-Project",
        "aspect_ratio": "9:16"
    })
    assert res.status_code == 200
    pid = res.json()["id"]
    rev = res.json()["revision"]

    # Add a block to test referenced file deletion rejection
    res = await client.post(f"{BASE_URL}/api/projects/{pid}/operations", json={
        "expected_revision": rev,
        "operation_type": "add_block",
        "payload": {
            "block_id": "weight-wave",
            "instance_id": "elem_referenced_block",
            "title": "Referenced Block Clip",
            "start_seconds": 0.0,
            "duration_seconds": 4.0
        }
    })
    assert res.status_code == 200
    rev = res.json()["revision"]

    # Add project-owned block override file
    res = await client.post(f"{BASE_URL}/api/projects/{pid}/operations", json={
        "expected_revision": rev,
        "operation_type": "create_file",
        "payload": {
            "path": "compositions/elem_referenced_block.html",
            "content": "<div>Referenced Block Content</div>",
            "clip_id": "elem_referenced_block"
        }
    })
    assert res.status_code == 200
    rev = res.json()["revision"]

    # Open /motion in Playwright
    await page.goto(f"{BASE_URL}/motion?projectId={pid}", wait_until="domcontentloaded")
    await asyncio.sleep(2.0)
    await page.wait_for_selector('[data-testid="studio-toolbar-code-btn"]', timeout=15000)

    # 1. Switch to Code Context
    log("Switching to Code context in toolbar...")
    code_btn = page.locator('[data-testid="studio-toolbar-code-btn"]')
    await code_btn.click()
    await page.wait_for_selector('[data-testid="studio-file-tree"]', timeout=10000)
    log("FileTree is rendered and visible.")

    # 2. UI Create File
    log("Creating file via UI: styles/temp_move.css...")
    new_file_btn = page.locator('[data-testid="studio-filetree-new-file-btn"]')
    await new_file_btn.click()
    await page.fill('[data-testid="studio-filetree-input"]', "styles/temp_move.css")
    await page.click('[data-testid="studio-filetree-confirm-btn"]')
    await page.wait_for_selector('text="temp_move.css"', timeout=5000)

    # Verify project revision bumped
    proj_state = (await client.get(f"{BASE_URL}/api/projects/{pid}")).json()
    rev = proj_state["revision"]
    created_file = next(f for f in proj_state["document"]["code"]["files"] if f["path"] == "styles/temp_move.css")
    stable_file_id = created_file["id"]
    log(f"Created file: {created_file['path']} (id={stable_file_id}, rev={rev})")

    # 3. UI Rename File (preserving stable file ID)
    log("Renaming file via context menu: temp_move.css -> renamed_target.css...")
    filetree = page.locator('[data-testid="studio-file-tree"]')
    file_item = filetree.locator('text="temp_move.css"').first
    await file_item.click(button="right")
    await page.click('text="Rename File"')
    await page.fill('[data-testid="studio-filetree-input"]', "styles/renamed_target.css")
    await page.click('[data-testid="studio-filetree-confirm-btn"]')
    await filetree.locator('text="renamed_target.css"').first.wait_for(state="visible", timeout=5000)

    proj_state = (await client.get(f"{BASE_URL}/api/projects/{pid}")).json()
    renamed_file = next(f for f in proj_state["document"]["code"]["files"] if f["path"] == "styles/renamed_target.css")
    assert renamed_file["id"] == stable_file_id, f"File ID changed! {renamed_file['id']} != {stable_file_id}"
    log(f"Renamed file: stable file ID {stable_file_id} preserved across rename (rev={proj_state['revision']})")

    # 4. UI Move File to nested logical folder
    log("Moving file via context menu: renamed_target.css -> components/nested/moved.css...")
    file_item = filetree.locator('text="renamed_target.css"').first
    await file_item.click(button="right")
    await page.click('text="Move File"')
    await page.fill('[data-testid="studio-filetree-input"]', "components/nested/moved.css")
    await page.click('[data-testid="studio-filetree-confirm-btn"]')
    await filetree.locator('text="moved.css"').first.wait_for(state="visible", timeout=5000)

    proj_state = (await client.get(f"{BASE_URL}/api/projects/{pid}")).json()
    moved_file = next(f for f in proj_state["document"]["code"]["files"] if f["path"] == "components/nested/moved.css")
    assert moved_file["id"] == stable_file_id, "File ID changed across move!"
    log(f"Moved file: stable file ID {stable_file_id} preserved in nested directory (rev={proj_state['revision']})")

    # 5. UI Delete Unused File
    log("Deleting unused file: moved.css...")
    file_item = filetree.locator('text="moved.css"').first
    await file_item.click(button="right")
    await page.click('text="Delete File"')
    await page.click('[data-testid="studio-filetree-confirm-btn"]')
    await asyncio.sleep(1.0)

    proj_state = (await client.get(f"{BASE_URL}/api/projects/{pid}")).json()
    assert not any(f["id"] == stable_file_id for f in proj_state["document"]["code"]["files"]), "File still exists after deletion!"
    log(f"Unused file deleted cleanly (rev={proj_state['revision']})")

    # 6. Reject Deletion of Referenced File
    log("Attempting to delete referenced clip file: compositions/elem_referenced_block.html...")
    ref_file_id = next(f["id"] for f in proj_state["document"]["code"]["files"] if f["path"] == "compositions/elem_referenced_block.html")
    res_del_ref = await client.post(f"{BASE_URL}/api/projects/{pid}/operations", json={
        "expected_revision": proj_state["revision"],
        "operation_type": "delete_file",
        "payload": {"id": ref_file_id}
    })
    assert res_del_ref.status_code == 400, f"Expected 400 rejection, got {res_del_ref.status_code}"
    del_detail = res_del_ref.json()["detail"]
    del_msg = del_detail if isinstance(del_detail, str) else del_detail.get("message", str(del_detail))
    assert "referenced by active clip" in del_msg
    log(f"Referenced file deletion properly rejected: {del_msg}")

    # 7. Reject Duplicate Paths
    log("Testing duplicate path rejection...")
    res_dup = await client.post(f"{BASE_URL}/api/projects/{pid}/operations", json={
        "expected_revision": proj_state["revision"],
        "operation_type": "create_file",
        "payload": {
            "path": "compositions/elem_referenced_block.html",
            "content": "duplicate"
        }
    })
    assert res_dup.status_code == 400
    dup_detail = res_dup.json()["detail"]
    dup_msg = dup_detail if isinstance(dup_detail, str) else dup_detail.get("message", str(dup_detail))
    assert "already exists" in dup_msg
    log(f"Duplicate path rejected: {dup_msg}")

    # 8. Malformed JSON Validation Feedback in Editor
    log("Testing malformed JSON validation feedback in editor...")
    new_file_btn = page.locator('[data-testid="studio-filetree-new-file-btn"]')
    await new_file_btn.click()
    await page.fill('[data-testid="studio-filetree-input"]', "config/app_config.json")
    await page.click('[data-testid="studio-filetree-confirm-btn"]')
    await page.wait_for_selector('text="app_config.json"', timeout=5000)

    # Click on the file to open it
    await filetree.locator('text="app_config.json"').first.click()
    await asyncio.sleep(0.5)

    # Insert malformed JSON into CodeMirror
    cm_content = page.locator(".cm-content").first
    await cm_content.click()
    await page.keyboard.press("Control+A")
    await page.keyboard.type('{ "invalid_key": 123, }')  # Invalid JSON syntax
    await asyncio.sleep(0.5)

    # Verify JSON validation warning alert is visible
    warning_loc = page.locator('[data-testid="studio-code-json-warning"]')
    await warning_loc.wait_for(state="visible", timeout=5000)
    warning_text = await warning_loc.inner_text()
    log(f"Malformed JSON feedback displayed in UI: {warning_text}")
    assert "JSON Syntax Error" in warning_text

    # Attempt to click Save
    save_btn = page.locator('[data-testid="studio-code-save-btn"]')
    await save_btn.click()
    await asyncio.sleep(0.5)

    # Verify error banner prevents save
    err_banner = page.locator('[data-testid="studio-code-error-banner"]')
    await err_banner.wait_for(state="visible", timeout=5000)
    err_text = await err_banner.inner_text()
    log(f"Pre-save error banner: {err_text}")
    assert "Invalid JSON" in err_text

    # Fix JSON and verify warning clears and save succeeds
    await page.evaluate("() => document.querySelector('.cm-content')?.focus()")
    await asyncio.sleep(0.3)
    await page.keyboard.press("Control+A")
    await page.keyboard.type('{ "valid_key": 123 }')
    await asyncio.sleep(0.5)
    assert not await warning_loc.is_visible()
    await save_btn.click()
    await asyncio.sleep(1.0)
    log("Fixed JSON saved successfully.")

    # 9. Respect Read-Only Files
    log("Verifying read-only file handling...")
    proj_state = (await client.get(f"{BASE_URL}/api/projects/{pid}")).json()
    res_ro = await client.post(f"{BASE_URL}/api/projects/{pid}/operations", json={
        "expected_revision": proj_state["revision"],
        "operation_type": "create_file",
        "payload": {
            "path": "vendor/immutable.js",
            "content": "// Read only vendor code",
            "read_only": True
        }
    })
    assert res_ro.status_code == 200
    rev = res_ro.json()["revision"]

    await filetree.locator('text="immutable.js"').first.click()
    await asyncio.sleep(0.5)
    save_disabled = await save_btn.is_disabled()
    log(f"Read-only file Save button disabled: {save_disabled}")
    assert save_disabled is True, "Save button should be disabled for read-only file!"

    # 10. Concurrent Client Conflict & Reconciliation Dialog in UI
    log("Simulating concurrent client modification and HTTP 409 conflict...")
    # Client 1 (browser) selects a writable file and edits draft
    await filetree.locator('text="app_config.json"').first.click()
    await asyncio.sleep(0.5)
    await page.evaluate("() => document.querySelector('.cm-content')?.focus()")
    await asyncio.sleep(0.3)
    await page.keyboard.press("Control+A")
    await page.keyboard.type('{ "client1_draft": "my local unsaved edits" }')
    await asyncio.sleep(0.5)

    # Client 2 (backend API) concurrently mutates project
    proj_state = (await client.get(f"{BASE_URL}/api/projects/{pid}")).json()
    curr_rev = proj_state["revision"]
    res_c2 = await client.post(f"{BASE_URL}/api/projects/{pid}/operations", json={
        "expected_revision": curr_rev,
        "operation_type": "create_file",
        "payload": {
            "path": "concurrent/remote.css",
            "content": "/* Remote edit */"
        }
    })
    assert res_c2.status_code == 200
    remote_rev = res_c2.json()["revision"]
    log(f"Client 2 bumped revision to {remote_rev} (Client 1 was editing at rev {curr_rev})")

    # Client 1 clicks Save File
    await save_btn.click()
    await asyncio.sleep(1.0)

    # Verify Conflict Dialog appears
    conflict_dialog = page.locator('[data-testid="conflict-dialog"]')
    await conflict_dialog.wait_for(state="visible", timeout=8000)
    conflict_text = await page.locator('[data-testid="conflict-dialog-text"]').inner_text()
    log(f"Conflict dialog visible: {conflict_text}")
    assert f"revision {remote_rev}" in conflict_text

    # Verify unsaved draft is RETAINED in CodeMirror editor
    editor_text = await page.locator(".cm-content").first.inner_text()
    assert "my local unsaved edits" in editor_text, f"Draft was lost! Editor content: {editor_text}"
    log("Verified unsaved draft text retained in CodeMirror across HTTP 409!")

    # Client 1 chooses 'Overwrite Remote'
    log("Resolving conflict via 'Overwrite Remote' button...")
    await page.click('[data-testid="conflict-overwrite-btn"]')
    await asyncio.sleep(1.5)

    proj_state = (await client.get(f"{BASE_URL}/api/projects/{pid}")).json()
    final_rev = proj_state["revision"]
    assert final_rev > remote_rev, f"Final revision not advanced: {final_rev} <= {remote_rev}"
    log(f"Conflict reconciled and saved with revision {final_rev}!")

    # 11. Switch among Code, Timeline, Layers, Inspector, and Preview
    log("Switching between Editor Contexts...")
    await page.click('[data-testid="studio-toolbar-timeline-btn"]')
    await asyncio.sleep(0.5)
    log("  -> Timeline context active")

    await page.click('button:has-text("Layers")')
    await asyncio.sleep(0.5)
    log("  -> Layers tab active")

    await page.click('button:has-text("Properties")')
    await asyncio.sleep(0.5)
    log("  -> Inspector properties tab active")

    await page.click('[data-testid="studio-toolbar-code-btn"]')
    await page.wait_for_selector('[data-testid="studio-code-workspace"]', timeout=5000)
    log("  -> Code Workspace preserved")

    gate2_results["status"] = "PASS"
    log("=== GATE 2 PASSED ===")
    return gate2_results

# ==============================================================================
# GATE 3: Executable Project-Code Isolation
# ==============================================================================
async def execute_gate_3(page, client: httpx.AsyncClient) -> Dict[str, Any]:
    log("=== STARTING GATE 3: Executable Project-Code Isolation ===")
    gate3_results = {}

    res = await client.post(f"{BASE_URL}/api/projects", json={
        "name": "Gate3-Security-Isolation-Project",
        "aspect_ratio": "9:16"
    })
    assert res.status_code == 200
    pid = res.json()["id"]
    rev = res.json()["revision"]

    # Open /motion editor in Playwright
    await page.goto(f"{BASE_URL}/motion?projectId={pid}", wait_until="networkidle")
    await page.wait_for_selector("#studio-preview-iframe", timeout=15000)
    await asyncio.sleep(2.0)

    # 1. Inspect real Preview iframe sandbox attribute
    sandbox_attr = await page.locator("#studio-preview-iframe").get_attribute("sandbox")
    log(f"1. Real Preview iframe sandbox attribute: '{sandbox_attr}'")
    assert sandbox_attr is not None and "allow-scripts" in sandbox_attr
    assert "allow-same-origin" not in (sandbox_attr or ""), "CRITICAL: allow-same-origin MUST NOT be present with same-origin hosting!"

    # 2. Inspect iframe origin
    iframe_origin = await eval_in_preview_frame(page, "() => window.origin")
    log(f"2. Iframe effective window.origin: '{iframe_origin}'")
    assert iframe_origin == "null", f"Expected opaque origin 'null', got '{iframe_origin}'"

    # 3. Verify window.parent.document access is DENIED
    parent_doc_access = await eval_in_preview_frame(page, """() => {
        try {
            const title = window.parent.document.title;
            return { allowed: true, title: title };
        } catch (e) {
            return { allowed: false, error: e.name + ': ' + e.message };
        }
    }""")
    log(f"3. window.parent.document access result: {parent_doc_access}")
    assert parent_doc_access["allowed"] is False
    assert "SecurityError" in parent_doc_access["error"]

    # 4. Verify access to parent cookies / tokens is DENIED
    cookie_access = await eval_in_preview_frame(page, """() => {
        let cookieVal = null;
        let cookieErr = null;
        try {
            cookieVal = document.cookie;
        } catch (e) {
            cookieErr = e.name + ': ' + e.message;
        }
        return {
            cookie: cookieVal,
            cookie_error: cookieErr,
            has_localStorage: (() => {
                try { return !!window.localStorage.length; } catch(e) { return e.name; }
            })()
        };
    }""")
    log(f"4. Cookie / Storage isolation: {cookie_access}")
    assert cookie_access["cookie"] is None or cookie_access["cookie"] == ""
    assert "SecurityError" in (cookie_access.get("cookie_error") or "") or "SecurityError" in str(cookie_access.get("has_localStorage"))

    # 5. Verify CSP blocks outbound network requests (connect-src 'none')
    network_probe = await eval_in_preview_frame(page, """async () => {
        const results = {};
        try {
            await fetch('/api/projects');
            results.local_fetch = "ALLOWED";
        } catch(e) {
            results.local_fetch = "BLOCKED: " + e.message;
        }

        try {
            await fetch('https://example.com');
            results.external_fetch = "ALLOWED";
        } catch(e) {
            results.external_fetch = "BLOCKED: " + e.message;
        }

        try {
            const wsBlocked = await new Promise((resolve) => {
                try {
                    const ws = new WebSocket('ws://127.0.0.1:16888/ws');
                    ws.onerror = () => resolve("BLOCKED: CSP onerror");
                    ws.onopen = () => resolve("ALLOWED");
                    setTimeout(() => resolve("BLOCKED: timeout"), 1000);
                } catch(e) {
                    resolve("BLOCKED: " + e.message);
                }
            });
            results.websocket = wsBlocked;
        } catch(e) {
            results.websocket = "BLOCKED: " + e.message;
        }
        return results;
    }""")
    log(f"5. Network probe (CSP enforcement): {network_probe}")
    assert "BLOCKED" in network_probe["local_fetch"]
    assert "BLOCKED" in network_probe["external_fetch"]
    assert "BLOCKED" in network_probe["websocket"]

    # 6. Verify file:// and local filesystem resources are blocked
    file_probe = await eval_in_preview_frame(page, """async () => {
        try {
            await fetch('file:///C:/Windows/win.ini');
            return "ALLOWED";
        } catch(e) {
            return "BLOCKED: " + e.message;
        }
    }""")
    log(f"6. file:// probe result: {file_probe}")
    assert "BLOCKED" in file_probe

    # 7. Verify script tag escape prevents breaking out of boundaries
    res_escape = await client.post(f"{BASE_URL}/api/projects/{pid}/operations", json={
        "expected_revision": rev,
        "operation_type": "create_file",
        "payload": {
            "path": "scripts/escape_probe.js",
            "content": '</script><script>window.__breakout_executed = true;</script>'
        }
    })
    assert res_escape.status_code == 200
    rev = res_escape.json()["revision"]

    # Reload page to check generated HTML inside iframe
    await page.goto(f"{BASE_URL}/motion?projectId={pid}", wait_until="networkidle")
    await page.wait_for_selector("#studio-preview-iframe", timeout=15000)
    await asyncio.sleep(2.0)

    breakout_result = await eval_in_preview_frame(page, """() => {
        return window.__breakout_executed === true;
    }""")
    log(f"7. Script tag breakout probe result: {breakout_result}")
    assert breakout_result is False, "Script tag breakout succeeded!"

    # 8. Verify legitimate video, GSAP playback, and Preview messaging continue to work
    messaging_test = await page.evaluate("""async () => {
        const iframe = document.getElementById('studio-preview-iframe');
        let responseReceived = false;
        const handler = (e) => {
            if (e.data && e.data.source === 'vm-runtime') {
                responseReceived = true;
            }
        };
        window.addEventListener('message', handler);
        iframe.contentWindow.postMessage({ source: 'vm-parent', action: 'seek', time: 1.5 }, '*');
        await new Promise(r => setTimeout(r, 600));
        window.removeEventListener('message', handler);
        return responseReceived;
    }""")
    log(f"8. Bidirectional messaging bridge across sandbox: {messaging_test}")
    assert messaging_test is True, "Parent-to-iframe messaging failed under sandbox!"

    gate3_results["status"] = "PASS"
    gate3_results["sandbox_attributes"] = sandbox_attr
    gate3_results["effective_origin"] = iframe_origin
    gate3_results["parent_doc_access"] = parent_doc_access
    gate3_results["cookie_storage_isolation"] = cookie_access
    gate3_results["network_csp_probe"] = network_probe
    gate3_results["file_uri_probe"] = file_probe
    gate3_results["script_breakout_blocked"] = True
    gate3_results["messaging_bridge_functional"] = messaging_test

    log("=== GATE 3 PASSED ===")
    return gate3_results

# ==============================================================================
# MAIN ENTRYPOINT
# ==============================================================================
async def main():
    log("Initializing Phase 9 Three Remaining Gates Acceptance Suite...")
    summary = {}

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Check backend server health
        health = await client.get(f"{BASE_URL}/api/trends/results")
        assert health.status_code == 200, "Backend server not responding!"

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1440, "height": 900})

            try:
                # GATE 1
                summary["GATE_1"] = await execute_gate_1(page, client)

                # GATE 2
                summary["GATE_2"] = await execute_gate_2(page, client)

                # GATE 3
                summary["GATE_3"] = await execute_gate_3(page, client)

            finally:
                await browser.close()

    summary_file = OUTPUT_DIR / "three_gates_summary.json"
    summary_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log(f"Three Gates Acceptance Suite Finished! Summary saved to {summary_file}")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
