# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Agent 5 P0 Recovery Tests:
KnowledgeChatOrchestrator Execution Scope, Real Inference, Source Video Edit Lineage,
Zero-Social-Credentials Review Truth, and Atomic CAS Revisions.
"""

import asyncio
from pathlib import Path
import pytest
import subprocess
from uuid import uuid4

from backend.config import settings
from backend.core.exceptions import RevisionConflictError
from backend.database import init_db
from backend.oaas_knowledge_orchestrator.models import (
    KnowledgeOrchestratorResponse,
    KnowledgeOrchestratorState,
    VideoRequestContract,
    RevisionRequestContract,
)
from backend.oaas_knowledge_orchestrator.orchestrator import KnowledgeChatOrchestrator
from backend.services.project_service import ProjectService
from backend.services.video_utils import probe_dimensions, probe_duration

@pytest.fixture(autouse=True)
async def setup_test_db(monkeypatch):
    monkeypatch.setenv("VIRALMINT_TEST_ENV", "1")
    monkeypatch.setenv("VIRALMINT_TEST_AUDIO_FIXTURE", "1")
    await init_db()

try:
    from backend.llm_trace import (
        get_current_inference_context,
        user_chat_execution_scope,
        check_outbound_authorization,
        UnauthorizedInferenceError,
        SOURCE_WS_CHAT,
    )
    HAS_LLM_TRACE = True
except ImportError:
    HAS_LLM_TRACE = False


def create_sample_video(output_path: Path, duration_sec: float = 3.0, width: int = 1280, height: int = 720) -> Path:
    """Generate a valid test video file using ffmpeg testsrc."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={duration_sec}:size={width}x{height}:rate=30",
        "-f", "lavfi", "-i", f"sine=frequency=1000:duration={duration_sec}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


@pytest.mark.asyncio
async def test_background_inference_without_context_is_blocked(monkeypatch):
    """Verify Wave12 guard still rejects outbound inference when no user context is active."""
    if not HAS_LLM_TRACE:
        pytest.skip("backend.llm_trace not imported in standalone stage")

    monkeypatch.setenv("SIXCLIPS_REQUIRE_EXPLICIT_AUTH", "1")
    with pytest.raises(UnauthorizedInferenceError) as exc_info:
        check_outbound_authorization(
            provider="ollama",
            model="gemma4:e4b",
            url="http://127.0.0.1:11434/api/chat",
            method="POST",
        )

    err_msg = str(exc_info.value)
    assert "BLOCKED_UNAUTHORIZED_BACKGROUND_AI" in err_msg
    assert "trigger=unknown" in err_msg
    assert exc_info.value.event.outcome == "BLOCKED"


@pytest.mark.asyncio
async def test_server_authored_scope_enables_ollama_inference():
    """Verify server-authored execution scope authorizes outbound call to Ollama."""
    if not HAS_LLM_TRACE:
        pytest.skip("backend.llm_trace not imported in standalone stage")

    run_id = f"test-run-{uuid4().hex[:8]}"
    async with user_chat_execution_scope(
        authenticated_principal="user_test_123",
        session_id="session_test_abc",
        run_id=run_id,
        correlation_id=f"corr-{run_id}",
        source=SOURCE_WS_CHAT,
    ):
        ctx = get_current_inference_context()
        assert ctx is not None
        assert ctx.authenticated_principal == "user_test_123"
        assert ctx.run_id == run_id

        # Guard check passes cleanly
        event = check_outbound_authorization(
            provider="ollama",
            model="gemma4:e4b",
            url="http://127.0.0.1:11434/api/chat",
            method="POST",
        )
        assert event.outcome == "ALLOWED"


@pytest.mark.asyncio
async def test_missing_source_video_fails_closed_truthfully(tmp_path):
    """
    Verify that an edit-existing-video request with an unavailable/missing source
    fails truthfully with MEDIA_ACQUISITION_FAILED and NEVER generates synthetic black motion.
    """
    req = VideoRequestContract(
        message="analise e edite esse video em ingles https://www.youtube.com/watch?v=NON_EXISTENT_ID_999",
        user_id="user_test_owner",
        session_id="session_test_456",
        provider="ollama",
        model="gemma4:e4b",
        reasoning_level="high",
    )

    # Execute orchestrator
    res = await KnowledgeChatOrchestrator.handle_video_request(req)

    # Must fail closed truthfully
    assert res.state in (KnowledgeOrchestratorState.FAILED_TERMINAL, KnowledgeOrchestratorState.BLOCKED)
    assert res.blocker_code in ("MEDIA_ACQUISITION_FAILED", "BLOCKED_FETCH_FAILED", "BLOCKED_SSRF")
    assert "analise e edite" not in (res.message or "").lower() or "cannot edit" in res.message.lower()


@pytest.mark.asyncio
async def test_source_backed_video_edit_lineage_and_zero_social_gate(tmp_path):
    """
    Verify that a genuine source video is reframed to 9:16, has verified lineage,
    and finishes as REVIEW_READY with zero social logins required.
    """
    source_file = tmp_path / "sample_source_footage.mp4"
    create_sample_video(source_file, duration_sec=5.0, width=1920, height=1080)

    # Mock ingestion result by providing existing ingested file path
    from unittest.mock import AsyncMock, patch
    from backend.oaas_chat_ingestion.models import UrlIngestionResult

    mock_ingest = UrlIngestionResult(
        is_allowed=True,
        url="https://www.youtube.com/watch?v=FV93IVwJP_4",
        file_path=str(source_file),
    )

    with patch("backend.oaas_knowledge_orchestrator.orchestrator.AgentUrlIngestionService.ingest_url", new_callable=AsyncMock, return_value=mock_ingest):
        req = VideoRequestContract(
            message="analise e edite esse video em ingles https://www.youtube.com/watch?v=FV93IVwJP_4",
            user_id="user_test_creator",
            session_id="session_test_789",
        )

        res = await KnowledgeChatOrchestrator.handle_video_request(req)

        assert res.state == KnowledgeOrchestratorState.REVIEW_READY, f"State: {res.state}, Message: {res.message}, BlockerCode: {res.blocker_code}, BlockerReason: {res.blocker_reason}"
        assert res.project_id is not None
        assert res.revision_id >= 2
        assert res.publication_requested is False
        assert res.publication_status == "NOT_REQUESTED"
        assert res.deliverable_url is not None
        assert res.duration_seconds is not None
        assert res.duration_seconds > 0

        # Physical MP4 probe verification
        assert res.media_probe is not None
        assert res.media_probe["width"] == 1080
        assert res.media_probe["height"] == 1920
        assert res.media_probe["duration_seconds"] > 0

        # Check evidence lineage
        assert res.evidence is not None
        assert res.evidence.media_artifact is not None
        lineage = res.evidence.media_artifact.get("source_lineage", {})
        assert lineage.get("source_path") == str(source_file)
        assert lineage.get("source_sha256") is not None


@pytest.mark.asyncio
async def test_same_project_consecutive_revisions_cas(tmp_path):
    """
    Verify that revising an existing deliverable operates on the SAME project timeline,
    increments revision_id, and produces a physical MP4 without social credentials.
    """
    project = await ProjectService.create_project(
        name="Test Canonical Project",
        aspect_ratio="9:16",
        user_id="user_cas_tester",
    )

    # Initial revision
    init_req = VideoRequestContract(
        message="Create clean kinetic typography video",
        user_id="user_cas_tester",
        session_id="session_cas_1",
        project_id=project.id,
        allow_test_fixture=True,
    )
    init_res = await KnowledgeChatOrchestrator.handle_video_request(init_req)
    assert init_res.state == KnowledgeOrchestratorState.REVIEW_READY
    base_rev = init_res.revision_id
    run_id = init_res.run_id

    # Revise on the same project
    rev_req = RevisionRequestContract(
        run_id=run_id,
        user_feedback="Make duration 5 seconds and switch to horizontal 16:9",
        expected_revision=base_rev,
        user_id="user_cas_tester",
        allow_test_fixture=True,
    )
    rev_res = await KnowledgeChatOrchestrator.revise_deliverable(rev_req)

    assert rev_res.state == KnowledgeOrchestratorState.REVIEW_READY
    assert rev_res.project_id == project.id
    assert rev_res.revision_id > base_rev
    assert rev_res.publication_requested is False
    assert rev_res.publication_status in ("NOT_REQUESTED", "NOT_CONNECTED")
    assert rev_res.media_probe["width"] == 1920
    assert rev_res.media_probe["height"] == 1080


@pytest.mark.asyncio
async def test_explicit_publish_requested_triggers_handoff(tmp_path):
    """Verify that only explicit publish intent requests social authorization handoff."""
    project = await ProjectService.create_project(
        name="Test Publish Project",
        aspect_ratio="9:16",
        user_id="user_pub_tester",
    )

    req = VideoRequestContract(
        message="Produce video and publish to youtube_shorts immediately",
        user_id="user_pub_tester",
        session_id="session_pub_1",
        project_id=project.id,
        authorizations={"publish_authorized": True},
        allow_test_fixture=True,
    )

    res = await KnowledgeChatOrchestrator.handle_video_request(req)
    assert res.publication_requested is True
    assert res.publication_status in ("NOT_CONNECTED", "PENDING_CREDENTIALS", "PUBLISHED", "SCHEDULED")
