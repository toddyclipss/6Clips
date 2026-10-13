# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Mocked Transport Contract Tests for 6Clips Cloud Providers.

Validates exact serialized outgoing HTTP requests across Low, Medium, Hard
for all requested OpenAI, Anthropic, OpenRouter, and Google Gemini models.
Captures URL, headers, and request body without consuming paid cloud API keys.
"""
import asyncio
import json
import pytest
import httpx
import httpx2
from unittest.mock import patch, MagicMock

import openai
import anthropic
from google import genai
from google.genai import types

from backend.core.ai_provider import (
    AIProvider,
    AIClient,
    map_reasoning_effort,
)

_REAL_ASYNC_OPENAI = openai.AsyncOpenAI
_REAL_ASYNC_ANTHROPIC = anthropic.AsyncAnthropic

OPENAI_MODELS = ["gpt-6-astra", "gpt-6.1-sol", "gpt-6-luna"]
ANTHROPIC_MODELS = ["claude-fable-5-1", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"]
OPENROUTER_MODELS = [
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
GEMINI_MODELS = ["gemini-3.8-flash", "gemini-3.1-pro-preview"]
LEVELS = [("low", "low"), ("medium", "medium"), ("high", "high"), ("hard", "high")]


# ── 1. OpenAI Responses API Contract Tests ────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("model", OPENAI_MODELS)
@pytest.mark.parametrize("ui_level, native_effort", LEVELS)
async def test_openai_responses_api_serialized_request(model, ui_level, native_effort):
    captured_requests = []

    def handler(request: httpx.Request):
        captured_requests.append({
            "url": str(request.url),
            "method": request.method,
            "headers": dict(request.headers),
            "body": json.loads(request.content.decode("utf-8")),
        })
        sse_data = (
            "event: response.output_item.added\ndata: {\"type\": \"response.output_item.added\", \"item\": {\"type\": \"message\", \"role\": \"assistant\"}}\n\n"
            "event: response.output_text.delta\ndata: {\"type\": \"response.output_text.delta\", \"delta\": \"Verified OK\"}\n\n"
            "event: response.completed\ndata: {\"type\": \"response.completed\"}\n\n"
        )
        return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, content=sse_data.encode("utf-8"))

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)

    with patch("openai.AsyncOpenAI", side_effect=lambda **kwargs: _REAL_ASYNC_OPENAI(api_key="sk-test-key", http_client=http_client)):
        client = AIClient(provider=AIProvider.OPENAI, api_key="sk-test-key", model=model)
        chunks = [c async for c in client.chat_stream([{"role": "user", "content": "Ping"}], reasoning_level=ui_level)]

    assert chunks == ["Verified OK"]
    assert len(captured_requests) == 1
    req = captured_requests[0]
    assert req["url"] == "https://api.openai.com/v1/responses"
    assert req["method"] == "POST"
    assert req["headers"]["authorization"] == "Bearer sk-test-key"
    assert req["body"]["model"] == model
    assert req["body"]["reasoning"] == {"effort": native_effort}
    assert req["body"]["stream"] is True
    assert req["body"]["input"] == [{"role": "user", "content": "Ping"}]


# ── 2. Anthropic Messages API Contract Tests ──────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("model", ANTHROPIC_MODELS)
@pytest.mark.parametrize("ui_level, native_effort", LEVELS)
async def test_anthropic_messages_api_serialized_request(model, ui_level, native_effort):
    captured_requests = []

    def handler(request: httpx2.Request):
        captured_requests.append({
            "url": str(request.url),
            "method": request.method,
            "headers": dict(request.headers),
            "body": json.loads(request.content.decode("utf-8")),
        })
        sse_data = (
            "event: message_start\ndata: {\"type\": \"message_start\", \"message\": {\"id\": \"msg_1\", \"type\": \"message\", \"role\": \"assistant\", \"content\": [], \"model\": \"claude\", \"stop_reason\": null, \"stop_sequence\": null, \"usage\": {\"input_tokens\": 5, \"output_tokens\": 5}}}\n\n"
            "event: content_block_start\ndata: {\"type\": \"content_block_start\", \"index\": 0, \"content_block\": {\"type\": \"text\", \"text\": \"\"}}\n\n"
            "event: content_block_delta\ndata: {\"type\": \"content_block_delta\", \"index\": 0, \"delta\": {\"type\": \"text_delta\", \"text\": \"Anthropic OK\"}}\n\n"
            "event: content_block_stop\ndata: {\"type\": \"content_block_stop\", \"index\": 0}\n\n"
            "event: message_delta\ndata: {\"type\": \"message_delta\", \"delta\": {\"stop_reason\": \"end_turn\", \"stop_sequence\": null}, \"usage\": {\"output_tokens\": 10}}\n\n"
            "event: message_stop\ndata: {\"type\": \"message_stop\"}\n\n"
        )
        return httpx2.Response(200, headers={"Content-Type": "text/event-stream"}, content=sse_data.encode("utf-8"))

    transport = httpx2.MockTransport(handler)
    http_client = httpx2.AsyncClient(transport=transport)

    with patch("anthropic.AsyncAnthropic", side_effect=lambda **kwargs: _REAL_ASYNC_ANTHROPIC(api_key="sk-ant-test", http_client=http_client)):
        client = AIClient(provider=AIProvider.ANTHROPIC, api_key="sk-ant-test", model=model)
        chunks = [c async for c in client.chat_stream([{"role": "user", "content": "Ping"}], reasoning_level=ui_level)]

    assert "".join(chunks) == "Anthropic OK"
    assert len(captured_requests) == 1
    req = captured_requests[0]
    assert req["url"] == "https://api.anthropic.com/v1/messages"
    assert req["method"] == "POST"
    assert req["headers"]["x-api-key"] == "sk-ant-test"
    assert req["body"]["model"] == model
    assert req["body"]["output_config"] == {"effort": native_effort}
    assert "thinking" not in req["body"]


# ── 3. OpenRouter Reasonings and Routing Contract Tests ───────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("model", OPENROUTER_MODELS)
@pytest.mark.parametrize("ui_level, native_effort", LEVELS)
async def test_openrouter_routing_serialized_request(model, ui_level, native_effort):
    captured_requests = []

    def handler(request: httpx.Request):
        captured_requests.append({
            "url": str(request.url),
            "method": request.method,
            "headers": dict(request.headers),
            "body": json.loads(request.content.decode("utf-8")),
        })
        sse_data = (
            "data: {\"choices\": [{\"delta\": {\"content\": \"OpenRouter OK\"}}]}\n\n"
            "data: [DONE]\n\n"
        )
        return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, content=sse_data.encode("utf-8"))

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)

    with patch("openai.AsyncOpenAI", side_effect=lambda **kwargs: _REAL_ASYNC_OPENAI(
        api_key="sk-or-key",
        base_url="https://openrouter.ai/api/v1",
        default_headers={"HTTP-Referer": "https://6clips.app", "X-Title": "6Clips"},
        http_client=http_client,
    )):
        client = AIClient(provider=AIProvider.OPENROUTER, api_key="sk-or-key", model=model)
        chunks = [c async for c in client.chat_stream([{"role": "user", "content": "Ping"}], reasoning_level=ui_level)]

    assert "".join(chunks) == "OpenRouter OK"
    assert len(captured_requests) == 1
    req = captured_requests[0]
    assert req["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert req["method"] == "POST"
    assert req["headers"]["authorization"] == "Bearer sk-or-key"
    assert req["body"]["model"] == model
    assert req["body"]["reasoning"] == {"effort": native_effort}
    assert req["body"]["provider"] == {"require_parameters": True, "allow_fallbacks": False}


# ── 4. Google Gemini Thinking Level Contract Tests ────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("model", GEMINI_MODELS)
@pytest.mark.parametrize("ui_level, native_effort", LEVELS)
async def test_gemini_thinking_level_configuration(model, ui_level, native_effort):
    captured_config = {}

    class FakeChunk:
        def __init__(self, text):
            self.text = text

    class FakeAsyncIterable:
        def __aiter__(self):
            return self._gen()
        async def _gen(self):
            yield FakeChunk("Gemini OK")

    class FakeAsyncModels:
        async def generate_content_stream(self, model, contents, config=None):
            captured_config["model"] = model
            captured_config["config"] = config
            return FakeAsyncIterable()

    mock_client = MagicMock()
    mock_client.aio.models = FakeAsyncModels()

    with patch("google.genai.Client", return_value=mock_client):
        client = AIClient(provider=AIProvider.GEMINI, api_key="test-gemini-key", model=model)
        chunks = [c async for c in client.chat_stream([{"role": "user", "content": "Ping"}], reasoning_level=ui_level)]

    assert "".join(chunks) == "Gemini OK"
    assert captured_config["model"] == model
    tc = captured_config["config"].thinking_config
    assert tc is not None
    expected_enum = getattr(types.ThinkingLevel, native_effort.upper())
    assert tc.thinking_level == expected_enum
