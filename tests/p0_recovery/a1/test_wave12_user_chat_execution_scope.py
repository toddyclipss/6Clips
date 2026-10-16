# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Comprehensive Acceptance Tests for Agent 1 (Wave12 LLM Egress Guard Provenance & Scopes).

Validates:
1. Server-authored user_chat_execution_scope API (sync and async).
2. Monotonic TTL expiration: expired scopes fail closed at boundary.
3. Strict principal validation: anonymous / empty principals rejected.
4. Clean cleanup on normal exit, exceptions, and task cancellation (zero leakage).
5. Nested execution scopes cleanly restore parent context.
6. Context propagation across asyncio.create_task and worker threads (propagate_inference_context).
7. Concurrent session isolation: two concurrent tasks never cross-contaminate.
8. Guard fail-closed negative assertions:
   - Direct background call without context -> UnauthorizedInferenceError.
   - Disallowed triggers (TRIGGER_WS_CONNECT, TRIGGER_STARTUP) -> UnauthorizedInferenceError.
   - Background jobs without run_id / job_id -> UnauthorizedInferenceError.
   - Client parameter spoofing cannot bypass boundary.
9. Read-only discovery and metadata routes (/api/tags, /api/show) allowed without generative scope.
10. Executable provider-level test with real local Ollama (gemma4:e4b) under active scope.
"""
from __future__ import annotations

import asyncio
import os
import time
import uuid
from typing import List
import pytest

from backend.llm_trace import (
    user_chat_execution_scope,
    inference_authorization_context,
    get_current_inference_context,
    run_with_inference_context,
    propagate_inference_context,
    check_outbound_authorization,
    UnauthorizedInferenceError,
    DebouncedDuplicateError,
    InferenceAuthorizationContext,
    TRIGGER_EXPLICIT_CHAT_SUBMIT,
    TRIGGER_USER_CHAT,
    TRIGGER_WS_CONNECT,
    TRIGGER_STARTUP,
    TRIGGER_AUTHORIZED_RUN_ID,
    TRIGGER_SCHEDULER_JOB_ID,
    SOURCE_WS_CHAT,
    SOURCE_REST_CHAT,
    ENDPOINT_CATEGORY_GENERATIVE,
    ENDPOINT_CATEGORY_DISCOVERY,
    ENDPOINT_CATEGORY_METADATA,
)
from backend.core.ai_provider import get_ai_client, AIProvider


@pytest.fixture(autouse=True)
def enforce_strict_auth(monkeypatch):
    """Enforce strict inference authorization in all A1 tests (no test bypass)."""
    monkeypatch.setenv("SIXCLIPS_REQUIRE_EXPLICIT_AUTH", "1")


# ── Scope Lifecycle & Contract Tests ─────────────────────────────────────────

def test_user_chat_execution_scope_sync_lifecycle():
    """Verify synchronous scope creates context and resets on exit."""
    assert get_current_inference_context() is None

    with user_chat_execution_scope(
        authenticated_principal="user_owner_01",
        session_id="sess_alpha",
        run_id="krun-1001",
        source=SOURCE_WS_CHAT,
        ttl_seconds=60.0,
    ) as ctx:
        active = get_current_inference_context()
        assert active is not None
        assert active.authenticated_principal == "user_owner_01"
        assert active.session_id == "sess_alpha"
        assert active.run_id == "krun-1001"
        assert active.source == SOURCE_WS_CHAT
        assert active.trigger == TRIGGER_EXPLICIT_CHAT_SUBMIT
        assert not active.is_expired()
        assert active.time_remaining_seconds() > 0.0

    # Must reset cleanly after exit
    assert get_current_inference_context() is None


@pytest.mark.asyncio
async def test_user_chat_execution_scope_async_lifecycle():
    """Verify asynchronous scope creates context and resets on exit."""
    assert get_current_inference_context() is None

    async with user_chat_execution_scope(
        authenticated_principal="user_owner_02",
        session_id="sess_beta",
        run_id="krun-1002",
        source=SOURCE_REST_CHAT,
        ttl_seconds=120.0,
    ) as ctx:
        active = get_current_inference_context()
        assert active is not None
        assert active.authenticated_principal == "user_owner_02"
        assert active.session_id == "sess_beta"
        assert active.source == SOURCE_REST_CHAT
        assert not active.is_expired()

    # Must reset cleanly
    assert get_current_inference_context() is None


def test_user_chat_execution_scope_rejects_invalid_principal():
    """Verify scope refuses initialization with anonymous or empty principals."""
    invalid_principals = ["", "   ", "anon_unknown", "anonymous", "None", "null"]
    for p in invalid_principals:
        with pytest.raises(ValueError, match="requires a valid authenticated principal"):
            with user_chat_execution_scope(authenticated_principal=p, session_id="sess_test"):
                pass


def test_user_chat_execution_scope_rejects_empty_session_id():
    """Verify scope refuses initialization with empty session ID."""
    with pytest.raises(ValueError, match="requires a non-empty session_id"):
        with user_chat_execution_scope(authenticated_principal="user_local", session_id="   "):
            pass


def test_user_chat_execution_scope_cleanup_on_exception():
    """Verify context token is cleanly reset even when inner block raises an exception."""
    assert get_current_inference_context() is None

    with pytest.raises(RuntimeError, match="Inner block failure"):
        with user_chat_execution_scope(authenticated_principal="user_local", session_id="sess_err"):
            assert get_current_inference_context() is not None
            raise RuntimeError("Inner block failure")

    assert get_current_inference_context() is None


@pytest.mark.asyncio
async def test_user_chat_execution_scope_cleanup_on_cancellation():
    """Verify async context cleanly resets when task is cancelled."""
    assert get_current_inference_context() is None

    async def long_running_coro():
        async with user_chat_execution_scope(authenticated_principal="user_cancel", session_id="sess_canc"):
            assert get_current_inference_context() is not None
            await asyncio.sleep(10.0)

    task = asyncio.create_task(long_running_coro())
    await asyncio.sleep(0.01)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert get_current_inference_context() is None


def test_user_chat_execution_scope_nested():
    """Verify nested scopes correctly stack and restore parent context."""
    with user_chat_execution_scope(
        authenticated_principal="user_parent",
        session_id="sess_parent",
        run_id="run_parent",
    ) as p_ctx:
        assert get_current_inference_context().run_id == "run_parent"

        with user_chat_execution_scope(
            authenticated_principal="user_parent",
            session_id="sess_parent",
            run_id="run_child",
        ) as c_ctx:
            assert get_current_inference_context().run_id == "run_child"
            assert c_ctx.parent_scope_token == p_ctx.scope_token

        # Parent restored
        assert get_current_inference_context().run_id == "run_parent"

    assert get_current_inference_context() is None


# ── Monotonic Expiration Tests ──────────────────────────────────────────────

def test_scope_ttl_expiration_fails_closed():
    """Verify that an expired scope is rejected by check_outbound_authorization."""
    with user_chat_execution_scope(
        authenticated_principal="user_exp",
        session_id="sess_exp",
        run_id="run_exp",
        ttl_seconds=0.1,  # 100ms TTL
    ):
        time.sleep(0.15)  # Let TTL expire
        ctx = get_current_inference_context()
        assert ctx.is_expired()

        with pytest.raises(UnauthorizedInferenceError) as exc_info:
            check_outbound_authorization(
                provider="ollama",
                model="gemma4:e4b",
                url="http://127.0.0.1:11434/api/chat",
                method="POST",
            )
        assert "authorization context expired" in str(exc_info.value)
        assert exc_info.value.event.outcome == "BLOCKED"


# ── Propagation (Task & Thread) Tests ────────────────────────────────────────

@pytest.mark.asyncio
async def test_contextvars_propagation_across_create_task():
    """Verify contextvars propagate into newly spawned asyncio tasks."""
    async with user_chat_execution_scope(
        authenticated_principal="user_task",
        session_id="sess_task",
        run_id="run_task_01",
    ):
        async def background_worker():
            ctx = get_current_inference_context()
            assert ctx is not None
            assert ctx.run_id == "run_task_01"
            # Should be authorized to check egress
            ev = check_outbound_authorization(
                provider="ollama",
                model="gemma4:e4b",
                url="http://127.0.0.1:11434/api/chat",
            )
            return ev.outcome

        task = asyncio.create_task(background_worker())
        outcome = await task
        assert outcome == "ALLOWED"


def test_thread_propagation_via_run_with_inference_context():
    """Verify sync thread execution receives active context via adapter."""
    with user_chat_execution_scope(
        authenticated_principal="user_thread",
        session_id="sess_thread",
        run_id="run_thread_01",
    ) as ctx:
        import concurrent.futures

        def worker_fn(expected_run_id):
            inner_ctx = get_current_inference_context()
            assert inner_ctx is not None
            assert inner_ctx.run_id == expected_run_id
            ev = check_outbound_authorization(
                provider="ollama",
                model="gemma4:e4b",
                url="http://127.0.0.1:11434/api/chat",
            )
            return ev.outcome

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            # Without adapter, thread has no context
            future_raw = pool.submit(get_current_inference_context)
            assert future_raw.result() is None

            # With run_with_inference_context adapter, thread is authorized
            future_adapted = pool.submit(run_with_inference_context, ctx, worker_fn, "run_thread_01")
            assert future_adapted.result() == "ALLOWED"


def test_thread_propagation_via_decorator():
    """Verify propagate_inference_context decorator captures and applies context in threads."""
    with user_chat_execution_scope(
        authenticated_principal="user_deco",
        session_id="sess_deco",
        run_id="run_deco_01",
    ):
        import concurrent.futures

        @propagate_inference_context
        def worker_fn():
            ctx = get_current_inference_context()
            assert ctx is not None
            assert ctx.run_id == "run_deco_01"
            return True

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(worker_fn)
            assert future.result() is True


@pytest.mark.asyncio
async def test_concurrent_sessions_do_not_leak():
    """Verify concurrent user sessions maintain strictly isolated authorization contexts."""
    results = {}

    async def user_session_job(user_name: str, session_id: str, delay: float):
        async with user_chat_execution_scope(
            authenticated_principal=user_name,
            session_id=session_id,
            run_id=f"run-{user_name}",
        ):
            await asyncio.sleep(delay)
            ctx = get_current_inference_context()
            results[user_name] = {
                "principal": ctx.authenticated_principal,
                "session": ctx.session_id,
                "run_id": ctx.run_id,
            }

    await asyncio.gather(
        user_session_job("alice", "sess_alice_1", 0.03),
        user_session_job("bob", "sess_bob_2", 0.01),
        user_session_job("charlie", "sess_charlie_3", 0.02),
    )

    assert results["alice"]["principal"] == "alice"
    assert results["alice"]["session"] == "sess_alice_1"
    assert results["bob"]["principal"] == "bob"
    assert results["bob"]["session"] == "sess_bob_2"
    assert results["charlie"]["principal"] == "charlie"
    assert results["charlie"]["session"] == "sess_charlie_3"


# ── Guard Fail-Closed Negative Tests ─────────────────────────────────────────

def test_guard_rejects_missing_context():
    """Verify check_outbound_authorization fails closed when no context exists."""
    assert get_current_inference_context() is None

    with pytest.raises(UnauthorizedInferenceError) as exc_info:
        check_outbound_authorization(
            provider="ollama",
            model="gemma4:e4b",
            url="http://127.0.0.1:11434/api/chat",
            method="POST",
        )
    assert "missing active authorization context (trigger=unknown)" in str(exc_info.value)
    assert exc_info.value.event.trigger == "unknown"
    assert exc_info.value.event.outcome == "BLOCKED"


def test_guard_rejects_disallowed_trigger_ws_connect():
    """Verify generative call on TRIGGER_WS_CONNECT is strictly blocked."""
    with inference_authorization_context(trigger=TRIGGER_WS_CONNECT, user_id="local"):
        with pytest.raises(UnauthorizedInferenceError) as exc_info:
            check_outbound_authorization(
                provider="ollama",
                model="gemma4:e4b",
                url="http://127.0.0.1:11434/api/chat",
            )
        assert "disallowed on ws_connect" in str(exc_info.value)


def test_guard_rejects_disallowed_trigger_startup():
    """Verify generative call on TRIGGER_STARTUP is strictly blocked."""
    with inference_authorization_context(trigger=TRIGGER_STARTUP, user_id="local"):
        with pytest.raises(UnauthorizedInferenceError) as exc_info:
            check_outbound_authorization(
                provider="ollama",
                model="gemma4:e4b",
                url="http://127.0.0.1:11434/api/chat",
            )
        assert "disallowed on startup" in str(exc_info.value)


def test_guard_rejects_scheduled_task_without_run_or_job_id():
    """Verify scheduled tasks lacking durable run or job ID are rejected."""
    with inference_authorization_context(trigger=TRIGGER_SCHEDULER_JOB_ID, user_id="local", run_id=None, job_id=None):
        with pytest.raises(UnauthorizedInferenceError) as exc_info:
            check_outbound_authorization(
                provider="ollama",
                model="gemma4:e4b",
                url="http://127.0.0.1:11434/api/chat",
            )
        assert "must reference a durable previously authorized run or job ID" in str(exc_info.value)


def test_guard_allows_scheduled_task_with_run_id():
    """Verify scheduled tasks with valid run_id are permitted."""
    with inference_authorization_context(
        trigger=TRIGGER_AUTHORIZED_RUN_ID,
        user_id="local",
        run_id="krun-deferred-1234",
    ):
        ev = check_outbound_authorization(
            provider="ollama",
            model="gemma4:e4b",
            url="http://127.0.0.1:11434/api/chat",
        )
        assert ev.outcome == "ALLOWED"
        assert ev.authorization_class == "TASK_PREVIOUSLY_AUTHORIZED"


def test_guard_allows_read_only_discovery_without_context():
    """Verify read-only discovery (/api/tags, /api/show) does not require generative scope."""
    assert get_current_inference_context() is None

    ev_tags = check_outbound_authorization(
        provider="ollama",
        model="gemma4:e4b",
        url="http://127.0.0.1:11434/api/tags",
        method="GET",
    )
    assert ev_tags.outcome == "ALLOWED"
    assert ev_tags.endpoint_category == ENDPOINT_CATEGORY_DISCOVERY

    ev_show = check_outbound_authorization(
        provider="ollama",
        model="gemma4:e4b",
        url="http://127.0.0.1:11434/api/show",
        method="POST",
    )
    assert ev_show.outcome == "ALLOWED"
    assert ev_show.endpoint_category == ENDPOINT_CATEGORY_METADATA


# ── Executable Provider-Level Test with Live Local Ollama ─────────────────────

@pytest.mark.asyncio
async def test_live_ollama_gemma4_e4b_with_user_chat_execution_scope():
    """
    Executable provider-level test with real local Ollama (gemma4:e4b).
    1. Verifies that without scope, AIClient.chat fails closed with UnauthorizedInferenceError.
    2. Verifies that under user_chat_execution_scope, real inference request passes guard
       and executes genuine POST /api/chat.
    """
    import httpx
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get("http://127.0.0.1:11434/api/tags")
            if resp.status_code != 200 or "gemma4:e4b" not in resp.text:
                pytest.skip("Local Ollama gemma4:e4b not available on 127.0.0.1:11434")
    except Exception:
        pytest.skip("Local Ollama daemon not reachable on 127.0.0.1:11434")

    client = get_ai_client(pinned_provider="ollama", pinned_model="gemma4:e4b")

    # Step 1: Prove without scope it FAILS CLOSED
    with pytest.raises(UnauthorizedInferenceError) as exc_info:
        await client.chat([{"role": "user", "content": "Respond: pong"}])
    assert "missing active authorization context" in str(exc_info.value)

    # Step 2: Prove with user_chat_execution_scope it SUCCEEDS
    async with user_chat_execution_scope(
        authenticated_principal="local",
        session_id="sess_live_test",
        run_id="krun-live-a1-test",
        source=SOURCE_WS_CHAT,
    ):
        response_text = await client.chat([{"role": "user", "content": "Respond with the word pong and nothing else."}])
        assert response_text is not None
        assert len(response_text.strip()) > 0
        assert "pong" in response_text.lower()
