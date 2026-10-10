# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests proving persistent async Run resume when a background Job completes."""
import pytest
import json
import subprocess
from uuid import uuid4
from sqlalchemy import select

from backend.database import init_db, AsyncSessionLocal
from backend.models.job import Job
from backend.models.execution import ExecutionRun, ExecutionStep
from backend.models.downloaded_video import DownloadedVideo
from backend.agents.job_helper import create_job, update_job_status
from backend.services.executor_service import ExecutorService
from backend.services.project_service import ProjectService


@pytest.mark.asyncio
async def test_async_job_completion_recovers_run_and_resumes_next_step(tmp_path):
    await init_db()

    # 1. Create dummy video for the subsequent step
    test_video = tmp_path / "resume_source.mp4"
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=5:size=320x240:rate=30",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "5",
        "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p",
        str(test_video)
    ]
    subprocess.run(cmd, capture_output=True, check=True)

    dv_id = f"dv_resume_{uuid4().hex[:8]}"
    async with AsyncSessionLocal() as db:
        dv = DownloadedVideo(
            id=dv_id,
            user_id="local",
            title="Video for Resume",
            video_path=str(test_video),
            duration_seconds=5,
        )
        db.add(dv)
        await db.commit()

    # 2. Create project
    proj = await ProjectService.create_project("Async Resume Project")

    # 3. Create a background Job simulating an asynchronous task
    job = await create_job("generate", "local", {"type": "heavy_render"})
    assert job.status == "pending"

    # 4. Create an ExecutionRun with a queued pending step
    pending_next_step = {
        "capability": "suggest_clips",
        "name": "Step 2: Propose moments",
        "payload": {
            "video_id": dv_id,
            "max_clips": 2,
        }
    }
    run = await ExecutorService.create_run(
        objective="Run that waits on background job then resumes",
        project_id=proj.id,
        user_id="local",
    )
    # Store pending_steps in run context
    async with AsyncSessionLocal() as db:
        r_db = await db.get(ExecutionRun, run.id)
        r_db.context_json = json.dumps({"pending_steps": [pending_next_step]})
        await db.commit()

    # 5. Start Step 1 linked to the background Job
    step1_res = await ExecutorService.execute_step(
        run_id=run.id,
        step_name="Step 1: Background Job",
        capability_name="project_operation",
        payload={
            "project_id": proj.id,
            "expected_revision": 1,
            "operation_type": "patch_document",
            "payload": {"patch": {"render_started": True}},
            "job_id": job.id,
            "wait_for_job": True,
        },
        job_id=job.id,
        authorized=True,
    )

    assert step1_res["status"] == "running"
    assert step1_res["waiting_for_job"] is True

    # Verify Step 1 is in running state in DB with unverified status
    async with AsyncSessionLocal() as db:
        s1 = await db.get(ExecutionStep, step1_res["step_id"])
        assert s1.status == "running"
        assert s1.job_id == job.id
        assert s1.verification_status == "unverified"

    # 6. Background Job completes! This invokes update_job_status
    # which triggers ExecutorService.handle_job_completed
    await update_job_status(
        job_id=job.id,
        status="success",
        output_data={"status": "completed", "artifact": "rendered.mp4"},
    )

    # 7. Verification: check that Step 1 was recovered, verified, and Step 2 was resumed!
    async with AsyncSessionLocal() as db:
        # Step 1 should be verified
        s1_after = await db.get(ExecutionStep, step1_res["step_id"])
        assert s1_after.status == "success"
        assert s1_after.verification_status == "verified"
        assert s1_after.output_payload_json is not None

        # Step 2 should have been created and executed by the resume loop
        steps_res = await db.execute(
            select(ExecutionStep)
            .where(ExecutionStep.run_id == run.id)
            .order_by(ExecutionStep.step_number)
        )
        all_steps = steps_res.scalars().all()
        assert len(all_steps) == 2, f"Expected 2 steps, got {len(all_steps)}"
        s2 = all_steps[1]
        assert s2.capability == "suggest_clips"
        assert s2.status == "success"
        assert s2.verification_status == "verified"

        # Run should now be marked completed
        r_after = await db.get(ExecutionRun, run.id)
        assert r_after.status == "completed"
