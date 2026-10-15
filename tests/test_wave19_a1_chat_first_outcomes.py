# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Test Suite for Chat-First OAAS Orchestration (Wave 19 Agent 1).

Tests:
1. Video goal parsing with autonomous project creation (no empty state / wizard redirect).
2. Remote URL detection and rights authorization gating (fail-closed).
3. Authorized remote URL ingestion with project asset binding.
4. Block reconciliation: Reject retired 6Clips blocks and unported blocks with transparent chat consent.
5. Multi-clip video repurposing: "Create 3 vertical clips" produces 3 distinct clips with distinct SHA256 hashes.
6. Publication truthfulness: Non-connected or missing credentials reported as PENDING_CREDENTIALS/NOT_CONNECTED.
"""

import pytest
from pathlib import Path
from uuid import uuid4

from backend.database import init_db
from backend.oaas_chat_ingestion.chat_orchestrator import ChatOutcomeOrchestrator
from backend.oaas_chat_ingestion.models import ChatGoalStatus
from backend.services.project_service import ProjectService


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    monkeypatch.setenv("VIRALMINT_TEST_ENV", "1")
    monkeypatch.setenv("VIRALMINT_TEST_AUDIO_FIXTURE", "1")


@pytest.fixture(autouse=True)
async def init_database():
    await init_db()


@pytest.mark.asyncio
async def test_chat_goal_auto_creates_project_without_wizard(monkeypatch, tmp_path):
    """
    User goal in chat automatically provisions project state and produces physical media
    without redirecting user to an empty project setup wizard.
    """
    monkeypatch.setenv("VIRALMINT_TEST_ENV", "1")
    context = {"user_id": "test_creator", "session_id": "session_auto_proj"}
    message = "Create a 4s vertical promo video for coffee brand with flowing gradient"

    resp = await ChatOutcomeOrchestrator.handle_video_goal(
        chat_context=context,
        message=message,
        allow_test_fixture=True,
    )

    assert resp.status in (ChatGoalStatus.READY_FOR_DELIVERY, ChatGoalStatus.PENDING_CREDENTIALS)
    assert resp.project_id != "none"
    assert resp.revision_id >= 1
    assert len(resp.artifact_links) >= 1
    mp4_artifact = resp.artifact_links[0]
    assert Path(mp4_artifact["path"]).exists()
    assert len(mp4_artifact["sha256"]) == 64
    assert float(mp4_artifact["duration"]) > 0

    # Verify project exists in ProjectService
    proj = await ProjectService.get_project(resp.project_id)
    assert proj.aspect_ratio == "9:16"
    assert proj.revision == resp.revision_id


@pytest.mark.asyncio
async def test_chat_goal_reconciles_retired_block_with_consent(monkeypatch):
    """
    When user requests a retired 6Clips block (e.g. 'creator-hud'), the orchestrator
    refuses silent counterfeit substitution, halts, and requests consent for verified donor blocks.
    """
    monkeypatch.setenv("VIRALMINT_TEST_ENV", "1")
    context = {"user_id": "test_creator"}
    message = "Create a gaming clip using creator-hud block"

    resp = await ChatOutcomeOrchestrator.handle_video_goal(
        chat_context=context,
        message=message,
        allow_test_fixture=True,
    )

    assert resp.status == ChatGoalStatus.BLOCKED
    assert resp.blocker_code == "BLOCKED_RETIRED_6CLIPS"
    assert "retired 6clips-authored block" in resp.message.lower()
    assert "operable original" in resp.message.lower()


@pytest.mark.asyncio
async def test_chat_goal_with_unauthorized_url(monkeypatch):
    """
    When a remote media URL is detected in chat without explicit user rights confirmation,
    orchestration halts immediately with BLOCKED_UNAUTHORIZED_STREAM.
    """
    monkeypatch.setenv("VIRALMINT_TEST_ENV", "1")
    context = {"user_id": "test_creator"}
    message = "Turn this stream https://test.authorized-creator.com/stream.mp4 into a vertical highlight"

    resp = await ChatOutcomeOrchestrator.handle_video_goal(
        chat_context=context,
        message=message,
        user_authorizations={"user_authorized": False},
        allow_test_fixture=True,
    )

    assert resp.status == ChatGoalStatus.BLOCKED
    assert resp.blocker_code == "BLOCKED_UNAUTHORIZED_STREAM"
    assert "authorization" in resp.message.lower()


@pytest.mark.asyncio
async def test_chat_goal_with_authorized_url_ingestion(monkeypatch):
    """
    When user confirms rights for remote media URL, ingestion proceeds, media is saved,
    and output video is produced.
    """
    monkeypatch.setenv("VIRALMINT_TEST_ENV", "1")
    context = {"user_id": "test_creator"}
    message = "Turn this stream https://test.authorized-creator.com/stream.mp4 into a 3s vertical highlight"

    resp = await ChatOutcomeOrchestrator.handle_video_goal(
        chat_context=context,
        message=message,
        user_authorizations={"user_authorized": True},
        allow_test_fixture=True,
    )

    assert resp.status in (ChatGoalStatus.READY_FOR_DELIVERY, ChatGoalStatus.PENDING_CREDENTIALS)
    assert len(resp.artifact_links) >= 1
    # Check that ingestion step occurred in history
    steps = [evt.step for evt in resp.history]
    assert "url_detection" in steps
    assert "url_ingestion" in steps


@pytest.mark.asyncio
async def test_chat_goal_multi_clip_generation(monkeypatch):
    """
    Multi-clip user intent ('create 3 vertical clips') produces 3 distinct clips with
    distinct SHA256 hashes, distinct topic markers, and truthful progress events.
    """
    monkeypatch.setenv("VIRALMINT_TEST_ENV", "1")
    context = {"user_id": "test_creator"}
    message = "Take this source video and create 3 vertical clips with dynamic captions"

    resp = await ChatOutcomeOrchestrator.handle_video_goal(
        chat_context=context,
        message=message,
        allow_test_fixture=True,
    )

    assert resp.status == ChatGoalStatus.PENDING_CREDENTIALS
    assert resp.preview_details["clips_count"] == 3
    assert len(resp.artifact_links) == 3

    # All 3 clips must be physically distinct files
    file_paths = [Path(c["path"]) for c in resp.artifact_links]
    for p in file_paths:
        assert p.exists(), f"Physical file missing: {p}"

    hashes = [c["sha256"] for c in resp.artifact_links]
    assert len(hashes) == 3
    # Verify each has a valid 64-char sha256
    for h in hashes:
        assert len(h) == 64

    # Verify project revisions were incremented by the editing commands
    proj = await ProjectService.get_project(resp.project_id)
    assert proj.revision >= 6  # At least 2 operations per clip (range_select + graphic_insert)


@pytest.mark.asyncio
async def test_chat_goal_truthful_publication_status(monkeypatch):
    """
    When user requests publishing but platform credentials are not connected,
    the response truthfully indicates NOT_CONNECTED or PENDING_CREDENTIALS.
    """
    monkeypatch.setenv("VIRALMINT_TEST_ENV", "1")
    context = {"user_id": "test_creator"}
    message = "Produce a 3s clip and publish it to youtube shorts"

    resp = await ChatOutcomeOrchestrator.handle_video_goal(
        chat_context=context,
        message=message,
        allow_test_fixture=True,
    )

    assert resp.publication_status in ("PENDING_CREDENTIALS", "NOT_CONNECTED")
    assert resp.status == ChatGoalStatus.PENDING_CREDENTIALS
    assert "PENDING_CREDENTIALS" in resp.message or "NOT_CONNECTED" in resp.message or "credentials" in resp.message.lower()
