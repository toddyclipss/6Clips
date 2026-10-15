# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Unit and Integration Tests for Wave 19 Agent 5:
Original 21 Tools Forensic Parity & Native CAS Execution.
"""

import json
import pytest
import pytest_asyncio
from uuid import uuid4

from backend.database import init_db
from backend.services.project_service import ProjectService
from backend.tools_native import (
    NativeToolType,
    NativeToolRegistry,
    ToolsNativeAdapter,
    ToolActionRequest,
    NativeToolExecutor,
)


@pytest.fixture(autouse=True)
async def setup_db():
    """Ensure database schema is created before tests."""
    await init_db()


@pytest_asyncio.fixture
async def sample_project():
    """Create an isolated test project with standard video/audio tracks."""
    proj_name = f"proj_test_w19_a5_{uuid4().hex[:8]}"
    init_doc = {
        "schema_version": 2,
        "aspect_ratio": "9:16",
        "timeline": {
            "fps": 30,
            "duration_seconds": 15.0,
            "tracks": [
                {
                    "id": "track_video_main",
                    "type": "video",
                    "name": "Main Video",
                    "clips": [
                        {
                            "id": "clip_main_01",
                            "name": "Interview Segment",
                            "start_time": 0.0,
                            "end_time": 15.0,
                            "duration": 15.0,
                            "speed": 1.0,
                        }
                    ],
                },
                {
                    "id": "track_audio_main",
                    "type": "audio",
                    "name": "Master Audio",
                    "clips": [
                        {
                            "id": "clip_audio_01",
                            "name": "Dialogue Track",
                            "start_time": 0.0,
                            "end_time": 15.0,
                            "duration": 15.0,
                        }
                    ],
                },
            ],
        },
    }
    project = await ProjectService.create_project(
        name=proj_name,
        aspect_ratio="9:16",
        initial_document=init_doc,
        user_id="test_user"
    )
    yield project.id


@pytest.mark.asyncio
async def test_01_registry_enumeration_and_integrity():
    """Verify registry has all 21 tools plus ingestion, correct categories, and endpoints."""
    assert NativeToolRegistry.count() == 22
    all_tools = NativeToolRegistry.list_all()
    slugs = {t.slug for t in all_tools}
    
    expected_21 = {
        NativeToolType.CAPTIONS, NativeToolType.REFRAME, NativeToolType.AUDIO_ENHANCE,
        NativeToolType.WATERMARK, NativeToolType.MERGE_CLIPS, NativeToolType.REMOVE_SILENCE,
        NativeToolType.TRANSLATE, NativeToolType.HOOK_ANALYSIS, NativeToolType.ENHANCE_PROMPT,
        NativeToolType.VOICEOVER, NativeToolType.TRANSFORM, NativeToolType.MUSIC_VISUALIZER,
        NativeToolType.GIF, NativeToolType.SPEED, NativeToolType.METADATA,
        NativeToolType.AUTO_CHAPTERS, NativeToolType.TRIM, NativeToolType.SUBTITLES,
        NativeToolType.COMPRESS, NativeToolType.CROP, NativeToolType.AUTO_ZOOM
    }
    assert expected_21.issubset(slugs)
    
    # Check that inspector tools exclude non-inspector tools
    inspector_tools = NativeToolRegistry.list_inspector_tools()
    assert len(inspector_tools) >= 20


@pytest.mark.asyncio
async def test_02_captions_mutation(sample_project):
    """Verify Captions tool mutates document.captions and increments revision."""
    res = await ToolsNativeAdapter.execute_tool_command(
        project_id=sample_project,
        tool="captions",
        params={"style": "bold", "font_size": 42, "color": "#FFFF00", "uppercase": True},
    )
    assert res.success is True
    assert res.new_revision == 2
    assert res.document_delta["captions"]["style"] == "bold"
    assert res.document_delta["captions"]["color"] == "#FFFF00"

    proj = await ProjectService.get_project(sample_project)
    doc = json.loads(proj.document_json)
    assert proj.revision == 2
    assert doc["captions"]["style"] == "bold"


@pytest.mark.asyncio
async def test_03_reframe_aspect_ratio_mutation(sample_project):
    """Verify Reframe tool updates aspect ratio and focal mode."""
    res = await ToolsNativeAdapter.execute_tool_command(
        project_id=sample_project,
        tool=NativeToolType.REFRAME,
        params={"aspect_ratio": "9:16", "focal_mode": "speaker_tracking"},
    )
    assert res.success is True
    assert res.document_delta["aspect_ratio"] == "9:16"

    proj = await ProjectService.get_project(sample_project)
    doc = json.loads(proj.document_json)
    assert doc["aspect_ratio"] == "9:16"
    assert doc["reframe"]["focal_mode"] == "speaker_tracking"


@pytest.mark.asyncio
async def test_04_audio_enhance_mutation(sample_project):
    """Verify Audio Enhance applies loudness normalization and denoise parameters."""
    res = await ToolsNativeAdapter.execute_tool_command(
        project_id=sample_project,
        tool=NativeToolType.AUDIO_ENHANCE,
        params={"normalize_loudness": True, "target_lufs": -16.0, "denoise": True, "denoise_strength": 0.75},
    )
    assert res.success is True
    assert res.document_delta["audio_filters"]["target_lufs"] == -16.0

    proj = await ProjectService.get_project(sample_project)
    doc = json.loads(proj.document_json)
    assert doc["audio_filters"]["target_lufs"] == -16.0


@pytest.mark.asyncio
async def test_05_watermark_overlay_mutation(sample_project):
    """Verify Watermark updates branding overlay configuration."""
    res = await ToolsNativeAdapter.execute_tool_command(
        project_id=sample_project,
        tool=NativeToolType.WATERMARK,
        params={"position": "bottom_right", "opacity": 0.9, "scale": 0.2},
    )
    assert res.success is True
    assert res.document_delta["watermark"]["enabled"] is True
    assert res.document_delta["watermark"]["position"] == "bottom_right"


@pytest.mark.asyncio
async def test_06_trim_and_speed_clip_mutations(sample_project):
    """Verify Trim and Speed update target clip timing and multiplier."""
    # 1. Trim
    res_trim = await ToolsNativeAdapter.execute_tool_command(
        project_id=sample_project,
        tool="trim",
        params={"start_time": 2.5, "end_time": 10.0, "clip_id": "clip_main_01"},
    )
    assert res_trim.success is True
    assert res_trim.document_delta["trim"]["start_time"] == 2.5
    assert res_trim.document_delta["trim"]["end_time"] == 10.0

    # 2. Speed
    res_speed = await ToolsNativeAdapter.execute_tool_command(
        project_id=sample_project,
        tool="speed",
        params={"speed_factor": 1.5, "preserve_pitch": True, "clip_id": "clip_main_01"},
    )
    assert res_speed.success is True
    assert res_speed.document_delta["speed_factor"] == 1.5

    proj = await ProjectService.get_project(sample_project)
    doc = json.loads(proj.document_json)
    tracks = doc.get("timeline", {}).get("tracks") or doc.get("tracks")
    clip = tracks[0]["clips"][0]
    assert clip["start_time"] == 2.5
    assert clip["end_time"] == 10.0
    assert clip["speed"] == 1.5


@pytest.mark.asyncio
async def test_07_crop_and_transform_mutations(sample_project):
    """Verify Crop and Transform apply geometric mutations."""
    # 1. Crop
    res_crop = await ToolsNativeAdapter.execute_tool_command(
        project_id=sample_project,
        tool="crop",
        params={"x": 100, "y": 100, "width": 800, "height": 800},
    )
    assert res_crop.success is True
    assert res_crop.document_delta["crop"]["width"] == 800

    # 2. Transform
    res_tf = await ToolsNativeAdapter.execute_tool_command(
        project_id=sample_project,
        tool="transform",
        params={"scale": 1.2, "rotation": 90.0, "flip_x": True},
    )
    assert res_tf.success is True

    proj = await ProjectService.get_project(sample_project)
    doc = json.loads(proj.document_json)
    tracks = doc.get("timeline", {}).get("tracks") or doc.get("tracks")
    clip = tracks[0]["clips"][0]
    assert clip["crop"]["width"] == 800
    assert clip["transform"]["rotation"] == 90.0
    assert clip["transform"]["flip_x"] is True


@pytest.mark.asyncio
async def test_08_silence_removal_and_translation(sample_project):
    """Verify Remove Silence and Translate apply audio/language mutations."""
    # 1. Remove silence
    res_sil = await ToolsNativeAdapter.execute_tool_command(
        project_id=sample_project,
        tool="remove-silence",
        params={"threshold_db": -30.0, "min_silence_duration": 0.5},
    )
    assert res_sil.success is True
    assert res_sil.document_delta["silence_removal"]["threshold_db"] == -30.0

    # 2. Translate
    res_trans = await ToolsNativeAdapter.execute_tool_command(
        project_id=sample_project,
        tool="translate",
        params={"target_language": "pt", "source_language": "en"},
    )
    assert res_trans.success is True
    assert res_trans.document_delta["language_translation"] == "pt"


@pytest.mark.asyncio
async def test_09_metadata_and_intelligence_tools(sample_project):
    """Verify Hook Analysis, Enhance Prompt, and Metadata mutations."""
    # 1. Metadata
    res_meta = await ToolsNativeAdapter.execute_tool_command(
        project_id=sample_project,
        tool="metadata",
        params={"title": "Viral Reel 01", "author": "ViralMint Pro", "tags": ["trending", "ai"]},
    )
    assert res_meta.success is True

    # 2. Hook Analysis
    res_hook = await ToolsNativeAdapter.execute_tool_command(
        project_id=sample_project,
        tool="hook-analysis",
        params={"sample_window_sec": 4.0},
    )
    assert res_hook.success is True
    assert res_hook.document_delta["hook_analysis"]["hook_score"] > 80

    # 3. Enhance Prompt
    res_prompt = await ToolsNativeAdapter.execute_tool_command(
        project_id=sample_project,
        tool="enhance-prompt",
        params={"prompt": "make a fast-paced clip"},
    )
    assert res_prompt.success is True
    assert "Cinematic Viral" in res_prompt.document_delta["enhanced_prompt"]


@pytest.mark.asyncio
async def test_10_media_generators_voiceover_and_visualizer(sample_project):
    """Verify Voiceover audio insertion and Music Visualizer overlay layer creation."""
    # 1. Voiceover
    res_vo = await ToolsNativeAdapter.execute_tool_command(
        project_id=sample_project,
        tool="voiceover",
        params={"script": "Welcome back to the channel!", "voice_id": "en-US-JennyNeural"},
    )
    assert res_vo.success is True
    assert "voiceover_clip_inserted" in res_vo.document_delta

    # 2. Music Visualizer
    res_vis = await ToolsNativeAdapter.execute_tool_command(
        project_id=sample_project,
        tool="music-visualizer",
        params={"style": "wave", "color": "#FF0055"},
    )
    assert res_vis.success is True
    assert "visualizer_inserted" in res_vis.document_delta

    proj = await ProjectService.get_project(sample_project)
    doc = json.loads(proj.document_json)
    tracks = doc.get("timeline", {}).get("tracks") or doc.get("tracks")
    track_types = [t.get("type") for t in tracks]
    assert "audio" in track_types
    assert "overlay" in track_types


@pytest.mark.asyncio
async def test_11_export_pipes_gif_and_compress(sample_project):
    """Verify GIF and Compress configure export_settings."""
    # 1. GIF
    res_gif = await ToolsNativeAdapter.execute_tool_command(
        project_id=sample_project,
        tool="gif",
        params={"fps": 24, "scale_width": 720, "loop_count": 0},
    )
    assert res_gif.success is True
    assert res_gif.document_delta["gif_settings"]["fps"] == 24

    # 2. Compress
    res_comp = await ToolsNativeAdapter.execute_tool_command(
        project_id=sample_project,
        tool="compress",
        params={"crf": 20, "preset": "fast"},
    )
    assert res_comp.success is True
    assert res_comp.document_delta["compression"]["crf"] == 20


@pytest.mark.asyncio
async def test_12_cas_concurrency_conflict_rejection(sample_project):
    """Verify optimistic locking rejects stale expected_revision."""
    proj = await ProjectService.get_project(sample_project)
    rev = proj.revision

    # First update passes
    res1 = await ToolsNativeAdapter.execute_tool_command(
        project_id=sample_project,
        tool="captions",
        params={"style": "clean"},
        expected_revision=rev,
    )
    assert res1.success is True
    assert res1.new_revision == rev + 1

    # Second update passing old revision is rejected with CAS conflict
    res2 = await ToolsNativeAdapter.execute_tool_command(
        project_id=sample_project,
        tool="captions",
        params={"style": "cyberpunk"},
        expected_revision=rev,
    )
    assert res2.success is False
    assert "CAS Revision Conflict" in res2.error


@pytest.mark.asyncio
async def test_13_batch_execution_chaining(sample_project):
    """Verify batch_execute sequentially executes and chains revisions."""
    commands = [
        {"tool": "reframe", "params": {"aspect_ratio": "16:9"}},
        {"tool": "watermark", "params": {"position": "top_left"}},
        {"tool": "auto-chapters", "params": {}},
    ]
    results = await ToolsNativeAdapter.batch_execute(project_id=sample_project, commands=commands)
    assert len(results) == 3
    assert all(r.success for r in results)

    proj = await ProjectService.get_project(sample_project)
    doc = json.loads(proj.document_json)
    assert doc["aspect_ratio"] == "16:9"
    assert doc["watermark"]["position"] == "top_left"
    assert len(doc["markers"]) >= 3
