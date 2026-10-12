# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
6Clips Isolated Acceptance Verification:
Clip Studio Capability Audit & First Canonical /motion Integration

Tests:
1. Environment & Database Isolation (production DB 100% immutable).
2. Genuine Creator Media Assembly & Provenance.
3. Whisper Local Transcription with Word-level Timestamps & Quality Mapping.
4. AI Viral Scoring & Sentence Boundary Snapping.
5. Canonical ProjectService & CAS Optimistic Concurrency Control.
6. Track Lock Enforcement & Stale Revision Rejection.
7. Missing Media Strict Render Validation.
8. Verified 9:16 Render/Export to Playable MP4.
9. Final Byte-for-Byte SHA-256 Immutability Check.
"""
import asyncio
import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
import sys
from pathlib import Path
from uuid import uuid4

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("6clips_acceptance")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
PROD_DB_PATH = REPO_ROOT / "viralmint.db"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().upper()


async def generate_genuine_speech_narration(out_audio_path: Path) -> Path:
    """Generate genuine speech narration using offline local SpeechSynthesizer."""
    script_text = (
        "Watch this incredible gaming clutch play. In round fifteen, our entire squad was down "
        "and I had only ten health remaining. By staying calm and holding this exact angle, "
        "we took down three opponents in five seconds to secure the victory."
    )
    wav_path = out_audio_path.with_suffix(".wav")
    ps_cmd = f"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SetOutputToWaveFile('{str(wav_path).replace("\\", "\\\\")}')
$s.Speak('{script_text}')
$s.Dispose()
"""
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=True, capture_output=True)
    # Convert to standard 44.1kHz AAC/MP3
    cmd = ["ffmpeg", "-y", "-i", str(wav_path), "-c:a", "libmp3lame", "-b:a", "192k", "-ar", "44100", str(out_audio_path)]
    subprocess.run(cmd, check=True, capture_output=True)
    wav_path.unlink(missing_ok=True)
    return out_audio_path


def assemble_genuine_gaming_video(audio_path: Path, out_video_path: Path) -> Path:
    """Combine speech audio with a dynamic 1080x1920 video canvas using ffmpeg."""
    base_video = REPO_ROOT / "motion" / "studio" / "test_moving_video.mp4"
    assert base_video.exists(), f"Base video missing at {base_video}"

    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1",
        "-i", str(base_video),
        "-i", str(audio_path),
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
        "-shortest",
        str(out_video_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_video_path


async def run_full_acceptance():
    logger.info("=== 6CLIPS CLIP STUDIO & CANONICAL /motion INTEGRATION ACCEPTANCE ===")

    # 1. PREFLIGHT & ISOLATION
    assert PROD_DB_PATH.exists(), f"Production DB missing at {PROD_DB_PATH}"
    initial_db_sha256 = sha256_file(PROD_DB_PATH)
    logger.info(f"[PREFLIGHT] Production DB SHA-256: {initial_db_sha256}")

    sandbox_dir = Path(tempfile.mkdtemp(prefix="6clips-clipstudio-iso-"))
    # Point VIRALMINT_DATA_DIR to sandbox before importing backend modules
    os.environ["VIRALMINT_DATA_DIR"] = str(sandbox_dir)

    sandbox_db = sandbox_dir / "viralmint.db"
    shutil.copy2(PROD_DB_PATH, sandbox_db)

    sandbox_storage = sandbox_dir / "storage"
    sandbox_storage.mkdir(parents=True, exist_ok=True)
    sandbox_gen = sandbox_storage / "generated"
    sandbox_gen.mkdir(parents=True, exist_ok=True)
    sandbox_raw = sandbox_storage / "raw"
    sandbox_raw.mkdir(parents=True, exist_ok=True)
    sandbox_thumbs = sandbox_storage / "thumbnails"
    sandbox_thumbs.mkdir(parents=True, exist_ok=True)

    from backend.config import settings
    from backend.database import init_db, AsyncSessionLocal
    await init_db()

    results = {}

    # 2. GENUINE SOURCE MEDIA CREATION
    logger.info("\n--- Phase 2: Generating Authorized Creator Gaming Media ---")
    speech_path = sandbox_raw / "genuine_gaming_narration.mp3"
    await generate_genuine_speech_narration(speech_path)
    logger.info(f"Speech narration generated: {speech_path} ({speech_path.stat().st_size} bytes)")

    video_source_path = sandbox_raw / "genuine_gaming_clutch_source.mp4"
    assemble_genuine_gaming_video(speech_path, video_source_path)
    logger.info(f"Assembled gaming video: {video_source_path} ({video_source_path.stat().st_size} bytes)")

    # Probe media
    from backend.services.video_utils import probe_media
    w, h, duration = probe_media(video_source_path)
    logger.info(f"Probed video: {w}x{h}, duration={duration:.2f}s")
    assert w == 1080 and h == 1920, f"Expected 1080x1920, got {w}x{h}"
    assert duration > 10.0, f"Expected > 10s, got {duration}"
    results["media_assembly"] = {
        "status": "PASS",
        "path": str(video_source_path),
        "sha256": sha256_file(video_source_path),
        "dimensions": f"{w}x{h}",
        "duration": duration,
    }

    # 3. REGISTER SOURCE ASSET IN ISOLATED DB
    logger.info("\n--- Phase 3: Registering Authorized DownloadedVideo in Isolated DB ---")
    from backend.models.downloaded_video import DownloadedVideo
    from sqlalchemy import select

    video_id = f"gameplay-{uuid4().hex[:8]}"
    async with AsyncSessionLocal() as db:
        dv = DownloadedVideo(
            id=video_id,
            user_id="local",
            title="Pro Gaming Clutch Play 1v3",
            video_path=str(video_source_path),
            duration_seconds=int(round(duration)),
            platform="creator_gaming",
        )
        db.add(dv)
        await db.commit()
        await db.refresh(dv)
    logger.info(f"Registered DownloadedVideo in isolated DB: id={video_id}")
    results["asset_import"] = {"status": "PASS", "video_id": video_id}

    # 4. WHISPER LOCAL TRANSCRIPTION WITH TIMESTAMPS
    logger.info("\n--- Phase 4: Running Whisper Transcription ---")
    from backend.services.whisper_service import WhisperService, whisper_service, WHISPER_QUALITY_MAP
    assert WhisperService.is_model_cached("fast"), "Whisper 'fast' (base) model must be cached"
    logger.info(f"Whisper Quality Map verified: {WHISPER_QUALITY_MAP}")

    transcript_res = await whisper_service.transcribe(
        video_source_path,
        language="en",
        quality="fast",
    )
    segments = transcript_res.get("segments", [])
    full_text = transcript_res.get("text", "")
    detected_lang = transcript_res.get("language", "")
    logger.info(f"Transcription complete: {len(segments)} segments, lang={detected_lang}")
    logger.info(f"Full transcript: {full_text[:120]}...")

    assert len(segments) >= 2, f"Expected >= 2 segments, got {len(segments)}"
    first_seg = segments[0]
    assert "start" in first_seg and "end" in first_seg, "Segment must have start and end"
    assert "words" in first_seg and len(first_seg["words"]) > 0, "Segment must have word timestamps"
    assert "clutch" in full_text.lower() or "gaming" in full_text.lower() or "watch" in full_text.lower(), "Transcript must match spoken text"

    # Save transcript to DB row
    async with AsyncSessionLocal() as db:
        v_row = await db.get(DownloadedVideo, video_id)
        v_row.transcript_segments_json = json.dumps(segments)
        v_row.transcript = full_text
        v_row.transcript_language = detected_lang
        await db.commit()
    logger.info("Saved transcript segments to isolated DB")
    results["transcription"] = {
        "status": "PASS",
        "segment_count": len(segments),
        "language": detected_lang,
        "sample_text": full_text[:100],
        "has_word_timestamps": True,
    }

    # 5. REAL VIRAL SCORING & CANDIDATE EXTRACTION
    logger.info("\n--- Phase 5: Executing AI Viral Candidate Scoring & Boundary Snapping ---")
    from backend.services.executor_service import ExecutorService
    sugg_res, verif_res = await ExecutorService._execute_suggest_clips(
        payload={
            "video_id": f"dl:{video_id}",
            "max_clips": 3,
            "min_duration": 4.0,
            "max_duration": 15.0,
            "whisper_quality": "fast",
        },
        user_id="local",
    )
    suggestions = sugg_res.get("suggestions", [])
    logger.info(f"Generated {len(suggestions)} scored candidate highlights")
    assert len(suggestions) > 0, "Must return at least 1 candidate highlight"
    top_cand = suggestions[0]
    logger.info(f"Top Candidate: title='{top_cand['title']}' | score={top_cand['virality_score']} | hook={top_cand['hook_score']} ({top_cand['hook_type']}) | window={top_cand['start']}s -> {top_cand['end']}s (dur={top_cand['duration']}s)")
    assert top_cand["virality_score"] >= 1.0 and top_cand["virality_score"] <= 10.0, "Virality score must be in [1, 10]"
    assert "score_breakdown" in top_cand, "Must contain score_breakdown"
    breakdown = top_cand["score_breakdown"]
    for factor in ("flow", "value", "trend", "shareability"):
        assert factor in breakdown, f"Score breakdown missing factor: {factor}"
    assert top_cand["end"] > top_cand["start"], "End must be strictly greater than start"
    results["scoring"] = {
        "status": "PASS",
        "candidate_count": len(suggestions),
        "top_title": top_cand["title"],
        "virality_score": top_cand["virality_score"],
        "hook_score": top_cand["hook_score"],
        "hook_type": top_cand["hook_type"],
        "breakdown": breakdown,
        "provenance": top_cand.get("provenance"),
    }

    # 6. CANONICAL ProjectService & CAS CONCURRENCY CONTROL
    logger.info("\n--- Phase 6: Canonical ProjectService & CAS Verification ---")
    from backend.services.project_service import ProjectService
    from backend.core.exceptions import RevisionConflictError, ProjectError

    # Create empty project
    proj = await ProjectService.create_project(name="Gaming Shorts Vertical Highlight", aspect_ratio="9:16", user_id="local")
    logger.info(f"Created canonical project: id={proj.id}, revision={proj.revision}")
    assert proj.revision == 1, "Initial project revision must be 1"

    init_doc = json.loads(proj.document_json)
    clips_in_init = [c for t in init_doc.get("timeline", {}).get("tracks", []) for c in t.get("clips", [])]
    assert len(clips_in_init) == 0, f"Expected 0 clips in fresh project, got {len(clips_in_init)}"
    logger.info("Confirmed fresh project is genuinely empty (0 clips)")

    # CAS Conflict Test: wrong expected revision
    cas_failed = False
    try:
        await ProjectService.apply_operation(
            project_id=proj.id,
            expected_revision=999,  # Stale/invalid revision
            operation_type="add_clip",
            payload={"track_id": "track_video_main", "clip": {"id": "bad_clip"}},
            author="agent",
        )
    except RevisionConflictError:
        cas_failed = True
        logger.info("CAS correctly rejected stale expected_revision=999")
    assert cas_failed, "CAS must reject stale revision with RevisionConflictError"

    # Confirm revision remained unchanged
    proj_check = await ProjectService.get_project(proj.id)
    assert proj_check.revision == 1, f"Revision should remain 1 after rejected CAS, got {proj_check.revision}"

    # Valid CAS Step 1: Add Asset reference
    op_asset = await ProjectService.apply_operation(
        project_id=proj.id,
        expected_revision=1,
        operation_type="add_asset",
        payload={"asset": {
            "id": f"dl:{video_id}",
            "type": "downloaded",
            "title": "Pro Gaming Clutch Play 1v3",
            "video_path": str(video_source_path),
            "duration": duration,
        }},
        author="agent",
    )
    assert op_asset["revision"] == 2, f"Expected revision 2 after add_asset, got {op_asset['revision']}"
    logger.info("Added source media asset (rev 1 -> 2)")

    # Valid CAS Step 2: Add 9:16 Highlight Clip referencing original media with exact in/out offsets
    highlight_clip_id = f"clip_gaming_highlight_{uuid4().hex[:6]}"
    op_clip = await ProjectService.apply_operation(
        project_id=proj.id,
        expected_revision=2,
        operation_type="add_clip",
        payload={
            "track_id": "track_video_main",
            "clip": {
                "id": highlight_clip_id,
                "type": "video",
                "name": top_cand["title"],
                "asset_id": f"dl:{video_id}",
                "video_id": f"dl:{video_id}",
                "start_time": 0.0,
                "duration": top_cand["duration"],
                "source_in": top_cand["start"],
                "source_out": top_cand["end"],
                "virality_score": top_cand["virality_score"],
                "hook_type": top_cand["hook_type"],
            }
        },
        author="agent",
    )
    assert op_clip["revision"] == 3, f"Expected revision 3 after add_clip, got {op_clip['revision']}"
    logger.info(f"Inserted highlight clip into canonical timeline (rev 2 -> 3): in={top_cand['start']}s out={top_cand['end']}s dur={top_cand['duration']}s")

    # Verify document snapshot
    doc_rev3 = op_clip["document"]
    main_track = next((t for t in doc_rev3.get("timeline", {}).get("tracks", []) if t.get("id") == "track_video_main"), None)
    assert main_track and len(main_track.get("clips", [])) == 1, "Track must contain exactly 1 highlight clip"
    inserted_clip = main_track["clips"][0]
    assert inserted_clip["source_in"] == top_cand["start"], "source_in offset preserved"
    assert inserted_clip["source_out"] == top_cand["end"], "source_out offset preserved"
    assert inserted_clip["duration"] == top_cand["duration"], "clip duration preserved"
    results["project_service_cas"] = {
        "status": "PASS",
        "project_id": proj.id,
        "final_revision": op_clip["revision"],
        "inserted_clip_id": highlight_clip_id,
        "source_in": top_cand["start"],
        "source_out": top_cand["end"],
    }

    # 7. TRACK LOCK PROTECTION
    logger.info("\n--- Phase 7: Track Lock Enforcement ---")
    # Mutate track to locked=True
    await ProjectService.apply_operation(
        project_id=proj.id,
        expected_revision=3,
        operation_type="patch_document",
        payload={
            "patch": {
                "timeline": {
                    "tracks": [
                        {**main_track, "locked": True}
                    ]
                }
            }
        },
        author="user",
    )
    proj_locked = await ProjectService.get_project(proj.id)
    assert proj_locked.revision == 4

    lock_rejection = False
    try:
        await ProjectService.apply_operation(
            project_id=proj.id,
            expected_revision=4,
            operation_type="add_clip",
            payload={"track_id": "track_video_main", "clip": {"id": "illegal_locked_clip"}},
            author="agent",
        )
    except ProjectError as pe:
        if "locked" in str(pe).lower():
            lock_rejection = True
            logger.info(f"Track lock correctly rejected mutation: {pe}")
    assert lock_rejection, "Must reject clip insertion into locked track"

    # Unlock track
    await ProjectService.apply_operation(
        project_id=proj.id,
        expected_revision=4,
        operation_type="patch_document",
        payload={
            "patch": {
                "timeline": {
                    "tracks": [
                        {**main_track, "locked": False}
                    ]
                }
            }
        },
        author="user",
    )
    proj_unlocked = await ProjectService.get_project(proj.id)
    assert proj_unlocked.revision == 5
    results["track_lock"] = {"status": "PASS", "enforced": True}

    # 8. STAGING & HYPERFRAMES COMPOSITION HTML
    logger.info("\n--- Phase 8: Staging & Composition Generation ---")
    from backend.services.hyperframes_adapter import HyperFramesAdapter
    from backend.services.studio_service import StudioService

    curr_doc = json.loads(proj_unlocked.document_json)
    stage_dir = sandbox_storage / "motion_studio_staging" / proj.id
    stage_dir.mkdir(parents=True, exist_ok=True)

    composition_html = HyperFramesAdapter.project_doc_to_html(curr_doc)
    (stage_dir / "index.html").write_text(composition_html, encoding="utf-8")
    logger.info(f"Generated composition HTML: {len(composition_html)} bytes")
    assert "<video" in composition_html, "Composition HTML must contain <video> element"
    assert f'data-media-start="{top_cand["start"]}"' in composition_html or f'data-playback-start="{top_cand["start"]}"' in composition_html, "HTML must bind playback start offset"
    results["html_composition"] = {"status": "PASS", "html_bytes": len(composition_html)}

    # 9. STRICT RENDER VALIDATION FOR MISSING MEDIA
    logger.info("\n--- Phase 9: Strict Render Validation for Missing Media ---")
    from backend.services.motion_render_service import MotionRenderService

    # Create project with deliberately missing media reference
    corrupt_proj = await ProjectService.create_project(name="Corrupt Media Test", aspect_ratio="9:16", user_id="local")
    await ProjectService.apply_operation(
        project_id=corrupt_proj.id,
        expected_revision=1,
        operation_type="add_clip",
        payload={
            "track_id": "track_video_main",
            "clip": {
                "id": "missing_media_clip",
                "type": "video",
                "asset_id": "dl:nonexistent-media-file-999",
                "video_id": "dl:nonexistent-media-file-999",
                "start_time": 0.0,
                "duration": 5.0,
            }
        },
        author="agent",
    )
    corrupt_rev2 = await ProjectService.get_project(corrupt_proj.id)

    render_rejected = False
    try:
        await MotionRenderService.render_project(
            project_id=corrupt_proj.id,
            revision=corrupt_rev2.revision,
            user_id="local",
        )
    except Exception as re_err:
        render_rejected = True
        logger.info(f"Render pipeline strictly rejected missing media: {re_err}")
    assert render_rejected, "Render pipeline MUST strictly reject missing media assets"
    results["missing_media_strict_check"] = {"status": "PASS", "rejected_correctly": True}

    # 10. VERIFIED RENDER/EXPORT OF VALID PROJECT
    logger.info("\n--- Phase 10: Executing Verified Render/Export of Valid Project ---")
    render_job = await MotionRenderService.render_project(
        project_id=proj.id,
        revision=proj_unlocked.revision,
        user_id="local",
    )
    logger.info(f"Render job completed: {render_job}")
    output_mp4_path = Path(render_job["video_path"])
    assert output_mp4_path.exists(), f"Rendered MP4 file missing at {output_mp4_path}"
    out_size = output_mp4_path.stat().st_size
    assert out_size > 50000, f"Rendered MP4 file too small: {out_size} bytes"

    out_w, out_h, out_dur = probe_media(output_mp4_path)
    logger.info(f"Verified Render Output: {output_mp4_path} ({out_size} bytes, {out_w}x{out_h}, {out_dur:.2f}s)")
    assert out_w == 1080 and out_h == 1920, f"Expected 1080x1920 9:16 export, got {out_w}x{out_h}"
    results["verified_render_export"] = {
        "status": "PASS",
        "output_path": str(output_mp4_path),
        "size_bytes": out_size,
        "resolution": f"{out_w}x{out_h}",
        "duration": out_dur,
    }

    # 11. FINAL PRODUCTION DATABASE IMMUTABILITY CHECK
    logger.info("\n--- Phase 11: Production Database SHA-256 Immutability Check ---")
    final_db_sha256 = sha256_file(PROD_DB_PATH)
    logger.info(f"Initial DB SHA-256: {initial_db_sha256}")
    logger.info(f"Final DB SHA-256:   {final_db_sha256}")
    assert final_db_sha256 == initial_db_sha256, (
        f"CRITICAL TEST ISOLATION FAILURE: Production DB was mutated!\n"
        f"Before: {initial_db_sha256}\nAfter:  {final_db_sha256}"
    )
    results["db_immutability"] = {
        "status": "PASS",
        "sha256_before": initial_db_sha256,
        "sha256_after": final_db_sha256,
        "identical": True,
    }

    # Clean up sandbox
    try:
        shutil.rmtree(sandbox_dir, ignore_errors=True)
    except Exception:
        pass

    logger.info("\n=== ALL ISOLATED ACCEPTANCE GATES PASSED CLEANLY ===")
    print(json.dumps(results, indent=2))
    return results


if __name__ == "__main__":
    asyncio.run(run_full_acceptance())
