# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Real End-to-End Test Suite for Wave 20 Agent 1:
Chat-First Knowledge Orchestrator & Real Physical MP4 Revision.

Executes:
1. Real authorized chat video-goal request -> knowledge search -> native motion spec ->
   canonical project revision -> physical MP4 render -> FFprobe verify -> Library persistence.
2. Subsequent genuine chat correction on the SAME deliverable -> atomic CAS revision bump ->
   re-rendered physical MP4 -> verified media artifact.
"""

from pathlib import Path
import pytest

from backend.database import AsyncSessionLocal, init_db
from backend.models.generated_video import GeneratedVideo
from backend.oaas_knowledge_orchestrator.models import (
    KnowledgeOrchestratorState,
    RevisionRequestContract,
    VideoRequestContract,
)
from backend.oaas_knowledge_orchestrator.orchestrator import KnowledgeChatOrchestrator
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
async def test_wave20_agent1_e2e_video_goal_and_chat_revision():
    """
    End-to-End Journey:
    1. Chat message: "Create a 3s vertical promo for artisan matcha with kinetic typography"
    2. Physical MP4 produced and probed via ffprobe.
    3. Reopened in project service.
    4. Chat correction on the SAME deliverable: "make the second title more cinematic and remove dead air"
    5. Verified revision bump and re-rendered physical MP4.
    """
    context = {"user_id": "test_creator_w20", "session_id": "session_w20_a1"}
    req_message = "Create a 3s vertical promo for artisan matcha with kinetic typography"

    # ─── Part 1: Initial Video Request ────────────────────────────────────────
    response = await KnowledgeChatOrchestrator.handle_video_request(
        request_or_message=req_message,
        authenticated_context=context,
        allow_test_fixture=True,
    )

    assert response.state in (
        KnowledgeOrchestratorState.REVIEW_READY,
        KnowledgeOrchestratorState.PENDING_CREDENTIALS,
    )
    assert response.project_id is not None
    assert response.revision_id >= 2
    assert len(response.artifact_links) >= 1

    artifact = response.artifact_links[0]
    mp4_path = Path(artifact["file_path"])
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

    # Verify Library record in DB
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        res = await db.execute(
            select(GeneratedVideo).where(GeneratedVideo.user_id == "test_creator_w20")
        )
        videos = res.scalars().all()
        assert len(videos) >= 1

    # Verify Project document persisted
    proj = await ProjectService.get_project(response.project_id)
    assert proj.aspect_ratio == "9:16"
    assert proj.revision == response.revision_id

    # ─── Part 2: Chat-Based Correction on the SAME Canonical Project ───────────
    revision_feedback = "make the second title more cinematic and remove dead air"
    rev_resp = await KnowledgeChatOrchestrator.revise_deliverable(
        request_or_run_id=response.run_id,
        user_feedback=revision_feedback,
        expected_revision=response.revision_id,
        authenticated_context=context,
        allow_test_fixture=True,
    )

    assert rev_resp.state == KnowledgeOrchestratorState.REVIEW_READY
    assert rev_resp.project_id == response.project_id, "Revision mutated an orphan project!"
    assert rev_resp.revision_id == response.revision_id + 1

    # Verify revised physical MP4
    assert len(rev_resp.artifact_links) >= 1
    rev_mp4_path = Path(rev_resp.artifact_links[0]["file_path"])
    assert rev_mp4_path.exists()
    assert rev_mp4_path.stat().st_size > 0

    rev_verif = MediaVerifier.verify_media_file(
        media_path=rev_mp4_path,
        expected_aspect_ratio="9:16",
        min_duration_sec=0.5,
    )
    assert rev_verif.is_verified is True
    assert rev_verif.probe_width == 1080
    assert rev_verif.probe_height == 1920

    # Verify project has updated revision
    proj_after = await ProjectService.get_project(response.project_id)
    assert proj_after.revision == rev_resp.revision_id
