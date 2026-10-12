# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Comprehensive tests for native Ollama provider integration.

Validates:
- AIProvider.OLLAMA enum, defaults, compatibility, and sanitization
- Strict provider selection and rejection of silent cloud fallback
- Thinking toggle discovery, request propagation, and monologue suppression
- Native multi-turn tool call loop, CapabilityRegistry validation, and CAS enforcement
- Live inference and tool calling against local Ollama instance (gemma4:e4b)
- Database safety invariant (zero mutations to production viralmint.db)
"""
import pytest
import hashlib
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from backend.config import settings
from backend.core.ai_provider import (
    AIProvider,
    PROVIDER_DEFAULTS,
    AIClient,
    get_ai_client,
    is_model_compatible_with_provider,
    sanitize_model_for_provider,
    _is_ollama_available,
)
from backend.core.exceptions import AIKeyMissingError
from backend.core.capabilities import CapabilityRegistry


def _get_db_hash() -> str:
    db_path = Path("viralmint.db")
    if not db_path.exists():
        return ""
    h = hashlib.sha256()
    with open(db_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class TestOllamaProviderUnit:
    """Isolated unit tests for Ollama provider logic."""

    def test_provider_enum_and_defaults(self):
        assert AIProvider.OLLAMA == "ollama"
        assert AIProvider.OLLAMA in PROVIDER_DEFAULTS
        assert PROVIDER_DEFAULTS[AIProvider.OLLAMA] == "gemma4:e4b"

    def test_model_compatibility(self):
        # Ollama models
        assert is_model_compatible_with_provider("gemma4:e4b", AIProvider.OLLAMA) is True
        assert is_model_compatible_with_provider("llama3:8b", AIProvider.OLLAMA) is True
        assert is_model_compatible_with_provider("mistral:instruct", AIProvider.OLLAMA) is True

        # Incompatible proprietary models
        assert is_model_compatible_with_provider("gpt-5.4-mini", AIProvider.OLLAMA) is False
        assert is_model_compatible_with_provider("claude-sonnet-4-6", AIProvider.OLLAMA) is False
        assert is_model_compatible_with_provider("anthropic/claude-opus-4.7", AIProvider.OLLAMA) is False

    def test_model_sanitization(self):
        assert sanitize_model_for_provider("gemma4:e4b", AIProvider.OLLAMA) == "gemma4:e4b"
        assert sanitize_model_for_provider("gpt-5.4", AIProvider.OLLAMA) == "gemma4:e4b"
        assert sanitize_model_for_provider(None, AIProvider.OLLAMA) == "gemma4:e4b"

    def test_get_ai_client_pinned_ollama(self):
        client = get_ai_client(pinned_provider="ollama")
        assert client.provider == AIProvider.OLLAMA
        assert client.api_key == "ollama_local"
        assert client.model == "gemma4:e4b"

    def test_get_ai_client_user_settings_ollama(self):
        user_settings = MagicMock()
        user_settings.ai_provider = "ollama"
        user_settings.ai_api_key_encrypted = None
        user_settings.ai_model = "gemma4:e4b"

        client = get_ai_client(user_settings=user_settings)
        assert client.provider == AIProvider.OLLAMA
        assert client.api_key == "ollama_local"
        assert client.model == "gemma4:e4b"

    def test_strict_provider_fallback_semantics(self):
        """Explicitly selected cloud providers MUST NEVER silently fall back to Ollama."""
        # 1. Pinned OpenAI without keys
        with patch.object(settings, "OPENAI_API_KEY", None), \
             patch("backend.core.ai_provider._is_ollama_available", return_value=True):
            with pytest.raises(AIKeyMissingError) as exc_info:
                get_ai_client(pinned_provider="openai")
            assert "pinned provider 'openai'" in str(exc_info.value)

        # 2. Settings configured Anthropic without keys
        user_settings = MagicMock()
        user_settings.ai_provider = "anthropic"
        user_settings.ai_api_key_encrypted = None
        user_settings.ai_model = "claude-sonnet-4-6"

        with patch.object(settings, "ANTHROPIC_API_KEY", None), \
             patch("backend.core.ai_provider._is_ollama_available", return_value=True):
            with pytest.raises(AIKeyMissingError) as exc_info:
                get_ai_client(user_settings=user_settings)
            assert "anthropic" in str(exc_info.value).lower()

        # 3. Settings configured OpenRouter without keys
        user_settings.ai_provider = "openrouter"
        user_settings.ai_model = "anthropic/claude-opus-4.7"

        with patch.object(settings, "OPENROUTER_API_KEY", None), \
             patch("backend.core.ai_provider._is_ollama_available", return_value=True):
            with pytest.raises(AIKeyMissingError) as exc_info:
                get_ai_client(user_settings=user_settings)
            assert "openrouter" in str(exc_info.value).lower()

        # 4. Unpinned and unconfigured with no .env keys: DOES fall back to Ollama if available
        with patch.object(settings, "ANTHROPIC_API_KEY", None), \
             patch.object(settings, "OPENAI_API_KEY", None), \
             patch.object(settings, "OPENROUTER_API_KEY", None), \
             patch("backend.core.ai_provider._is_ollama_available", return_value=True):
            client = get_ai_client(user_settings=None)
            assert client.provider == AIProvider.OLLAMA
            assert client.api_key == "ollama_local"

    @pytest.mark.asyncio
    async def test_thinking_toggle_and_monologue_suppression(self):
        """Verifies thinking toggle payload, monologue suppression, and neutral status signal."""
        lines = [
            b'{"model":"gemma4:e4b","message":{"role":"assistant","content":"","thinking":"internal reasoning 1"},"done":false}\n',
            b'{"model":"gemma4:e4b","message":{"role":"assistant","content":"","thinking":"internal reasoning 2"},"done":false}\n',
            b'{"model":"gemma4:e4b","message":{"role":"assistant","content":"Final "},"done":false}\n',
            b'{"model":"gemma4:e4b","message":{"role":"assistant","content":"answer."},"done":false}\n',
            b'{"model":"gemma4:e4b","done":true}\n',
        ]

        captured_payload = {}

        class MockStreamResponse:
            status_code = 200

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def aiter_lines(self):
                for l in lines:
                    yield l.decode("utf-8")

        class MockAsyncClient:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            def stream(self, method, url, **kwargs):
                nonlocal captured_payload
                captured_payload = kwargs.get("json", {})
                return MockStreamResponse()

        statuses = []

        async def record_status(status_name):
            statuses.append(status_name)

        with patch("httpx.AsyncClient", MockAsyncClient):
            client = AIClient(provider=AIProvider.OLLAMA, api_key="ollama_local", model="gemma4:e4b")
            tokens = []
            async for t in client.chat_stream(
                [{"role": "user", "content": "test"}],
                think=True,
                on_status=record_status,
            ):
                tokens.append(t)

            # 1. Payload had think=True
            assert captured_payload.get("think") is True

            # 2. Internal reasoning tokens were completely suppressed from output
            full_text = "".join(tokens)
            assert full_text == "Final answer."
            assert "internal reasoning" not in full_text

            # 3. Neutral thinking status was signaled exactly once
            assert statuses == ["thinking"]

    @pytest.mark.asyncio
    async def test_native_tool_call_execution_loop(self):
        """Verifies multi-turn tool call round trip via chat_with_tools."""
        round1_resp = {
            "model": "gemma4:e4b",
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {
                            "name": "suggest_clips",
                            "arguments": {"video_id": "vid_abc", "max_clips": 3},
                        },
                    }
                ],
            },
            "done": True,
        }

        round2_resp = {
            "model": "gemma4:e4b",
            "message": {
                "role": "assistant",
                "content": "Found 3 clips for video vid_abc.",
            },
            "done": True,
        }

        call_count = 0

        class MockPostResponse:
            status_code = 200

            def __init__(self, data):
                self._data = data

            def json(self):
                return self._data

        class MockAsyncClient:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def post(self, url, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return MockPostResponse(round1_resp)
                return MockPostResponse(round2_resp)

        executed_tools = []

        def mock_executor(name, args):
            executed_tools.append((name, args))
            return {"clips": [{"start": 0, "end": 15}, {"start": 20, "end": 35}]}

        tools_schema = [
            {
                "type": "function",
                "function": {
                    "name": "suggest_clips",
                    "description": "Analyze source video and propose clips",
                    "parameters": {
                        "type": "object",
                        "properties": {"video_id": {"type": "string"}},
                        "required": ["video_id"],
                    },
                },
            }
        ]

        with patch("httpx.AsyncClient", MockAsyncClient):
            client = AIClient(provider=AIProvider.OLLAMA, api_key="ollama_local", model="gemma4:e4b")
            result = await client.chat_with_tools(
                messages=[{"role": "user", "content": "Suggest clips for vid_abc"}],
                tools=tools_schema,
                tool_executor=mock_executor,
            )

            assert result["content"] == "Found 3 clips for video vid_abc."
            assert len(result["tool_calls"]) == 1
            assert result["tool_calls"][0]["name"] == "suggest_clips"
            assert result["rounds"] == 2
            assert executed_tools == [("suggest_clips", {"video_id": "vid_abc", "max_clips": 3})]

    @pytest.mark.asyncio
    async def test_unauthorized_and_invalid_tool_rejection(self):
        """Verifies rejection of unknown tools or tools missing required parameters."""
        round1_resp = {
            "model": "gemma4:e4b",
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_bad",
                        "function": {
                            "name": "unauthorized_admin_drop",
                            "arguments": {"target": "all"},
                        },
                    },
                    {
                        "id": "call_missing",
                        "function": {
                            "name": "apply_captions",
                            "arguments": {},  # missing required 'video_id'
                        },
                    },
                ],
            },
            "done": True,
        }

        round2_resp = {
            "model": "gemma4:e4b",
            "message": {
                "role": "assistant",
                "content": "Encountered permission and parameter errors.",
            },
            "done": True,
        }

        call_count = 0

        class MockPostResponse:
            status_code = 200

            def __init__(self, data):
                self._data = data

            def json(self):
                return self._data

        class MockAsyncClient:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def post(self, url, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return MockPostResponse(round1_resp)
                return MockPostResponse(round2_resp)

        with patch("httpx.AsyncClient", MockAsyncClient):
            client = AIClient(provider=AIProvider.OLLAMA, api_key="ollama_local", model="gemma4:e4b")
            result = await client.chat_with_tools(
                messages=[{"role": "user", "content": "Execute bad tools"}],
                tools=[],
            )

            assert len(result["tool_calls"]) == 2
            # 1. Unauthorized capability rejected
            assert "Unauthorized or unknown capability" in result["tool_calls"][0]["result"]["error"]
            # 2. Missing required params rejected
            assert "missing required parameters" in result["tool_calls"][1]["result"]["error"]

    @pytest.mark.asyncio
    async def test_project_operation_cas_enforcement(self):
        """Verifies project_operation tool enforces expected_revision."""
        round1_resp = {
            "model": "gemma4:e4b",
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_op",
                        "function": {
                            "name": "project_operation",
                            "arguments": {
                                "project_id": "proj_123",
                                "expected_revision": 5,
                                "operation_type": "insert_track",
                                "payload": {"track_type": "audio"},
                            },
                        },
                    }
                ],
            },
            "done": True,
        }

        round2_resp = {
            "model": "gemma4:e4b",
            "message": {
                "role": "assistant",
                "content": "Operation applied at revision 6.",
            },
            "done": True,
        }

        call_count = 0

        class MockPostResponse:
            status_code = 200

            def __init__(self, data):
                self._data = data

            def json(self):
                return self._data

        class MockAsyncClient:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def post(self, url, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return MockPostResponse(round1_resp)
                return MockPostResponse(round2_resp)

        def cas_executor(name, args):
            if args.get("expected_revision") != 5:
                raise ValueError("CAS Conflict: Revision mismatch!")
            return {"project_id": "proj_123", "new_revision": 6, "status": "committed"}

        with patch("httpx.AsyncClient", MockAsyncClient):
            client = AIClient(provider=AIProvider.OLLAMA, api_key="ollama_local", model="gemma4:e4b")
            result = await client.chat_with_tools(
                messages=[{"role": "user", "content": "Add audio track"}],
                tools=[],
                tool_executor=cas_executor,
            )

            assert len(result["tool_calls"]) == 1
            assert result["tool_calls"][0]["result"]["new_revision"] == 6


class TestOllamaProviderLive:
    """Live integration tests against local Ollama instance (skipped if daemon offline)."""

    @pytest.fixture(autouse=True)
    def check_daemon(self):
        if not _is_ollama_available():
            pytest.skip("Local Ollama daemon is not running")

    @pytest.mark.asyncio
    async def test_live_ollama_chat_completion(self):
        db_before = _get_db_hash()
        client = get_ai_client(pinned_provider=AIProvider.OLLAMA)
        response = await client.chat(
            [{"role": "user", "content": "Say hello in two words"}],
            max_tokens=512,
        )
        assert len(response.strip()) > 0
        db_after = _get_db_hash()
        assert db_before == db_after, "viralmint.db was mutated during test!"

    @pytest.mark.asyncio
    async def test_live_ollama_thinking_on_and_off(self):
        """Verifies live inference with think=True and think=False against local daemon."""
        db_before = _get_db_hash()
        client = get_ai_client(pinned_provider=AIProvider.OLLAMA)

        # 1. With think=False
        resp_off = await client.chat(
            [{"role": "user", "content": "What is 1+1? Answer with digit only."}],
            max_tokens=20,
            think=False,
        )
        assert "2" in resp_off

        # 2. With think=True
        resp_on = await client.chat(
            [{"role": "user", "content": "What is 2+2? Answer with digit only."}],
            max_tokens=50,
            think=True,
        )
        assert "4" in resp_on

        db_after = _get_db_hash()
        assert db_before == db_after, "viralmint.db was mutated during test!"

    @pytest.mark.asyncio
    async def test_live_ollama_native_tool_calling(self):
        """Verifies real multi-turn native tool calling against local gemma4:e4b model."""
        db_before = _get_db_hash()
        client = get_ai_client(pinned_provider=AIProvider.OLLAMA)

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "suggest_clips",
                    "description": "Suggest video clips for editing",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "video_id": {"type": "string", "description": "The video identifier"},
                        },
                        "required": ["video_id"],
                    },
                },
            }
        ]

        def live_tool_executor(name, args):
            return {"video_id": args.get("video_id"), "found_clips": 3, "best_score": 9.2}

        result = await client.chat_with_tools(
            messages=[{"role": "user", "content": "Call the suggest_clips tool for video_id 'vid-sample-123'"}],
            tools=tools,
            tool_executor=live_tool_executor,
            max_tokens=300,
        )

        assert len(result["tool_calls"]) >= 1
        assert result["tool_calls"][0]["name"] == "suggest_clips"
        assert len(result["content"].strip()) > 0

        db_after = _get_db_hash()
        assert db_before == db_after, "viralmint.db was mutated during test!"

    @pytest.mark.asyncio
    async def test_live_planner_agent_search_catalog_tool_calling(self):
        """Verifies end-to-end PlannerAgent.handle_message with live local gemma4:e4b calling search_catalog."""
        db_before = _get_db_hash()
        from backend.agents.planner import PlannerAgent
        from unittest.mock import patch, AsyncMock

        planner = PlannerAgent()
        ws_messages = []

        async def mock_ws_send(payload, user_id):
            ws_messages.append(payload)

        common_ctx = {
            "ctx": {}, "suggestions": [], "cred_status": {},
            "user_profile": {}, "failures_text": "None", "perf_insights": {},
            "news_ctx": {}, "pipeline": {}
        }

        with patch("backend.core.ws_manager.ws_manager.send", side_effect=mock_ws_send), \
             patch.object(planner, "_gather_common_context", new=AsyncMock(return_value=common_ctx)), \
             patch("backend.core.user_intelligence.UserIntelligence.record_event", new=AsyncMock()):
            # Send message asking to find lower third motion blocks
            response = await planner.handle_message(
                message="Please search the catalog for lower third blocks",
                history=[],
                user_settings=None,
                user_id="test_user",
                pinned_provider="ollama",
                pinned_model="gemma4:e4b",
                pinned_think=False,
            )

            # Assert response exists and contains synthesis
            assert len(response.strip()) > 0

            # Verify that capability_executed event was emitted over WebSocket
            cap_events = [m for m in ws_messages if m.get("type") == "capability_executed"]
            assert len(cap_events) >= 1
            assert cap_events[0]["capability"] == "search_catalog"
            assert cap_events[0]["status"] == "success"
            assert "items" in cap_events[0]["output"]

            # Verify chat_done was emitted
            done_events = [m for m in ws_messages if m.get("type") == "chat_done"]
            assert len(done_events) == 1

        db_after = _get_db_hash()
        assert db_before == db_after, "viralmint.db was mutated during test!"


class TestPlannerToolBridgeUnit:
    """Unit tests for PlannerAgent tool execution bridge and CapabilityRegistry conversion."""

    def test_capability_registry_to_tool_definitions(self):
        from backend.core.capabilities import CapabilityRegistry
        defs = CapabilityRegistry.to_tool_definitions()
        assert len(defs) > 0
        names = [d["function"]["name"] for d in defs]
        assert "search_catalog" in names
        assert "project_operation" in names
        assert "suggest_clips" in names

        # Validate search_catalog parameters schema
        sc = next(d for d in defs if d["function"]["name"] == "search_catalog")
        assert "query" in sc["function"]["parameters"]["properties"]

    @pytest.mark.asyncio
    async def test_planner_tool_executor_project_operation_cas(self):
        """Verifies that project_operation tool rejects stale expected_revision."""
        db_before = _get_db_hash()
        from backend.agents.planner import PlannerAgent
        from unittest.mock import patch, AsyncMock

        round1_resp = {
            "model": "gemma4:e4b",
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_cas",
                        "function": {
                            "name": "project_operation",
                            "arguments": {
                                "project_id": "test_proj_1",
                                "expected_revision": 999,
                                "operation_type": "insert_track",
                                "payload": {},
                            },
                        },
                    }
                ],
            },
            "done": True,
        }
        round2_resp = {
            "model": "gemma4:e4b",
            "message": {
                "role": "assistant",
                "content": "CAS conflict: revision mismatch.",
            },
            "done": True,
        }

        call_count = 0

        class MockPostResponse:
            status_code = 200
            def __init__(self, data):
                self._data = data
            def json(self):
                return self._data

        class MockAsyncClient:
            def __init__(self, **kwargs):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            async def post(self, url, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return MockPostResponse(round1_resp)
                return MockPostResponse(round2_resp)

        planner = PlannerAgent()
        ws_messages = []

        async def mock_ws_send(payload, user_id):
            ws_messages.append(payload)

        common_ctx = {
            "ctx": {}, "suggestions": [], "cred_status": {},
            "user_profile": {}, "failures_text": "None", "perf_insights": {},
            "news_ctx": {}, "pipeline": {}
        }

        with patch("httpx.AsyncClient", MockAsyncClient), \
             patch("backend.core.ws_manager.ws_manager.send", side_effect=mock_ws_send), \
             patch.object(planner, "_gather_common_context", new=AsyncMock(return_value=common_ctx)), \
             patch("backend.core.user_intelligence.UserIntelligence.record_event", new=AsyncMock()), \
             patch("backend.services.project_service.ProjectService.apply_operation", side_effect=ValueError("Revision conflict")):
            resp = await planner.handle_message(
                message="Apply track update at revision 999",
                history=[],
                user_settings=None,
                user_id="test_user",
                pinned_provider="ollama",
                pinned_model="gemma4:e4b",
                pinned_think=False,
            )

            assert "conflict" in resp.lower()
            cap_events = [m for m in ws_messages if m.get("type") == "capability_executed"]
            assert len(cap_events) == 1
            assert cap_events[0]["status"] == "failed"

        db_after = _get_db_hash()
        assert db_before == db_after, "viralmint.db was mutated during test!"
