# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Comprehensive Test Suite for OAAS Outcome Delivery (Wave 17 Agent 1).
Tests:
- Outcome state machine transitions and invalid transition rejection
- Physical media verification requirement for VERIFIED state
- Autonomous block selection (37 operable originals only, truthful rejection of 159 unported and retired blocks)
- Fail-closed distribution handoff without mock/dummy publisher
- Idempotent duplicate dispatch guard
- Interruption recovery and crash resumability
- Real local physical render & ffprobe decode
- Database persistence to Project, ProjectRevision, and GeneratedVideo
"""

import asyncio
from datetime import datetime
import json
from pathlib import Path
import pytest
from sqlalchemy import select
from uuid import uuid4

from backend.database import AsyncSessionLocal, init_db
from backend.models.connected_channel import ConnectedChannel
from backend.models.generated_video import GeneratedVideo
from backend.models.project import Project
from backend.oaas_outcomes.adapter import OAASOutcomeAdapter
from backend.oaas_outcomes.block_selector import (
    BlockSelector,
    OPERABLE_ORIGINALS_37,
    RETIRED_BLOCKS,
)
from backend.oaas_outcomes.distribution_handoff import DistributionHandoffManager
from backend.oaas_outcomes.engine import OutcomeDeliveryEngine
from backend.oaas_outcomes.media_verifier import MediaVerificationError, MediaVerifier
from backend.oaas_outcomes.models import (
    Agent5DistributionHandoffContract,
    DurationPolicy,
    MediaVerificationResult,
    OutcomeJobRecord,
    OutcomeJobState,
    OutcomePlan,
    OutcomeRequestContract,
)
from backend.oaas_outcomes.state_machine import (
    InvalidStateTransitionError,
    OutcomeStateMachine,
)


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    monkeypatch.setenv("VIRALMINT_TEST_AUDIO_FIXTURE", "1")


@pytest.mark.asyncio
async def test_state_machine_strict_linear_transitions():
    """State machine must enforce strict linear progression and reject illegal leaps."""
    req = OutcomeRequestContract(user_intent="Test linear progression")
    job = OutcomeJobRecord(request=req, state=OutcomeJobState.REQUESTED)
    sm = OutcomeStateMachine(job)

    # Cannot jump from REQUESTED to RENDERED or READY_FOR_DELIVERY
    with pytest.raises(InvalidStateTransitionError):
        sm.transition_to(OutcomeJobState.RENDERED)

    with pytest.raises(InvalidStateTransitionError):
        sm.transition_to(OutcomeJobState.READY_FOR_DELIVERY)

    # Valid step 1: REQUESTED -> PLANNED
    sm.transition_to(OutcomeJobState.PLANNED, reason="Plan created")
    assert sm.current_state == OutcomeJobState.PLANNED

    # Valid step 2: PLANNED -> PRODUCING
    sm.transition_to(OutcomeJobState.PRODUCING, reason="Project initialized")
    assert sm.current_state == OutcomeJobState.PRODUCING

    # Valid step 3: PRODUCING -> RENDERED
    sm.transition_to(OutcomeJobState.RENDERED, reason="Render finished")
    assert sm.current_state == OutcomeJobState.RENDERED

    # Cannot transition to VERIFIED without verified media result
    with pytest.raises(InvalidStateTransitionError):
        sm.transition_to(OutcomeJobState.VERIFIED)

    # Provide valid verified media result
    fake_ver = MediaVerificationResult(
        file_path="C:/tmp/test.mp4",
        file_size_bytes=2048,
        sha256_hash="abc12345",
        probe_width=1080,
        probe_height=1920,
        probe_duration_sec=3.0,
        video_codec="h264",
        is_verified=True,
    )
    sm.transition_to(OutcomeJobState.VERIFIED, verification_result=fake_ver)
    assert sm.current_state == OutcomeJobState.VERIFIED

    # Check audit history has all 4 transitions
    assert len(job.history) == 4
    assert job.history[0].from_state == OutcomeJobState.REQUESTED
    assert job.history[0].to_state == OutcomeJobState.PLANNED


def test_block_selector_operable_vs_unported_and_retired():
    """Selector must only pick from the 37 operable originals, never unported or retired blocks."""
    assert len(OPERABLE_ORIGINALS_37) == 37

    # Verify retired blocks are strictly disallowed
    for r in RETIRED_BLOCKS:
        is_avail, reason = BlockSelector.check_block_availability(r)
        assert not is_avail
        assert "retired" in reason.lower()

    # Verify unported block is truthfully rejected and replaced
    unported_id = "liquid-paint-splash-unported"
    is_avail, reason = BlockSelector.check_block_availability(unported_id)
    assert not is_avail
    assert "unported" in reason.lower()

    # Selecting with unported block requested must substitute with a verified operable original
    chosen_id, cat, rationale = BlockSelector.select_operable_block(
        intent_text="Make a financial chart video",
        requested_block_id=unported_id,
    )
    assert chosen_id in OPERABLE_ORIGINALS_37
    assert "not operable" in rationale
    assert chosen_id == "data-chart"

    # Selecting with retired block requested must substitute
    chosen_id, cat, rationale = BlockSelector.select_operable_block(
        intent_text="Tech futuristic overlay",
        requested_block_id="creator-hud",
    )
    assert chosen_id in OPERABLE_ORIGINALS_37
    assert "retired" in rationale


def test_media_verifier_on_missing_and_empty_files(tmp_path):
    """MediaVerifier must strictly fail on missing, 0-byte, or corrupt files."""
    missing_file = tmp_path / "does_not_exist.mp4"
    with pytest.raises(MediaVerificationError, match="missing on disk"):
        MediaVerifier.verify_media_file(missing_file, raise_on_failure=True)

    # Empty 0-byte file
    empty_file = tmp_path / "empty.mp4"
    empty_file.write_bytes(b"")
    with pytest.raises(MediaVerificationError, match="empty or too small"):
        MediaVerifier.verify_media_file(empty_file, raise_on_failure=True)

    # Corrupt tiny file (<1KB)
    corrupt_file = tmp_path / "corrupt.mp4"
    corrupt_file.write_bytes(b"not a valid mp4 header data")
    with pytest.raises(MediaVerificationError, match="too small"):
        MediaVerifier.verify_media_file(corrupt_file, raise_on_failure=True)


@pytest.mark.asyncio
async def test_distribution_handoff_fail_closed_without_credentials():
    """Handoff must fail closed if channel is unconnected or lacks credentials."""
    await init_db()

    # Test with unregistered channel
    handoff = await DistributionHandoffManager.prepare_handoff_contract(
        job_id="job_test_fail_closed",
        idempotency_token="idem_test_123",
        render_file_sha256="dummy_hash_for_test",
        media_path="C:/dummy/path.mp4",
        project_id="proj_1",
        revision_id=1,
        destination_channel="youtube_shorts",
        user_id="user_unconnected",
        user_authorized=True,
    )
    assert handoff.fail_closed is True
    assert handoff.provider_status == "PENDING_CREDENTIALS"
    assert "No connected channel found" in (handoff.error_truth or "")


@pytest.mark.asyncio
async def test_distribution_handoff_connected_with_credentials():
    """Handoff succeeds when channel is connected with valid credentials and user authorization."""
    await init_db()

    test_uid = f"user_conn_{uuid4().hex[:6]}"
    async with AsyncSessionLocal() as db:
        ch = ConnectedChannel(
            user_id=test_uid,
            platform="youtube",
            channel_url="https://youtube.com/@test_channel",
            channel_name="Test Creator Channel",
            auth_type="oauth_publishing",
            can_publish=True,
            credentials_ref="cred_token_vault_ref",
        )
        db.add(ch)
        await db.commit()

    handoff = await DistributionHandoffManager.prepare_handoff_contract(
        job_id="job_test_connected",
        idempotency_token="idem_test_connected",
        render_file_sha256="valid_sha256",
        media_path="C:/dummy/path.mp4",
        project_id="proj_2",
        revision_id=1,
        destination_channel="youtube_shorts",
        user_id=test_uid,
        user_authorized=True,
    )
    assert handoff.fail_closed is False
    assert handoff.provider_status == "CONNECTED"
    assert handoff.error_truth is None


@pytest.mark.asyncio
async def test_idempotent_duplicate_dispatch_guard():
    """Submitting the exact same idempotency token must return existing job without re-dispatching."""
    await init_db()

    token = f"idem_dup_{uuid4().hex}"
    req = OutcomeRequestContract(
        user_intent="Explain inflation and interest rates in 3 seconds",
        idempotency_token=token,
        minimal_preferences={
            "aspect_ratio": "9:16",
            "duration_seconds": 3.0,
            "duration_policy": DurationPolicy.TARGET,
        },
    )

    job1 = await OutcomeDeliveryEngine.execute_outcome(req, allow_test_fixture=True)
    assert job1.job_id is not None

    # Dispatch second time with same token
    job2 = await OutcomeDeliveryEngine.execute_outcome(req, allow_test_fixture=True)
    assert job2.job_id == job1.job_id
    assert job2.created_at == job1.created_at


@pytest.mark.asyncio
async def test_cancellation_and_resumability():
    """Jobs can be truthfully cancelled or reconciled after crash."""
    req = OutcomeRequestContract(
        user_intent="Test cancellation workflow",
        idempotency_token=f"idem_cancel_{uuid4().hex}",
    )
    job = OutcomeJobRecord(request=req, state=OutcomeJobState.REQUESTED)
    OutcomeDeliveryEngine._save_job(job)

    # Cancel job
    cancelled = OutcomeDeliveryEngine.cancel_job(job.job_id, reason="User clicked stop")
    assert cancelled.state == OutcomeJobState.CANCELLED

    # Reconciliation on incomplete job without render
    job_crash = OutcomeJobRecord(
        request=req,
        state=OutcomeJobState.PRODUCING,
        job_id=f"crash_{uuid4().hex[:8]}",
    )
    OutcomeDeliveryEngine._save_job(job_crash)

    reconciled = await OutcomeDeliveryEngine.reconcile_job(job_crash.job_id)
    assert reconciled is not None
    assert reconciled.state == OutcomeJobState.FAILED
    assert "interrupted" in reconciled.error_truth.lower()


@pytest.mark.asyncio
async def test_real_end_to_end_local_outcome_delivery():
    """
    Genuine end-to-end local outcome delivery:
    User request -> Plan -> Project -> Physical MP4 Render -> ffprobe verify -> Library -> Distribution Handoff.
    """
    await init_db()

    unique_goal = f"Quick analysis of market volatility - {uuid4().hex[:6]}"
    job = await OAASOutcomeAdapter.execute_goal(
        user_goal=unique_goal,
        channel_targets=["youtube_shorts"],
        preferences={
            "aspect_ratio": "9:16",
            "duration_seconds": 3.0,
            "duration_policy": DurationPolicy.TARGET,
            "language": "en",
        },
        standing_authorization=False,
        session_id="e2e_test_session",
        user_id="local",
        allow_test_fixture=True,
    )

    # 1. State must be verified or pending credentials
    assert job.state in (OutcomeJobState.VERIFIED, OutcomeJobState.PENDING_CREDENTIALS, OutcomeJobState.NEEDS_APPROVAL)

    # 2. Operable HyperFrames block selected
    assert job.plan is not None
    assert job.plan.selected_block_id in OPERABLE_ORIGINALS_37

    # 3. Project and revision recorded
    assert job.project_id is not None
    assert job.revision_id == 1

    # Verify project exists in database
    async with AsyncSessionLocal() as db:
        p = await db.get(Project, job.project_id)
        assert p is not None
        assert p.aspect_ratio == "9:16"

    # 4. Media verification must be genuinely verified
    assert job.media_verification is not None
    assert job.media_verification.is_verified is True
    assert job.media_verification.file_size_bytes > 50000
    assert len(job.media_verification.sha256_hash) == 64
    assert job.media_verification.probe_width == 1080
    assert job.media_verification.probe_height == 1920
    assert job.media_verification.probe_duration_sec > 1.0

    # 5. Persisted in Library
    assert job.library_asset_id is not None
    async with AsyncSessionLocal() as db:
        gv = await db.get(GeneratedVideo, job.library_asset_id)
        assert gv is not None
        assert gv.video_path == job.media_verification.file_path

    # 6. Distribution handoff contract present and fail-closed
    assert job.distribution_handoff is not None
    assert job.distribution_handoff.fail_closed is True
    assert job.distribution_handoff.render_file_sha256 == job.media_verification.sha256_hash
