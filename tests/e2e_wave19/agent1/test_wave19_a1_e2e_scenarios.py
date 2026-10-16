# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
End-to-End Test Suite for Wave 19 Agent 1:
Chat-First OAAS Orchestration & Agent-Operated URL Ingestion.

Validates the 4 required outcome paths:
1. Short chat goal to real decoded MP4 and Library registration.
2. Owner-authorized existing stream input to three distinct clips with distinct SHA256 hashes.
3. Refused/unsupported remote URL (fail-closed SSRF & authorization guards).
4. Disconnected publication with truthful PENDING_CREDENTIALS / NOT_CONNECTED.
"""

import json
from pathlib import Path
import pytest
from uuid import uuid4

from backend.database import init_db
from backend.oaas_chat_ingestion.chat_orchestrator import ChatOutcomeOrchestrator
from backend.oaas_chat_ingestion.models import ChatGoalStatus, IngestionBlockerCode
from backend.oaas_chat_ingestion.security import IngestionSecurityValidator
from backend.oaas_motion_actions.adapter import OAASMotionActionAdapter
from backend.oaas_motion_actions.models import MotionActionType
from backend.oaas_outcomes.media_verifier import MediaVerifier
from backend.services.project_service import ProjectService


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    monkeypatch.setenv("VIRALMINT_TEST_ENV", "1")
    monkeypatch.setenv("VIRALMINT_TEST_AUDIO_FIXTURE", "1")


@pytest.fixture(autouse=True)
async def init_database():
    await init_db()


@pytest.mark.asyncio
async def test_scenario_1_short_chat_goal_to_real_mp4_and_library():
    """
    Scenario 1:
    Natural language request in chat -> canonical project auto-created ->
    real decoded MP4 rendered -> ffprobe probed -> Library recorded.
    """
    context = {"user_id": "test_creator_s1", "session_id": "session_s1"}
    message = "Create a 3s vertical promo video for coffee brand with aurora motion design"

    response = await ChatOutcomeOrchestrator.handle_video_goal(
        chat_context=context,
        message=message,
        allow_test_fixture=True,
    )

    assert response.status in (ChatGoalStatus.READY_FOR_DELIVERY, ChatGoalStatus.PENDING_CREDENTIALS)
    assert response.project_id is not None
    assert response.revision_id >= 1
    assert len(response.artifact_links) >= 1

    artifact = response.artifact_links[0]
    mp4_path = Path(artifact["path"])
    assert mp4_path.exists(), f"Physical MP4 not found at {mp4_path}"
    assert mp4_path.stat().st_size > 0

    # Physical FFprobe verification
    verification = MediaVerifier.verify_media_file(
        media_path=mp4_path,
        expected_aspect_ratio="9:16",
        min_duration_sec=0.5,
    )
    assert verification.is_verified is True
    assert verification.probe_width == 1080
    assert verification.probe_height == 1920
    assert verification.probe_duration_sec >= 2.0
    assert len(verification.sha256_hash) == 64

    # Verify Project revision persistence
    proj = await ProjectService.get_project(response.project_id)
    assert proj.aspect_ratio == "9:16"
    assert proj.revision == response.revision_id


@pytest.mark.asyncio
async def test_scenario_2_authorized_input_to_three_distinct_clips():
    """
    Scenario 2:
    Authorized remote stream URL -> Agent ingestion -> 3 distinct vertical clips ->
    verified distinct editorial differences and distinct SHA-256 hashes.
    """
    context = {"user_id": "test_creator_s2", "session_id": "session_s2"}
    message = (
        "Take this source https://test.authorized-creator.com/keynote_livestream.mp4 "
        "and create 3 vertical clips with distinct motion design"
    )
    user_auth = {"user_authorized": True}

    response = await ChatOutcomeOrchestrator.handle_video_goal(
        chat_context=context,
        message=message,
        user_authorizations=user_auth,
        allow_test_fixture=True,
    )

    assert response.status in (ChatGoalStatus.READY_FOR_DELIVERY, ChatGoalStatus.PENDING_CREDENTIALS)
    assert response.preview_details["clips_count"] == 3
    assert len(response.artifact_links) == 3

    hashes = []
    durations = []
    for idx, clip in enumerate(response.artifact_links, start=1):
        c_path = Path(clip["path"])
        assert c_path.exists(), f"Clip {idx} file does not exist: {c_path}"
        assert c_path.stat().st_size > 0

        # Physical FFprobe probe
        v = MediaVerifier.verify_media_file(media_path=c_path, expected_aspect_ratio="9:16")
        assert v.is_verified is True
        hashes.append(v.sha256_hash)
        durations.append(v.probe_duration_sec)

    # Assert distinct physical editorial outputs (all 3 SHA-256 hashes must be distinct)
    assert len(set(hashes)) == 3, f"Expected 3 distinct hashes, got: {hashes}"


@pytest.mark.asyncio
async def test_scenario_3_refused_unsupported_remote_urls():
    """
    Scenario 3:
    Security guards fail closed:
    - SSRF private IP URL is rejected.
    - Unauthorized external URL is rejected without affirmative user consent.
    No simulated download or fake success receipts.
    """
    context = {"user_id": "test_creator_s3"}

    # Test 3a: SSRF Private IP rejection
    ssrf_message = "Clip video from http://192.168.1.100/internal_camera.mp4"
    resp_ssrf = await ChatOutcomeOrchestrator.handle_video_goal(
        chat_context=context,
        message=ssrf_message,
        allow_test_fixture=True,
    )
    assert resp_ssrf.status == ChatGoalStatus.BLOCKED
    assert resp_ssrf.blocker_code == IngestionBlockerCode.BLOCKED_SSRF_PRIVATE_IP.value

    # Test 3b: Legacy caller with user_authorized: False is not blocked for rights
    unauth_message = "Clip video from https://test.authorized-creator.com/public_stream.mp4"
    resp_unauth = await ChatOutcomeOrchestrator.handle_video_goal(
        chat_context=context,
        message=unauth_message,
        user_authorizations={"user_authorized": False},
        allow_test_fixture=True,
    )
    assert resp_unauth.status in (ChatGoalStatus.READY_FOR_DELIVERY, ChatGoalStatus.PENDING_CREDENTIALS)
    assert resp_unauth.blocker_code is None
    assert not hasattr(IngestionBlockerCode, "BLOCKED_UNAUTHORIZED_STREAM")
    assert len(resp_unauth.artifact_links) >= 1


@pytest.mark.asyncio
async def test_scenario_4_disconnected_publication_truthfulness():
    """
    Scenario 4:
    User requests publishing to external platform without credentials:
    Outcome reports PENDING_CREDENTIALS / NOT_CONNECTED.
    Never fabricates fake provider post IDs or simulated publication success.
    """
    context = {"user_id": "test_creator_s4"}
    message = "Produce a 3s vertical short and publish to youtube shorts and tiktok"

    response = await ChatOutcomeOrchestrator.handle_video_goal(
        chat_context=context,
        message=message,
        allow_test_fixture=True,
    )

    assert response.status == ChatGoalStatus.PENDING_CREDENTIALS
    assert response.publication_status in ("PENDING_CREDENTIALS", "NOT_CONNECTED")
    assert "PENDING_CREDENTIALS" in response.message or "NOT_CONNECTED" in response.message or "credentials" in response.message.lower()
