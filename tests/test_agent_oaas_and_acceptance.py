# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
import asyncio
import json
import subprocess
import pytest
from pathlib import Path

from backend.database import init_db, AsyncSessionLocal
from backend.services.project_service import ProjectService
from backend.services.executor_service import ExecutorService
from backend.services.hyperframes_adapter import HyperFramesAdapter
from backend.services.motion_render_service import MotionRenderService
from backend.agents.planner import PlannerAgent
from backend.core.capabilities import CapabilityRegistry
from backend.models.execution import ExecutionRun, ExecutionStep
from backend.core.exceptions import RevisionConflictError
from backend.core.ws_manager import ws_manager
from backend.config import settings
from sqlalchemy import select


@pytest.fixture(autouse=True)
async def setup_database():
    await init_db()


@pytest.mark.asyncio
async def test_provider_and_model_pinned_per_run():
    """Verify that provider and model are pinned per ExecutionRun."""
    run = await ExecutorService.create_run(
        objective="Generate short video hook",
        provider="anthropic",
        model="claude-3-5-sonnet-20241022",
        budget_limit_usd=0.05,
    )
    assert run.id
    assert run.status == "running"
    assert run.resolved_provider == "anthropic"
    assert run.resolved_model == "claude-3-5-sonnet-20241022"
    assert run.budget_limit_usd == 0.05

    async with AsyncSessionLocal() as db:
        db_run = await db.get(ExecutionRun, run.id)
        assert db_run.resolved_provider == "anthropic"
        assert db_run.resolved_model == "claude-3-5-sonnet-20241022"


@pytest.mark.asyncio
async def test_agent_observe_verify_replan_on_conflict():
    """
    Test user + agent concurrent editing on the same project:
    1. Project created at revision 1.
    2. User concurrently edits project -> bumps to revision 2.
    3. Agent attempts step with expected_revision=1.
    4. Observe -> Verify -> Replan catches RevisionConflictError,
       reads latest revision 2, replans with expected_revision=2,
       and successfully bumps to revision 3 without data loss.
    """
    events = []
    async def mock_send(msg, user_id="local"):
        events.append(msg)

    orig_send = ws_manager.send
    ws_manager.send = mock_send
    try:
        planner = PlannerAgent()
        proj = await ProjectService.create_project(name="Concurrent Workspace Project")
        assert proj.revision == 1

        # User edits first (bumping revision to 2)
        user_res = await ProjectService.apply_operation(
            project_id=proj.id,
            expected_revision=1,
            operation_type="update_document",
            payload={"document": {"title": "User Edited Title", "aspect_ratio": "9:16", "timeline": {"tracks": []}}},
            author="user",
        )
        assert user_res["revision"] == 2

        # Agent executes an action that thought expected_revision was 1
        agent_action = {
            "type": "project_operation",
            "project_id": proj.id,
            "expected_revision": 1,  # Stale revision!
            "operation_type": "add_clip",
            "payload": {
                "track_id": "track_video_main",
                "clip": {"id": "c_agent", "title": "Agent Proposed Cut", "duration_seconds": 4.5},
            },
        }

        # Dispatch via planner
        await planner._dispatch_action(agent_action, user_settings=None, user_id="local")

        # Project should now be at revision 3 (user edit + agent replanned edit)
        proj_updated = await ProjectService.get_project(proj.id)
        assert proj_updated.revision == 3
        doc = json.loads(proj_updated.document_json)
        assert doc["title"] == "User Edited Title"  # Preserved user change!
        # Preserved agent addition
        track = next(t for t in doc["timeline"]["tracks"] if t["id"] == "track_video_main")
        assert any(c["id"] == "c_agent" for c in track["clips"])

        # Check WebSocket messages indicate update
        update_events = [e for e in events if e.get("type") == "project_updated"]
        assert len(update_events) >= 1
        assert update_events[-1]["revision"] == 3
    finally:
        ws_manager.send = orig_send


@pytest.mark.asyncio
async def test_agent_multi_step_observe_verify_replan_execution():
    """
    Test PlannerAgent.execute_plan running a multi-step objective:
    Step 1: Set bench ranges
    Step 2: Add clip to timeline
    Observes verification evidence for each step, commits runs.
    """
    events = []
    async def mock_send(msg, user_id="local"):
        events.append(msg)

    orig_send = ws_manager.send
    ws_manager.send = mock_send
    try:
        planner = PlannerAgent()
        proj = await ProjectService.create_project(name="Multi-step OaaS Project")

        plan = [
            {
                "capability": "set_bench_ranges",
                "name": "Persist Source Bench Ranges",
                "payload": {
                    "source_id": "src_video_xyz",
                    "ranges": [{"id": "r1", "start": 0.0, "end": 5.0, "label": "Hook 1"}],
                },
            },
            {
                "capability": "project_operation",
                "name": "Add Cut to Timeline",
                "payload": {
                    "operation_type": "add_clip",
                    "payload": {
                        "track_id": "track_video_main",
                        "clip": {"id": "c1", "title": "Hook Cut", "duration_seconds": 5.0},
                    },
                },
            },
        ]

        result = await planner.execute_plan(
            objective="Produce 5-second teaser from source bench",
            plan_steps=plan,
            project_id=proj.id,
            user_id="local",
            provider="deterministic",
            model="offline",
        )

        assert result["status"] == "completed"
        assert len(result["steps"]) == 2
        assert all(s["verification"]["ok"] for s in result["steps"])

        # Verify DB run state
        async with AsyncSessionLocal() as db:
            run_row = await db.get(ExecutionRun, result["run_id"])
            assert run_row.status == "completed"
            assert run_row.completed_at is not None

            step_rows = (await db.execute(
                select(ExecutionStep).where(ExecutionStep.run_id == result["run_id"])
            )).scalars().all()
            assert len(step_rows) == 2
            assert all(s.verification_status == "verified" for s in step_rows)

        # Verify document updated to revision 3
        proj_final = await ProjectService.get_project(proj.id)
        assert proj_final.revision == 3
        doc = json.loads(proj_final.document_json)
        assert "bench_ranges" in doc
        assert doc["bench_ranges"]["src_video_xyz"][0]["label"] == "Hook 1"
    finally:
        ws_manager.send = orig_send


@pytest.mark.asyncio
async def test_suggest_clips_capability_and_executor():
    """Verify suggest_clips capability is registered and produces verified suggestions."""
    from backend.models.downloaded_video import DownloadedVideo
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "dummy_for_suggest.mp4"
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=15:size=320x240:rate=30",
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", "15", "-c:v", "libx264", "-c:a", "aac", str(src)
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except Exception:
            pytest.skip("ffmpeg not available")

        async with AsyncSessionLocal() as db:
            dv = DownloadedVideo(
                user_id="local",
                title="Podcast Episode 1",
                video_path=str(src),
                duration_seconds=15.0,
            )
            db.add(dv)
            await db.commit()
            await db.refresh(dv)
            video_id = dv.id

        run = await ExecutorService.create_run(objective="Ask AI suggest clips")
        step_res = await ExecutorService.execute_step(
            run_id=run.id,
            step_name="Suggest viral moments",
            capability_name="suggest_clips",
            payload={"video_id": video_id, "max_clips": 3, "min_duration": 3.0, "max_duration": 6.0},
        )
        assert step_res["status"] == "success"
        assert step_res["verification"]["ok"] is True
        assert step_res["verification"]["count"] == 3
        assert len(step_res["output"]["suggestions"]) == 3


@pytest.mark.asyncio
async def test_real_hyperframes_chromium_render_and_ffprobe(tmp_path):
    """
    End-to-end verification of real HyperFrames / Chromium render:
    ProjectRevision -> HyperFrames -> Chromium -> actual MP4 -> ffprobe stream check.
    """
    proj = await ProjectService.create_project(name="HyperFrames E2E Render", aspect_ratio="9:16")
    doc = {
        "title": "HyperFrames Verified Composition",
        "aspect_ratio": "9:16",
        "timeline": {
            "duration_seconds": 1.0,
            "tracks": [
                {
                    "id": "t_text",
                    "type": "text",
                    "clips": [{"id": "c1", "text": "ViralMint E2E Render", "duration_seconds": 1.0}],
                }
            ],
        },
    }
    await ProjectService.apply_operation(
        project_id=proj.id,
        expected_revision=1,
        operation_type="update_document",
        payload={"document": doc},
    )

    rev, work_dir = await HyperFramesAdapter.stage_project_for_render(proj.id, revision=2)
    out_mp4 = tmp_path / "hf_render_verified.mp4"

    try:
        rendered = await MotionRenderService.render_project(
            work_dir,
            aspect="9:16",
            out_path=out_mp4,
            keep=True,
        )
        assert rendered.is_file()
        assert rendered.stat().st_size > 5000

        # ffprobe verification
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration,size:stream=codec_name,width,height",
            "-of", "json",
            str(rendered),
        ]
        probe_res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        meta = json.loads(probe_res.stdout)
        streams = meta.get("streams", [])
        assert len(streams) >= 1
        video_stream = streams[0]
        assert video_stream["codec_name"] == "h264"
        assert int(video_stream["width"]) == 2160  # 4K supersampled 9:16
        assert int(video_stream["height"]) == 3840
        duration = float(meta["format"]["duration"])
        assert 0.9 <= duration <= 1.5
    finally:
        import shutil
        shutil.rmtree(work_dir, ignore_errors=True)
