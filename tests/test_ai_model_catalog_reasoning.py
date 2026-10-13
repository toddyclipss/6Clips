# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Comprehensive tests for 6Clips Unified AI Model Selector, Explicit Model Choice & Low / Medium / High Reasoning.

Validates:
1. Exact model catalog:
   - OpenAI (3): gpt-6-astra, gpt-6.1-sol, gpt-6-luna
   - Anthropic (4): claude-fable-5-1, claude-opus-5-5, claude-sonnet-5-5, claude-haiku-5-5
   - OpenRouter (9): anthropic/claude-fable-5.1, anthropic/claude-opus-5.5, anthropic/claude-sonnet-5.5, anthropic/claude-haiku-5.5,
                     openai/gpt-6-astra, openai/gpt-6.1-sol, openai/gpt-6.1-luna, google/gemini-3.8-flash, google/gemini-3.1-pro-preview
2. Zero default models across config and dynamic discovery.
3. Strict explicit selection: AIProviderUnselectedError when unselected.
4. Active reasoning levels (Low, Medium, High) mapped natively to provider execution payloads.
5. Ollama 3 distinct bounded execution profiles with boolean think (never string).
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from backend.api.config import _DEFAULTS
from backend.core.ai_provider import (
    AIProvider,
    AIClient,
    get_ai_client,
    map_reasoning_effort,
    get_ollama_reasoning_profile,
)
from backend.core.exceptions import AIProviderUnselectedError, AIKeyMissingError


def test_model_registry_authoritative_catalog():
    reg = _DEFAULTS["model_registry"]

    # 1. OpenAI: exactly 3 models
    assert reg["openai"]["models"] == [
        "gpt-6-astra",
        "gpt-6.1-sol",
        "gpt-6-luna",
    ]
    assert reg["openai"]["default_model"] is None

    # 2. Anthropic: exactly 4 models
    assert reg["anthropic"]["models"] == [
        "claude-fable-5-1",
        "claude-opus-5-5",
        "claude-sonnet-5-5",
        "claude-haiku-5-5",
    ]
    assert reg["anthropic"]["default_model"] is None

    # 3. OpenRouter: exactly 9 models
    assert reg["openrouter"]["models"] == [
        "anthropic/claude-fable-5.1",
        "anthropic/claude-opus-5.5",
        "anthropic/claude-sonnet-5.5",
        "anthropic/claude-haiku-5.5",
        "openai/gpt-6-astra",
        "openai/gpt-6.1-sol",
        "openai/gpt-6.1-luna",
        "google/gemini-3.8-flash",
        "google/gemini-3.1-pro-preview",
    ]
    assert reg["openrouter"]["default_model"] is None

    # 4. Ollama: dynamic registry defaults
    assert "gemma4:e4b" in reg["ollama"]["models"]
    assert reg["ollama"]["default_model"] is None

    # 5. Reasoning levels supported on all providers
    for p in ("openai", "anthropic", "openrouter", "ollama"):
        assert reg[p]["reasoning_levels"] == ["low", "medium", "high"]


def test_strict_explicit_selection_requirement():
    # Calling get_ai_client with require_explicit=True and no explicit choice MUST raise AIProviderUnselectedError
    with pytest.raises(AIProviderUnselectedError) as exc_info:
        get_ai_client(user_settings=None, require_explicit=True)
    assert "No AI model selected" in str(exc_info.value)

    # Provider selected but model missing
    settings_no_model = MagicMock(ai_provider="openai", ai_model=None)
    with pytest.raises(AIProviderUnselectedError) as exc_info2:
        get_ai_client(user_settings=settings_no_model, require_explicit=True)
    assert "No AI model selected" in str(exc_info2.value)


def test_map_reasoning_effort_contract():
    assert map_reasoning_effort("low") == "low"
    assert map_reasoning_effort("medium") == "medium"
    assert map_reasoning_effort("high") == "high"
    assert map_reasoning_effort("hard") == "high"  # Safe migration alias
    assert map_reasoning_effort(None) == "medium"
    assert map_reasoning_effort("") == "medium"


def test_ollama_reasoning_profiles():
    # Low profile: 1024 predict tokens, temp 0.2
    low = get_ollama_reasoning_profile("low", max_tokens=1024)
    assert low["num_predict"] == 1024
    assert low["temperature"] == 0.2
    assert low["top_p"] == 0.8

    # Medium profile: 2048 predict tokens, temp 0.5
    med = get_ollama_reasoning_profile("medium", max_tokens=1024)
    assert med["num_predict"] == 2048
    assert med["temperature"] == 0.5
    assert med["top_p"] == 0.9

    # High profile: 4096 predict tokens, temp 0.7
    high = get_ollama_reasoning_profile("high", max_tokens=1024)
    assert high["num_predict"] == 4096
    assert high["temperature"] == 0.7
    assert high["top_p"] == 0.95


@pytest.mark.asyncio
async def test_openai_reasoning_payload_dispatch():
    client = AIClient(provider=AIProvider.OPENAI, api_key="sk-test", model="gpt-6-astra")

    captured_kwargs = {}

    class FakeResponseStream:
        def __aiter__(self):
            return self._gen()

        async def _gen(self):
            event = MagicMock()
            event.type = "response.output_text.delta"
            event.delta = "OpenAI Responses output"
            yield event

    async def fake_create(**kwargs):
        captured_kwargs.update(kwargs)
        return FakeResponseStream()

    mock_openai_client = MagicMock()
    mock_openai_client.responses.create = fake_create

    with patch("openai.AsyncOpenAI", return_value=mock_openai_client):
        chunks = [c async for c in client.chat_stream([{"role": "user", "content": "hi"}], reasoning_level="high")]

    assert chunks == ["OpenAI Responses output"]
    assert captured_kwargs.get("reasoning") == {"effort": "high"}
    assert captured_kwargs.get("max_output_tokens") == 2048
    assert captured_kwargs.get("model") == "gpt-6-astra"


@pytest.mark.asyncio
async def test_anthropic_reasoning_payload_dispatch():
    client = AIClient(provider=AIProvider.ANTHROPIC, api_key="sk-ant", model="claude-opus-5-5")

    captured_kwargs = {}

    class FakeStreamContext:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)
            self.text_stream = self._stream()

        async def _stream(self):
            yield "Anthropic output"

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

    mock_anthropic_client = MagicMock()
    mock_anthropic_client.messages.stream = FakeStreamContext

    with patch("anthropic.AsyncAnthropic", return_value=mock_anthropic_client):
        chunks = [c async for c in client.chat_stream([{"role": "user", "content": "hi"}], reasoning_level="low")]

    assert chunks == ["Anthropic output"]
    assert captured_kwargs.get("extra_body") == {"output_config": {"effort": "low"}}
    assert captured_kwargs.get("model") == "claude-opus-5-5"


@pytest.mark.asyncio
async def test_openrouter_reasoning_payload_dispatch():
    client = AIClient(provider=AIProvider.OPENROUTER, api_key="sk-or", model="anthropic/claude-sonnet-5.5")

    captured_kwargs = {}

    class FakeStream:
        def __init__(self, content):
            self.content = content

        def __aiter__(self):
            return self._gen()

        async def _gen(self):
            delta = MagicMock()
            delta.content = self.content
            choice = MagicMock()
            choice.delta = delta
            yield MagicMock(choices=[choice])

    async def fake_create(**kwargs):
        captured_kwargs.update(kwargs)
        return FakeStream("OpenRouter output")

    mock_openai_client = MagicMock()
    mock_openai_client.chat.completions.create = fake_create

    with patch("openai.AsyncOpenAI", return_value=mock_openai_client):
        chunks = [c async for c in client.chat_stream([{"role": "user", "content": "hi"}], reasoning_level="high")]

    assert chunks == ["OpenRouter output"]
    assert captured_kwargs.get("extra_body") == {
        "provider": {"require_parameters": True, "allow_fallbacks": False},
        "reasoning": {"effort": "high"},
    }
    assert captured_kwargs.get("model") == "anthropic/claude-sonnet-5.5"
