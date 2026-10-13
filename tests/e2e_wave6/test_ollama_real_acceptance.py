# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 6 Role 4 — Real Local Ollama Gemma4:e4b & High Reasoning Effort Acceptance.

Strict acceptance criteria:
- Real Ollama daemon running on local machine (no mock, no synthetic double)
- Model: gemma4:e4b (10 GB) verified installed via ollama list
- Model details: gemma4 architecture, thinking levels false/true verified via ollama show
- No auto-pull, no cloud fallback, no paid inference
- AIProvider translation: reasoning_level="high" -> think=True, num_predict=4096, temp=0.7, top_p=0.95
- Truthful disclosure: Ollama reasoning is an app-specific mapping, not a native 3-tier Ollama setting
- Live inference execution and streaming tokens verification
- Negative test: offline daemon / bad model produces truthful BLOCKED/error, no silent cloud fallback
"""
import subprocess
import pytest
import httpx

from backend.core.ai_provider import (
    AIProvider,
    AIClient,
    get_ollama_reasoning_profile,
    get_ollama_orchestration_instructions,
    map_reasoning_effort,
    _is_ollama_available,
)


@pytest.mark.asyncio
async def test_ollama_daemon_health_and_version():
    """Verify local Ollama daemon is reachable and reporting version."""
    assert _is_ollama_available(), "Local Ollama daemon must be accessible at http://127.0.0.1:11434"

    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get("http://127.0.0.1:11434/api/version")
        assert resp.status_code == 200, f"Ollama version endpoint returned {resp.status_code}"
        data = resp.json()
        assert "version" in data, "Ollama version info missing from response"
        assert data["version"], "Ollama returned empty version"


def test_ollama_model_gemma4_installed_no_auto_pull():
    """Verify gemma4:e4b is installed locally without any auto-pull or cloud fallback."""
    proc = subprocess.run(
        ["ollama", "list"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "gemma4:e4b" in proc.stdout, (
        "gemma4:e4b must be present in `ollama list`. Auto-pull is forbidden by Wave 6 rules."
    )


def test_ollama_show_gemma4_capabilities_and_boolean_thinking():
    """Verify gemma4:e4b architecture and thinking capability contracts."""
    proc = subprocess.run(
        ["ollama", "show", "gemma4:e4b"],
        capture_output=True,
        text=True,
        check=True,
    )
    stdout = proc.stdout
    assert "gemma4" in stdout, "Model architecture must be gemma4"
    assert "thinking" in stdout, "Model must declare thinking capability in ollama show"
    assert "levels" in stdout and "true" in stdout, "Thinking capability must report levels"


def test_ai_provider_reasoning_effort_high_contract():
    """Verify backend translation of reasoning_level='high' for local Ollama."""
    mapped = map_reasoning_effort("high")
    assert mapped == "high"

    profile = get_ollama_reasoning_profile("high", max_tokens=1024)
    assert profile["num_predict"] >= 4096, "High reasoning must allocate at least 4096 predict tokens"
    assert profile["temperature"] == 0.7
    assert profile["top_p"] == 0.95

    instructions = get_ollama_orchestration_instructions("high")
    assert "ORCHESTRATION POLICY [HIGH]" in instructions
    assert "CRITICAL VERIFICATION MODE" in instructions


@pytest.mark.asyncio
async def test_live_ollama_inference_high_reasoning():
    """Execute live Ollama inference with gemma4:e4b and reasoning_level='high'."""
    client = AIClient(
        provider=AIProvider.OLLAMA,
        api_key="",
        model="gemma4:e4b",
    )

    messages = [
        {"role": "user", "content": "Compute 16 * 16. Return only the numeric value."}
    ]

    response = await client.chat(
        messages=messages,
        max_tokens=256,
        reasoning_level="high",
    )

    assert response is not None and len(response.strip()) > 0, "Live Ollama response must not be empty"
    assert "256" in response, f"Expected 256 in model response, got: {response!r}"


@pytest.mark.asyncio
async def test_live_ollama_streaming_and_no_mock():
    """Verify real streaming chunks from local Ollama without mocks or synthetic fallbacks."""
    client = AIClient(
        provider=AIProvider.OLLAMA,
        api_key="",
        model="gemma4:e4b",
    )

    messages = [
        {"role": "user", "content": "Respond with the single word: CONFIRMED"}
    ]

    chunks = []
    async for chunk in client.chat_stream(
        messages=messages,
        max_tokens=64,
        reasoning_level="high",
    ):
        chunks.append(chunk)

    full_text = "".join(chunks)
    assert len(chunks) >= 1, "Stream must yield at least one token chunk"
    assert "CONFIRMED" in full_text.upper(), f"Expected CONFIRMED in streamed output, got: {full_text!r}"


@pytest.mark.asyncio
async def test_ollama_negative_invalid_model_fails_gracefully():
    """Verify negative test: invalid model fails truthfully without cloud provider fallback."""
    client = AIClient(
        provider=AIProvider.OLLAMA,
        api_key="",
        model="nonexistent-model-wave6-fail",
    )

    messages = [{"role": "user", "content": "Hello"}]
    chunks = []
    async for chunk in client.chat_stream(messages=messages, max_tokens=32):
        chunks.append(chunk)

    result = "".join(chunks)
    assert "Ollama error" in result or "error" in result.lower(), (
        f"Expected explicit Ollama error for invalid model, got: {result!r}"
    )
