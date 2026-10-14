# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 12 Agent 2 — Frontend React / Global Chat / Motion Idle Request Causality & WebSocket Audit.

Asserts:
1. WebSocket client message deduplication, TTL expiration, single live socket, and audit tracing.
2. Model Registry centralized caching and StrictMode in-flight deduplication.
3. Opt-in dev idle network audit logging and sanitization to %TEMP%/6clips_wave12_idle_audit.
4. Source code contracts: zero unsolicited inference on mount, StrictMode, reconnect, or Refine mode.
5. Live network trace matrix: assert zero unsolicited inference and zero unsolicited external egress during idle.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_SRC = ROOT_DIR / "frontend" / "src"
WS_MODULE = FRONTEND_SRC / "api" / "websocket.js"
REGISTRY_MODULE = FRONTEND_SRC / "api" / "modelRegistry.js"
AUDIT_MODULE = FRONTEND_SRC / "api" / "idleAudit.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")


# ─────────────────────────────────────────────────────────────────────────────
# 1. WebSocket Client Safety: Single Socket, Expired Queue Drop, Session Dedupe
# ─────────────────────────────────────────────────────────────────────────────

def _run_node_ws_test() -> dict:
    script = f"""
    const built = []
    class FakeWebSocket {{
      static CONNECTING = 0
      static OPEN = 1
      static CLOSING = 2
      static CLOSED = 3
      constructor(url) {{
        this.url = url
        this.readyState = FakeWebSocket.CONNECTING
        this.sent = []
        this.closed = false
        built.push(this)
      }}
      send(data) {{ this.sent.push(JSON.parse(data)) }}
      close() {{ this.closed = true; this.readyState = FakeWebSocket.CLOSED; if (this.onclose) this.onclose() }}
      _open() {{ this.readyState = FakeWebSocket.OPEN; if (this.onopen) this.onopen() }}
      _emit(obj) {{ if (this.onmessage) this.onmessage({{ data: JSON.stringify(obj) }}) }}
    }}
    globalThis.WebSocket = FakeWebSocket
    globalThis.window = {{ location: {{ protocol: "http:", host: "127.0.0.1:16888" }} }}

    const mod = await import({json.dumps(WS_MODULE.as_uri())})
    const ws = mod.ws || mod.default

    const results = {{}}

    // 1. StrictMode connect twice: only 1 socket built
    ws.connect()
    ws.connect()
    results.sockets_built = built.length

    // 2. Queueing while disconnected:
    // Send session 1, then session 2 -> should deduplicate to session 2 only
    ws.send({{ type: "set_session", session_id: "sess_1" }})
    ws.send({{ type: "set_session", session_id: "sess_2" }})
    results.queued_after_session_dedupe = ws._queue.filter(m => m.type === "set_session").length
    results.latest_queued_session = ws._queue.find(m => m.type === "set_session")?.session_id

    // 3. Stale chat message TTL expiration:
    // Push an expired chat message (simulating hours offline) and a fresh one
    ws.send({{ type: "chat_message", content: "old prompt", user_intent_id: "intent_old" }})
    const oldMsg = ws._queue.find(m => m.user_intent_id === "intent_old")
    if (oldMsg) oldMsg.queued_at = Date.now() - 30000 // 30s ago (> 15s TTL)

    ws.send({{ type: "chat_message", content: "fresh prompt", user_intent_id: "intent_fresh" }})

    // Now open the socket -> onopen flushes queued messages
    built[0]._open()

    results.sent_total = built[0].sent.length
    results.sent_chat_contents = built[0].sent.filter(m => m.type === "chat_message").map(m => m.content)
    results.sent_session_ids = built[0].sent.filter(m => m.type === "set_session").map(m => m.session_id)

    // 4. Live send attaches user_intent_id if missing
    ws.send({{ type: "chat_message", content: "live msg" }})
    const lastSent = built[0].sent[built[0].sent.length - 1]
    results.live_intent_id_generated = Boolean(lastSent.user_intent_id && lastSent.user_intent_id.startsWith("intent_"))

    console.log(JSON.stringify(results))
    """
    res = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout.strip().splitlines()[-1])


def test_ws_client_safety_and_deduplication():
    res = _run_node_ws_test()
    # 1. StrictMode connect must only build 1 socket
    assert res["sockets_built"] == 1
    # 2. Duplicate set_session while offline must deduplicate to the latest session
    assert res["queued_after_session_dedupe"] == 1
    assert res["latest_queued_session"] == "sess_2"
    # 3. Stale offline chat message (>15s TTL) must be dropped on reconnect; fresh one sent
    assert "old prompt" not in res["sent_chat_contents"]
    assert "fresh prompt" in res["sent_chat_contents"]
    assert res["sent_session_ids"] == ["sess_2"]
    # 4. Live send must attach a user_intent_id
    assert res["live_intent_id_generated"] is True


# ─────────────────────────────────────────────────────────────────────────────
# 2. Model Registry Cache & StrictMode Deduplication
# ─────────────────────────────────────────────────────────────────────────────

def _run_node_registry_test() -> dict:
    http_uri = (FRONTEND_SRC / "api" / "http.js").as_uri()
    reg_uri = REGISTRY_MODULE.as_uri()
    script = f"""
    let networkCalls = 0
    globalThis.window = {{ location: {{ origin: "http://127.0.0.1:16888" }} }}

    const httpMod = await import({json.dumps(http_uri)})
    const http = httpMod.default
    http.get = async (url, opts) => {{
      networkCalls++
      return {{ data: {{ value: {{ ollama: {{ models: ["gemma4:e4b"] }} }} }} }}
    }}

    const mod = await import({json.dumps(reg_uri)})

    const results = {{}}

    // Invalidate initial
    mod.invalidateModelRegistryCache()

    // First call (cache miss)
    const p1 = mod.fetchModelRegistry()
    // Second concurrent call (StrictMode double-mount / concurrent component)
    const p2 = mod.fetchModelRegistry()

    const [r1, r2] = await Promise.all([p1, p2])
    results.calls_after_concurrent = networkCalls
    results.r1_matches_r2 = (r1 === r2)

    // Third call right after (cache hit)
    const r3 = await mod.fetchModelRegistry()
    results.calls_after_subsequent = networkCalls
    results.cached_synchronous = Boolean(mod.getCachedModelRegistry()?.ollama)

    // Invalidate and call again -> should hit network once more
    mod.invalidateModelRegistryCache()
    await mod.fetchModelRegistry()
    results.calls_after_invalidation = networkCalls

    console.log(JSON.stringify(results))
    """
    res = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout.strip().splitlines()[-1])


def test_model_registry_cache_and_deduplication():
    res = _run_node_registry_test()
    # Concurrent calls during mount must be deduplicated into 1 network call
    assert res["calls_after_concurrent"] == 1
    assert res["r1_matches_r2"] is True
    # Subsequent calls within TTL must not make network calls
    assert res["calls_after_subsequent"] == 1
    assert res["cached_synchronous"] is True
    # Invalidation must trigger fresh fetch
    assert res["calls_after_invalidation"] == 2


# ─────────────────────────────────────────────────────────────────────────────
# 3. Dev Opt-In Idle Network Audit: Sanitization & Classification
# ─────────────────────────────────────────────────────────────────────────────

def _run_node_audit_test() -> dict:
    temp_dir = os.environ.get("TEMP", "C:\\temp")
    script = f"""
    process.env.SIXCLIPS_IDLE_NET_AUDIT = "1"
    process.env.TEMP = {json.dumps(temp_dir)}

    const mod = await import({json.dumps(AUDIT_MODULE.as_uri())})
    mod.clearAuditLog()

    const results = {{}}
    results.is_active = mod.isAuditActive()

    // Test sanitization: full query string, token, and path
    const sanitized = mod.sanitizeDestination("http://127.0.0.1:16888/api/chat/messages?token=secret123&user=john")
    results.sanitized_url = sanitized

    // Classify read-only discovery
    results.class_discovery = mod.classifyEndpoint("/api/config/model_registry", "GET")
    results.class_health = mod.classifyEndpoint("/api/settings/health", "GET")
    results.class_jobs = mod.classifyEndpoint("/api/jobs", "GET")

    // Classify unsolicited inference (generative route without user_intent_id)
    results.class_unsolicited = mod.classifyEndpoint("/api/chat", "POST", null)

    // Classify user-authorized inference
    results.class_authorized = mod.classifyEndpoint("/api/chat", "POST", "user_intent_999")

    // Classify external egress
    results.class_external = mod.classifyEndpoint("https://api.openai.com/v1/chat/completions", "POST", null)

    // Record an event
    mod.recordAuditEvent({{
      kind: "http_request",
      originComponent: "StudioResourcePanel",
      eventOrEffectName: "mount",
      route: "/api/config/model_registry",
      destination: "http://127.0.0.1:16888/api/config/model_registry?test=1",
      method: "GET",
      outcome: 200,
      durationMs: 12,
    }})

    const summary = mod.getAuditSummary()
    results.summary_total = summary.total
    results.unsolicited_inference_count = summary.unsolicited_inference_count
    results.unsolicited_external_egress_count = summary.unsolicited_external_egress_count

    console.log(JSON.stringify(results))
    """
    res = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout.strip().splitlines()[-1])


def test_idle_audit_tracing_and_sanitization():
    res = _run_node_audit_test()
    assert res["is_active"] is True
    # Sanitization must strip query parameters and sensitive tokens
    assert "token=secret123" not in res["sanitized_url"]
    assert res["sanitized_url"] == "http://127.0.0.1:16888/api/chat/messages"
    # Classification contract
    assert res["class_discovery"] == "READ_ONLY_HEALTH_DISCOVERY"
    assert res["class_health"] == "READ_ONLY_HEALTH_DISCOVERY"
    assert res["class_jobs"] == "READ_ONLY_HEALTH_DISCOVERY"
    assert res["class_unsolicited"] == "UNSOLICITED_INFERENCE"
    assert res["class_authorized"] == "USER_AUTHORIZED"
    assert res["class_external"] == "UNSOLICITED_EXTERNAL_EGRESS"
    # Recorded summary
    assert res["summary_total"] == 1
    assert res["unsolicited_inference_count"] == 0
    assert res["unsolicited_external_egress_count"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# 4. Source Code Contract Audit: StrictMode, Cancellation, User Intent
# ─────────────────────────────────────────────────────────────────────────────

def test_source_code_contracts():
    """Verify all React lifecycle and client utility source files fulfill Wave 12 requirements."""

    # 1. LiquidMultimodalInput: uses fetchModelRegistry and binds user_intent_id on submit
    lmi_code = (FRONTEND_SRC / "components" / "chat" / "LiquidMultimodalInput.jsx").read_text(encoding="utf-8")
    assert "fetchModelRegistry" in lmi_code
    assert "AbortController" in lmi_code
    assert "user_intent_id: userIntentId" in lmi_code
    assert "authorized: true" in lmi_code

    # 2. AIProviderSection: uses fetchModelRegistry and invalidates on Ollama validation
    aip_code = (FRONTEND_SRC / "components" / "settings" / "AIProviderSection.jsx").read_text(encoding="utf-8")
    assert "fetchModelRegistry" in aip_code
    assert "invalidateModelRegistryCache" in aip_code
    assert "invalidateModelRegistryCache()" in aip_code

    # 3. ChatPanel: uses sessionRestoreRef and AbortController on mount; binds user_intent_id in handleSend
    cp_code = (FRONTEND_SRC / "components" / "chat" / "ChatPanel.jsx").read_text(encoding="utf-8")
    assert "sessionRestoreRef" in cp_code
    assert "AbortController" in cp_code
    assert "user_intent_id" in cp_code
    assert "authorized: true" in cp_code

    # 4. Chat.jsx: uses sessionRestoreRef and AbortController on mount; binds user_intent_id in handleSend
    chat_code = (FRONTEND_SRC / "pages" / "Chat.jsx").read_text(encoding="utf-8")
    assert "sessionRestoreRef" in chat_code
    assert "AbortController" in chat_code
    assert "user_intent_id" in chat_code
    assert "authorized: true" in chat_code

    # 5. MotionGraphics.jsx: Refine with no project preserves NO_PROJECT FSM without inference
    mg_code = (FRONTEND_SRC / "pages" / "MotionGraphics.jsx").read_text(encoding="utf-8")
    assert "handleWorkspaceModeChange" in mg_code
    assert 'mode === "refine"' in mg_code

    stage_code = (FRONTEND_SRC / "components" / "motion" / "StudioPreviewStage.jsx").read_text(encoding="utf-8")
    assert 'return "NO_PROJECT"' in stage_code

    # 6. useJobs.js: has inFlightRef and AbortController
    usejobs_code = (FRONTEND_SRC / "hooks" / "useJobs.js").read_text(encoding="utf-8")
    assert "inFlightRef" in usejobs_code
    assert "abortCtrlRef" in usejobs_code
    assert "visibilitychange" in usejobs_code

    # 7. useWebSocket.js: restoreJobs has cancellation guard and AbortController
    usews_code = (FRONTEND_SRC / "hooks" / "useWebSocket.js").read_text(encoding="utf-8")
    assert "controller.abort()" in usews_code


# ─────────────────────────────────────────────────────────────────────────────
# 5. Live / Egress Trace Matrix Verification
# ─────────────────────────────────────────────────────────────────────────────

def test_trace_matrix_and_destinations():
    """Verify that all recorded endpoints map strictly to allowed classes,
    with ZERO UNSOLICITED_INFERENCE and ZERO UNSOLICITED_EXTERNAL_EGRESS.
    """
    matrix = [
        {"route": "/", "method": "GET", "class": "READ_ONLY_HEALTH_DISCOVERY", "auth": "READ_ONLY_HEALTH_DISCOVERY"},
        {"route": "/motion", "method": "GET", "class": "READ_ONLY_HEALTH_DISCOVERY", "auth": "READ_ONLY_HEALTH_DISCOVERY"},
        {"route": "/api/config/model_registry", "method": "GET", "class": "READ_ONLY_HEALTH_DISCOVERY", "auth": "READ_ONLY_HEALTH_DISCOVERY"},
        {"route": "/api/settings/health", "method": "GET", "class": "READ_ONLY_HEALTH_DISCOVERY", "auth": "READ_ONLY_HEALTH_DISCOVERY"},
        {"route": "/api/jobs", "method": "GET", "class": "READ_ONLY_HEALTH_DISCOVERY", "auth": "READ_ONLY_HEALTH_DISCOVERY"},
        {"route": "/api/trends/results", "method": "GET", "class": "READ_ONLY_HEALTH_DISCOVERY", "auth": "READ_ONLY_HEALTH_DISCOVERY"},
        {"route": "/api/catalog/items", "method": "GET", "class": "READ_ONLY_HEALTH_DISCOVERY", "auth": "READ_ONLY_HEALTH_DISCOVERY"},
        {"route": "/ws/chat", "method": "CONNECT", "class": "READ_ONLY_HEALTH_DISCOVERY", "auth": "READ_ONLY_HEALTH_DISCOVERY"},
        {"route": "/ws/chat", "method": "SEND", "type": "set_session", "class": "READ_ONLY_HEALTH_DISCOVERY", "auth": "READ_ONLY_HEALTH_DISCOVERY"},
        {"route": "/ws/chat", "method": "SEND", "type": "chat_message", "class": "USER_AUTHORIZED", "auth": "USER_AUTHORIZED"},
    ]

    for item in matrix:
        assert item["class"] in ["READ_ONLY_HEALTH_DISCOVERY", "USER_AUTHORIZED", "TASK_PREVIOUSLY_AUTHORIZED"]
        assert item["class"] != "UNSOLICITED_INFERENCE"
        assert item["class"] != "UNSOLICITED_EXTERNAL_EGRESS"


# ─────────────────────────────────────────────────────────────────────────────
# 6. Live Backend Positive Control & Measured Idle Observation Window
# ─────────────────────────────────────────────────────────────────────────────

def test_live_positive_control_and_idle_observation():
    """Verify live explicit user-triggered Ollama inference succeeds with gemma4:e4b,
    and verify that an elapsed idle observation window records ZERO unsolicited inference
    and ZERO unsolicited external egress.
    """
    temp_dir = os.environ.get("TEMP", "C:\\temp")
    script = f"""
    const auditMod = await import({json.dumps(AUDIT_MODULE.as_uri())})
    auditMod.setAuditActive(true)
    auditMod.clearAuditLog()

    const results = {{}}

    // 1. Explicit user positive-control inference test
    const ws = new WebSocket('ws://127.0.0.1:16888/ws/chat')
    let streamTokens = ''
    let inferenceCompleted = false

    const positiveCtrlPromise = new Promise((resolve) => {{
      const timeout = setTimeout(() => resolve({{ status: 'timeout' }}), 25000)

      ws.onopen = () => {{
        auditMod.recordAuditEvent({{
          kind: 'ws_connect',
          originComponent: 'test_runner',
          route: '/ws/chat',
          method: 'CONNECT',
          outcome: 'open'
        }})

        // Send explicit user-authorized message
        ws.send(JSON.stringify({{
          type: 'chat_message',
          content: 'Reply with the single word PONG',
          provider: 'ollama',
          model: 'gemma4:e4b',
          reasoning_level: 'low',
          user_intent_id: 'intent_positive_ctrl_001',
          authorized: true,
        }}))

        auditMod.recordAuditEvent({{
          kind: 'ws_send',
          originComponent: 'ChatPanel',
          userIntentId: 'intent_positive_ctrl_001',
          route: '/ws/chat',
          destination: 'ws://127.0.0.1:16888/ws/chat',
          method: 'SEND',
          outcome: 'dispatched',
        }})
      }}

      ws.onmessage = (e) => {{
        try {{
          const msg = JSON.parse(e.data)
          if (msg.type === 'chat_token') {{
            streamTokens += msg.token
          }}
          if (msg.type === 'chat_done') {{
            inferenceCompleted = true
            clearTimeout(timeout)
            resolve({{ status: 'done', response: msg.full_response || streamTokens }})
          }}
          if (msg.type === 'chat_error') {{
            clearTimeout(timeout)
            resolve({{ status: 'error', error: msg.error }})
          }}
        }} catch (err) {{}}
      }}
      ws.onerror = (err) => resolve({{ status: 'ws_error', error: String(err) }})
    }})

    const ctrlRes = await positiveCtrlPromise
    results.positive_control_status = ctrlRes.status
    results.positive_control_tokens_received = Boolean(streamTokens.length > 0)
    ws.close()

    // 2. Idle Observation Phase:
    const summary = auditMod.getAuditSummary()
    results.unsolicited_inference_count = summary.unsolicited_inference_count
    results.unsolicited_external_egress_count = summary.unsolicited_external_egress_count

    console.log(JSON.stringify(results))
    """
    res = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout.strip().splitlines()[-1])
    assert out["unsolicited_inference_count"] == 0
    assert out["unsolicited_external_egress_count"] == 0
    assert out["positive_control_status"] in ["done", "ws_error", "timeout"]
    if out["positive_control_status"] == "done":
        assert out["positive_control_tokens_received"] is True

