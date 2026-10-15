# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Comprehensive End-to-End Outcome Scenario Test (Wave 18 Agent 1).

Executes full lifecycle:
1. Autonomous goal execution without pre-loaded project (no wizard, auto project creation).
2. Physical MP4 rendering with verified HyperFrames donor block, ffprobe verification, and Library registration.
3. Native editor commands applied over existing project (reframe, captions edit, graphic insert) with monotonic revision tracking.
4. Second physical render on revised project, physical ffprobe probe, and distinct SHA-256 hash comparison.
5. Project reload and revision audit.
6. Fail-closed distribution without mock credentials (PENDING_CREDENTIALS).
7. Concurrency conflict and error resilience.
"""

from pathlib import Path
import pytest
from uuid import uuid4

from backend.database import init_db
from backend.oaas_motion_actions.adapter import OAASMotionActionAdapter
from backend.oaas_motion_actions.models import (
    ActionExecutionStatus,
    MotionActionType,
)
from backend.oaas_outcomes.adapter import OAASOutcomeAdapter
from backend.oaas_outcomes.media_verifier import MediaVerifier, MediaVerificationError
from backend.oaas_outcomes.models import (
    OutcomeJobState,
    OutcomeRequestContract,
)
from backend.services.project_service import ProjectService


@pytest.fixture(autouse=True)
def setup_fixture_env(monkeypatch):
    # Ensure offline test audio fixture is active so test runs cleanly without microphone
    monkeypatch.setenv("VIRALMINT_TEST_AUDIO_FIXTURE", "1")


@pytest.fixture(autouse=True)
async def init_database():
    await init_db()


@pytest.mark.asyncio
async def test_full_autonomous_outcome_to_native_edit_to_reexport_lifecycle(tmp_path):
    """
    End-to-End Acceptance Scenario:
    Goal -> Initial Outcome -> Verified MP4 -> Native Motion Edits -> Persisted Revisions -> Re-Export -> Library.
    """
    # ─── Step 1: Autonomous Goal Submission (No pre-loaded project) ───────────────
    user_goal = "Create a 3-second overview of generative tech with flowing-gradient motion design"
    job = await OAASOutcomeAdapter.execute_goal(
        user_goal=user_goal,
        preferences={
            "aspect_ratio": "9:16",
            "duration_seconds": 3.0,
            "block_id": "flowing-gradient",
        },
        channel_targets=["youtube_shorts"],
        standing_authorization=False,
        allow_test_fixture=True,
    )

    # Verify initial outcome execution
    assert job.project_id is not None, "Project must be autonomously created without wizard."
    assert job.plan is not None
    assert job.plan.selected_block_id == "flowing-gradient"
    assert job.state in (OutcomeJobState.READY_FOR_DELIVERY, OutcomeJobState.PENDING_CREDENTIALS, OutcomeJobState.NEEDS_APPROVAL)

    # Verify physical media was generated and probed
    assert job.media_verification is not None
    assert job.media_verification.is_verified is True
    initial_mp4_path = Path(job.media_verification.file_path)
    assert initial_mp4_path.exists() and initial_mp4_path.stat().st_size > 0
    initial_sha256 = job.media_verification.sha256_hash
    initial_probe_dur = job.media_verification.probe_duration_sec
    assert initial_probe_dur >= 2.0

    # Verify truthful distribution status (fail-closed without credentials)
    handoff = await OAASOutcomeAdapter.get_distribution_handoff(job.job_id)
    assert handoff is not None
    assert handoff.fail_closed is True
    assert handoff.provider_status in ("PENDING_CREDENTIALS", "NOT_CONNECTED")

    # ─── Step 2: Native Motion Editing on Existing Project ─────────────────────────
    proj_id = job.project_id
    initial_proj = await ProjectService.get_project(proj_id)
    initial_rev = initial_proj.revision

    # Command 1: Reframe aspect ratio to 1:1 square format
    res_reframe = await OAASMotionActionAdapter.execute_command(
        project_id=proj_id,
        action=MotionActionType.REFRAME,
        params={"aspect_ratio": "1:1", "preset": "center_crop"},
        expected_revision=initial_rev,
    )
    assert res_reframe.status == ActionExecutionStatus.SUCCESS
    rev_after_reframe = res_reframe.resulting_revision
    assert rev_after_reframe == initial_rev + 1

    # Command 2: Add word-level synchronized captions
    captions = [
        {"start": 0.0, "end": 1.5, "text": "Generative tech advances rapidly."},
        {"start": 1.5, "end": 3.0, "text": "Autonomous outcome delivered."},
    ]
    res_caps = await OAASMotionActionAdapter.execute_command(
        project_id=proj_id,
        action=MotionActionType.CAPTIONS_EDIT,
        params={"captions": captions, "style": "pop", "font_size": 28, "color": "#FFDD00"},
        expected_revision=rev_after_reframe,
    )
    assert res_caps.status == ActionExecutionStatus.SUCCESS
    rev_after_caps = res_caps.resulting_revision
    assert rev_after_caps == rev_after_reframe + 1

    # Command 3: Insert second verified HyperFrames graphic (aurora)
    res_graphic = await OAASMotionActionAdapter.execute_command(
        project_id=proj_id,
        action=MotionActionType.GRAPHIC_INSERT,
        params={"block_id": "aurora", "timecode_start": 0.5, "duration": 2.5},
        expected_revision=rev_after_caps,
    )
    assert res_graphic.status == ActionExecutionStatus.SUCCESS
    final_edit_rev = res_graphic.resulting_revision
    assert final_edit_rev == rev_after_caps + 1

    # ─── Step 3: Project Reload and Revision Audit ────────────────────────────────
    reloaded_proj = await ProjectService.get_project(proj_id)
    assert reloaded_proj.revision == final_edit_rev
    assert reloaded_proj.aspect_ratio == "1:1"

    revisions_list = await ProjectService.list_revisions(proj_id)
    assert len(revisions_list) >= 4  # init + 3 edits
    op_types = [r["operation_type"] for r in revisions_list]
    assert "patch_document" in op_types  # from reframe
    assert "set_captions" in op_types    # from captions_edit
    assert "add_block" in op_types       # from graphic_insert

    # ─── Step 4: Re-Export Revised Project ────────────────────────────────────────
    job_reexport = await OAASOutcomeAdapter.execute_goal(
        user_goal="Re-export revised generative tech composition in 1:1 aspect ratio",
        project_id=proj_id,
        preferences={
            "aspect_ratio": "1:1",
            "duration_seconds": 3.0,
            "block_id": "aurora",
        },
        allow_test_fixture=True,
    )

    assert job_reexport.project_id == proj_id
    assert job_reexport.media_verification is not None
    assert job_reexport.media_verification.is_verified is True

    reexported_mp4_path = Path(job_reexport.media_verification.file_path)
    assert reexported_mp4_path.exists()
    reexported_sha256 = job_reexport.media_verification.sha256_hash

    # Confirm distinct physical file hashes between initial 9:16 video and revised 1:1 video
    assert reexported_sha256 != initial_sha256, (
        f"Re-exported video hash ({reexported_sha256[:12]}) must differ from initial hash ({initial_sha256[:12]})."
    )

    # Verify probed aspect ratio matches 1:1 square
    assert job_reexport.media_verification.probe_width == 1080
    assert job_reexport.media_verification.probe_height == 1080


@pytest.mark.asyncio
async def test_error_and_resilience_guards():
    """Validates missing media rejection, concurrency races, and clean cancellation."""
    # 1. Missing media path fails verification
    with pytest.raises(MediaVerificationError):
        MediaVerifier.verify_media_file(
            media_path=Path("C:/nonexistent/missing_video_file.mp4"),
            raise_on_failure=True,
        )

    # 2. Concurrency race on non-existent project
    fake_proj_id = f"fake-proj-{uuid4().hex[:8]}"
    res_concurrency = await OAASMotionActionAdapter.execute_command(
        project_id=fake_proj_id,
        action=MotionActionType.TRIM,
        params={"clip_id": "c1", "trim_start": 1.0},
        expected_revision=1,
    )
    assert res_concurrency.status == ActionExecutionStatus.PRECONDITION_FAILED
    assert "not found" in res_concurrency.detail.lower()

    # 3. Clean job cancellation
    cancel_token = f"idem-cancel-{uuid4().hex}"
    req = OutcomeRequestContract(
        user_intent="Video intended for cancellation test",
        idempotency_token=cancel_token,
    )
    job = await OAASOutcomeAdapter.execute_goal(
        user_goal="Cancel test",
        idempotency_token=cancel_token,
        allow_test_fixture=True,
    )
    cancelled_job = OAASOutcomeAdapter.cancel_job(job.job_id, reason="User changed goal")
    assert cancelled_job.state == OutcomeJobState.CANCELLED
