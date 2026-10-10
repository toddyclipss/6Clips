# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
import json
import pytest
from backend.database import init_db
from backend.services.executor_service import ExecutorService
from backend.services.project_service import ProjectService
from backend.core.capabilities import CapabilityRegistry
from backend.core.exceptions import CapabilityPreconditionError, RevisionConflictError


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.mark.asyncio
async def test_capabilities_surface_filtering():
    create_caps = CapabilityRegistry.list_for_surface("create")
    assert any(c["name"] == "project_operation" for c in create_caps)
    assert any(c["name"] == "extract_clips" for c in create_caps)

    dist_caps = CapabilityRegistry.list_for_surface("distribute")
    assert any(c["name"] == "upload_youtube" for c in dist_caps)
    assert not any(c["name"] == "extract_clips" for c in dist_caps)


@pytest.mark.asyncio
async def test_capability_validation_missing_param():
    with pytest.raises(CapabilityPreconditionError):
        # Missing project_id and expected_revision
        CapabilityRegistry.validate_input("project_operation", {"operation_type": "add_clip"})


@pytest.mark.asyncio
async def test_executor_run_and_step_lifecycle():
    proj = await ProjectService.create_project(name="Executor Test Project")
    run = await ExecutorService.create_run(
        objective="Add clips to project",
        project_id=proj.id,
        input_revision=1,
    )
    assert run.id
    assert run.status == "running"
    assert run.resolved_provider in ("none", "anthropic", "openai", "openrouter")

    # Execute step 1: project_operation
    step_res = await ExecutorService.execute_step(
        run_id=run.id,
        step_name="Add intro cut",
        capability_name="project_operation",
        payload={
            "project_id": proj.id,
            "expected_revision": 1,
            "operation_type": "add_clip",
            "payload": {
                "track_id": "track_video_main",
                "clip": {"id": "c_intro", "duration_seconds": 12.0},
            },
        },
    )
    assert step_res["status"] == "success"
    assert step_res["verification"]["ok"] is True
    assert step_res["verification"]["new_revision"] == 2


@pytest.mark.asyncio
async def test_executor_bench_ranges_capability():
    proj = await ProjectService.create_project(name="Bench Ranges Executor Test")
    run = await ExecutorService.create_run(
        objective="Set bench ranges via Executor",
        project_id=proj.id,
        input_revision=1,
    )

    ranges = [{"id": "r1", "start": 2.5, "end": 7.0, "label": "Hook"}]
    step_res = await ExecutorService.execute_step(
        run_id=run.id,
        step_name="Persist Bench Ranges",
        capability_name="set_bench_ranges",
        payload={
            "project_id": proj.id,
            "expected_revision": 1,
            "source_id": "src_video_abc",
            "ranges": ranges,
        },
    )
    assert step_res["status"] == "success"
    assert step_res["verification"]["ok"] is True
    assert step_res["verification"]["new_revision"] == 2
    assert step_res["output"]["revision"] == 2

    # Verify Project document persisted the ranges
    import json
    p_res = await ProjectService.get_project(proj.id)
    assert p_res.revision == 2
    doc = json.loads(p_res.document_json)
    assert "bench_ranges" in doc
    assert doc["bench_ranges"]["src_video_abc"] == ranges


@pytest.mark.asyncio
async def test_executor_deterministic_tool_trim(tmp_path):
    from backend.models.downloaded_video import DownloadedVideo
    from backend.database import AsyncSessionLocal
    import subprocess

    # Create dummy source video with ffmpeg
    src_file = tmp_path / "test_src.mp4"
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=5:size=320x240:rate=30",
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-t", "5", "-c:v", "libx264", "-c:a", "aac", str(src_file)
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except Exception:
        # If ffmpeg is not available, skip
        pytest.skip("ffmpeg not available")

    async with AsyncSessionLocal() as db:
        dv = DownloadedVideo(
            user_id="local",
            title="Trim Test Input",
            video_path=str(src_file),
            duration_seconds=5.0,
        )
        db.add(dv)
        await db.commit()
        await db.refresh(dv)
        vid_id = dv.id

    run = await ExecutorService.create_run(objective="Test Tool Trim")
    step_res = await ExecutorService.execute_step(
        run_id=run.id,
        step_name="Trim first 2 seconds",
        capability_name="tool_trim",
        payload={
            "video_id": vid_id,
            "start_seconds": 0.0,
            "end_seconds": 2.0,
        },
    )
    assert step_res["status"] == "success"
    assert step_res["verification"]["ok"] is True
    assert "video_path" in step_res["output"]
    assert "generated_video_id" in step_res["output"]


@pytest.mark.asyncio
async def test_planner_capability_dispatch_integration():
    from backend.agents.planner import PlannerAgent
    from backend.core.ws_manager import ws_manager

    messages = []
    async def mock_send(msg, user_id="local"):
        messages.append(msg)

    orig_send = ws_manager.send
    ws_manager.send = mock_send
    try:
        planner = PlannerAgent()
        proj = await ProjectService.create_project(name="Planner Dispatch Test")
        action = {
            "type": "set_bench_ranges",
            "project_id": proj.id,
            "expected_revision": 1,
            "source_id": "src_test_123",
            "ranges": [{"id": "rng_1", "start": 1.0, "end": 3.0, "label": "Cut 1"}],
        }
        await planner._dispatch_action(action, user_settings=None, user_id="local")

        # Verify ws_manager received capability_executed event
        executed_events = [m for m in messages if m.get("type") == "capability_executed"]
        assert len(executed_events) == 1
        assert executed_events[0]["capability"] == "set_bench_ranges"
        assert executed_events[0]["status"] == "success"

        # Verify document updated to revision 2
        p_res = await ProjectService.get_project(proj.id)
        assert p_res.revision == 2
        doc = json.loads(p_res.document_json)
        assert doc["bench_ranges"]["src_test_123"][0]["label"] == "Cut 1"
    finally:
        ws_manager.send = orig_send

