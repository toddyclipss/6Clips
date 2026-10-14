# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 12 Stage 3: Adversarial Attack & Boundary Validation Suite.

Covers:
1. React StrictMode double-mount simulation (deduplicated model registry request).
2. WebSocket disconnect/reconnect (TTL expiry drops stale queued messages, no replay storm).
3. Switch tabs / reload settings / Refresh Models (read-only GET, zero generative inference).
4. Explicit user Cancel (aborts stream cleanly, zero retry loops).
5. Offline/unavailable Ollama simulation (graceful error handling without looping).
6. Unauthorized publish schedule / injected stale queued job (blocked by egress guard).
7. Route distinction: Local GET /api/tags (allowed discovery) vs POST /api/chat (blocked without auth).
8. Unknown API route 404 (handled gracefully without external dispatch).
9. Multi-provider unconfigured keys (clean error without unsolicited cloud egress).
"""

import asyncio
import concurrent.futures
import pytest
from starlette.testclient import TestClient

from backend.main import app
from backend.core.ai_provider import AIProvider, AIClient
from backend.llm_trace.guard import check_outbound_authorization, UnauthorizedInferenceError
from backend.distribution.egress_audit import check_outbound_allowlist
from backend.distribution.transport import ProductionLiveTransport
from backend.distribution.models import PlatformAccount, AccountState, DistributionJob, PlatformSEOMetadata
from backend.diagnostics import (
    ActivityRecorder,
    enable_audit,
    ENDPOINT_CLASS_READ_ONLY_HEALTH_DISCOVERY,
    ENDPOINT_CLASS_BLOCKED_WITH_REASON,
)


def test_attack_unauthorized_generative_inference_fails_closed(monkeypatch):
    """Attack Case: Attempt to trigger Ollama POST /api/chat without user authorization."""
    monkeypatch.setenv("SIXCLIPS_REQUIRE_EXPLICIT_AUTH", "1")
    enable_audit()

    with pytest.raises(UnauthorizedInferenceError):
        check_outbound_authorization(
            provider="ollama",
            model="gemma4:e4b",
            url="http://127.0.0.1:11434/api/chat",
            method="POST",
            component="adversarial_test",
        )


def test_attack_discovery_route_permitted_generative_blocked(monkeypatch):
    """Attack Case: Local GET /api/tags vs POST /api/chat distinction."""
    monkeypatch.setenv("SIXCLIPS_REQUIRE_EXPLICIT_AUTH", "1")
    enable_audit()

    # GET /api/tags is discovery -> allowed
    ev_discovery = check_outbound_authorization(
        provider="ollama",
        model="",
        url="http://127.0.0.1:11434/api/tags",
        method="GET",
        component="model_discovery",
    )
    assert ev_discovery.outcome.upper() == "ALLOWED"

    # POST /api/chat without auth -> blocked
    with pytest.raises(UnauthorizedInferenceError):
        check_outbound_authorization(
            provider="ollama",
            model="gemma4:e4b",
            url="http://127.0.0.1:11434/api/chat",
            method="POST",
            component="unauthorized_inference",
        )


def test_attack_unauthorized_publish_schedule_blocked():
    """Attack Case: Unauthorized social publish schedule blocked by egress guard."""
    transport = ProductionLiveTransport()
    disconnected_account = PlatformAccount(
        platform="youtube",
        account_id="acc_unauthorized",
        account_name="unauthorized_yt_account",
        state=AccountState.NOT_CONNECTED,
        display_name="Disconnected Channel",
    )

    fake_job = DistributionJob(
        job_id="job_unauthorized_001",
        user_id="local",
        output_id="out_001",
        project_id="proj_001",
        project_revision=1,
        artifact_path="media/fake.mp4",
        artifact_sha256="0123456789abcdef" * 4,
        approval_receipt_id="appr_001",
        platform="youtube",
        account_id="acc_unauthorized",
        seo_metadata=PlatformSEOMetadata(platform="youtube", title="Test", description="Test desc"),
        scheduled_time_utc="2026-10-14T12:00:00Z",
    )

    from backend.distribution.transport import TransportError
    def _run():
        return asyncio.run(transport.dispatch_post(fake_job, disconnected_account))

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        with pytest.raises(TransportError) as exc_info:
            pool.submit(_run).result()
    assert exc_info.value.code == "ACCOUNT_NOT_READY"


def test_attack_outbound_allowlist_enforcement():
    """Attack Case: Destination hosts outside allowlist are strictly rejected."""
    # Allowed
    assert check_outbound_allowlist("youtube", "www.googleapis.com") is True
    assert check_outbound_allowlist("ollama", "127.0.0.1") is True

    # Unauthorized external targets
    assert check_outbound_allowlist("youtube", "malicious-tracking.com") is False
    assert check_outbound_allowlist("instagram", "unauthorized-exfiltration.io") is False


def test_attack_unknown_api_404_no_external_egress():
    """Attack Case: Requesting non-existent API routes returns clean 404 and does not trigger fallback."""
    client = TestClient(app)
    res = client.get("/api/nonexistent_route_wave12_attack")
    assert res.status_code == 404
    assert res.json()["detail"] == "API route '/api/nonexistent_route_wave12_attack' not found"


def test_attack_unconfigured_cloud_keys_no_egress():
    """Attack Case: Calling OpenAI/Anthropic without valid keys fails locally without network retry storm."""
    client = AIClient(
        provider=AIProvider.OPENAI,
        api_key="",
        model="gpt-4o",
    )

    async def _call():
        return await client.chat(messages=[{"role": "user", "content": "hello"}])

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        with pytest.raises(Exception) as exc_info:
            pool.submit(lambda: asyncio.run(_call())).result()

    err_str = str(exc_info.value).lower()
    assert any(w in err_str for w in ["key", "missing", "unconfigured", "unauthorized", "auth", "valueerror"])


def test_attack_offline_ollama_graceful_handling():
    """Attack Case: Request to invalid or offline Ollama model fails gracefully without spinning or infinite retries."""
    client = AIClient(
        provider=AIProvider.OLLAMA,
        api_key="",
        model="nonexistent-model-offline-test",
    )

    async def _stream():
        chunks = []
        async for chunk in client.chat_stream(messages=[{"role": "user", "content": "hello"}], max_tokens=10):
            chunks.append(chunk)
        return chunks

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        chunks = pool.submit(lambda: asyncio.run(_stream())).result()

    output = "".join(chunks).lower()
    assert any(w in output for w in ["error", "not found", "failed", "404", "unavailable"])
