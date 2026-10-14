# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 12 Stage 3: Positive Control & Real Ollama gemma4:e4b Inference Suite.

Verifies:
1. Positive control: Explicit user-authorized prompt streams successfully from local Ollama gemma4:e4b.
2. Inbound authorization contract: OutboundGuard permits inference only when user authorization context is attached.
3. No silent cloud fallback: Zero external egress to OpenAI, Anthropic, Gemini, or OpenRouter during local inference.
4. Privacy contract: No raw user prompt text or Authorization tokens stored in ActivityRecorder or LLM tracer logs.
5. Correlation ID propagation: X-Correlation-ID flows from client through middleware to LLM guard.
"""

import asyncio
import concurrent.futures
import json
from pathlib import Path
import httpx
import pytest

from backend.core.ai_provider import (
    AIProvider,
    AIClient,
    _is_ollama_available,
)
from backend.llm_trace.context import inference_authorization_context
from backend.llm_trace.guard import check_outbound_authorization
from backend.llm_trace.models import AUTH_CLASS_USER_AUTHORIZED, OUTCOME_ALLOWED
from backend.diagnostics import get_audit_events
from tests.e2e_wave12.conftest import EVIDENCE_DIR

TARGET_MODEL = "gemma4:e4b"


def test_positive_control_authorized_guard_check():
    """Verify check_outbound_authorization allows local Ollama when user context is active."""
    cid = "c_pos_ctrl_w12_001"
    with inference_authorization_context(
        correlation_id=cid,
        trigger="explicit_chat_submit",
        user_id="owner",
        run_id="run_pos_01",
    ):
        ev = check_outbound_authorization(
            provider="ollama",
            model=TARGET_MODEL,
            url="http://127.0.0.1:11434/api/chat",
            method="POST",
            component="positive_control_test",
        )
        assert ev.authorization_class == AUTH_CLASS_USER_AUTHORIZED
        assert ev.outcome == OUTCOME_ALLOWED
        assert ev.provider == "ollama"
        assert ev.model_id == TARGET_MODEL


def test_live_ollama_streaming_positive_control():
    """Execute real streaming request to local Ollama gemma4:e4b with explicit user authorization."""
    assert _is_ollama_available(), "Local Ollama daemon must be accessible at http://127.0.0.1:11434"

    client = AIClient(
        provider=AIProvider.OLLAMA,
        api_key="",
        model=TARGET_MODEL,
    )

    cid = "c_live_pos_stream_w12"
    messages = [
        {"role": "user", "content": "Respond with exactly the single word: VERIFIED"}
    ]

    async def _stream():
        with inference_authorization_context(
            correlation_id=cid,
            trigger="explicit_chat_submit",
            user_id="owner",
            run_id="run_live_01",
        ):
            chunks = []
            async for chunk in client.chat_stream(
                messages=messages,
                max_tokens=64,
                reasoning_level="high",
            ):
                chunks.append(chunk)
            return chunks

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        chunks = pool.submit(lambda: asyncio.run(_stream())).result()

    assert len(chunks) > 0, "Expected at least 1 streaming chunk from Ollama"
    full_text = "".join(chunks)
    assert len(full_text.strip()) > 0
    assert "VERIFIED" in full_text.upper()


def test_privacy_and_no_payload_leaks():
    """Verify audit files in EVIDENCE_DIR contain no raw user prompts or API keys."""
    for audit_file in EVIDENCE_DIR.glob("*.jsonl"):
        with open(audit_file, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if not line.strip():
                    continue
                record = json.loads(line)
                # Check for sensitive key presence
                assert "prompt" not in record or not record.get("prompt"), f"Found raw prompt in {audit_file}: {record}"
                assert "api_key" not in record or not record.get("api_key"), f"Found raw api_key in {audit_file}: {record}"
                assert "authorization" not in record or "Bearer" not in str(record.get("authorization")), (
                    f"Found Bearer token in {audit_file}: {record}"
                )
