import pytest
import json
import base64
import httpx
from unittest.mock import patch

from backend.core.ai_provider import (
    AIProvider,
    AIClient,
    map_reasoning_effort,
    is_model_compatible_with_provider,
    get_ai_client,
)
from backend.core.exceptions import AIKeyMissingError
from backend.config import settings
from google import genai


def create_mocked_genai_client(api_key: str, mock_async_client: httpx.AsyncClient):
    """Instantiate a real google.genai Client with mocked httpx transport before patching."""
    client = genai.Client(api_key=api_key)
    client._api_client._use_aiohttp = lambda: False
    client._api_client._async_httpx_client = mock_async_client
    return client


@pytest.mark.asyncio
async def test_gemini_native_endpoint_and_auth_for_flash_and_pro():
    """Verify exact Google native endpoints, authentication header, and model IDs for both models."""
    models_to_test = ["gemini-3.8-flash", "gemini-3.1-pro-preview"]

    for model_id in models_to_test:
        captured_requests = []

        def handler(request: httpx.Request):
            captured_requests.append({
                "url": str(request.url),
                "method": request.method,
                "headers": dict(request.headers),
                "payload": json.loads(request.content.decode("utf-8")),
            })
            resp_body = {
                "candidates": [{
                    "content": {
                        "role": "model",
                        "parts": [{"text": f"Response from {model_id}"}],
                    }
                }]
            }
            sse_lines = f"data: {json.dumps(resp_body)}\r\n\r\n"
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=sse_lines)

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

        ai = AIClient(
            provider=AIProvider.GEMINI,
            api_key="direct-google-secret-key-12345",
            model=model_id,
        )

        real_genai_client = create_mocked_genai_client("direct-google-secret-key-12345", mock_client)
        with patch("google.genai.Client", return_value=real_genai_client):
            res = await ai.chat(
                messages=[{"role": "user", "content": "Hello Gemini"}],
                reasoning_level="low",
            )

            assert res == f"Response from {model_id}"
            assert len(captured_requests) == 1
            req = captured_requests[0]

            expected_endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:streamGenerateContent?alt=sse"
            assert req["url"] == expected_endpoint
            assert req["headers"]["x-goog-api-key"] == "direct-google-secret-key-12345"
            assert req["method"] == "POST"


@pytest.mark.asyncio
@pytest.mark.parametrize("level,expected_thinking_level", [
    ("low", "LOW"),
    ("medium", "MEDIUM"),
    ("high", "HIGH"),
])
async def test_gemini_native_thinking_level_mapping(level, expected_thinking_level):
    """Verify canonical reasoning levels low/medium/high map to native ThinkingLevel and include_thoughts."""
    captured_requests = []

    def handler(request: httpx.Request):
        captured_requests.append(json.loads(request.content.decode("utf-8")))
        resp_body = {
            "candidates": [{
                "content": {"role": "model", "parts": [{"text": "Answer"}]}
            }]
        }
        sse_lines = f"data: {json.dumps(resp_body)}\r\n\r\n"
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=sse_lines)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    ai = AIClient(
        provider=AIProvider.GEMINI,
        api_key="google-key",
        model="gemini-3.8-flash",
    )

    real_client = create_mocked_genai_client("google-key", mock_client)
    with patch("google.genai.Client", return_value=real_client):
        _ = await ai.chat(
            messages=[{"role": "user", "content": "Explain relativity"}],
            reasoning_level=level,
        )

        assert len(captured_requests) == 1
        gen_cfg = captured_requests[0].get("generationConfig", {})
        thinking_cfg = gen_cfg.get("thinkingConfig", {})

        assert thinking_cfg.get("thinking_level") == expected_thinking_level
        assert thinking_cfg.get("include_thoughts") is True


@pytest.mark.asyncio
async def test_gemini_native_streaming_and_error_handling():
    """Verify SSE streaming format and graceful API error handling."""
    captured_urls = []

    def stream_handler(request: httpx.Request):
        captured_urls.append(str(request.url))
        sse_lines = (
            f"data: {json.dumps({'candidates': [{'content': {'parts': [{'text': 'Stream '}]}}]})}\r\n\r\n"
            f"data: {json.dumps({'candidates': [{'content': {'parts': [{'text': 'verified!'}]}}]})}\r\n\r\n"
        )
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=sse_lines)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(stream_handler))
    ai = AIClient(provider=AIProvider.GEMINI, api_key="test-key", model="gemini-3.8-flash")

    real_client = create_mocked_genai_client("test-key", mock_client)
    with patch("google.genai.Client", return_value=real_client):
        tokens = []
        async for chunk in ai.chat_stream([{"role": "user", "content": "Ping"}]):
            tokens.append(chunk)

        assert "".join(tokens) == "Stream verified!"
        assert "streamGenerateContent?alt=sse" in captured_urls[0]

    # Test error handling on HTTP 403
    def error_handler(request: httpx.Request):
        return httpx.Response(403, json={"error": {"code": 403, "message": "API key expired"}})

    err_client = httpx.AsyncClient(transport=httpx.MockTransport(error_handler))
    err_genai_client = create_mocked_genai_client("test-key", err_client)
    with patch("google.genai.Client", return_value=err_genai_client):
        with pytest.raises(Exception) as exc_info:
            async for _ in ai.chat_stream([{"role": "user", "content": "Ping"}]):
                pass
        assert "403" in str(exc_info.value) or "API key expired" in str(exc_info.value)


@pytest.mark.asyncio
async def test_gemini_native_multiturn_tool_calling_and_thought_signature():
    """Verify function calling loop, tool result continuation, and thought signature preservation."""
    raw_thought_sig = b"crypto-signature-turn-1-hash"
    b64_sig = base64.b64encode(raw_thought_sig).decode("ascii")

    request_history = []

    def mock_server(request: httpx.Request):
        body = json.loads(request.content.decode("utf-8"))
        request_history.append(body)

        round_num = len(request_history)
        if round_num == 1:
            # First turn: Gemini emits a tool call with thought signature
            resp = {
                "candidates": [{
                    "content": {
                        "role": "model",
                        "parts": [
                            {
                                "thought": True,
                                "text": "I should call suggest_clips to recommend motion graphics.",
                            },
                            {
                                "thoughtSignature": b64_sig,
                                "functionCall": {
                                    "name": "suggest_clips",
                                    "args": {"limit": 2},
                                },
                            },
                        ],
                    }
                }]
            }
        else:
            # Second turn: Gemini emits the final response after seeing tool output
            resp = {
                "candidates": [{
                    "content": {
                        "role": "model",
                        "parts": [
                            {"text": "I found 2 clips ready for Motion Graphics."}
                        ],
                    }
                }]
            }
        return httpx.Response(200, json=resp)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_server))
    ai = AIClient(provider=AIProvider.GEMINI, api_key="google-key", model="gemini-3.8-flash")

    tools = [{
        "function": {
            "name": "suggest_clips",
            "description": "Suggest video clips",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer"}},
            },
        }
    }]

    async def fake_tool_executor(name, args):
        assert name == "suggest_clips"
        return {"clips": ["clip_001.mp4", "clip_002.mp4"]}

    real_client = create_mocked_genai_client("google-key", mock_client)
    with patch("google.genai.Client", return_value=real_client):
        with patch("backend.core.capabilities.CapabilityRegistry.get", return_value={"name": "suggest_clips"}):
            with patch("backend.core.capabilities.CapabilityRegistry.validate_input", return_value=True):
                result = await ai.chat_with_tools(
                    messages=[{"role": "user", "content": "Show clip suggestions"}],
                    tools=tools,
                    tool_executor=fake_tool_executor,
                    reasoning_level="high",
                )

    assert result["content"] == "I found 2 clips ready for Motion Graphics."
    assert len(result["tool_calls"]) == 1
    assert result["tool_calls"][0]["name"] == "suggest_clips"
    assert result["rounds"] == 2

    # Verify serialized HTTP requests sent to Google
    assert len(request_history) == 2

    # Request 1: Initial tool declaration and high thinking level
    req1 = request_history[0]
    assert req1["generationConfig"]["thinkingConfig"]["thinking_level"] == "HIGH"
    assert len(req1["tools"][0]["functionDeclarations"]) == 1
    assert req1["tools"][0]["functionDeclarations"][0]["name"] == "suggest_clips"

    # Request 2: Continuation with thought signature preserved in model turn
    req2 = request_history[1]
    contents2 = req2["contents"]
    assert len(contents2) == 3

    # Turn 0: User input
    assert contents2[0]["role"] == "user"
    assert contents2[0]["parts"][0]["text"] == "Show clip suggestions"

    # Turn 1: Model response containing preserved function call & thought signature
    assert contents2[1]["role"] == "model"
    model_parts = contents2[1]["parts"]
    fc_part = next(p for p in model_parts if "functionCall" in p)
    assert fc_part["functionCall"]["name"] == "suggest_clips"
    assert fc_part["thoughtSignature"] == b64_sig

    # Turn 2: User tool response containing functionResponse
    assert contents2[2]["role"] == "user"
    user_parts = contents2[2]["parts"]
    fr_part = next(p for p in user_parts if "functionResponse" in p)
    assert fr_part["functionResponse"]["name"] == "suggest_clips"
    assert "clip_001.mp4" in str(fr_part["functionResponse"]["response"])


def test_independent_credentials_and_no_unwanted_fallback():
    """Verify independent Google vs OpenRouter credentials and strict model rejection."""
    # 1. Structural compatibility: direct Gemini rejects OpenRouter vendor prefixes
    assert is_model_compatible_with_provider("gemini-3.8-flash", AIProvider.GEMINI) is True
    assert is_model_compatible_with_provider("gemini-3.1-pro-preview", AIProvider.GEMINI) is True
    assert is_model_compatible_with_provider("google/gemini-3.8-flash", AIProvider.GEMINI) is False
    assert is_model_compatible_with_provider("gpt-6-astra", AIProvider.GEMINI) is False

    # OpenRouter requires vendor slug
    assert is_model_compatible_with_provider("google/gemini-3.8-flash", AIProvider.OPENROUTER) is True
    assert is_model_compatible_with_provider("gemini-3.8-flash", AIProvider.OPENROUTER) is True

    # 2. No automatic fallback if unconfigured
    with patch.object(settings, "GEMINI_API_KEY", None):
        with patch.object(settings, "OPENROUTER_API_KEY", "openrouter-key"):
            # Requesting Gemini without Gemini key should NOT fall back to OpenRouter
            with pytest.raises(AIKeyMissingError):
                get_ai_client(pinned_provider="gemini")
