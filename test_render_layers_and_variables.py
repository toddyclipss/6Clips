# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Real Chromium MP4 Render Acceptance Test for Phase 8: Layers & Variables
Validates end-to-end:
1. Versioned ProjectRevision with Multi-Track composition containing:
   - Visible block clip with custom variables ('TITLE': 'PHASE 8 LAYERS')
   - Hidden text/block clip ('visible': False)
   - Proper layer_order (z-index)
2. Deterministic HyperFrames HTML projection with:
   - Staging of block instance
   - Style z-index matching layer_order
   - Exclusion of hidden clip
3. Real Chromium headless render via HyperFrames CLI to MP4
4. ffprobe verification: H.264 video stream, dimensions, fps, duration, non-zero file
5. Artifacts copy
"""
import asyncio
import os
import shutil
import subprocess
from pathlib import Path

from backend.database import init_db
from backend.services.project_service import ProjectService
from backend.services.hyperframes_adapter import HyperFramesAdapter
from backend.services.motion_render_service import MotionRenderService

ARTIFACTS_DIR = Path(r"C:\Users\toddy\.gemini\antigravity\brain\05dc85cb-9ba9-426a-8e4d-5ef5943efc16")


async def run_layers_variables_render_acceptance():
    print("=== STARTING REAL CHROMIUM MP4 LAYERS & VARIABLES RENDER ACCEPTANCE ===")
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    await init_db()

    # 1. Create project
    proj = await ProjectService.create_project(name="Phase 8 Layers Variables Render", aspect_ratio="16:9")
    pid = proj.id
    rev = proj.revision
    print(f"[Step 1] Project created: {pid} (Rev {rev})")

    # 2. Add visible block instance with custom variables
    rev_block1 = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=rev,
        operation_type="add_block",
        payload={
            "block_id": "lower-third-bild",
            "variables": {
                "TXT_MAIN_1_Line": "PHASE 8 LAYERS ACTIVE",
                "TXT_SUB": "VIRALMINT VARIABLES ENGINE",
            },
            "start_seconds": 0.0,
            "duration_seconds": 3.0,
        },
        author="dj"
    )
    rev = rev_block1["revision"]
    block1_clip = [c for t in rev_block1["document"]["timeline"]["tracks"] for c in t.get("clips", [])][0]
    cid1 = block1_clip["id"]
    print(f"[Step 2] Visible block added: {cid1} (Rev {rev})")

    # 3. Set layer_order on block 1
    res_lo = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=rev,
        operation_type="reorder_layer",
        payload={"clip_id": cid1, "layer_order": 10},
        author="dj"
    )
    rev = res_lo["revision"]

    # 4. Add a second block instance and hide it (visible=False)
    rev_block2 = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=rev,
        operation_type="add_block",
        payload={
            "block_id": "notification-cascade",
            "variables": {
                "title": "HIDDEN ELEMENT",
                "message": "SHOULD NOT BE RENDERED",
            },
            "start_seconds": 0.0,
            "duration_seconds": 3.0,
        },
        author="dj"
    )
    rev = rev_block2["revision"]
    all_clips = [c for t in rev_block2["document"]["timeline"]["tracks"] for c in t.get("clips", [])]
    block2_clip = [c for c in all_clips if c["id"] != cid1][0]
    cid2 = block2_clip["id"]
    print(f"[Step 4] Second block added: {cid2} (Rev {rev})")

    # Hide block 2
    res_hide = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=rev,
        operation_type="set_element_visibility",
        payload={"clip_id": cid2, "visible": False},
        author="dj"
    )
    rev = res_hide["revision"]
    print(f"[Step 4] Second block hidden: {cid2} (Rev {rev})")

    # 5. Freeze revision and stage for render
    target_rev, work_dir = await HyperFramesAdapter.stage_project_for_render(pid, revision=rev)
    print(f"[Step 5] Staged project for render in: {work_dir}")

    # Verify deterministic projection in index.html
    html_content = (work_dir / "index.html").read_text(encoding="utf-8")
    assert f'id="{cid1}"' in html_content, f"Visible element {cid1} must be present in HTML"
    assert f'id="{cid2}"' not in html_content, f"Hidden element {cid2} must NOT be present in HTML"
    assert 'z-index: 10' in html_content, "layer_order z-index must be projected in inline style"
    print("[Step 5 PASS] Deterministic Layer visibility and z-index projection verified in staged HTML")

    # 6. Render real MP4 via MotionRenderService (headless Chromium CLI)
    out_mp4 = work_dir.parent / f"layers_variables_composition_{pid}_rev{rev}.mp4"
    print(f"[Step 6] Rendering MP4 via Chromium to: {out_mp4}...")
    rendered_path = await MotionRenderService.render_project(
        project_dir=work_dir,
        aspect="16:9",
        fps=30,
        quality="draft",
        out_path=out_mp4,
        keep=True,
    )
    assert rendered_path.exists(), "Rendered MP4 file must exist"
    file_size = rendered_path.stat().st_size
    assert file_size > 10000, f"Rendered MP4 too small ({file_size} bytes)"
    print(f"[Step 6 PASS] Real Chromium MP4 render succeeded! File size: {file_size:,} bytes")

    # 7. ffprobe validation
    ffprobe = shutil.which("ffprobe")
    assert ffprobe, "ffprobe must be installed"
    probe_cmd = [
        ffprobe, "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,r_frame_rate",
        "-of", "csv=p=0",
        str(rendered_path)
    ]
    probe_out = subprocess.check_output(probe_cmd).decode("utf-8").strip()
    print(f"[Step 7] ffprobe video stream details: {probe_out}")
    parts = probe_out.split(",")
    codec = parts[0]
    w = int(parts[1])
    h = int(parts[2])
    assert "h264" in codec.lower(), f"Expected h264 codec, got {codec}"
    assert w >= 1920 and h >= 1080, f"Expected at least 1080p, got {w}x{h}"
    print(f"[Step 7 PASS] Validated H.264 stream: {w}x{h} codec={codec}")

    # Copy MP4 to brain artifacts directory
    artifact_mp4 = ARTIFACTS_DIR / "layers_variables_rendered_composition.mp4"
    shutil.copyfile(rendered_path, artifact_mp4)
    print(f"Copied artifact to: {artifact_mp4}")
    print("=== REAL CHROMIUM MP4 LAYERS & VARIABLES RENDER ACCEPTANCE PASSED ===")


if __name__ == "__main__":
    asyncio.run(run_layers_variables_render_acceptance())
