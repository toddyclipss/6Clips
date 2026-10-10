import pytest
from backend.database import init_db
from backend.services.project_service import ProjectService
from backend.core.exceptions import RevisionConflictError, ProjectNotFoundError


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()



@pytest.mark.asyncio
async def test_project_create_and_revisions():
    p = await ProjectService.create_project(name="Test Workflow", aspect_ratio="9:16")
    assert p.id
    assert p.name == "Test Workflow"
    assert p.revision == 1

    # Apply add_clip with expected_revision=1
    clip_data = {
        "id": "clip_test_1",
        "asset_id": "dl:12345",
        "start_seconds": 0.0,
        "duration_seconds": 15.0,
        "trim_start": 0.0,
        "trim_end": 15.0,
    }
    res = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=1,
        operation_type="add_clip",
        payload={"track_id": "track_video_main", "clip": clip_data},
        idempotency_key="op_clip_1",
        author="agent",
    )
    assert res["applied"] is True
    assert res["revision"] == 2
    assert len(res["document"]["timeline"]["tracks"][0]["clips"]) == 1
    assert res["document"]["timeline"]["duration_seconds"] == 15.0


@pytest.mark.asyncio
async def test_project_revision_conflict():
    p = await ProjectService.create_project(name="Conflict Test")
    
    # Try to apply operation expecting revision 99 when project is at 1
    with pytest.raises(RevisionConflictError) as exc_info:
        await ProjectService.apply_operation(
            project_id=p.id,
            expected_revision=99,
            operation_type="set_aspect_ratio",
            payload={"aspect_ratio": "16:9"},
        )
    assert exc_info.value.current_revision == 1
    assert exc_info.value.expected_revision == 99


@pytest.mark.asyncio
async def test_project_idempotency():
    p = await ProjectService.create_project(name="Idempotency Test")
    
    # Apply operation with key "key_1"
    res1 = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=1,
        operation_type="set_aspect_ratio",
        payload={"aspect_ratio": "16:9"},
        idempotency_key="key_1",
    )
    assert res1["applied"] is True
    assert res1["revision"] == 2

    # Replay with same idempotency key
    res2 = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=2,
        operation_type="set_aspect_ratio",
        payload={"aspect_ratio": "16:9"},
        idempotency_key="key_1",
    )
    assert res2["applied"] is False
    assert res2.get("idempotent_replay") is True
    assert res2["revision"] == 2


@pytest.mark.asyncio
async def test_project_freeze_for_render():
    p = await ProjectService.create_project(name="Render Freeze Test")
    
    # Add clip at rev 1 -> 2
    await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=1,
        operation_type="add_clip",
        payload={"track_id": "track_video_main", "clip": {"id": "c1", "duration_seconds": 10.0}},
    )
    
    # Freeze rev 2
    rev_num, snapshot = await ProjectService.freeze_for_render(p.id, revision=2)
    assert rev_num == 2
    assert snapshot["timeline"]["duration_seconds"] == 10.0

    # User modifies at rev 2 -> 3
    await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=2,
        operation_type="add_clip",
        payload={"track_id": "track_video_main", "clip": {"id": "c2", "duration_seconds": 20.0}},
    )

    # Re-reading frozen rev 2 snapshot remains untouched!
    frozen_rev, frozen_snap = await ProjectService.freeze_for_render(p.id, revision=2)
    assert frozen_rev == 2
    assert frozen_snap["timeline"]["duration_seconds"] == 10.0
