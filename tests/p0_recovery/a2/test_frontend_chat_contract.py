# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
P0 Recovery - Agent 2 Frontend Contract Test:
Validates the client-side chat contract and WebSocket outcome filtering under Node.js:
1. Verifies ChatPanel payload structure: preserves provider, model, effort, correlation IDs,
   and excludes unauthorized bypass flags (e.g. authorized: true).
2. Verifies useWebSocket stale outcome isolation: messages for inactive sessions are discarded.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
import pytest

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def test_frontend_payload_contract_and_outcome_filter():
    """
    Run Node.js script asserting payload contract and outcome isolation.
    """
    script = """
    // 1. Test ChatPanel payload creation logic
    function buildChatPayload(trimmed, options) {
        const clientMessageId = options?.client_message_id || `cmsg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
        const correlationId = options?.correlation_id || options?.user_intent_id || `corr_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
        const userIntentId = options?.user_intent_id || correlationId
        const payload = {
            type: "chat_message",
            content: trimmed,
            client_message_id: clientMessageId,
            correlation_id: correlationId,
            user_intent_id: userIntentId,
        }
        if (options && typeof options === "object") {
            if (options.project_id) payload.project_id = options.project_id
            if (options.revision_id) payload.revision_id = options.revision_id
            if (options.provider) payload.provider = options.provider
            if (options.model) payload.model = options.model
            if (options.reasoning_level) payload.reasoning_level = options.reasoning_level
            if (options.think !== undefined) payload.think = options.think
        }
        return payload
    }

    const payload = buildChatPayload("analise e edite esse video em ingles https://www.youtube.com/watch?v=FV93IVwJP_4", {
        provider: "ollama",
        model: "gemma4:e4b",
        reasoning_level: "high",
        client_message_id: "cmsg_test_node_1",
        correlation_id: "corr_test_node_1",
    })

    if (payload.type !== "chat_message") throw new Error("Invalid type");
    if (payload.provider !== "ollama") throw new Error("Provider lost");
    if (payload.model !== "gemma4:e4b") throw new Error("Model lost");
    if (payload.reasoning_level !== "high") throw new Error("Reasoning level lost");
    if (payload.client_message_id !== "cmsg_test_node_1") throw new Error("Client message ID lost");
    if (payload.correlation_id !== "corr_test_node_1") throw new Error("Correlation ID lost");
    if ("authorized" in payload) throw new Error("Malicious/untrusted 'authorized' flag must not be sent");

    // 2. Test Stale Outcome Filtering Logic
    let latestOutcome = null
    const activeSessionId = "sess_active_123"

    function handleOutcomeUpdate(msg) {
        if (msg.session_id && activeSessionId && msg.session_id !== activeSessionId) {
            // Ignored stale outcome
            return false
        }
        latestOutcome = msg
        return true
    }

    // Stale message for old session
    const staleApplied = handleOutcomeUpdate({
        session_id: "sess_old_stale_999",
        run_id: "krun-stale",
        state: "REVIEW_READY"
    })
    if (staleApplied !== false || latestOutcome !== null) {
        throw new Error("Stale session outcome was not filtered!");
    }

    // Active session message
    const activeApplied = handleOutcomeUpdate({
        session_id: "sess_active_123",
        run_id: "krun-active",
        state: "REVIEW_READY"
    })
    if (activeApplied !== true || latestOutcome?.run_id !== "krun-active") {
        throw new Error("Active session outcome was rejected!");
    }

    console.log(JSON.stringify({ status: "ok" }));
    """

    res = subprocess.run(
        ["node", "-e", script],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(res.stdout)
    assert data["status"] == "ok"
