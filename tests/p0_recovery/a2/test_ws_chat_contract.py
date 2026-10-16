# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
P0 Recovery - Agent 2 Test Suite:
Comprehensive contract verification for /ws/chat endpoint:
- Exact Ollama model + High reasoning effort propagation
- Strict explicit selection validation (rejection before inference if unselected)
- Rejection of untrusted client-supplied authorization bypass
- Server-authored execution provenance context (TRIGGER_EXPLICIT_CHAT_SUBMIT)
- Duplicate client message suppression (debouncing / idempotency)
- Preservation of exact YouTube URL with uppercase I
- Revision request authorization and run_id propagation
- Fail-closed error handling (no silent provider swap or mock cards)
- Exact reproduction of the user incident with SIXCLIPS_REQUIRE_EXPLICIT_AUTH=1
"""
import os
import json
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from starlette.testclient import TestClient

from backend.main import create_app
from backend.config import settings
from backend.database import init_db
from backend.llm_trace import (
    TRIGGER_EXPLICIT_CHAT_SUBMIT,
    get_current_inference_context,
)
from backend.oaas_knowledge_orchestrator.models import (
    KnowledgeOrchestratorResponse,
    KnowledgeOrchestratorState,
)


@pytest.fixture(autouse=True)
def setup_test_db():
    asyncio.run(init_db())


@pytest.fixture
def test_client():
    app = create_app()
    return TestClient(app)


def _read_until(ws, target_types=("chat_done", "chat_error"), max_reads=15):
    """Safely drain messages until one of target_types is encountered."""
    received = []
    for _ in range(max_reads):
        try:
            m = ws.receive_json()
            received.append(m)
            if m.get("type") in target_types:
                break
        except Exception:
            break
    return received


def test_ollama_gemma4_propagation_and_server_context(test_client):
    """
    Test 1: Verify exact Ollama provider and gemma4:e4b model with High effort
    are passed intact to KnowledgeChatOrchestrator with active server-authored
    authorization context (TRIGGER_EXPLICIT_CHAT_SUBMIT).
    """
    captured = {}

    async def mock_handle_video_request(*args, **kwargs):
        captured["context"] = get_current_inference_context()
        captured["auth_ctx"] = kwargs.get("authenticated_context")
        captured["msg"] = kwargs.get("request_or_message")
        return KnowledgeOrchestratorResponse(
            run_id="krun-test123456",
            project_id="proj_p0_a2",
            revision_id=1,
            state=KnowledgeOrchestratorState.REVIEW_READY,
            message="Knowledge video generated successfully.",
            deliverable_url="/media/test.mp4",
        )

    with patch("backend.oaas_knowledge_orchestrator.KnowledgeChatOrchestrator.handle_video_request",
               side_effect=mock_handle_video_request):
        with patch.object(settings, "KNOWLEDGE_FIRST", True):
            with test_client.websocket_connect("/ws/chat") as ws:
                ws.send_json({"type": "set_session", "session_id": "sess_a2_test_1"})
                ws.send_json({
                    "type": "chat_message",
                    "content": "analise e edite esse video https://www.youtube.com/watch?v=FV93IVwJP_4",
                    "provider": "ollama",
                    "model": "gemma4:e4b",
                    "reasoning_level": "high",
                    "client_message_id": "cmsg_unique_101",
                    "correlation_id": "corr_unique_101",
                })

                received = _read_until(ws, target_types=("chat_done", "chat_error"))

    # Verify captured call parameters
    assert captured.get("auth_ctx") is not None
    assert captured["auth_ctx"]["provider"] == "ollama"
    assert captured["auth_ctx"]["model"] == "gemma4:e4b"
    assert captured["auth_ctx"]["reasoning_level"] == "high"
    assert captured["auth_ctx"]["correlation_id"] == "corr_unique_101"

    # Verify server-authored context inside execution
    active_ctx = captured.get("context")
    assert active_ctx is not None, "Inference authorization context was not active during orchestrator execution!"
    assert active_ctx.trigger == TRIGGER_EXPLICIT_CHAT_SUBMIT
    assert active_ctx.correlation_id == "corr_unique_101"

    # Verify client received outcomes
    outcome_msgs = [m for m in received if m.get("type") == "oaas_outcome_update"]
    assert len(outcome_msgs) >= 1
    assert outcome_msgs[0]["state"] == "REVIEW_READY"
    assert outcome_msgs[0]["run_id"] == "krun-test123456"


def test_unselected_model_or_effort_rejected_fail_closed(test_client):
    """
    Test 2: Reject before calling inference if model or effort is unselected.
    Ensure fail-closed rejection without silent fallback.
    """
    with patch("backend.oaas_knowledge_orchestrator.KnowledgeChatOrchestrator.handle_video_request") as mock_orch:
        with test_client.websocket_connect("/ws/chat") as ws:
            ws.send_json({"type": "set_session", "session_id": "sess_a2_unselected"})

            # Case A: Missing provider and model
            ws.send_json({
                "type": "chat_message",
                "content": "make video",
                "provider": None,
                "model": None,
                "reasoning_level": "high",
            })
            msgs1 = _read_until(ws, target_types=("chat_error",), max_reads=5)
            err1 = next((m for m in msgs1 if m.get("type") == "chat_error"), None)
            assert err1 is not None
            assert "No AI model selected" in err1["error"]

            # Case B: Missing reasoning effort
            ws.send_json({
                "type": "chat_message",
                "content": "make video",
                "provider": "ollama",
                "model": "gemma4:e4b",
                "reasoning_level": None,
            })
            msgs2 = _read_until(ws, target_types=("chat_error",), max_reads=5)
            err2 = next((m for m in msgs2 if m.get("type") == "chat_error"), None)
            assert err2 is not None
            assert "No reasoning effort selected" in err2["error"]

        # Ensure orchestrator was never called
        assert not mock_orch.called


def test_untrusted_client_bypass_ignored(test_client):
    """
    Test 3: Reject / ignore untrusted client claims of authorization (e.g., authorized=True,
    trigger=bypass_guard). Verify that server creates TRIGGER_EXPLICIT_CHAT_SUBMIT authoritatively.
    """
    captured_ctx = None

    async def mock_handle_video_request(*args, **kwargs):
        nonlocal captured_ctx
        captured_ctx = get_current_inference_context()
        return KnowledgeOrchestratorResponse(
            run_id="krun-test999",
            project_id="proj_test",
            revision_id=1,
            state=KnowledgeOrchestratorState.REVIEW_READY,
            message="OK",
        )

    with patch("backend.oaas_knowledge_orchestrator.KnowledgeChatOrchestrator.handle_video_request",
               side_effect=mock_handle_video_request):
        with patch.object(settings, "KNOWLEDGE_FIRST", True):
            with test_client.websocket_connect("/ws/chat") as ws:
                ws.send_json({"type": "set_session", "session_id": "sess_a2_bypass_test"})
                ws.send_json({
                    "type": "chat_message",
                    "content": "test bypass",
                    "provider": "ollama",
                    "model": "gemma4:e4b",
                    "reasoning_level": "high",
                    "authorized": True,
                    "trigger": "UNSOLICITED_BYPASS",
                    "authorization_class": "FORGED_CLASS",
                })

                _read_until(ws, target_types=("chat_done", "chat_error"))

    assert captured_ctx is not None
    assert captured_ctx.trigger == TRIGGER_EXPLICIT_CHAT_SUBMIT
    assert captured_ctx.trigger != "UNSOLICITED_BYPASS"


def test_duplicate_submission_suppressed(test_client):
    """
    Test 4: Rapid duplicate submissions or reconnect resends with the same
    client_message_id are suppressed and do not trigger duplicate inference.
    """
    call_count = 0

    async def mock_handle_video_request(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return KnowledgeOrchestratorResponse(
            run_id="krun-dedup",
            project_id="proj_test",
            revision_id=1,
            state=KnowledgeOrchestratorState.REVIEW_READY,
            message="OK",
        )

    with patch("backend.oaas_knowledge_orchestrator.KnowledgeChatOrchestrator.handle_video_request",
               side_effect=mock_handle_video_request):
        with patch.object(settings, "KNOWLEDGE_FIRST", True):
            with test_client.websocket_connect("/ws/chat") as ws:
                ws.send_json({"type": "set_session", "session_id": "sess_a2_dedup"})
                # First submission
                ws.send_json({
                    "type": "chat_message",
                    "content": "edit video once",
                    "provider": "ollama",
                    "model": "gemma4:e4b",
                    "reasoning_level": "high",
                    "client_message_id": "cmsg_idempotent_key_42",
                })

                _read_until(ws, target_types=("chat_done", "chat_error"))

                # Immediate duplicate submission with identical client_message_id
                ws.send_json({
                    "type": "chat_message",
                    "content": "edit video once",
                    "provider": "ollama",
                    "model": "gemma4:e4b",
                    "reasoning_level": "high",
                    "client_message_id": "cmsg_idempotent_key_42",
                })

                dup_msgs = _read_until(ws, target_types=("chat_status",), max_reads=5)
                dup_status = next((m for m in dup_msgs if m.get("type") == "chat_status" and m.get("status") == "duplicate_suppressed"), None)
                assert dup_status is not None, f"Expected duplicate_suppressed status, got: {dup_msgs}"

    # Orchestrator should only have been called ONCE
    assert call_count == 1


def test_exact_youtube_url_preservation(test_client):
    """
    Test 5: The exact user prompt including YouTube URL with uppercase 'I'
    (FV93IVwJP_4) is preserved verbatim without lowercase mutation or double decoding.
    """
    captured_msg = None

    async def mock_handle_video_request(*args, **kwargs):
        nonlocal captured_msg
        captured_msg = kwargs.get("request_or_message")
        return KnowledgeOrchestratorResponse(
            run_id="krun-url-test",
            project_id="proj_test",
            revision_id=1,
            state=KnowledgeOrchestratorState.REVIEW_READY,
            message="OK",
        )

    user_text = "analise e edite esse video em ingles https://www.youtube.com/watch?v=FV93IVwJP_4"

    with patch("backend.oaas_knowledge_orchestrator.KnowledgeChatOrchestrator.handle_video_request",
               side_effect=mock_handle_video_request):
        with patch.object(settings, "KNOWLEDGE_FIRST", True):
            with test_client.websocket_connect("/ws/chat") as ws:
                ws.send_json({"type": "set_session", "session_id": "sess_a2_url_test"})
                ws.send_json({
                    "type": "chat_message",
                    "content": user_text,
                    "provider": "ollama",
                    "model": "gemma4:e4b",
                    "reasoning_level": "high",
                    "client_message_id": "cmsg_url_test_1",
                })

                _read_until(ws, target_types=("chat_done", "chat_error"))

    assert captured_msg == user_text
    assert "FV93IVwJP_4" in captured_msg
    assert "fv93ivwjp_4" not in captured_msg
    assert "FV93lVwJP_4" not in captured_msg


def test_revision_request_server_provenance(test_client):
    """
    Test 6: Revision request establishes server-authored authorization context,
    carries run_id and correlation_id to revise_deliverable.
    """
    captured = {}

    async def mock_revise(*args, **kwargs):
        captured["context"] = get_current_inference_context()
        captured["auth_ctx"] = kwargs.get("authenticated_context")
        captured["run_id"] = kwargs.get("request_or_run_id")
        captured["feedback"] = kwargs.get("user_feedback")
        return KnowledgeOrchestratorResponse(
            run_id="krun-rev123456",
            project_id="proj_rev",
            revision_id=2,
            state=KnowledgeOrchestratorState.REVIEW_READY,
            message="Revision created.",
        )

    with patch("backend.oaas_knowledge_orchestrator.KnowledgeChatOrchestrator.revise_deliverable",
               side_effect=mock_revise):
        with test_client.websocket_connect("/ws/chat") as ws:
            ws.send_json({"type": "set_session", "session_id": "sess_a2_rev_test"})
            ws.send_json({
                "type": "revision_request",
                "run_id": "krun-rev123456",
                "feedback": "increase caption font size",
                "expected_revision": 2,
                "correlation_id": "corr_rev_777",
                "client_message_id": "cmsg_rev_777",
            })

            msgs = _read_until(ws, target_types=("oaas_outcome_update", "chat_error"), max_reads=5)
            resp = next((m for m in msgs if m.get("type") == "oaas_outcome_update"), None)

    assert resp is not None
    assert resp.get("revision") == 2
    assert captured.get("context") is not None
    assert captured["context"].trigger == TRIGGER_EXPLICIT_CHAT_SUBMIT
    assert captured["context"].run_id == "krun-rev123456"
    assert captured["context"].correlation_id == "corr_rev_777"


def test_fail_closed_error_handling(test_client):
    """
    Test 7: When an unhandled error occurs during inference/orchestration,
    emit oaas_outcome_update with FAILED_TERMINAL and chat_error with stable IDs.
    Never silently substitute another provider or generate a fake title card.
    """
    async def mock_failing_request(*args, **kwargs):
        raise RuntimeError("LLM inference timeout on ollama/gemma4:e4b")

    with patch("backend.oaas_knowledge_orchestrator.KnowledgeChatOrchestrator.handle_video_request",
               side_effect=mock_failing_request):
        with patch.object(settings, "KNOWLEDGE_FIRST", True):
            with test_client.websocket_connect("/ws/chat") as ws:
                ws.send_json({"type": "set_session", "session_id": "sess_a2_fail_test"})
                ws.send_json({
                    "type": "chat_message",
                    "content": "analise e edite https://www.youtube.com/watch?v=FV93IVwJP_4",
                    "provider": "ollama",
                    "model": "gemma4:e4b",
                    "reasoning_level": "high",
                    "client_message_id": "cmsg_fail_test",
                    "correlation_id": "corr_fail_test",
                })

                msgs = _read_until(ws, target_types=("chat_error",), max_reads=8)

    outcome_msgs = [m for m in msgs if m.get("type") == "oaas_outcome_update"]
    assert len(outcome_msgs) >= 1
    assert outcome_msgs[0]["state"] == "FAILED_TERMINAL"
    assert "LLM inference timeout" in outcome_msgs[0]["message"]

    err_msgs = [m for m in msgs if m.get("type") == "chat_error"]
    assert len(err_msgs) >= 1
    assert "LLM inference timeout" in err_msgs[0]["error"]
    assert err_msgs[0]["correlation_id"] == "corr_fail_test"


def test_e2e_user_observed_incident_with_strict_guard(test_client):
    """
    Test 8: Exact user-observed incident reproduction test.
    Under SIXCLIPS_REQUIRE_EXPLICIT_AUTH=1, user submits:
    'analise e edite esse video em ingles https://www.youtube.com/watch?v=FV93IVwJP_4'
    with provider='ollama', model='gemma4:e4b', reasoning_level='high'.
    Verify that Wave 12 guard passes without BLOCKED_UNAUTHORIZED_BACKGROUND_AI.
    """
    with patch.dict(os.environ, {"SIXCLIPS_REQUIRE_EXPLICIT_AUTH": "1"}):
        from backend.llm_trace.guard import check_outbound_authorization

        guard_checked = False

        async def mock_handle_video_request(*args, **kwargs):
            nonlocal guard_checked
            # Simulate real LLM callsite checking outbound authorization under strict guard
            check_outbound_authorization(
                provider="ollama",
                model="gemma4:e4b",
                url="http://127.0.0.1:11434/api/chat",
                method="POST",
            )
            guard_checked = True
            return KnowledgeOrchestratorResponse(
                run_id="krun-e2e-ok",
                project_id="proj_e2e",
                revision_id=1,
                state=KnowledgeOrchestratorState.REVIEW_READY,
                message="Video successfully analyzed and edited.",
                deliverable_url="/media/FV93IVwJP_4_edit.mp4",
            )

        with patch("backend.oaas_knowledge_orchestrator.KnowledgeChatOrchestrator.handle_video_request",
                   side_effect=mock_handle_video_request):
            with patch.object(settings, "KNOWLEDGE_FIRST", True):
                with test_client.websocket_connect("/ws/chat") as ws:
                    ws.send_json({"type": "set_session", "session_id": "sess_a2_e2e"})
                    ws.send_json({
                        "type": "chat_message",
                        "content": "analise e edite esse video em ingles https://www.youtube.com/watch?v=FV93IVwJP_4",
                        "provider": "ollama",
                        "model": "gemma4:e4b",
                        "reasoning_level": "high",
                        "client_message_id": "cmsg_e2e_repro",
                        "correlation_id": "corr_e2e_repro",
                    })

                    received = _read_until(ws, target_types=("chat_done", "chat_error"))

        assert guard_checked is True, "Outbound authorization check was not executed!"
        error_msgs = [m for m in received if m.get("type") == "chat_error"]
        assert len(error_msgs) == 0, f"Unexpected chat_error received: {error_msgs}"

        outcome_msgs = [m for m in received if m.get("type") == "oaas_outcome_update"]
        assert len(outcome_msgs) >= 1
        assert outcome_msgs[0]["state"] == "REVIEW_READY"
        assert outcome_msgs[0]["deliverable_url"] == "/media/FV93IVwJP_4_edit.mp4"
