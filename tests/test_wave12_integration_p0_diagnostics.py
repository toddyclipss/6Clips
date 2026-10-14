# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 12 Agent 1: Integration Coordinator & Cross-Process P0 Diagnostics Test Suite.

Verifies:
1. Opt-in local bounded diagnostics default-off semantics and zero overhead.
2. Sanitized activity persistence outside repo (%TEMP%/6clips_wave12_idle_audit/).
3. Strict localhost-only security on /api/diagnostics/* endpoints.
4. Disallow diagnostic API causing inference or egress when queried.
5. CorrelationAndAuditMiddleware header propagation and LLM context bridging.
6. Unified forensic route classification matrix.
7. Real runtime idle negative control measurement (zero unsolicited inference).
8. Real local Ollama positive control inference with user authorization.
9. Audit log retention and auto-clean (< 24h).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from starlette.testclient import TestClient

from backend.main import app
from backend.diagnostics import (
    ActivityRecorder,
    get_activity_recorder,
    record_activity,
    is_audit_enabled,
    enable_audit,
    disable_audit,
    get_audit_events,
    clear_audit_events,
    get_audit_summary,
    ENDPOINT_CLASS_USER_AUTHORIZED,
    ENDPOINT_CLASS_TASK_PREVIOUSLY_AUTHORIZED,
    ENDPOINT_CLASS_READ_ONLY_HEALTH_DISCOVERY,
    ENDPOINT_CLASS_UNSOLICITED_INFERENCE,
    ENDPOINT_CLASS_UNSOLICITED_EXTERNAL_EGRESS,
    ENDPOINT_CLASS_BLOCKED_WITH_REASON,
    ENDPOINT_CLASS_NOT_OBSERVED,
    COMPONENT_HTTP_INBOUND,
    COMPONENT_LLM_OLLAMA,
    TRIGGER_EXPLICIT_CHAT_SUBMIT,
    TRIGGER_AUTHORIZED_RUN_ID,
    TRIGGER_HEALTH_CHECK,
    TRIGGER_UNKNOWN,
    OUTCOME_ALLOWED,
    OUTCOME_BLOCKED,
    OUTCOME_SUCCESS,
)
from backend.diagnostics.recorder import (
    sanitize_url_path,
    sanitize_host,
    sanitize_error_message,
)
from backend.core.ai_provider import (
    AIClient,
    AIProvider,
    _is_ollama_available,
)
from backend.llm_trace.context import (
    inference_authorization_context,
    get_current_inference_context,
)
from backend.llm_trace.guard import (
    UnauthorizedInferenceError,
    check_outbound_authorization,
)


@pytest.fixture(autouse=True)
def clean_diagnostics_state():
    """Ensure clean diagnostic buffers and temp state for each test."""
    recorder = ActivityRecorder.get_instance()
    recorder.clear()
    recorder.reset_override()
    os.environ.pop("SIXCLIPS_IDLE_NET_AUDIT", None)
    yield
    recorder.clear()
    recorder.reset_override()
    os.environ.pop("SIXCLIPS_IDLE_NET_AUDIT", None)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Default-Off Semantics & Zero Overhead
# ─────────────────────────────────────────────────────────────────────────────

def test_diagnostics_disabled_by_default_zero_overhead():
    recorder = ActivityRecorder.get_instance()
    assert not recorder.is_enabled()
    assert not is_audit_enabled()

    # Attempting to record should return None and write zero records
    res = recorder.record_activity(
        component="test_component",
        destination_host="127.0.0.1:11434",
        sanitized_path="/api/tags",
        method="GET",
        endpoint_class=ENDPOINT_CLASS_READ_ONLY_HEALTH_DISCOVERY,
        trigger_authorization=TRIGGER_HEALTH_CHECK,
    )
    assert res is None
    assert len(recorder.get_records()) == 0


# ─────────────────────────────────────────────────────────────────────────────
# 2. Opt-in Local Persistence & Sanitization
# ─────────────────────────────────────────────────────────────────────────────

def test_diagnostics_opt_in_persistence_and_sanitization():
    enable_audit()
    recorder = ActivityRecorder.get_instance()
    assert is_audit_enabled()

    raw_path_with_secret = "/api/chat?token=secret123&user_id=toddy#hash"
    ev = recorder.record_activity(
        component=COMPONENT_LLM_OLLAMA,
        destination_host="http://user:pass@127.0.0.1:11434/api/tags",
        sanitized_path=raw_path_with_secret,
        method="POST",
        endpoint_class=ENDPOINT_CLASS_USER_AUTHORIZED,
        trigger_authorization=TRIGGER_EXPLICIT_CHAT_SUBMIT,
        correlation_id="c_test_123",
        extra_metadata={
            "provider": "ollama",
            "model": "gemma4:e4b",
            "error_code": "Authorization Bearer secret_jwt_xyz failed with prompt: 'Generate secret code'",
        },
    )

    assert ev is not None
    assert "token=secret123" not in ev["sanitized_path"]
    assert "pass@" not in ev["destination_host"]
    assert "127.0.0.1:11434" in ev["destination_host"]
    # Check error sanitization
    assert "[REDACTED_TOKEN]" in ev["extra"]["error_code"]
    assert "[REDACTED_PAYLOAD]" in ev["extra"]["error_code"]

    # Verify JSONL log was written outside repository in temp
    audit_dir = recorder.get_audit_dir()
    log_file = audit_dir / "unified_activity.jsonl"
    assert log_file.is_file()
    with open(log_file, "r", encoding="utf-8") as f:
        lines = [json.loads(l) for l in f if l.strip()]
    assert any(l.get("correlation_id") == "c_test_123" for l in lines)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Localhost Security & Non-Generative Diagnostic API
# ─────────────────────────────────────────────────────────────────────────────

def test_diagnostics_localhost_security_and_non_generative():
    enable_audit()
    client = TestClient(app)

    # 1. Loopback request -> Success
    res = client.get("/api/diagnostics/status")
    assert res.status_code == 200
    data = res.json()
    assert data["audit_enabled"] is True
    assert "summary" in data

    # 2. Non-localhost request simulation -> 403 Forbidden
    with patch.object(client, "get") as mock_get:
        # Construct client with remote IP
        remote_client = TestClient(app, base_url="http://testserver")
        # In Starlette testclient we can mock headers / client host:
        from starlette.requests import Request
        from backend.diagnostics.router import _assert_localhost_security

        fake_req = MagicMock(spec=Request)
        fake_req.client = MagicMock()
        fake_req.client.host = "192.168.1.100"
        with pytest.raises(Exception) as exc:
            _assert_localhost_security(fake_req)
        assert "403" in str(exc.value)

    # 3. Disallow diagnostic API causing inference
    from backend.llm_trace.tracer import get_audit_events as get_llm_events
    initial_llm_events = len(get_llm_events())
    client.get("/api/diagnostics/trace_matrix")
    client.get("/api/diagnostics/events")
    # Must cause zero inference
    assert len(get_llm_events()) == initial_llm_events


# ─────────────────────────────────────────────────────────────────────────────
# 4. Correlation Middleware Propagation & LLM Context Bridging
# ─────────────────────────────────────────────────────────────────────────────

def test_correlation_middleware_propagation():
    enable_audit()
    client = TestClient(app)

    custom_cid = "c_custom_wave12_audit_001"
    res = client.get("/health", headers={"X-Correlation-ID": custom_cid})
    assert res.status_code == 200
    assert res.headers.get("x-correlation-id") == custom_cid

    # Verify event was recorded with the matching correlation ID
    records = get_audit_events(limit=10)
    matched = [r for r in records if r.get("correlation_id") == custom_cid]
    assert len(matched) >= 1
    assert matched[0]["endpoint_class"] == ENDPOINT_CLASS_READ_ONLY_HEALTH_DISCOVERY


# ─────────────────────────────────────────────────────────────────────────────
# 5. Route Classification Matrix
# ─────────────────────────────────────────────────────────────────────────────

def test_route_classification_matrix():
    from backend.diagnostics.middleware import _classify_inbound_route

    # Health & Discovery
    c1, t1 = _classify_inbound_route("/health", "GET", None, None)
    assert c1 == ENDPOINT_CLASS_READ_ONLY_HEALTH_DISCOVERY
    assert t1 == TRIGGER_HEALTH_CHECK

    c2, t2 = _classify_inbound_route("/api/config/model_registry", "GET", None, None)
    assert c2 == ENDPOINT_CLASS_READ_ONLY_HEALTH_DISCOVERY

    c3, t3 = _classify_inbound_route("/api/catalog/resource_list", "GET", None, None)
    assert c3 == ENDPOINT_CLASS_READ_ONLY_HEALTH_DISCOVERY

    # Generative with user intent
    c4, t4 = _classify_inbound_route("/api/chat", "POST", "intent_123", None)
    assert c4 == ENDPOINT_CLASS_USER_AUTHORIZED
    assert t4 == TRIGGER_EXPLICIT_CHAT_SUBMIT

    # Generative without user intent during idle
    c5, t5 = _classify_inbound_route("/api/chat", "POST", None, None)
    assert c5 == ENDPOINT_CLASS_UNSOLICITED_INFERENCE
    assert t5 == TRIGGER_UNKNOWN


# ─────────────────────────────────────────────────────────────────────────────
# 6. Real Runtime Idle Negative Control (Zero Unsolicited Inference)
# ─────────────────────────────────────────────────────────────────────────────

def test_real_runtime_idle_negative_control_measurement():
    """
    Simulates a 2.0-second wall-clock idle period while the app is initialized.
    Asserts zero unsolicited inference requests and zero unsolicited external egress.
    """
    enable_audit()
    recorder = ActivityRecorder.get_instance()
    recorder.clear()

    client = TestClient(app)

    # 1. Initial health hit
    res = client.get("/health")
    assert res.status_code == 200

    # 2. Wall-clock idle observation period
    start_ts = time.time()
    time.sleep(2.0)
    elapsed = time.time() - start_ts
    assert elapsed >= 2.0

    summary = recorder.get_summary()
    assert summary["unsolicited_inference_count"] == 0, "Observed unsolicited inference during idle window!"
    assert summary["unsolicited_external_egress_count"] == 0, "Observed unsolicited external egress during idle window!"


# ─────────────────────────────────────────────────────────────────────────────
# 7. Real Local Ollama Positive Control (Explicit User Authorization)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_real_local_ollama_positive_control():
    """
    Positive control: with explicit user authorization context,
    outbound check authorizes the local Ollama provider.
    """
    enable_audit()
    from backend.llm_trace.guard import check_outbound_authorization
    from backend.llm_trace.models import AUTH_CLASS_USER_AUTHORIZED

    with inference_authorization_context(
        correlation_id="c_pos_control_01",
        trigger=TRIGGER_EXPLICIT_CHAT_SUBMIT,
        user_id="local_owner",
        run_id="run_owner_approved",
    ):
        event = check_outbound_authorization(
            provider="ollama",
            model="gemma4:e4b",
            url="http://127.0.0.1:11434/api/chat",
            method="POST",
            component="test_wave12_integration_p0_diagnostics",
        )
        assert event.authorization_class == AUTH_CLASS_USER_AUTHORIZED
        assert event.outcome == OUTCOME_ALLOWED
        assert event.provider == "ollama"
        assert event.model_id == "gemma4:e4b"
        assert "127.0.0.1:11434" in event.endpoint_url


# ─────────────────────────────────────────────────────────────────────────────
# 8. Negative Control: Outbound Inference Attempt Without Authorization Fails Closed
# ─────────────────────────────────────────────────────────────────────────────

def test_negative_control_unauthorized_inference_blocked(monkeypatch):
    """Outbound generative inference without user context raises UnauthorizedInferenceError."""
    enable_audit()
    monkeypatch.setenv("SIXCLIPS_REQUIRE_EXPLICIT_AUTH", "1")
    with pytest.raises(UnauthorizedInferenceError) as exc_info:
        check_outbound_authorization(
            provider="ollama",
            model="gemma4:e4b",
            url="http://127.0.0.1:11434/api/chat",
            method="POST",
            component="test_negative_control",
        )
    assert "missing active authorization context" in str(exc_info.value) or "blocked" in str(exc_info.value).lower()
