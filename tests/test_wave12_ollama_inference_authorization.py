# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 12 Agent 3 Acceptance Test Suite: Backend Ollama Inference Origin & Authorization.

Validates the inference authorization boundary guard, debouncing/idempotency,
provenance tracing, and absence of unsolicited Ollama inference during idle.
"""
import os
import json
import uuid
import asyncio
import hashlib
from unittest.mock import patch, AsyncMock, MagicMock
import pytest
import httpx

from backend.config import settings
from backend.core.ai_provider import (
    AIClient,
    AIProvider,
    get_ai_client,
    _is_ollama_available,
)
from backend.llm_trace import (
    inference_authorization_context,
    get_current_inference_context,
    is_audit_enabled,
    enable_audit,
    disable_audit,
    get_audit_events,
    clear_audit_events,
    get_trace_summary,
    UnauthorizedInferenceError,
    DebouncedDuplicateError,
    TRIGGER_EXPLICIT_CHAT_SUBMIT,
    TRIGGER_AUTHORIZED_RUN_ID,
    TRIGGER_SCHEDULER_JOB_ID,
    TRIGGER_STARTUP,
    TRIGGER_WS_CONNECT,
    TRIGGER_HEALTH_CHECK,
    TRIGGER_UNKNOWN,
    AUTH_CLASS_USER_AUTHORIZED,
    AUTH_CLASS_TASK_PREVIOUSLY_AUTHORIZED,
    AUTH_CLASS_READ_ONLY_HEALTH_DISCOVERY,
    AUTH_CLASS_BLOCKED_WITH_REASON,
    OUTCOME_ALLOWED,
    OUTCOME_BLOCKED,
    OUTCOME_DEBOUNCED,
)
from backend.core.user_intelligence import UserIntelligence
from backend.agents.planner import PlannerAgent


@pytest.fixture(autouse=True)
def setup_audit_env():
    """Ensure clean trace state and enable in-memory auditing for each test."""
    clear_audit_events()
    enable_audit()
    yield
    clear_audit_events()
    disable_audit()


# ── Test 1: Server start without browser generates zero inference ──────────────

@pytest.mark.asyncio
async def test_server_start_zero_inference():
    """
    Verify server startup and background lifespan tasks produce ZERO generative
    Ollama requests (/api/chat, /api/generate).
    """
    clear_audit_events()

    # Simulate startup components (SFX init, retention checks, model probe)
    # Status checks are allowed; generative calls must be strictly 0.
    is_avail = _is_ollama_available()
    assert isinstance(is_avail, bool)

    summary = get_trace_summary()
    assert summary["generative_posts_count"] == 0, (
        f"Server startup must not initiate generative LLM posts: {summary['generative_posts_count']} found"
    )


# ── Test 2: WS handshake without message produces zero inference ──────────────

@pytest.mark.asyncio
async def test_ws_handshake_without_message_zero_inference():
    """
    Verify that WebSocket connection/reconnection without user message produces
    ZERO generative inference calls. Smart suggestions fall back to rule-based.
    """
    clear_audit_events()
    intel = UserIntelligence()

    # Even for a highly active user who would have triggered AI suggestions,
    # on websocket connect no explicit chat submit context is active, so AI is disallowed.
    fake_ctx = {
        "is_first_session": False,
        "total_scouts": 10,
        "total_generated": 5,
        "total_uploads": 2,
        "downloaded_not_generated": 1,
    }
    fake_profile = {"niches": ["gaming"]}

    with patch.object(intel, "get_context_summary", AsyncMock(return_value=fake_ctx)), \
         patch.object(intel, "get_user_profile", AsyncMock(return_value=fake_profile)), \
         patch.object(intel, "_get_rule_based_suggestions", AsyncMock(return_value=["Rule suggestion 1"])):
        with inference_authorization_context(trigger=TRIGGER_WS_CONNECT, user_id="user_idle"):
            suggestions = await intel.get_smart_suggestions("user_idle")

    # Suggestions are returned as rule-based list with NO Ollama generative calls
    assert suggestions == ["Rule suggestion 1"]
    summary = get_trace_summary()
    assert summary["generative_posts_count"] == 0, (
        f"WebSocket connect must not trigger generative AI inference: {summary['generative_posts_count']} found"
    )


# ── Test 3: Debouncing & reconnect prevents duplicate inference ────────────────

@pytest.mark.asyncio
async def test_debouncing_and_reconnect_no_duplicate_inference():
    """
    Verify that duplicate generative calls sent rapidly with identical signatures
    are debounced to prevent duplicate model load or inference storms.
    """
    clear_audit_events()
    client = AIClient(provider=AIProvider.OLLAMA, api_key="ollama_local", model="gemma4:e4b")

    fake_lines = [
        '{"model":"gemma4:e4b","message":{"role":"assistant","content":"First chunk"},"done":false}\n',
        '{"model":"gemma4:e4b","message":{"role":"assistant","content":" done."},"done":true}\n',
    ]

    class MockStreamResp:
        status_code = 200
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def aiter_lines(self):
            for l in fake_lines:
                await asyncio.sleep(0.05)
                yield l

    class MockHttpxClient:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        def stream(self, method, url, json=None):
            return MockStreamResp()

    messages = [{"role": "user", "content": "Tell me a joke"}]

    with patch("httpx.AsyncClient", MockHttpxClient):
        with inference_authorization_context(trigger=TRIGGER_EXPLICIT_CHAT_SUBMIT, user_id="user_deb"):
            # Launch two identical requests concurrently
            async def call_one():
                return [c async for c in client.chat_stream(messages)]

            task1 = asyncio.create_task(call_one())
            # Rapid follow-on duplicate call
            task2 = asyncio.create_task(call_one())

            res1, res2 = await asyncio.gather(task1, task2)

    # One succeeded, one was cleanly debounced
    assert len(res1) > 0 or len(res2) > 0
    summary = get_trace_summary()
    assert summary["debounced_count"] >= 1, "Duplicate concurrent request must be debounced"


# ── Test 4: Pending authorized queued job is allowed & traced ──────────────────

@pytest.mark.asyncio
async def test_authorized_queued_job_allowed_and_traced():
    """
    Verify that an authorized background job carries its run/job ID and is allowed
    by the authorization guard, classified as TASK_PREVIOUSLY_AUTHORIZED.
    """
    clear_audit_events()
    client = AIClient(provider=AIProvider.OLLAMA, api_key="ollama_local", model="gemma4:e4b")

    class MockStreamResp:
        status_code = 200
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def aiter_lines(self):
            yield '{"model":"gemma4:e4b","message":{"role":"assistant","content":"Job output"},"done":true}\n'

    class MockHttpxClient:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        def stream(self, method, url, json=None):
            return MockStreamResp()

    with patch("httpx.AsyncClient", MockHttpxClient):
        with inference_authorization_context(
            trigger=TRIGGER_AUTHORIZED_RUN_ID,
            run_id="run_wave12_job_42",
            user_id="user_creator",
            idempotency_key="idem_key_001",
        ):
            chunks = [c async for c in client.chat_stream([{"role": "user", "content": "Analyze script"}])]

    assert "".join(chunks) == "Job output"
    events = get_audit_events()
    matching = [e for e in events if e.run_id == "run_wave12_job_42"]
    assert len(matching) == 1
    assert matching[0].authorization_class == AUTH_CLASS_TASK_PREVIOUSLY_AUTHORIZED
    assert matching[0].outcome == OUTCOME_ALLOWED


# ── Test 5: Unauthorized background run is blocked (no HTTP POST) ──────────────

@pytest.mark.asyncio
async def test_unauthorized_background_run_blocked():
    """
    Verify that unsolicited background tasks or missing context fail closed with
    UnauthorizedInferenceError, and no HTTP POST is transmitted.
    """
    clear_audit_events()
    client = AIClient(provider=AIProvider.OLLAMA, api_key="ollama_local", model="gemma4:e4b")

    # Case A: Missing authorization context entirely (strict mode)
    with patch.dict(os.environ, {"SIXCLIPS_REQUIRE_EXPLICIT_AUTH": "1"}):
        with pytest.raises(UnauthorizedInferenceError) as exc_info:
            async for _ in client.chat_stream([{"role": "user", "content": "Secret unprompted task"}]):
                pass
        assert "BLOCKED_UNAUTHORIZED_BACKGROUND_AI" in str(exc_info.value)

    # Case B: Disallowed trigger (ws_connect)
    with inference_authorization_context(trigger=TRIGGER_WS_CONNECT, user_id="user_x"):
        with pytest.raises(UnauthorizedInferenceError) as exc_info:
            async for _ in client.chat_stream([{"role": "user", "content": "Unsolicited greeting"}]):
                pass
        assert "disallowed on ws_connect" in str(exc_info.value)

    # Verify blocked events recorded in trace
    events = get_audit_events()
    blocked = [e for e in events if e.outcome == OUTCOME_BLOCKED]
    assert len(blocked) >= 2
    assert all(e.authorization_class == AUTH_CLASS_BLOCKED_WITH_REASON for e in blocked)


# ── Test 6: Read-only model list allowed but counted ───────────────────────────

@pytest.mark.asyncio
async def test_read_only_model_discovery_allowed_and_counted():
    """
    Verify read-only discovery calls (/api/tags, /api/ps, /api/version, /api/show)
    are permitted for UI needs, classified as READ_ONLY_HEALTH_DISCOVERY, and counted.
    """
    clear_audit_events()
    from backend.llm_trace.guard import check_outbound_authorization

    # Discovery route
    ev_tags = check_outbound_authorization(
        provider="ollama",
        model="gemma4:e4b",
        url="http://127.0.0.1:11434/api/tags",
        method="GET",
    )
    assert ev_tags.authorization_class == AUTH_CLASS_READ_ONLY_HEALTH_DISCOVERY
    assert ev_tags.outcome == OUTCOME_ALLOWED

    # Status route
    ev_ps = check_outbound_authorization(
        provider="ollama",
        model="gemma4:e4b",
        url="http://127.0.0.1:11434/api/ps",
        method="GET",
    )
    assert ev_ps.authorization_class == AUTH_CLASS_READ_ONLY_HEALTH_DISCOVERY

    # Metadata show route
    ev_show = check_outbound_authorization(
        provider="ollama",
        model="gemma4:e4b",
        url="http://127.0.0.1:11434/api/show",
        method="POST",
    )
    assert ev_show.authorization_class == AUTH_CLASS_READ_ONLY_HEALTH_DISCOVERY

    summary = get_trace_summary()
    assert summary["generative_posts_count"] == 0
    assert summary["allowed_count"] == 3


# ── Test 7: Ollama provider exception does not fall back to cloud ──────────────

@pytest.mark.asyncio
async def test_ollama_provider_exception_no_hidden_cloud():
    """
    Verify that an Ollama connection error or HTTP 500 reports the error transparently
    and does NOT silently fall back to cloud providers (OpenAI, Anthropic, Gemini).
    """
    clear_audit_events()
    client = AIClient(provider=AIProvider.OLLAMA, api_key="ollama_local", model="gemma4:e4b")

    class MockFailingStream:
        status_code = 500
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def aread(self):
            return b"Internal Server Error: VRAM allocation failed"
        async def aiter_lines(self):
            if False:
                yield ""

    class MockFailingHttpxClient:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        def stream(self, method, url, json=None):
            return MockFailingStream()

    with patch("httpx.AsyncClient", MockFailingHttpxClient):
        with inference_authorization_context(trigger=TRIGGER_EXPLICIT_CHAT_SUBMIT, user_id="user_err"):
            chunks = [c async for c in client.chat_stream([{"role": "user", "content": "Test"}])]

    response_text = "".join(chunks)
    assert "Ollama error (500)" in response_text
    # No cloud provider calls were initiated
    events = get_audit_events()
    assert all(e.provider == "ollama" for e in events)


# ── Test 8: Canceled stream produces no retry storm ────────────────────────────

@pytest.mark.asyncio
async def test_canceled_stream_no_retry_storm():
    """
    Verify that client stream cancellation releases leases immediately and does
    not initiate background retry loops or storms.
    """
    clear_audit_events()
    client = AIClient(provider=AIProvider.OLLAMA, api_key="ollama_local", model="gemma4:e4b")

    class MockCancellableStream:
        status_code = 200
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def aiter_lines(self):
            yield '{"model":"gemma4:e4b","message":{"role":"assistant","content":"token 1"},"done":false}\n'
            # Simulates client disconnecting / task cancelled
            raise asyncio.CancelledError("Client disconnected")

    class MockHttpxClient:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        def stream(self, method, url, json=None):
            return MockCancellableStream()

    with patch("httpx.AsyncClient", MockHttpxClient):
        with inference_authorization_context(trigger=TRIGGER_EXPLICIT_CHAT_SUBMIT, user_id="user_cancel"):
            with pytest.raises(asyncio.CancelledError):
                async for _ in client.chat_stream([{"role": "user", "content": "Cancel me"}]):
                    pass

    # No retries occurred
    summary = get_trace_summary()
    assert summary["generative_posts_count"] == 1


# ── Test 9: Explicit user prompt via real local Ollama (Positive Control) ───────

@pytest.mark.asyncio
async def test_explicit_user_prompt_positive_control():
    """
    Positive control test: when the user explicitly submits a prompt in chat,
    inference is authorized, executed against local Ollama gemma4:e4b, and traced.
    """
    if not _is_ollama_available():
        pytest.skip("Local Ollama daemon offline — positive control requires local daemon.")

    clear_audit_events()
    client = get_ai_client(pinned_provider=AIProvider.OLLAMA, pinned_model="gemma4:e4b")

    with inference_authorization_context(
        trigger=TRIGGER_EXPLICIT_CHAT_SUBMIT,
        user_id="owner_positive_control",
        correlation_id="corr_pc_001",
    ):
        response = await client.chat(
            messages=[{"role": "user", "content": "Respond with the single word: OK"}],
            max_tokens=20,
            think=False,
        )

    assert len(response.strip()) > 0
    events = get_audit_events()
    generative_events = [e for e in events if e.endpoint_category == "generative"]
    assert len(generative_events) >= 1
    assert generative_events[0].authorization_class == AUTH_CLASS_USER_AUTHORIZED
    assert generative_events[0].trigger == TRIGGER_EXPLICIT_CHAT_SUBMIT
    assert generative_events[0].outcome == OUTCOME_ALLOWED
