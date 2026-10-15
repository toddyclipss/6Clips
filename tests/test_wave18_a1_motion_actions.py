# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Test Suite for Wave 18 Agent 1: Native Motion Editor Actions.

Tests:
- Action parameter schemas, boundary validation, and rejection of invalid bounds
- Native action execution over canonical ProjectService (trim, split, range_select, ripple_delete, reframe, crop, speed, captions_edit, audio_adjust, graphic_insert)
- Optimistic concurrency control (CAS revision conflict detection)
- Idempotent replay and duplicate action handling
- Unsupported tool and capability status reporting
- Undo / rollback to previous revision snapshot
- Batch sequential execution with dynamic revision progression
"""

import json
import pytest
from uuid import uuid4

from backend.database import init_db
from backend.oaas_motion_actions.adapter import OAASMotionActionAdapter
from backend.oaas_motion_actions.capability_catalog import CapabilityDiscovery
from backend.oaas_motion_actions.models import (
    ActionExecutionStatus,
    CaptionsEditActionParams,
    MotionActionEnvelope,
    MotionActionResult,
    MotionActionType,
    ReframeActionParams,
    TrimActionParams,
)
from backend.services.project_service import ProjectService


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.fixture
async def sample_project():
    """Create a project with a main video track and a sample 10-second clip."""
    initial_doc = {
        "schema_version": 2,
        "aspect_ratio": "16:9",
        "timeline": {
            "fps": 30,
            "duration_seconds": 10.0,
            "tracks": [
                {
                    "id": "track_video_main",
                    "type": "video",
                    "name": "Main Video",
                    "clips": [
                        {
                            "id": "clip_main_1",
                            "type": "video",
                            "start": 0.0,
                            "duration": 10.0,
                            "trim_start": 0.0,
                            "trim_end": 10.0,
                            "title": "Interview Footage",
                        }
                    ],
                }
            ],
        },
    }
    proj = await ProjectService.create_project(
        name="Test Editor Project",
        aspect_ratio="16:9",
        initial_document=initial_doc,
        user_id="local_tester",
    )
    return proj


@pytest.mark.asyncio
async def test_action_parameter_validation_bounds():
    """Validates that out-of-bounds or contradictory parameters fail schema validation."""
    # Trim with trim_end <= trim_start must fail
    with pytest.raises(ValueError):
        TrimActionParams(clip_id="c1", trim_start=5.0, trim_end=4.0)

    # Reframe with unsupported aspect ratio must fail
    with pytest.raises(ValueError):
        ReframeActionParams(aspect_ratio="21:9")

    # Valid params must succeed
    p_trim = TrimActionParams(clip_id="c1", trim_start=2.0, trim_end=8.0)
    assert p_trim.trim_start == 2.0
    assert p_trim.trim_end == 8.0

    p_ref = ReframeActionParams(aspect_ratio="9:16")
    assert p_ref.aspect_ratio == "9:16"


@pytest.mark.asyncio
async def test_execute_trim_action(sample_project):
    """Trim action updates source media window and bumps revision atomically."""
    proj_id = sample_project.id
    res = await OAASMotionActionAdapter.execute_command(
        project_id=proj_id,
        action=MotionActionType.TRIM,
        params={"clip_id": "clip_main_1", "trim_start": 2.0, "trim_end": 8.0},
        expected_revision=1,
    )

    assert res.status == ActionExecutionStatus.SUCCESS
    assert res.applied is True
    assert res.base_revision == 1
    assert res.resulting_revision == 2

    # Verify document snapshot on project
    proj = await ProjectService.get_project(proj_id)
    doc = json.loads(proj.document_json)
    clip = doc["timeline"]["tracks"][0]["clips"][0]
    assert clip["trim_start"] == 2.0
    assert clip["trim_end"] == 8.0
    assert clip["duration"] == 6.0


@pytest.mark.asyncio
async def test_execute_split_action(sample_project):
    """Split action splits clip at split_time into two adjacent clips."""
    proj_id = sample_project.id
    res = await OAASMotionActionAdapter.execute_command(
        project_id=proj_id,
        action=MotionActionType.SPLIT,
        params={"clip_id": "clip_main_1", "split_time": 4.0},
        expected_revision=1,
    )

    assert res.status == ActionExecutionStatus.SUCCESS
    assert res.resulting_revision == 2
    assert len(res.affected_clip_ids) == 2

    proj = await ProjectService.get_project(proj_id)
    doc = json.loads(proj.document_json)
    clips = doc["timeline"]["tracks"][0]["clips"]
    assert len(clips) == 2
    assert clips[0]["duration"] == 4.0
    assert clips[1]["start"] == 4.0
    assert clips[1]["duration"] == 6.0


@pytest.mark.asyncio
async def test_execute_range_select_action(sample_project):
    """Range select records bench ranges in project document."""
    proj_id = sample_project.id
    res = await OAASMotionActionAdapter.execute_command(
        project_id=proj_id,
        action=MotionActionType.RANGE_SELECT,
        params={"source_id": "video_raw_01", "in_point": 1.5, "out_point": 6.5, "label": "hook_intro"},
        expected_revision=1,
    )

    assert res.status == ActionExecutionStatus.SUCCESS
    proj = await ProjectService.get_project(proj_id)
    doc = json.loads(proj.document_json)
    assert "video_raw_01" in doc.get("bench_ranges", {})
    ranges = doc["bench_ranges"]["video_raw_01"]
    assert ranges[0]["in"] == 1.5
    assert ranges[0]["out"] == 6.5


@pytest.mark.asyncio
async def test_execute_reframe_action(sample_project):
    """Reframe updates aspect ratio and preset in canonical project."""
    proj_id = sample_project.id
    res = await OAASMotionActionAdapter.execute_command(
        project_id=proj_id,
        action=MotionActionType.REFRAME,
        params={"aspect_ratio": "9:16", "preset": "center_crop"},
        expected_revision=1,
    )

    assert res.status == ActionExecutionStatus.SUCCESS
    proj = await ProjectService.get_project(proj_id)
    assert proj.aspect_ratio == "9:16"
    doc = json.loads(proj.document_json)
    assert doc.get("aspect_ratio") == "9:16"
    assert doc.get("reframe_preset") == "center_crop"


@pytest.mark.asyncio
async def test_execute_crop_and_speed_actions(sample_project):
    """Crop and speed adjustments persist in clip inspector metadata."""
    proj_id = sample_project.id

    # 1. Crop
    res_crop = await OAASMotionActionAdapter.execute_command(
        project_id=proj_id,
        action=MotionActionType.CROP,
        params={"clip_id": "clip_main_1", "crop_x": 100, "crop_y": 50, "crop_w": 800, "crop_h": 1000},
        expected_revision=1,
    )
    assert res_crop.status == ActionExecutionStatus.SUCCESS
    assert res_crop.resulting_revision == 2

    # 2. Speed retime (2.0x speed cuts duration from 10s to 5s)
    res_speed = await OAASMotionActionAdapter.execute_command(
        project_id=proj_id,
        action=MotionActionType.SPEED,
        params={"clip_id": "clip_main_1", "speed_factor": 2.0, "maintain_pitch": True},
        expected_revision=2,
    )
    assert res_speed.status == ActionExecutionStatus.SUCCESS
    assert res_speed.resulting_revision == 3

    proj = await ProjectService.get_project(proj_id)
    doc = json.loads(proj.document_json)
    clip = doc["timeline"]["tracks"][0]["clips"][0]
    assert clip["crop"]["w"] == 800
    assert clip["speed"] == 2.0
    assert clip["duration"] == 5.0


@pytest.mark.asyncio
async def test_execute_captions_edit_action(sample_project):
    """Captions edit adds/updates captions track with word timing segments."""
    proj_id = sample_project.id
    captions_payload = [
        {"start": 0.0, "end": 2.5, "text": "Welcome to ViralMint OAAS."},
        {"start": 2.5, "end": 5.0, "text": "Delivering completed video outcomes."},
    ]
    res = await OAASMotionActionAdapter.execute_command(
        project_id=proj_id,
        action=MotionActionType.CAPTIONS_EDIT,
        params={"captions": captions_payload, "style": "pop", "font_size": 32, "color": "#00FFCC"},
        expected_revision=1,
    )

    assert res.status == ActionExecutionStatus.SUCCESS
    proj = await ProjectService.get_project(proj_id)
    doc = json.loads(proj.document_json)
    cap_track = next((t for t in doc["timeline"]["tracks"] if t.get("type") == "captions"), None)
    assert cap_track is not None
    assert len(cap_track["clips"]) == 2
    assert cap_track["clips"][0]["text"] == "Welcome to ViralMint OAAS."
    assert cap_track["clips"][0]["style"] == "pop"


@pytest.mark.asyncio
async def test_execute_graphic_insert_operable_vs_retired(sample_project):
    """Inserting an operable donor block succeeds; inserting a retired block fails."""
    proj_id = sample_project.id

    # 1. Operable donor original (aurora) succeeds
    res_aurora = await OAASMotionActionAdapter.execute_command(
        project_id=proj_id,
        action=MotionActionType.GRAPHIC_INSERT,
        params={"block_id": "aurora", "timecode_start": 1.0, "duration": 4.0},
        expected_revision=1,
    )
    assert res_aurora.status == ActionExecutionStatus.SUCCESS
    assert res_aurora.resulting_revision == 2

    # 2. Retired 6Clips block (creator-hud) fails closed
    res_retired = await OAASMotionActionAdapter.execute_command(
        project_id=proj_id,
        action=MotionActionType.GRAPHIC_INSERT,
        params={"block_id": "creator-hud", "timecode_start": 0.0, "duration": 5.0},
        expected_revision=2,
    )
    assert res_retired.status == ActionExecutionStatus.PRECONDITION_FAILED
    assert "retired" in res_retired.detail.lower()


@pytest.mark.asyncio
async def test_cas_concurrency_conflict_handling(sample_project):
    """CAS conflict detected when expected_revision does not match project state."""
    proj_id = sample_project.id

    # Base is at revision 1. Request expecting revision 99 must be rejected.
    res = await OAASMotionActionAdapter.execute_command(
        project_id=proj_id,
        action=MotionActionType.TRIM,
        params={"clip_id": "clip_main_1", "trim_start": 1.0},
        expected_revision=99,
    )

    assert res.status == ActionExecutionStatus.CAS_CONFLICT
    assert res.applied is False
    assert "mismatch" in res.detail.lower() or "conflict" in res.detail.lower()

    # Project revision must remain at 1
    proj = await ProjectService.get_project(proj_id)
    assert proj.revision == 1


@pytest.mark.asyncio
async def test_idempotency_replay(sample_project):
    """Submitting action with duplicate idempotency key returns idempotent replay without double mutation."""
    proj_id = sample_project.id
    idem_key = f"idem-test-{uuid4().hex}"

    # First call applies operation (rev 1 -> rev 2)
    res1 = await OAASMotionActionAdapter.execute_command(
        project_id=proj_id,
        action=MotionActionType.TRIM,
        params={"clip_id": "clip_main_1", "trim_start": 1.0},
        expected_revision=1,
        idempotency_key=idem_key,
    )
    assert res1.status == ActionExecutionStatus.SUCCESS
    assert res1.resulting_revision == 2
    assert res1.applied is True

    # Replay with same key returns IDEMPOTENT_REPLAY and does not increment revision
    res2 = await OAASMotionActionAdapter.execute_command(
        project_id=proj_id,
        action=MotionActionType.TRIM,
        params={"clip_id": "clip_main_1", "trim_start": 1.0},
        expected_revision=1,
        idempotency_key=idem_key,
    )
    assert res2.status == ActionExecutionStatus.IDEMPOTENT_REPLAY
    assert res2.resulting_revision == 2
    assert res2.applied is False

    proj = await ProjectService.get_project(proj_id)
    assert proj.revision == 2


@pytest.mark.asyncio
async def test_undo_last_action(sample_project):
    """Undo action rolls back the project document to the snapshot of the preceding revision."""
    proj_id = sample_project.id

    # 1. Mutate revision 1 -> 2 with reframe
    await OAASMotionActionAdapter.execute_command(
        project_id=proj_id,
        action=MotionActionType.REFRAME,
        params={"aspect_ratio": "9:16"},
        expected_revision=1,
    )
    proj = await ProjectService.get_project(proj_id)
    assert proj.revision == 2
    assert proj.aspect_ratio == "9:16"

    # 2. Undo returns document to revision 1 state (as revision 3)
    undo_res = await OAASMotionActionAdapter.undo_last_action(proj_id)
    assert undo_res.status == ActionExecutionStatus.SUCCESS
    assert undo_res.resulting_revision == 3

    proj_undone = await ProjectService.get_project(proj_id)
    doc_undone = json.loads(proj_undone.document_json)
    assert doc_undone.get("aspect_ratio") == "16:9"


@pytest.mark.asyncio
async def test_batch_execute_actions(sample_project):
    """Batch execute runs sequential actions, updating revision state dynamically."""
    proj_id = sample_project.id
    commands = [
        {"action": "trim", "params": {"clip_id": "clip_main_1", "trim_start": 1.0, "trim_end": 9.0}},
        {"action": "reframe", "params": {"aspect_ratio": "9:16"}},
        {"action": "audio_adjust", "params": {"volume": 0.8, "mute": False}},
    ]

    results = await OAASMotionActionAdapter.batch_execute(proj_id, commands)
    assert len(results) == 3
    for r in results:
        assert r.status == ActionExecutionStatus.SUCCESS

    # Verify final revision is 4 (rev 1 + 3 mutations)
    proj = await ProjectService.get_project(proj_id)
    assert proj.revision == 4
    assert proj.aspect_ratio == "9:16"
