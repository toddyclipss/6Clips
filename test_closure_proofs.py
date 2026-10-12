"""
Test Closure Proofs:
Proof 1: Live Registry Mutation & Frozen Cache Reproducibility Render Proof
Proof 2: Two Simultaneous Instances of the Same Block in One Real MP4 with ffprobe
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
from pathlib import Path

from backend.services.project_service import ProjectService
from backend.services.registry_adapter import RegistryAdapter, get_registry_dir, get_registry_cache_dir
from backend.services.hyperframes_adapter import HyperFramesAdapter
from backend.services.motion_render_service import MotionRenderService
from backend.config import DATA_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_closure_proofs")

async def run_proofs():
    print("==================================================")
    print("STARTING CLOSURE PROOF 1: FROZEN REPRODUCIBILITY")
    print("==================================================")

    # Setup isolated test block in registry
    reg_dir = get_registry_dir()
    test_block_name = "closure-test-block"
    live_block_dir = reg_dir / test_block_name
    
    # Clean any previous artifacts
    if live_block_dir.exists():
        shutil.rmtree(live_block_dir)
        
    try:
        # Step A: Create version A in live registry
        live_block_dir.mkdir(parents=True, exist_ok=True)
        manifest_a = {
            "name": test_block_name,
            "title": "Closure Test Block",
            "category": "text",
            "version": "1.0.0",
            "files": [{"path": "index.html", "type": "hyperframes:composition"}],
            "variables": [
                {"name": "headline", "type": "string", "default": "VERSION_A_DEFAULT"}
            ]
        }
        (live_block_dir / "registry-item.json").write_text(json.dumps(manifest_a), encoding="utf-8")
        html_a = """<!DOCTYPE html>
<html>
<head><title>Closure Block</title></head>
<body>
<div id="composition" data-composition-id="closure-test-block" style="width: 1920px; height: 1080px; background: #112233; color: #ffffff;">
  <h1 id="txt" style="font-size: 80px;">VERSION_A_STATIC_MARKER</h1>
</div>
<script>
  window.__timelines = window.__timelines || {};
  window.__timelines["closure-test-block"] = { duration: 2.0, play: function(){} };
</script>
</body>
</html>"""
        (live_block_dir / "index.html").write_text(html_a, encoding="utf-8")

        # Step B: Create Project, add block while live registry has Version A
        proj = await ProjectService.create_project(name="Frozen Cache Reproducibility Test", aspect_ratio="16:9")
        pid = proj.id

        rev2 = await ProjectService.apply_operation(
            project_id=pid,
            expected_revision=1,
            operation_type="add_block",
            payload={
                "block_id": test_block_name,
                "variables": {"headline": "RUNNING_VERSION_A"},
                "start_seconds": 0.0,
                "duration_seconds": 2.0,
            },
            author="tester"
        )
        assert rev2["revision"] == 2
        all_clips = [c for t in rev2["document"]["timeline"]["tracks"] for c in t.get("clips", [])]
        clip = next(c for c in all_clips if c.get("block_id") == test_block_name)
        version_a_hash = clip["block_version"]
        cid = clip["id"]
        print(f"[Proof 1] Rev 2 created with block_version: {version_a_hash}")

        # Check cache directory exists for version A
        cache_a_dir = get_registry_cache_dir() / f"{test_block_name}_{version_a_hash}"
        assert cache_a_dir.exists(), f"Cache directory {cache_a_dir} must exist"
        print(f"[Proof 1] Version A snapshotted to cache: {cache_a_dir.name}")

        # Step C: Render Revision 2 while Version A is live
        rev2_stage, dir_a = await HyperFramesAdapter.stage_project_for_render(pid, revision=2)
        staged_comp_a = (dir_a / "compositions" / f"{cid}.html").read_text(encoding="utf-8")
        assert "VERSION_A_STATIC_MARKER" in staged_comp_a
        print(f"[Proof 1] Render staging 1 contains VERSION_A_STATIC_MARKER")

        # Step D: MUTATE LIVE REGISTRY TO VERSION B (Simulate upstream developer changing registry block)
        print("[Proof 1] Mutating live registry to Version B...")
        html_b = """<!DOCTYPE html>
<html>
<head><title>Closure Block V2</title></head>
<body>
<div id="composition" data-composition-id="closure-test-block" style="width: 1920px; height: 1080px; background: #ff0000; color: #ffffff;">
  <h1 id="txt" style="font-size: 80px;">VERSION_B_MUTATED_MARKER</h1>
</div>
<script>
  window.__timelines = window.__timelines || {};
  window.__timelines["closure-test-block"] = { duration: 2.0, play: function(){} };
</script>
</body>
</html>"""
        (live_block_dir / "index.html").write_text(html_b, encoding="utf-8")
        new_live_hash = RegistryAdapter.compute_block_hash(live_block_dir)
        assert new_live_hash != version_a_hash, "Mutated hash must be different"
        print(f"[Proof 1] Live registry mutated: new hash is {new_live_hash}")

        # Step E: RE-RENDER OLD REVISION 2
        # Must resolve to cached Version A, NOT mutated live Version B!
        print("[Proof 1] Re-rendering frozen Revision 2...")
        rev2_stage_after, dir_a_after = await HyperFramesAdapter.stage_project_for_render(pid, revision=2)
        staged_comp_after = (dir_a_after / "compositions" / f"{cid}.html").read_text(encoding="utf-8")
        
        assert "VERSION_A_STATIC_MARKER" in staged_comp_after, "Old revision must still have Version A marker!"
        assert "VERSION_B_MUTATED_MARKER" not in staged_comp_after, "Old revision must NOT leak Version B mutations!"
        print(f"[Proof 1] SUCCESS: Re-staged Revision 2 strictly preserved Version A from cache!")

        # Perform real Chromium render of old revision 2 to produce real MP4
        out_mp4_a = dir_a_after.parent / f"reproducibility_rev2_{cid}.mp4"
        mp4_path = await MotionRenderService.render_project(
            dir_a_after,
            aspect="16:9",
            fps=30,
            quality="draft",
            out_path=out_mp4_a,
            keep=True,
        )
        assert mp4_path.exists() and mp4_path.stat().st_size > 1000
        print(f"[Proof 1] SUCCESS: Real MP4 render of old revision completed ({mp4_path.stat().st_size} bytes)")

    finally:
        # Cleanup test block in registry
        if live_block_dir.exists():
            shutil.rmtree(live_block_dir)

    print("\n==================================================")
    print("STARTING CLOSURE PROOF 2: TWO SIMULTANEOUS INSTANCES IN ONE MP4")
    print("==================================================")
    
    # Create project with 2 simultaneous instances of the SAME block (lower-third-bild)
    proj2 = await ProjectService.create_project(name="Simultaneous Real MP4 Test", aspect_ratio="16:9")
    pid2 = proj2.id
    
    # Instance 1: "SPEAKER ONE"
    rev_inst1 = await ProjectService.apply_operation(
        project_id=pid2,
        expected_revision=1,
        operation_type="add_block",
        payload={
            "block_id": "lower-third-bild",
            "variables": {
                "TXT_MAIN_1_Line": "SPEAKER ONE (SIMULTANEOUS)",
                "TXT_SUB": "ROLE: LEAD RESEARCHER",
            },
            "start_seconds": 0.0,
            "duration_seconds": 2.0,
        },
        author="tester"
    )
    assert rev_inst1["revision"] == 2
    clip1 = [c for t in rev_inst1["document"]["timeline"]["tracks"] for c in t.get("clips", [])][0]
    id1 = clip1["id"]
    print(f"[Proof 2] Added instance 1: id={id1}")
    
    # Instance 2: "SPEAKER TWO" (Different track / graphics overlay, different variables)
    rev_inst2 = await ProjectService.apply_operation(
        project_id=pid2,
        expected_revision=2,
        operation_type="add_block",
        payload={
            "block_id": "lower-third-bild",
            "variables": {
                "TXT_MAIN_1_Line": "SPEAKER TWO (SIMULTANEOUS)",
                "TXT_SUB": "ROLE: LEAD ARCHITECT",
            },
            "start_seconds": 0.0,
            "duration_seconds": 2.0,
        },
        author="tester"
    )
    assert rev_inst2["revision"] == 3
    all_clips = [c for t in rev_inst2["document"]["timeline"]["tracks"] for c in t.get("clips", [])]
    assert len(all_clips) == 2
    clip2 = [c for c in all_clips if c["id"] != id1][0]
    id2 = clip2["id"]
    print(f"[Proof 2] Added instance 2: id={id2}")
    
    # Reload from SQLite database to guarantee durable state
    reloaded2 = await ProjectService.get_project(pid2)
    assert reloaded2.revision == 3
    doc2 = json.loads(reloaded2.document_json)
    reloaded_clips = [c for t in doc2["timeline"]["tracks"] for c in t.get("clips", [])]
    assert len(reloaded_clips) == 2
    print(f"[Proof 2] Reloaded from SQLite: verified 2 instances persisted")

    # Stage for render
    r_rev, stage_dir = await HyperFramesAdapter.stage_project_for_render(pid2, revision=3)
    index_html = (stage_dir / "index.html").read_text(encoding="utf-8")
    
    # Assert both subcompositions are mounted in index.html
    assert f'data-composition-id="{id1}"' in index_html or f'compositions/{id1}.html' in index_html
    assert f'data-composition-id="{id2}"' in index_html or f'compositions/{id2}.html' in index_html
    
    # Assert both composition files exist with isolated timelines
    c1_html = (stage_dir / "compositions" / f"{id1}.html").read_text(encoding="utf-8")
    c2_html = (stage_dir / "compositions" / f"{id2}.html").read_text(encoding="utf-8")
    assert f'window.__timelines["{id1}"]' in c1_html
    assert f'window.__timelines["{id2}"]' in c2_html
    assert "SPEAKER ONE" in c1_html
    assert "SPEAKER TWO" in c2_html
    print(f"[Proof 2] Staging verified: unique timeline keys window.__timelines['{id1}'] and window.__timelines['{id2}']")

    # Render ONE real MP4 containing BOTH simultaneous instances
    out_simult_mp4 = stage_dir.parent / f"simultaneous_dual_{id1}_{id2}.mp4"
    print(f"[Proof 2] Executing Chromium headless render for dual simultaneous instances...")
    mp4_result = await MotionRenderService.render_project(
        stage_dir,
        aspect="16:9",
        fps=30,
        quality="draft",
        out_path=out_simult_mp4,
        keep=True,
    )
    assert mp4_result.exists()
    size = mp4_result.stat().st_size
    assert size > 5000, f"MP4 file too small: {size} bytes"
    print(f"[Proof 2] Render succeeded: {out_simult_mp4.name} ({size} bytes)")

    # Forensic ffprobe check
    ff_cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,codec_name,r_frame_rate:format=duration",
        "-of", "json",
        str(out_simult_mp4)
    ]
    ff_proc = subprocess.run(ff_cmd, capture_output=True, text=True, check=True)
    probe = json.loads(ff_proc.stdout)
    stream = probe["streams"][0]
    assert stream["codec_name"] == "h264"
    assert int(stream["width"]) in [1920, 3840]
    assert int(stream["height"]) in [1080, 2160]
    assert float(probe["format"]["duration"]) >= 1.9
    print(f"[Proof 2] ffprobe PASS: codec={stream['codec_name']}, {stream['width']}x{stream['height']}, duration={probe['format']['duration']}s")
    
    print("\n>>> BOTH CLOSURE PROOFS 1 & 2 PASSED 100% <<<")

if __name__ == "__main__":
    asyncio.run(run_proofs())
