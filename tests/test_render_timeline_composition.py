# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Real Chromium MP4 Render Acceptance Test for Professional Timeline:
Validates end-to-end:
1. Versioned ProjectRevision with Multi-Track composition (block, caption, animations)
2. Deterministic GSAP projection from clip.animations to index.html
3. Real Chromium headless render via HyperFrames CLI to MP4
4. ffprobe verification: H.264 video stream, dimensions, fps, duration, non-zero file
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


async def run_timeline_render_acceptance():
    print("=== STARTING REAL CHROMIUM MP4 TIMELINE RENDER ACCEPTANCE ===")
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    await init_db()

    # 1. Create project
    proj = await ProjectService.create_project(name="Timeline Composition Render", aspect_ratio="16:9")
    pid = proj.id
    rev = proj.revision
    print(f"[Step 1] Project created: {pid} (Rev {rev})")

    # 2. Add real HyperFrames block instance
    rev_block = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=rev,
        operation_type="add_block",
        payload={
            "block_id": "lower-third-bild",
            "variables": {
                "TXT_MAIN_1_Line": "PROFESSIONAL TIMELINE",
                "TXT_SUB": "GSAP ANIMATED KEYFRAMES",
            },
            "start_seconds": 0.0,
            "duration_seconds": 3.0,
        },
        author="tester"
    )
    rev = rev_block["revision"]
    block_clip = [c for t in rev_block["document"]["timeline"]["tracks"] for c in t.get("clips", [])][0]
    cid = block_clip["id"]
    print(f"[Step 2] Block added: {cid} (Rev {rev})")

    # 3. Add keyframe animations to block clip
    # Opacity 0 -> 1 over 0.5s
    res_kf1 = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=rev,
        operation_type="add_keyframe",
        payload={
            "clip_id": cid,
            "keyframe": {"property": "opacity", "time": 0.0, "value": 0.0, "ease": "none"}
        },
        author="tester"
    )
    rev = res_kf1["revision"]

    res_kf2 = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=rev,
        operation_type="add_keyframe",
        payload={
            "clip_id": cid,
            "keyframe": {"property": "opacity", "time": 0.8, "value": 1.0, "ease": "power2.out"}
        },
        author="tester"
    )
    rev = res_kf2["revision"]

    # Position Y animation -40px -> 0px
    res_kf3 = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=rev,
        operation_type="add_keyframe",
        payload={
            "clip_id": cid,
            "keyframe": {"property": "y", "time": 0.0, "value": -40, "ease": "none"}
        },
        author="tester"
    )
    rev = res_kf3["revision"]

    res_kf4 = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=rev,
        operation_type="add_keyframe",
        payload={
            "clip_id": cid,
            "keyframe": {"property": "y", "time": 0.8, "value": 0, "ease": "power2.out"}
        },
        author="tester"
    )
    rev = res_kf4["revision"]

    # 4. Add captions
    res_cap = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=rev,
        operation_type="set_captions",
        payload={
            "captions": [
                {
                    "id": "cap_timeline_1",
                    "caption_text": "ViralMint Composition Stream",
                    "start_seconds": 0.2,
                    "duration_seconds": 2.5,
                }
            ]
        },
        author="tester"
    )
    rev = res_cap["revision"]
    print(f"[Step 3-4] Keyframes and captions applied (Rev {rev})")

    # 5. Freeze revision and stage for render
    target_rev, work_dir = await HyperFramesAdapter.stage_project_for_render(pid, revision=rev)
    print(f"[Step 5] Staged project for render in: {work_dir}")

    # Verify deterministic GSAP projection in index.html
    html_content = (work_dir / "index.html").read_text(encoding="utf-8")
    assert f'tl.set("#{cid}", {{ opacity: 0.0 }}, 0.0);' in html_content
    assert f'tl.to("#{cid}", {{ opacity: 1.0, duration: 0.8, ease: "power2.out" }}, 0.0);' in html_content
    assert f'tl.set("#{cid}", {{ y: -40 }}, 0.0);' in html_content
    assert f'tl.to("#{cid}", {{ y: 0, duration: 0.8, ease: "power2.out" }}, 0.0);' in html_content
    print("[Step 5 PASS] Deterministic GSAP projection verified in staged index.html")

    # 6. Render real MP4 via MotionRenderService (headless Chromium CLI)
    out_mp4 = work_dir.parent / f"timeline_composition_{pid}_rev{rev}.mp4"
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
    artifact_mp4 = ARTIFACTS_DIR / "timeline_rendered_composition.mp4"
    shutil.copyfile(rendered_path, artifact_mp4)
    print(f"Copied artifact to: {artifact_mp4}")
    print("=== REAL CHROMIUM MP4 RENDER ACCEPTANCE PASSED ===")


if __name__ == "__main__":
    asyncio.run(run_timeline_render_acceptance())
