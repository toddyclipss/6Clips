# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 13 Agent 1: Integration Closure & Boot Egress Guard Test Suite.

Verifies:
1. Server lifespan startup with ENABLE_YTDLP_AUTO_UPDATE unset emits 0 pip subprocesses
   and 0 outbound connections to pypi.org.
2. WebSocket /ws/chat connect emits 0 Ollama /api/chat calls and 0 LLM suggestion calls.
3. Repeated GET /api/config/model_registry requests hit the 60s+ TTL cache without spamming
   Ollama /api/tags or /api/show.
4. Localhost-restricted forensic diagnostic endpoints (/api/diagnostics/status,
   /api/diagnostics/events, /api/diagnostics/trace_matrix) remain operational and non-generative.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from starlette.testclient import TestClient

from backend.main import app
from backend.api.config import clear_model_registry_cache
from backend.diagnostics import (
    ActivityRecorder,
    enable_audit,
    disable_audit,
    is_audit_enabled,
    get_audit_events,
    clear_audit_events,
    get_audit_summary,
    ENDPOINT_CLASS_NOT_OBSERVED,
    ENDPOINT_CLASS_READ_ONLY_HEALTH_DISCOVERY,
)
from backend.llm_trace.tracer import (
    get_audit_events as get_llm_events,
    clear_audit_events as clear_llm_events,
)
from backend.distribution.egress_audit import (
    get_recent_audit_events as get_egress_events,
    clear_audit_events as clear_egress_events,
)


@pytest.fixture(autouse=True)
def clean_test_env():
    """Ensure clean audit state and unset opt-ins for each test."""
    recorder = ActivityRecorder.get_instance()
    recorder.clear()
    recorder.reset_override()
    clear_llm_events()
    clear_egress_events()
    clear_model_registry_cache()
    os.environ.pop("ENABLE_YTDLP_AUTO_UPDATE", None)
    os.environ.pop("SIXCLIPS_IDLE_NET_AUDIT", None)
    yield
    recorder.clear()
    recorder.reset_override()
    clear_llm_events()
    clear_egress_events()
    clear_model_registry_cache()
    os.environ.pop("ENABLE_YTDLP_AUTO_UPDATE", None)
    os.environ.pop("SIXCLIPS_IDLE_NET_AUDIT", None)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Lifespan Boot Egress Guard: Zero pip subprocesses & zero pypi.org egress
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_server_lifespan_startup_zero_pypi_egress_and_pip():
    """
    Assert that server lifespan startup without ENABLE_YTDLP_AUTO_UPDATE=1
    never invokes pip or opens connections to pypi.org.
    """
    enable_audit()
    recorder = ActivityRecorder.get_instance()

    with patch("subprocess.run") as mock_subproc_run, \
         patch("subprocess.Popen") as mock_subproc_popen:

        # Trigger lifespan startup
        async with app.router.lifespan_context(app):
            # Lifespan has executed startup routines
            pass

        # Verify no pip commands were spawned
        for call_args in mock_subproc_run.call_args_list:
            cmd = call_args[0][0] if call_args[0] else []
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
            assert "pip" not in cmd_str.lower(), f"Unexpected pip execution during boot: {cmd_str}"
            assert "pypi.org" not in cmd_str.lower(), f"Unexpected pypi destination in cmd: {cmd_str}"

        for call_args in mock_subproc_popen.call_args_list:
            cmd = call_args[0][0] if call_args[0] else []
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
            assert "pip" not in cmd_str.lower(), f"Unexpected pip Popen during boot: {cmd_str}"

    # Verify diagnostic audit logged NOT_OBSERVED for boot version check
    events = recorder.get_records(component="startup_bootstrap")
    assert len(events) >= 1
    boot_ev = events[0]
    assert boot_ev["endpoint_class"] == ENDPOINT_CLASS_NOT_OBSERVED
    assert boot_ev["outcome_status"] == "ZERO_REQUESTS"
    assert boot_ev["destination_host"] == "NONE_LOCAL"


# ─────────────────────────────────────────────────────────────────────────────
# 2. WebSocket /ws/chat Connect: Zero Ollama /api/chat & Zero LLM Suggestions
# ─────────────────────────────────────────────────────────────────────────────

def test_websocket_chat_connect_zero_ollama_and_zero_llm_suggestions():
    """
    Connecting to /ws/chat must never launch unsolicited Ollama inference
    or trigger LLM-based smart suggestions.
    """
    enable_audit()
    clear_llm_events()

    client = TestClient(app)

    with patch("backend.core.user_intelligence.UserIntelligence.get_smart_suggestions",
               new_callable=AsyncMock) as mock_llm_suggestions:
        mock_llm_suggestions.return_value = ["Create video", "Explore trends"]

        with client.websocket_connect("/ws/chat") as ws:
            # Client connects and sets session (idle state)
            ws.send_json({"type": "set_session", "session_id": "sess_idle_test"})

            # Verify no generative Ollama call was initiated
            llm_events = get_llm_events()
            generative_calls = [
                e for e in llm_events
                if "/api/chat" in e.endpoint_url or "/api/generate" in e.endpoint_url
            ]
            assert len(generative_calls) == 0, f"Unsolicited generative calls on WS connect: {generative_calls}"

            # Verify get_smart_suggestions (which calls LLM) was NOT called
            assert not mock_llm_suggestions.called, "get_smart_suggestions LLM method was unexpectedly invoked"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Model Registry Backend 60s+ TTL Cache: No Ollama Tags Spamming
# ─────────────────────────────────────────────────────────────────────────────

def test_model_registry_cache_avoids_repeated_ollama_tags():
    """
    Assert that repeated GET /api/config/model_registry requests within TTL
    return cached response and avoid repeating Ollama discovery requests.
    """
    clear_model_registry_cache()
    client = TestClient(app)

    ollama_call_count = 0

    import httpx
    orig_get = httpx.AsyncClient.get

    async def counting_get(self, url, *args, **kwargs):
        nonlocal ollama_call_count
        if "11434" in str(url) or "api/tags" in str(url):
            ollama_call_count += 1
            # Return valid fake Ollama response
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"models": [{"name": "gemma4:e4b"}]}
            return resp
        return await orig_get(self, url, *args, **kwargs)

    with patch.object(httpx.AsyncClient, "get", counting_get):
        # 1. First call -> Cache Miss (fetches once)
        r1 = client.get("/api/config/model_registry")
        assert r1.status_code == 200
        data1 = r1.json()
        assert "ollama" in data1["value"]
        first_count = ollama_call_count

        # 2. Repeated calls (2nd, 3rd, 4th, 5th) within 60s -> Cache Hit
        for _ in range(4):
            rx = client.get("/api/config/model_registry")
            assert rx.status_code == 200
            assert rx.json()["value"]["ollama"]["models"] == data1["value"]["ollama"]["models"]

        # Call count must NOT increase
        assert ollama_call_count == first_count, (
            f"Expected cache hit (count={first_count}), but observed network calls={ollama_call_count}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 4. Forensic Diagnostic Endpoints: Localhost-Only & Non-Generative
# ─────────────────────────────────────────────────────────────────────────────

def test_diagnostic_endpoints_operational_and_restricted():
    """
    Verify /api/diagnostics/status and trace_matrix endpoints are functional,
    restricted to localhost, and emit zero generative inference.
    """
    enable_audit()
    client = TestClient(app)

    # 1. Localhost query -> 200 OK
    res = client.get("/api/diagnostics/status")
    assert res.status_code == 200
    body = res.json()
    assert body["audit_enabled"] is True
    assert "summary" in body
    assert "server_time_utc" in body

    # 2. Trace matrix endpoint -> 200 OK
    matrix_res = client.get("/api/diagnostics/trace_matrix")
    assert matrix_res.status_code == 200
    m_body = matrix_res.json()
    assert "trace_matrix" in m_body
    assert "USER_AUTHORIZED" in m_body["trace_matrix"]
    assert "READ_ONLY_HEALTH_DISCOVERY" in m_body["trace_matrix"]

    # 3. Confirm querying diagnostics emits ZERO generative LLM inference
    llm_events = get_llm_events()
    gen_events = [e for e in llm_events if "/api/chat" in e.endpoint_url]
    assert len(gen_events) == 0

    # 4. Non-localhost access is blocked with 403 Forbidden
    from starlette.requests import Request
    from backend.diagnostics.router import _assert_localhost_security

    fake_remote_req = MagicMock(spec=Request)
    fake_remote_req.client = MagicMock()
    fake_remote_req.client.host = "10.0.0.55"

    with pytest.raises(Exception) as exc_info:
        _assert_localhost_security(fake_remote_req)
    assert "403" in str(exc_info.value)
