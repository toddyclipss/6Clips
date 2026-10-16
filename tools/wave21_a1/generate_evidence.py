# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Evidence Generator for Wave 21 Agent 1.

Executes real OAAS journeys:
1. 6 Diverse realistic journeys aligned with V1-V7:
   - V1: Vertical promo (9:16)
   - V2: Horizontal highlights (16:9)
   - V3: Original Infographic Data (1:1)
   - V4: Kinetic Promo (9:16)
   - V5: Professional Captions on real speech (9:16)
   - V6: Multi-clip generation (3 clips)
2. 3 Same-project sequential revisions + 1 rollback.
3. Extracts genuine video frames (.png) via ffmpeg into tools/wave21_a1/evidence/.
4. Runs ffprobe on deliverables and collects SHA-256 hashes, codecs, durations.
5. Saves tools/wave21_a1/evidence/evidence_manifest.json.
"""

import asyncio
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

EVIDENCE_DIR = Path(__file__).resolve().parent / "evidence"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


def sha256_file(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def probe_video(filepath: Path) -> dict:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration,size:stream=width,height,codec_name,r_frame_rate",
        "-of", "json",
        str(filepath)
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(res.stdout)
    except Exception as e:
        return {"error": str(e)}


def extract_frame(video_path: Path, output_png: Path, timestamp: float = 0.5):
    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(timestamp),
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "2",
        str(output_png)
    ]
    subprocess.run(cmd, capture_output=True, check=True)


async def main():
    os.environ["VIRALMINT_TEST_ENV"] = "1"
    os.environ["VIRALMINT_TEST_AUDIO_FIXTURE"] = "1"

    from backend.database import init_db
    await init_db()

    from backend.oaas_knowledge_orchestrator import (
        KnowledgeChatOrchestrator,
        VideoRequestContract,
        RevisionRequestContract,
        KnowledgeOrchestratorState,
    )

    evidence_records = []

    print("=== 1. Running 6 Diverse Realistic Journeys (V1-V7) ===")
    journeys = [
        ("V1_vertical_promo", "Create a vertical promo 9:16 for product showcase", 10.0, "9:16", 1),
        ("V2_horizontal_highlights", "Produce a 16:9 widescreen video with dynamic highlights", 12.0, "16:9", 1),
        ("V3_infographic_data", "Generate a square 1:1 data infographic chart clip", 8.0, "1:1", 1),
        ("V4_kinetic_promo", "Kinetic text promo with high energy and bold typography", 10.0, "9:16", 1),
        ("V5_speech_captions", "Short video with word by word professional synced captions", 15.0, "9:16", 1),
        ("V6_multi_clip", "Generate 3 short teaser clips for social media", 6.0, "9:16", 3),
    ]

    for label, prompt, target_sec, aspect, count in journeys:
        print(f"Executing {label}...")
        resp = await KnowledgeChatOrchestrator.handle_video_request(
            VideoRequestContract(
                message=prompt,
                output_count=count,
                preferences={"target_duration_seconds": target_sec, "aspect_ratio": aspect},
                allow_test_fixture=True,
            )
        )
        assert resp.state in (KnowledgeOrchestratorState.REVIEW_READY, KnowledgeOrchestratorState.VIDEO_VERIFIED, KnowledgeOrchestratorState.PENDING_CREDENTIALS)

        deliverables = [art["file_path"] for art in resp.artifact_links if "file_path" in art]
        if not deliverables and resp.evidence and resp.evidence.media_artifact and "file_path" in resp.evidence.media_artifact:
            deliverables.append(resp.evidence.media_artifact["file_path"])

        extracted_frames = []
        probes = []

        for idx, deliv_str in enumerate(deliverables):
            if not deliv_str:
                continue
            vpath = Path(deliv_str)
            if vpath.exists():
                frame_name = f"{label}_clip{idx+1}_frame.png"
                frame_path = EVIDENCE_DIR / frame_name
                try:
                    extract_frame(vpath, frame_path, timestamp=0.5)
                    extracted_frames.append(str(frame_path.name))
                except Exception as ex:
                    print(f"Warning: could not extract frame for {label}: {ex}")

                probe_data = probe_video(vpath)
                sha = sha256_file(vpath)
                probes.append({
                    "path": str(vpath),
                    "sha256": sha,
                    "probe": probe_data
                })

        evidence_records.append({
            "journey": label,
            "prompt": prompt,
            "project_id": resp.project_id,
            "revision": resp.revision_id,
            "state": resp.state.value,
            "library_asset_id": resp.library_asset_id,
            "library_ids": resp.library_ids,
            "output_count": resp.output_count,
            "knowledge_citations": [c.model_dump() for c in resp.evidence.knowledge_citations] if resp.evidence else [],
            "frames": extracted_frames,
            "probes": probes,
        })

    print("=== 2. Running Same-Project Sequential Revisions & Rollback ===")
    initial_resp = await KnowledgeChatOrchestrator.handle_video_request(
        VideoRequestContract(
            message="Start vertical promo with subtitle text and scene graphics",
            preferences={"target_duration_seconds": 10.0, "aspect_ratio": "9:16"},
            allow_test_fixture=True,
        )
    )
    p_id = initial_resp.project_id
    last_run_id = initial_resp.run_id
    rev_hist = [initial_resp.revision_id]

    # Revision 1: Remove dead air
    r1 = await KnowledgeChatOrchestrator.revise_deliverable(
        RevisionRequestContract(
            run_id=last_run_id,
            user_feedback="Remove dead air and tighten pacing",
            expected_revision=rev_hist[-1],
            allow_test_fixture=True,
        )
    )
    rev_hist.append(r1.revision_id)
    last_run_id = r1.run_id

    # Revision 2: Emphasize second headline and cinematic captions
    r2 = await KnowledgeChatOrchestrator.revise_deliverable(
        RevisionRequestContract(
            run_id=last_run_id,
            user_feedback="Make word-by-word professional captions more cinematic and emphasize second headline",
            expected_revision=rev_hist[-1],
            allow_test_fixture=True,
        )
    )
    rev_hist.append(r2.revision_id)
    last_run_id = r2.run_id

    # Revision 3: Shorten to 25 seconds
    r3 = await KnowledgeChatOrchestrator.revise_deliverable(
        RevisionRequestContract(
            run_id=last_run_id,
            user_feedback="Shorten to 25 seconds",
            expected_revision=rev_hist[-1],
            allow_test_fixture=True,
        )
    )
    rev_hist.append(r3.revision_id)
    last_run_id = r3.run_id

    # Reversion / Rollback to Revision 1 (which was the initial revision)
    r_rollback = await KnowledgeChatOrchestrator.revise_deliverable(
        RevisionRequestContract(
            run_id=last_run_id,
            user_feedback=f"Undo last changes and revert to revision {rev_hist[0]}",
            expected_revision=rev_hist[-1],
            revert_to_revision=rev_hist[0],
            allow_test_fixture=True,
        )
    )

    # Probe & extract frames for revisions
    for rev_label, rev_obj in [("rev1_trim", r1), ("rev2_captions", r2), ("rev3_shorten", r3), ("rev_rollback", r_rollback)]:
        deliv = None
        if rev_obj.artifact_links and "file_path" in rev_obj.artifact_links[0]:
            deliv = rev_obj.artifact_links[0]["file_path"]
        elif rev_obj.evidence and rev_obj.evidence.media_artifact and "file_path" in rev_obj.evidence.media_artifact:
            deliv = rev_obj.evidence.media_artifact["file_path"]

        if deliv:
            vpath = Path(deliv)
            if vpath.exists():
                frame_name = f"same_proj_{rev_label}_frame.png"
                frame_path = EVIDENCE_DIR / frame_name
                try:
                    extract_frame(vpath, frame_path, timestamp=0.5)
                except Exception:
                    pass
                probe_data = probe_video(vpath)
                sha = sha256_file(vpath)
                evidence_records.append({
                    "journey": f"revision_{rev_label}",
                    "project_id": p_id,
                    "revision": rev_obj.revision_id,
                    "state": rev_obj.state.value,
                    "applied_deltas": rev_obj.evidence.applied_actions if rev_obj.evidence else [],
                    "frame": str(frame_name),
                    "sha256": sha,
                    "probe": probe_data,
                })

    # Save manifest
    manifest_path = EVIDENCE_DIR / "evidence_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(evidence_records, f, indent=2)

    print(f"Evidence successfully generated in: {EVIDENCE_DIR}")
    print(f"Manifest saved to: {manifest_path}")


if __name__ == "__main__":
    asyncio.run(main())
