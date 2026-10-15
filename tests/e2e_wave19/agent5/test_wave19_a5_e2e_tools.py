# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
E2E Scenario Test for Wave 19 Agent 5:
Full lifecycle of native tools execution, document serialization, and CAS integrity.
"""

import json
import pytest
from uuid import uuid4

from backend.database import init_db
from backend.services.project_service import ProjectService
from backend.tools_native import ToolsNativeAdapter, NativeToolRegistry, NativeToolType


@pytest.fixture(autouse=True)
async def setup_db():
    """Ensure database schema is created before tests."""
    await init_db()


@pytest.mark.asyncio
async def test_wave19_a5_e2e_tools_lifecycle():
    """Execute end-to-end multi-tool transformation pipeline over a live project document."""
    proj_name = f"proj_e2e_w19_tools_{uuid4().hex[:8]}"
    initial_doc = {
        "schema_version": 2,
        "aspect_ratio": "16:9",
        "timeline": {
            "fps": 30,
            "duration_seconds": 60.0,
            "tracks": [
                {
                    "id": "trk_media_01",
                    "type": "video",
                    "name": "Live Camera Feed",
                    "clips": [
                        {
                            "id": "clip_raw_01",
                            "start_time": 0.0,
                            "end_time": 60.0,
                            "duration": 60.0,
                            "speed": 1.0,
                        }
                    ],
                }
            ],
        },
    }
    project = await ProjectService.create_project(
        name=proj_name,
        aspect_ratio="16:9",
        initial_document=initial_doc,
        user_id="e2e_agent5"
    )
    project_id = project.id

    # Step 1: Reframe to 9:16 vertical
    r1 = await ToolsNativeAdapter.execute_tool_command(
        project_id=project_id,
        tool="reframe",
        params={"aspect_ratio": "9:16", "focal_mode": "auto_face"},
    )
    assert r1.success is True
    assert r1.new_revision == 2

    # Step 2: Trim to hook window (0 to 15s)
    r2 = await ToolsNativeAdapter.execute_tool_command(
        project_id=project_id,
        tool="trim",
        params={"start_time": 0.0, "end_time": 15.0, "clip_id": "clip_raw_01"},
    )
    assert r2.success is True
    assert r2.new_revision == 3

    # Step 3: Enhance audio with broadcast LUFS
    r3 = await ToolsNativeAdapter.execute_tool_command(
        project_id=project_id,
        tool="audio-enhance",
        params={"normalize_loudness": True, "target_lufs": -14.0, "denoise": True},
    )
    assert r3.success is True
    assert r3.new_revision == 4

    # Step 4: Burn dynamic captions
    r4 = await ToolsNativeAdapter.execute_tool_command(
        project_id=project_id,
        tool="captions",
        params={"style": "viral", "font_size": 38, "uppercase": True},
    )
    assert r4.success is True
    assert r4.new_revision == 5

    # Step 5: Add watermark branding
    r5 = await ToolsNativeAdapter.execute_tool_command(
        project_id=project_id,
        tool="watermark",
        params={"position": "top_right", "opacity": 0.8},
    )
    assert r5.success is True
    assert r5.new_revision == 6

    # Verify final document state
    proj_final = await ProjectService.get_project(project_id)
    final_doc = json.loads(proj_final.document_json)
    assert proj_final.revision == 6
    assert final_doc["aspect_ratio"] == "9:16"
    tracks = final_doc.get("timeline", {}).get("tracks") or final_doc.get("tracks")
    assert tracks[0]["clips"][0]["end_time"] == 15.0
    assert final_doc["audio_filters"]["target_lufs"] == -14.0
    assert final_doc["captions"]["style"] == "viral"
    assert final_doc["watermark"]["enabled"] is True
