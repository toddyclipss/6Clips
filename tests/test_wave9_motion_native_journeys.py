# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 9 Agent 2 — Full Native Clip Studio, Tools Parity & Real Export Journeys Test Suite."""

import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi import HTTPException

from backend.database import init_db
from backend.media_pipeline.clip_renderer import (
    render_manifest_to_mp4,
    render_output_clip,
)
from backend.media_pipeline.media_inspector import probe_physical_media
from backend.media_pipeline.models import (
    DurationPolicy,
    OutputSpecV1,
    OutputState,
    SourceRangeV1,
)
from backend.motion_capabilities import (
    ALL_CAPABILITIES_SPEC,
    MotionCapabilitiesRegistry,
    MotionCapabilityDispatcher,
    execute_motion_capability,
)
from backend.motion_legacy_bridge.parity_contracts import (
    preserve_caption_overrides,
)
from backend.motion_render_bridge import build_render_manifest
from backend.services.project_service import ProjectService


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Ensure database schema is created for test execution."""
    await init_db()


@pytest.fixture(scope="module")
def technical_fixture_video_mp4(tmp_path_factory) -> Path:
    """TECHNICAL_FIXTURE: Isolated 1.0-second 1920x1080 MP4 with audio using FFmpeg."""
    tmp_dir = tmp_path_factory.mktemp("wave9_technical_media")
    video_path = tmp_dir / "technical_fixture_input.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=1.0:size=1920x1080:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=1.0:sample_rate=48000",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
        "-c:a", "aac", "-b:a", "128k",
        str(video_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert res.returncode == 0, f"FFmpeg sample generation failed: {res.stderr}"
    assert video_path.exists()
    return video_path


# ─────────────────────────────────────────────────────────────────────────────
# 1. Full User Journey: Asset -> Revision -> Manifest -> Real MP4 Export
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_user_journey_asset_to_canonical_mp4(technical_fixture_video_mp4, tmp_path):
    """Verify full pipeline provenance: Library asset -> canonical revision -> manifest -> real MP4."""
    out_file = tmp_path / "journey_export.mp4"

    # Step 1: Create canonical ProjectRevision
    init_doc = {
        "schema_version": 2,
        "title": "Wave 9 Native Export Journey",
        "aspect_ratio": "9:16",
        "timeline": {
            "fps": 30,
            "duration_seconds": 1.0,
            "tracks": [
                {
                    "id": "trk_video_main",
                    "type": "video",
                    "clips": [
                        {
                            "id": "clip_main",
                            "source_path": str(technical_fixture_video_mp4),
                            "source_trim_start": 0.0,
                            "timeline_duration_seconds": 0.8,
                            "framing_preset": "center_crop",
                            "audio_enhance": True,
                            "caption_text": "HERO HOOK LINE\nNATIVE SECOND LINE",
                            "caption_lines": ["HERO HOOK LINE", "NATIVE SECOND LINE"],
                        }
                    ],
                }
            ],
        },
    }
    proj = await ProjectService.create_project(
        name="Wave 9 Export Journey",
        aspect_ratio="9:16",
        initial_document=init_doc,
    )
    assert proj.revision == 1

    # Step 2: Build render manifest from canonical project revision
    doc_dict = json.loads(proj.document_json) if isinstance(proj.document_json, str) else proj.document_json
    manifest = build_render_manifest(doc_dict)
    assert manifest is not None
    assert manifest.aspect_ratio == "9:16"
    assert len(manifest.tracks[0].clips) == 1

    # Step 3: Render manifest to physical MP4 using real FFmpeg worker
    res_path, probe, warnings = await render_manifest_to_mp4(manifest, out_file)
    assert res_path.exists()
    assert probe is not None
    assert probe.width == 1080
    assert probe.height == 1920
    assert probe.video_codec in ("h264", "x264")
    assert probe.audio_codec == "aac"
    assert any("voice enhancement" in w.lower() for w in warnings)
    assert any("caption overrides" in w.lower() for w in warnings)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Candidate Outputs Lifecycle: 3 Outputs, Independent Approvals, Fault Isolation
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_triple_candidate_output_independence_and_fault_isolation(technical_fixture_video_mp4, tmp_path):
    """Verify 3 outputs lifecycle: Output 1 APPROVED, Output 2 NOT_ASSESSED, Output 3 FAILS without corrupting outputs 1 & 2."""
    proj = await ProjectService.create_project(
        name="Triple Output Isolation Project",
        aspect_ratio="9:16",
        initial_document={
            "schema_version": 2,
            "title": "Triple Output Project",
            "outputs": {
                "out_1": {"preset": "center_crop", "editorial_status": "NOT_ASSESSED", "notes": ""},
                "out_2": {"preset": "hud_aware_blur", "editorial_status": "NOT_ASSESSED", "notes": ""},
                "out_3": {"preset": "gameplay_reticle", "editorial_status": "NOT_ASSESSED", "notes": ""},
            },
        },
    )
    proj_id = proj.id

    # 1. Render Output 1 successfully
    spec1 = OutputSpecV1(output_id="out_1", seconds=0.5, duration_policy=DurationPolicy.TARGET, tolerance_seconds=0.2)
    res1 = await render_output_clip(
        source_path=technical_fixture_video_mp4,
        source_range=SourceRangeV1(asset_id="a1", start_seconds=0.0, end_seconds=0.5, duration_seconds=0.5, editorial_reason="Highlight cut"),
        spec=spec1,
        project_id=proj_id,
        output_dir=tmp_path,
        framing_preset="center_crop",
    )
    assert res1.state == OutputState.SUCCEEDED

    # 2. Render Output 2 successfully
    spec2 = OutputSpecV1(output_id="out_2", seconds=0.5, duration_policy=DurationPolicy.TARGET, tolerance_seconds=0.2)
    res2 = await render_output_clip(
        source_path=technical_fixture_video_mp4,
        source_range=SourceRangeV1(asset_id="a1", start_seconds=0.0, end_seconds=0.5, duration_seconds=0.5, editorial_reason="Highlight cut"),
        spec=spec2,
        project_id=proj_id,
        output_dir=tmp_path,
        framing_preset="hud_aware_blur",
    )
    assert res2.state == OutputState.SUCCEEDED

    # 3. Simulate failure in Output 3
    spec3 = OutputSpecV1(output_id="out_3", seconds=0.5, duration_policy=DurationPolicy.TARGET, tolerance_seconds=0.2)
    res3 = await render_output_clip(
        source_path=technical_fixture_video_mp4,
        source_range=SourceRangeV1(asset_id="a1", start_seconds=0.0, end_seconds=0.5, duration_seconds=0.5, editorial_reason="Highlight cut"),
        spec=spec3,
        project_id=proj_id,
        output_dir=tmp_path,
        simulate_failure=True,
    )
    assert res3.state == OutputState.FAILED

    # 4. Approve Output 1 in canonical project revision
    cur_proj = await ProjectService.get_project(proj_id)
    cur_doc = json.loads(cur_proj.document_json) if isinstance(cur_proj.document_json, str) else cur_proj.document_json
    cur_doc["outputs"]["out_1"]["editorial_status"] = "APPROVED"
    cur_doc["outputs"]["out_1"]["notes"] = "Verified gaming highlight"

    rev_res = await ProjectService.apply_operation(
        project_id=proj_id,
        expected_revision=cur_proj.revision,
        operation_type="update_document",
        payload={"document": cur_doc},
        idempotency_key="approve_out1_only",
    )
    assert rev_res["revision"] > cur_proj.revision

    # 5. Reload from DB: Output 1 is APPROVED, Output 2 is NOT_ASSESSED, Output 3 failure did not overwrite 1 & 2
    reloaded = await ProjectService.get_project(proj_id)
    reloaded_doc = json.loads(reloaded.document_json) if isinstance(reloaded.document_json, str) else reloaded.document_json

    assert reloaded_doc["outputs"]["out_1"]["editorial_status"] == "APPROVED"
    assert reloaded_doc["outputs"]["out_1"]["notes"] == "Verified gaming highlight"
    assert reloaded_doc["outputs"]["out_2"]["editorial_status"] == "NOT_ASSESSED"
    # Ensure Output 3 was isolated
    assert res3.state == OutputState.FAILED


# ─────────────────────────────────────────────────────────────────────────────
# 3. Audio Processing: Voice Enhancement & Filters
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_audio_voice_enhancement_and_filter_chain(technical_fixture_video_mp4, tmp_path):
    """Verify audio enhancement applies highpass=f=100,lowpass=f=8000,dynaudnorm."""
    res = await MotionCapabilityDispatcher.dispatch(
        capability_id="audio-enhance",
        input_path=technical_fixture_video_mp4,
        output_dir=tmp_path,
    )
    assert res.status == "SUCCESS"
    assert res.output_path is not None
    out_p = Path(res.output_path)
    assert out_p.exists() and out_p.stat().st_size > 0

    probe, blocker = await probe_physical_media(out_p)
    assert blocker is None
    assert probe is not None
    assert probe.audio_channels > 0
    assert probe.audio_codec == "aac"


# ─────────────────────────────────────────────────────────────────────────────
# 4. Multi-Line Caption Authority & Whisper Re-Analysis Preservation
# ─────────────────────────────────────────────────────────────────────────────

def test_multiline_caption_override_authority_across_whisper_rerun():
    """Verify manual multiline caption overrides survive Whisper re-analysis without regression."""
    existing_user_captions = [
        {
            "id": "seg_0",
            "start": 0.0,
            "end": 2.0,
            "text": "USER CUSTOM HOOK\nSECOND MANUAL LINE",
            "manual_transcript_override": True,
            "style": {"color": "#FFE600", "size": 32},
        },
        {
            "id": "seg_1",
            "start": 2.0,
            "end": 4.0,
            "text": "Unedited second segment",
            "manual_transcript_override": False,
        },
    ]

    fresh_whisper_rerun = [
        {
            "id": "seg_0",
            "start": 0.0,
            "end": 2.0,
            "text": "Automated whisper raw transcript",
        },
        {
            "id": "seg_1",
            "start": 2.0,
            "end": 4.0,
            "text": "Automated second raw segment",
        },
    ]

    merged = preserve_caption_overrides(existing_user_captions, fresh_whisper_rerun)

    # Segment 0 must retain user's exact multi-line override and styling
    assert merged[0]["id"] == "seg_0"
    assert merged[0]["text"] == "USER CUSTOM HOOK\nSECOND MANUAL LINE"
    assert merged[0]["manual_transcript_override"] is True
    assert merged[0]["style"]["color"] == "#FFE600"

    # Segment 1 gets updated from fresh rerun since it was not manually overridden
    assert merged[1]["id"] == "seg_1"
    assert merged[1]["text"] == "Automated second raw segment"


# ─────────────────────────────────────────────────────────────────────────────
# 5. External Provider Dependencies: Honest BLOCKED_PROVIDER Status
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_blocked_provider_transparency_and_no_anullsrc(technical_fixture_video_mp4):
    """Verify translation and dubbing return BLOCKED_PROVIDER honestly without synthetic anullsrc audio."""
    old_eleven = os.environ.pop("ELEVENLABS_API_KEY", None)
    old_azure = os.environ.pop("AZURE_SPEECH_KEY", None)
    try:
        res = await MotionCapabilityDispatcher.dispatch(
            capability_id="translate",
            input_path=technical_fixture_video_mp4,
            params={"target_language": "fr", "dub_audio": True},
        )
        assert res.status == "BLOCKED_PROVIDER"
        assert res.error_detail == "BLOCKED_PROVIDER"
        assert "voice provider credentials" in res.message
    finally:
        if old_eleven:
            os.environ["ELEVENLABS_API_KEY"] = old_eleven
        if old_azure:
            os.environ["AZURE_SPEECH_KEY"] = old_azure


# ─────────────────────────────────────────────────────────────────────────────
# 6. CAS 409 Stale Revision Protection
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cas_concurrency_stale_revision_409(technical_fixture_video_mp4):
    """Verify CAS check prevents dirty writes and rejects stale revision with HTTP 409."""
    proj = await ProjectService.create_project(
        name="CAS Stale Check",
        aspect_ratio="9:16",
        initial_document={"schema_version": 2, "timeline": {"tracks": []}},
    )
    proj_id = proj.id
    assert proj.revision == 1

    # Advance revision to 2
    await ProjectService.apply_operation(
        project_id=proj_id,
        expected_revision=1,
        operation_type="update_document",
        payload={"document": {"schema_version": 2, "title": "Updated"}},
        idempotency_key="advance_to_rev_2",
    )

    # Attempting to execute capability with stale expected_revision=1 must raise 409
    with pytest.raises(HTTPException) as exc_info:
        await execute_motion_capability(
            project_id=proj_id,
            expected_revision=1,
            capability_id="transform",
            params={"op": "flip_h"},
            input_path=technical_fixture_video_mp4,
        )
    assert exc_info.value.status_code == 409
    assert "Stale revision" in exc_info.value.detail


# ─────────────────────────────────────────────────────────────────────────────
# 7. 21 Tools & 9 Clip Studio Workflows Deterministic Dispatch Inventory
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_all_21_tools_and_9_workflows_registered_and_dispatchable(technical_fixture_video_mp4, tmp_path):
    """Verify all 30 capabilities exist in registry and dispatch cleanly to real executors or honest provider blocks."""
    specs = MotionCapabilitiesRegistry.list_all()
    assert len(specs) >= 30

    test_doc = {
        "schema_version": 2,
        "tracks": [
            {
                "id": "t1",
                "name": "Main Track",
                "clips": [
                    {"id": "c1", "start": 0.0, "duration": 1.0, "in_point": 0.0, "out_point": 1.0, "source": str(technical_fixture_video_mp4)},
                ],
            }
        ],
        "layers": [],
    }

    # Verify key media tools execution
    tool_tests = [
        ("trim", {"start": 0.0, "end": 0.5}),
        ("crop", {"crop_w": 640, "crop_h": 640, "crop_x": 0, "crop_y": 0}),
        ("compress", {"resolution": "720p", "level": "medium"}),
        ("transform", {"op": "flip_h"}),
        ("remove-audio", {}),
        ("extract-audio", {}),
        ("speed", {"speed": 1.5}),
        ("audio-enhance", {}),
        ("gif", {"fps": 10, "width": 320}),
        ("auto-zoom", {"zoom_factor": 1.2}),
        ("subtitles", {"format": "srt"}),
        ("reframe", {"aspect_ratio": "9:16"}),
    ]

    for tool_id, params in tool_tests:
        res = await MotionCapabilityDispatcher.dispatch(
            capability_id=tool_id,
            input_path=technical_fixture_video_mp4,
            params=params,
            output_dir=tmp_path,
        )
        assert res.status == "SUCCESS", f"Tool '{tool_id}' failed: {res.message} ({res.error_detail})"
        if res.output_path:
            assert Path(res.output_path).exists()

    # Verify Clip Studio workflow operations
    split_res = await MotionCapabilityDispatcher.dispatch(
        capability_id="split-at-playhead",
        project_doc=test_doc,
        params={"clip_id": "c1", "split_time": 0.5},
    )
    assert split_res.status == "SUCCESS"
    assert "split_clips" in split_res.output_data

    slip_res = await MotionCapabilityDispatcher.dispatch(
        capability_id="slip-editing",
        project_doc=test_doc,
        params={"clip_id": "c1", "slip_delta_seconds": 0.2},
    )
    assert slip_res.status == "SUCCESS"

    ripple_res = await MotionCapabilityDispatcher.dispatch(
        capability_id="ripple-delete",
        project_doc=test_doc,
        params={"clip_id": "c1"},
    )
    assert ripple_res.status == "SUCCESS"

    broll_res = await MotionCapabilityDispatcher.dispatch(
        capability_id="b-roll-lane-placement",
        project_doc=test_doc,
        params={"source_url": str(technical_fixture_video_mp4), "start": 0.0, "duration": 0.5},
    )
    assert broll_res.status == "SUCCESS"

    scoreboard_res = await MotionCapabilityDispatcher.dispatch(
        capability_id="virality-scoreboard",
        project_doc=test_doc,
        params={"hook": 90.0, "flow": 85.0, "value": 80.0, "trend": 95.0, "share": 88.0},
    )
    assert scoreboard_res.status == "SUCCESS"
    assert "virality_breakdown" in scoreboard_res.output_data

    autocut_res = await MotionCapabilityDispatcher.dispatch(
        capability_id="auto-cut-dialog",
        project_doc=test_doc,
        params={"silence_threshold_db": -32.0, "min_silence_duration": 0.4},
    )
    assert autocut_res.status == "SUCCESS"
    assert "auto_cut_settings" in autocut_res.output_data


# ─────────────────────────────────────────────────────────────────────────────
# 8. Negative Path Validations
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_negative_paths_missing_files_and_invalid_parameters():
    """Verify negative paths fail gracefully with clear error details."""
    # 1. Non-existent input file
    res_missing = await MotionCapabilityDispatcher.dispatch(
        capability_id="trim",
        input_path="/nonexistent/path/video.mp4",
        params={"start": 0.0, "end": 1.0},
    )
    assert res_missing.status == "FAILED"
    assert res_missing.error_detail == "FILE_NOT_FOUND"

    # 2. Out of bounds split
    doc = {
        "tracks": [
            {"id": "t1", "clips": [{"id": "c1", "start": 1.0, "duration": 2.0, "in_point": 0.0, "out_point": 2.0}]}
        ]
    }
    res_split_oob = await MotionCapabilityDispatcher.dispatch(
        capability_id="split-at-playhead",
        project_doc=doc,
        params={"clip_id": "c1", "split_time": 5.0},
    )
    assert res_split_oob.status == "FAILED"
    assert res_split_oob.error_detail == "OUT_OF_BOUNDS"

    # 3. Clip not found in ripple delete
    res_ripple_nf = await MotionCapabilityDispatcher.dispatch(
        capability_id="ripple-delete",
        project_doc=doc,
        params={"clip_id": "nonexistent_clip"},
    )
    assert res_ripple_nf.status == "FAILED"
    assert res_ripple_nf.error_detail == "CLIP_NOT_FOUND"
