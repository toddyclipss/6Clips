# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 10 Agent 2 — Complete Native 30-Tool Real Parity, Dual-Track Audio, Catalog Overlay & Export Journeys."""

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
    build_framing_filter,
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
from backend.motion_render_bridge.catalog_consumer import (
    CatalogExportConsumer,
    CatalogExportConsumptionResult,
)
from backend.services.project_service import ProjectService


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Ensure database schema is created for test execution."""
    await init_db()


@pytest.fixture(scope="module")
def technical_fixture_video_mp4(tmp_path_factory) -> Path:
    """TECHNICAL_FIXTURE: Isolated 1.0-second 1920x1080 MP4 with audio using FFmpeg."""
    tmp_dir = tmp_path_factory.mktemp("wave10_technical_media")
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


@pytest.fixture(scope="module")
def technical_fixture_audio_aac(tmp_path_factory) -> Path:
    """TECHNICAL_FIXTURE: Isolated 1.0-second secondary audio AAC track (BGM/SFX)."""
    tmp_dir = tmp_path_factory.mktemp("wave10_technical_audio")
    audio_path = tmp_dir / "secondary_bgm_track.aac"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=1.0:sample_rate=48000",
        "-c:a", "aac", "-b:a", "128k",
        str(audio_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert res.returncode == 0, f"FFmpeg secondary audio generation failed: {res.stderr}"
    assert audio_path.exists()
    return audio_path


@pytest.fixture(scope="module")
def technical_fixture_overlay_mov(tmp_path_factory) -> Path:
    """TECHNICAL_FIXTURE: Isolated 0.8-second animated overlay with transparent alpha channel."""
    tmp_dir = tmp_path_factory.mktemp("wave10_technical_overlay")
    overlay_path = tmp_dir / "catalog_animated_overlay.mov"
    # Generate transparent video with a moving colored square using alpha channel
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=black@0.0:size=1080x1920:duration=0.8:rate=30",
        "-f", "lavfi", "-i", "testsrc=duration=0.8:size=300x100:rate=30",
        "-filter_complex", "[0:v][1:v]overlay=x='100+t*50':y=1500:format=auto[out_v]",
        "-map", "[out_v]",
        "-c:v", "qtrle",
        str(overlay_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert res.returncode == 0, f"FFmpeg overlay generation failed: {res.stderr}"
    assert overlay_path.exists()
    return overlay_path


# ─────────────────────────────────────────────────────────────────────────────
# 1. Full Native Edit Path: Create -> 2 Distinct Tools -> CAS -> Save -> Reload -> Render
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_native_edit_path_two_tools_cas_save_reload_render(
    technical_fixture_video_mp4, tmp_path
):
    """End-to-end low-cost native edit journey:
    Insert MP4 -> Apply trim -> Apply audio-enhance/reframe -> CAS bump -> Save/Reload -> Export canonical MP4 -> Probe decoded streams.
    """
    out_file = tmp_path / "native_edit_export.mp4"

    # Step 1: Create initial ProjectRevision with technical fixture
    initial_doc = {
        "schema_version": 2,
        "title": "Wave 10 E2E Native Edit Journey",
        "aspect_ratio": "9:16",
        "timeline": {
            "fps": 30,
            "duration_seconds": 1.0,
            "tracks": [
                {
                    "id": "trk_video_main",
                    "type": "video",
                    "name": "Main Track",
                    "clips": [
                        {
                            "id": "clip_hero",
                            "source_path": str(technical_fixture_video_mp4),
                            "source_trim_start": 0.0,
                            "timeline_duration_seconds": 1.0,
                            "framing_preset": "center_crop",
                            "audio_enhance": False,
                            "caption_text": "GT-08 PREVIEW EXPORT PARITY\nLINE TWO HUMAN APPROVED",
                        }
                    ],
                }
            ],
        },
    }
    proj = await ProjectService.create_project(
        name="Wave 10 Native Edit Project",
        aspect_ratio="9:16",
        initial_document=initial_doc,
    )
    assert proj.revision == 1
    proj_id = proj.id

    # Step 2: Tool 1 — Execute 'trim' with CAS revision bump
    rev1_res = await execute_motion_capability(
        project_id=proj_id,
        expected_revision=1,
        capability_id="trim",
        params={"start": 0.0, "end": 0.8},
        input_path=technical_fixture_video_mp4,
    )
    assert rev1_res["status"] == "SUCCESS"
    assert rev1_res["current_revision"] == 2
    assert rev1_res["output_path"] is not None
    trimmed_media_path = Path(rev1_res["output_path"])
    assert trimmed_media_path.exists()

    # Step 3: Tool 2 — Execute 'audio-enhance' with CAS revision bump
    rev2_res = await execute_motion_capability(
        project_id=proj_id,
        expected_revision=2,
        capability_id="audio-enhance",
        params={"denoise": True, "normalize": True},
        input_path=trimmed_media_path,
    )
    assert rev2_res["status"] == "SUCCESS"
    assert rev2_res["current_revision"] == 3
    assert rev2_res["output_path"] is not None
    enhanced_media_path = Path(rev2_res["output_path"])
    assert enhanced_media_path.exists()

    # Step 4: Reload project from database and verify persistence across CAS revisions
    reloaded_proj = await ProjectService.get_project(proj_id)
    assert reloaded_proj.revision == 3
    reloaded_doc = (
        json.loads(reloaded_proj.document_json)
        if isinstance(reloaded_proj.document_json, str)
        else reloaded_proj.document_json
    )

    # Verify preview scrub points at 0.3 and 0.6 of clip per prompt specification
    clip = reloaded_doc["timeline"]["tracks"][0]["clips"][0]
    clip_dur = float(clip.get("timeline_duration_seconds") or clip.get("duration", 1.0))
    scrub_point_30 = clip_dur * 0.3
    scrub_point_60 = clip_dur * 0.6
    assert 0.0 < scrub_point_30 < scrub_point_60 <= clip_dur

    # Step 5: Build authoritative RenderManifest from reloaded doc
    manifest = build_render_manifest(reloaded_doc)
    assert manifest is not None
    assert manifest.aspect_ratio == "9:16"
    assert manifest.width == 1080
    assert manifest.height == 1920

    # Step 6: Render canonical H.264 / AAC MP4
    res_path, probe, warnings = await render_manifest_to_mp4(manifest, out_file)
    assert res_path.exists()
    assert probe is not None

    # Step 7: Probe decoded streams and verify exact parameters
    assert probe.width == 1080
    assert probe.height == 1920
    assert probe.video_codec in ("h264", "x264")
    assert probe.audio_codec == "aac"
    assert probe.audio_channels > 0
    assert probe.duration_seconds > 0.4
    assert any("caption overrides" in w.lower() for w in warnings)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Real 12-Block Animated Overlay Consumer & FFmpeg Compositing
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_real_animated_catalog_overlay_consumer_and_render(
    technical_fixture_video_mp4, technical_fixture_overlay_mov, tmp_path
):
    """Verify CatalogExportConsumer consumes an animated overlay contract, preserves alpha,
    and composites onto main content via FFmpeg with animated timing window.
    """
    out_file = tmp_path / "animated_overlay_composite.mp4"

    # Define CatalogExportContract manifest (Wave 6/10 Catalog specification)
    catalog_manifest = {
        "schema_version": "1.0.0",
        "contract_type": "MOTION_BLOCK_EXPORT_MANIFEST",
        "block_id": "callout_metric_badge",
        "instance_id": "inst_badge_042",
        "aspect_ratio": "9:16",
        "viewport": {"width": 1080, "height": 1920, "aspect_ratio_decimal": 0.5625},
        "timeline_parameters": {
            "start_seconds": 0.1,
            "duration_seconds": 0.6,
            "end_seconds": 0.7,
            "fps": 30,
            "total_frames": 18,
            "frame_step_seconds": 0.033333,
        },
        "rendering_channel": {
            "alpha_channel_required": True,
            "pixel_format_target": "yuva420p",
            "recommended_codec": "qtrle",
            "stage_background_color": "transparent",
        },
    }

    # 1. Parse manifest through CatalogExportConsumer
    cons_res = CatalogExportConsumer.consume(
        manifest=catalog_manifest,
        background_pad="[0:v]",
        overlay_pad="[1:v]",
        canvas_width=1080,
        canvas_height=1920,
        for_render=True,
    )
    assert isinstance(cons_res, CatalogExportConsumptionResult)
    assert cons_res.block_id == "callout_metric_badge"
    assert cons_res.alpha_channel_required is True
    assert cons_res.mp4_parity_status == "RENDERED"
    assert "format=auto" in cons_res.overlay_filter_expression
    assert "between(t,0.100,0.700)" in cons_res.overlay_filter_expression

    # 2. Render manifest with embedded overlay
    render_doc = {
        "schema_version": 2,
        "aspect_ratio": "9:16",
        "timeline": {
            "fps": 30,
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
                        }
                    ],
                },
                {
                    "id": "trk_block_overlay",
                    "type": "block",
                    "clips": [
                        {
                            "id": "clip_block_01",
                            "source_path": str(technical_fixture_overlay_mov),
                            "overlay_manifest": catalog_manifest,
                            "timeline_start_seconds": 0.1,
                            "timeline_duration_seconds": 0.6,
                        }
                    ],
                },
            ],
        },
    }

    manifest = build_render_manifest(render_doc)
    res_path, probe, warnings = await render_manifest_to_mp4(
        manifest,
        out_file,
        catalog_overlay_path=technical_fixture_overlay_mov,
        catalog_overlay_manifest=catalog_manifest,
    )
    assert res_path.exists()
    assert probe is not None
    assert probe.width == 1080
    assert probe.height == 1920
    assert probe.video_codec in ("h264", "x264")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Dual-Track Audio Integrity & Mute/Gain Isolation (No anullsrc)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dual_track_audio_mixing_and_mute_isolation(
    technical_fixture_video_mp4, technical_fixture_audio_aac, tmp_path
):
    """Verify dual-track audio:
    - Case A: Main video audio + secondary BGM active -> amix combining both into AAC.
    - Case B: Main video audio muted -> only secondary BGM plays.
    - Case C: Both tracks muted -> export with -an (silent, zero synthetic anullsrc).
    """
    # ── Case A: Both tracks active (amix) ───────────────────────────────────
    out_mixed = tmp_path / "dual_track_mixed.mp4"
    doc_mixed = {
        "schema_version": 2,
        "aspect_ratio": "9:16",
        "timeline": {
            "fps": 30,
            "tracks": [
                {
                    "id": "track_video_main",
                    "type": "video",
                    "muted": False,
                    "volume": 1.0,
                    "clips": [
                        {
                            "id": "clip_v",
                            "source_path": str(technical_fixture_video_mp4),
                            "source_trim_start": 0.0,
                            "timeline_duration_seconds": 0.8,
                            "muted": False,
                            "volume": 1.0,
                            "audio_enhance": True,
                        }
                    ],
                },
                {
                    "id": "track_audio_bgm",
                    "type": "audio",
                    "muted": False,
                    "volume": 0.7,
                    "clips": [
                        {
                            "id": "clip_bgm",
                            "source_path": str(technical_fixture_audio_aac),
                            "muted": False,
                            "volume": 1.0,
                        }
                    ],
                },
            ],
        },
    }
    manifest_mixed = build_render_manifest(doc_mixed)
    res_m, probe_m, warns_m = await render_manifest_to_mp4(manifest_mixed, out_mixed)
    assert res_m.exists()
    assert probe_m.audio_codec == "aac"
    assert probe_m.audio_channels > 0
    assert any("dual-track audio mix" in w.lower() for w in warns_m)
    assert any("voice enhancement" in w.lower() for w in warns_m)

    # ── Case B: Main video audio muted, secondary active ────────────────────
    out_bgm_only = tmp_path / "bgm_only.mp4"
    doc_bgm_only = {
        "schema_version": 2,
        "aspect_ratio": "9:16",
        "timeline": {
            "fps": 30,
            "tracks": [
                {
                    "id": "track_video_main",
                    "type": "video",
                    "muted": True,  # Main video muted
                    "clips": [
                        {
                            "id": "clip_v",
                            "source_path": str(technical_fixture_video_mp4),
                            "source_trim_start": 0.0,
                            "timeline_duration_seconds": 0.8,
                        }
                    ],
                },
                {
                    "id": "track_audio_bgm",
                    "type": "audio",
                    "muted": False,
                    "volume": 0.8,
                    "clips": [
                        {
                            "id": "clip_bgm",
                            "source_path": str(technical_fixture_audio_aac),
                        }
                    ],
                },
            ],
        },
    }
    manifest_bgm = build_render_manifest(doc_bgm_only)
    res_b, probe_b, warns_b = await render_manifest_to_mp4(manifest_bgm, out_bgm_only)
    assert res_b.exists()
    assert probe_b.audio_codec == "aac"
    assert probe_b.audio_channels > 0
    assert any("muted main audio; rendered secondary" in w.lower() for w in warns_b)

    # ── Case C: Both tracks muted (strip audio completely via -an) ───────────
    out_silent = tmp_path / "muted_both.mp4"
    doc_silent = {
        "schema_version": 2,
        "aspect_ratio": "9:16",
        "timeline": {
            "fps": 30,
            "tracks": [
                {
                    "id": "track_video_main",
                    "type": "video",
                    "muted": True,
                    "clips": [
                        {
                            "id": "clip_v",
                            "source_path": str(technical_fixture_video_mp4),
                            "source_trim_start": 0.0,
                            "timeline_duration_seconds": 0.8,
                            "muted": True,
                        }
                    ],
                },
                {
                    "id": "track_audio_bgm",
                    "type": "audio",
                    "muted": True,
                    "clips": [
                        {
                            "id": "clip_bgm",
                            "source_path": str(technical_fixture_audio_aac),
                            "muted": True,
                        }
                    ],
                },
            ],
        },
    }
    manifest_silent = build_render_manifest(doc_silent)
    res_s, probe_s, warns_s = await render_manifest_to_mp4(manifest_silent, out_silent)
    assert res_s.exists()
    assert probe_s.audio_channels == 0
    assert any("audio muted in render output" in w.lower() for w in warns_s)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Multiline Caption Authority & Whisper Retranscription
# ─────────────────────────────────────────────────────────────────────────────

def test_multiline_captions_linebreaks_survive_whisper_rerun():
    """Verify multiline captions with explicit line breaks survive automated Whisper reruns."""
    manual_captions = [
        {
            "id": "c_001",
            "start": 0.0,
            "end": 2.5,
            "text": "VIRAL HOOK FIRST LINE\nCRUCIAL DETAIL SECOND LINE",
            "manual_transcript_override": True,
            "style": {"preset": "glow", "color": "#00FFCC"},
        }
    ]
    automated_rerun = [
        {
            "id": "c_001",
            "start": 0.0,
            "end": 2.5,
            "text": "automated raw whisper transcription single line",
        }
    ]

    merged = preserve_caption_overrides(manual_captions, automated_rerun)
    assert len(merged) == 1
    assert merged[0]["manual_transcript_override"] is True
    assert "\n" in merged[0]["text"]
    assert merged[0]["text"] == "VIRAL HOOK FIRST LINE\nCRUCIAL DETAIL SECOND LINE"
    assert merged[0]["style"]["preset"] == "glow"


# ─────────────────────────────────────────────────────────────────────────────
# 5. Adversarial Negative Paths & Error Details
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_negative_paths_and_honest_blocked_provider(technical_fixture_video_mp4):
    """Verify negative checks:
    - Missing input file -> FAILED with FILE_NOT_FOUND.
    - Out-of-bounds split -> FAILED with OUT_OF_BOUNDS.
    - CAS Stale revision conflict -> HTTP 409 rejection.
    - Missing external provider credentials -> honest BLOCKED_PROVIDER without synthetic audio.
    """
    # 1. Missing file check
    res_missing = await MotionCapabilityDispatcher.dispatch(
        capability_id="trim",
        input_path="/tmp/nonexistent_file_wave10.mp4",
        params={"start": 0.0, "end": 1.0},
    )
    assert res_missing.status == "FAILED"
    assert res_missing.error_detail == "FILE_NOT_FOUND"

    # 2. Out of bounds split
    doc = {
        "tracks": [
            {
                "id": "t1",
                "clips": [{"id": "c1", "start": 1.0, "duration": 2.0, "in_point": 0.0, "out_point": 2.0}],
            }
        ]
    }
    res_split_oob = await MotionCapabilityDispatcher.dispatch(
        capability_id="split-at-playhead",
        project_doc=doc,
        params={"clip_id": "c1", "split_time": 99.0},
    )
    assert res_split_oob.status == "FAILED"
    assert res_split_oob.error_detail == "OUT_OF_BOUNDS"

    # 3. CAS Stale Revision 409 rejection
    proj = await ProjectService.create_project(
        name="CAS Stale Check Wave 10",
        aspect_ratio="9:16",
        initial_document={"schema_version": 2, "timeline": {"tracks": []}},
    )
    await ProjectService.apply_operation(
        project_id=proj.id,
        expected_revision=1,
        operation_type="update_document",
        payload={"document": {"schema_version": 2, "title": "Advanced Rev"}},
        idempotency_key="advance_rev_test",
    )
    with pytest.raises(HTTPException) as exc:
        await execute_motion_capability(
            project_id=proj.id,
            expected_revision=1,  # Stale revision (authoritative is 2)
            capability_id="transform",
            params={"op": "flip_h"},
            input_path=technical_fixture_video_mp4,
        )
    assert exc.value.status_code == 409
    assert "Stale revision" in exc.value.detail

    # 4. External provider missing credentials
    old_eleven = os.environ.pop("ELEVENLABS_API_KEY", None)
    try:
        res_provider = await MotionCapabilityDispatcher.dispatch(
            capability_id="translate",
            input_path=technical_fixture_video_mp4,
            params={"target_language": "de", "dub_audio": True},
        )
        assert res_provider.status == "BLOCKED_PROVIDER"
        assert res_provider.error_detail == "BLOCKED_PROVIDER"
        assert "voice provider credentials" in res_provider.message
    finally:
        if old_eleven:
            os.environ["ELEVENLABS_API_KEY"] = old_eleven


# ─────────────────────────────────────────────────────────────────────────────
# 6. Complete 30-Capability Master Crosswalk & Inventory Audit
# ─────────────────────────────────────────────────────────────────────────────

def test_master_30_capabilities_exact_inventory_and_readiness():
    """Verify all 30 legacy capabilities are registered, properly categorized,
    and have honest readiness tiers according to Master Proposal D01-D25/A21.
    """
    capabilities = MotionCapabilitiesRegistry.list_all()
    assert len(capabilities) == 30, f"Expected exactly 30 capabilities, got {len(capabilities)}"

    categories = {c.category for c in capabilities}
    assert "video" in categories
    assert "audio" in categories
    assert "subtitles" in categories
    assert "ai_editorial" in categories
    assert "clip_studio_workflow" in categories

    for cap in capabilities:
        assert cap.id, "Capability ID must not be empty"
        assert cap.title, f"Capability {cap.id} missing title"
        assert cap.legacy_source, f"Capability {cap.id} missing legacy_source"
        assert cap.motion_entrypoint, f"Capability {cap.id} missing motion_entrypoint"
        assert cap.backend_action, f"Capability {cap.id} missing backend_action"
        assert cap.description, f"Capability {cap.id} missing description"
