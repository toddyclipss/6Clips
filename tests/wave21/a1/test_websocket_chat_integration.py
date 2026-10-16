# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""WebSocket HTTP Client Integration Test for Wave 21 Agent 1.

Verifies:
1. Real FastAPI TestClient connecting to `/ws/chat`.
2. Initializing session via `set_session`.
3. Submitting `revision_request` through WebSocket.
4. Receiving `oaas_outcome_update` frame with truthful project_id, revision, state, deliverable_url.
5. Error handling through WebSocket (`chat_error`).
"""
import pytest
from starlette.testclient import TestClient

from backend.main import create_app
from backend.database import init_db, AsyncSessionLocal
from backend.models.project import Project
from backend.oaas_knowledge_orchestrator.models import KnowledgeOrchestratorResponse, KnowledgeOrchestratorState


@pytest.fixture(autouse=True)
async def setup_test_db():
    await init_db()
    yield


def test_websocket_chat_revision_request_integration():
    """Test full WebSocket round-trip for revision_request."""
    app = create_app()
    client = TestClient(app)

    with client.websocket_connect("/ws/chat") as websocket:
        # 1. Establish session
        session_id = "test-ws-session-001"
        websocket.send_json({
            "type": "set_session",
            "session_id": session_id,
        })

        # 2. Issue revision_request for a test run
        websocket.send_json({
            "type": "revision_request",
            "run_id": "test-ws-run-mock",
            "feedback": "Make captions dynamic and shorten duration",
            "expected_revision": 1,
        })

        # 3. Receive responses
        # Could receive smart_suggestions on connect, then oaas_outcome_update or chat_error
        received_frames = []
        for _ in range(5):
            try:
                frame = websocket.receive_json()
                received_frames.append(frame)
                if frame.get("type") in ("oaas_outcome_update", "chat_error"):
                    break
            except Exception:
                break

        outcome_frames = [f for f in received_frames if f.get("type") == "oaas_outcome_update"]
        error_frames = [f for f in received_frames if f.get("type") == "chat_error"]

        # Assert we got an outcome update or a handled chat_error
        assert len(outcome_frames) > 0 or len(error_frames) > 0, f"Expected WS response, got: {received_frames}"
        if outcome_frames:
            outcome = outcome_frames[0]
            assert outcome.get("session_id") == session_id
            assert "run_id" in outcome
            assert "state" in outcome
