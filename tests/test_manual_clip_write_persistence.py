# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Integration test proving manual clip write persistence in Timeline and Inspector."""
import pytest
import json
from uuid import uuid4

from backend.database import init_db
from backend.services.project_service import ProjectService
from backend.core.exceptions import RevisionConflictError


@pytest.mark.asyncio
async def test_timeline_and_inspector_write_persistence():
    await init_db()

    # 1. Create project with initial clip
    clip_id = f"clip_{uuid4().hex[:8]}"
    initial_doc = {
        "title": "Manual Persistence Test",
        "aspect_ratio": "9:16",
        "timeline": {
            "duration_seconds": 15.0,
            "fps": 30,
            "tracks": [
                {
                    "id": "track_video_main",
                    "type": "video",
                    "name": "Main Track",
                    "clips": [
                        {
                            "id": clip_id,
                            "start_seconds": 0.0,
                            "duration_seconds": 5.0,
                            "caption_text": "Original Title",
                            "file": "source.mp4",
                        }
                    ]
                }
            ]
        }
    }

    project = await ProjectService.create_project(
        name="Persistence Verification",
        aspect_ratio="9:16",
        initial_document=initial_doc,
    )
    assert project.revision == 1

    # 2. Timeline Interaction: Drag / trim clip timing
    # User drags clip to 3.5s and resizes duration to 7.2s
    res_timeline = await ProjectService.apply_operation(
        project_id=project.id,
        expected_revision=1,
        operation_type="update_clip",
        payload={
            "clip_id": clip_id,
            "patch": {
                "start_seconds": 3.5,
                "duration_seconds": 7.2,
            }
        },
        author="user",
    )
    assert res_timeline["revision"] == 2
    assert res_timeline["applied"] is True

    # Reload from DB (simulating page reload)
    reloaded_1 = await ProjectService.get_project(project.id)
    assert reloaded_1.revision == 2
    doc_1 = json.loads(reloaded_1.document_json)
    clip_1 = doc_1["timeline"]["tracks"][0]["clips"][0]
    assert clip_1["start_seconds"] == 3.5
    assert clip_1["duration_seconds"] == 7.2
    assert clip_1["caption_text"] == "Original Title"

    # 3. Inspector Interaction: Edit clip properties (caption text and duration)
    res_inspector = await ProjectService.apply_operation(
        project_id=project.id,
        expected_revision=2,
        operation_type="update_clip",
        payload={
            "clip_id": clip_id,
            "patch": {
                "caption_text": "Updated Viral Hook",
                "duration_seconds": 9.0,
            }
        },
        author="user",
    )
    assert res_inspector["revision"] == 3
    assert res_inspector["applied"] is True

    # Reload from DB (simulating subsequent page reload)
    reloaded_2 = await ProjectService.get_project(project.id)
    assert reloaded_2.revision == 3
    doc_2 = json.loads(reloaded_2.document_json)
    clip_2 = doc_2["timeline"]["tracks"][0]["clips"][0]
    assert clip_2["start_seconds"] == 3.5
    assert clip_2["duration_seconds"] == 9.0
    assert clip_2["caption_text"] == "Updated Viral Hook"

    # 4. Timeline clip removal
    res_remove = await ProjectService.apply_operation(
        project_id=project.id,
        expected_revision=3,
        operation_type="remove_clip",
        payload={"clip_id": clip_id},
        author="user",
    )
    assert res_remove["revision"] == 4

    reloaded_3 = await ProjectService.get_project(project.id)
    assert reloaded_3.revision == 4
    doc_3 = json.loads(reloaded_3.document_json)
    clips_left = doc_3["timeline"]["tracks"][0]["clips"]
    assert len(clips_left) == 0


@pytest.mark.asyncio
async def test_timeline_write_stale_revision_conflict():
    await init_db()

    clip_id = f"clip_{uuid4().hex[:8]}"
    project = await ProjectService.create_project(
        name="Conflict Test",
        initial_document={
            "timeline": {
                "tracks": [{"id": "t1", "clips": [{"id": clip_id, "start_seconds": 0.0, "duration_seconds": 4.0}]}]
            }
        }
    )

    # First write bumps revision to 2
    await ProjectService.apply_operation(
        project_id=project.id,
        expected_revision=1,
        operation_type="update_clip",
        payload={"clip_id": clip_id, "patch": {"start_seconds": 1.0}},
    )

    # Second write with stale expected_revision=1 must raise RevisionConflictError
    with pytest.raises(RevisionConflictError) as exc_info:
        await ProjectService.apply_operation(
            project_id=project.id,
            expected_revision=1,
            operation_type="update_clip",
            payload={"clip_id": clip_id, "patch": {"start_seconds": 2.0}},
        )
    assert exc_info.value.current_revision == 2
    assert exc_info.value.expected_revision == 1
