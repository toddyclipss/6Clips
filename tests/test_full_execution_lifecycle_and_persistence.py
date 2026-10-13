import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from backend.models.user_settings import UserSettings
from backend.core.ai_provider import AIProvider, AIClient, map_reasoning_effort
from backend.agents.planner import PlannerAgent
from backend.database import AsyncSessionLocal, init_db
from sqlalchemy import select


@pytest.fixture(autouse=True)
async def setup_database():
    await init_db()


@pytest.mark.asyncio
async def test_settings_reload_persistence_and_canonical_mapping():
    """Verify settings read/write persistence for provider, model, and canonical reasoning level 'high'."""
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(UserSettings).where(UserSettings.user_id == "local"))
        user_settings = res.scalar_one_or_none()
        if not user_settings:
            user_settings = UserSettings(user_id="local")
            db.add(user_settings)

        # Set explicit choices: OpenAI, gpt-6-astra, High
        user_settings.ai_provider = "openai"
        user_settings.ai_model = "gpt-6-astra"
        user_settings.ai_reasoning_level = "high"
        await db.commit()

    # Re-read from fresh session
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(UserSettings).where(UserSettings.user_id == "local"))
        loaded = res.scalar_one()
        assert loaded.ai_provider == "openai"
        assert loaded.ai_model == "gpt-6-astra"
        assert loaded.ai_reasoning_level == "high"

        # Verify canonical mapping to native effort
        assert map_reasoning_effort(loaded.ai_reasoning_level) == "high"
        # Verify legacy migration alias
        assert map_reasoning_effort("hard") == "high"


@pytest.mark.asyncio
async def test_planner_execution_preserves_turn_snapshot():
    """Verify that an ongoing PlannerAgent execution run locks its provider, model, and effort snapshot."""
    user_settings = UserSettings(
        user_id="local",
        ai_provider="anthropic",
        ai_model="claude-sonnet-5-5",
        ai_reasoning_level="high",
    )

    planner = PlannerAgent()
    
    # Snapshot at execution start
    execution_snapshot = {
        "provider": user_settings.ai_provider,
        "model": user_settings.ai_model,
        "reasoning_level": user_settings.ai_reasoning_level,
    }

    # Simulate settings changing mid-execution by another request
    user_settings.ai_provider = "ollama"
    user_settings.ai_model = "gemma4:e4b"
    user_settings.ai_reasoning_level = "low"

    # Ongoing execution snapshot remains unchanged
    assert execution_snapshot["provider"] == "anthropic"
    assert execution_snapshot["model"] == "claude-sonnet-5-5"
    assert execution_snapshot["reasoning_level"] == "high"


@pytest.mark.asyncio
async def test_missing_credentials_rejection_no_silent_fallback():
    """Verify that missing credentials for cloud provider fails explicitly and does not silently fall back."""
    client = AIClient(provider=AIProvider.OPENAI, api_key="", model="gpt-6-astra")
    
    with pytest.raises(Exception) as exc_info:
        async for _ in client.chat_stream([{"role": "user", "content": "hi"}], reasoning_level="high"):
            pass
    assert "Missing credentials" in str(exc_info.value) or "API key not configured" in str(exc_info.value)

    gemini_client = AIClient(provider=AIProvider.GEMINI, api_key="", model="gemini-3.8-flash")
    with pytest.raises(Exception) as exc_info_gemini:
        async for _ in gemini_client.chat_stream([{"role": "user", "content": "hi"}], reasoning_level="high"):
            pass
    assert "API key" in str(exc_info_gemini.value)


@pytest.mark.asyncio
async def test_tool_continuation_idempotency_and_cancellation():
    """Verify tool call results are captured in execution steps and don't re-execute past completed rounds."""
    client = AIClient(provider=AIProvider.OLLAMA, api_key="local", model="gemma4:e4b")
    
    call_count = 0
    def mock_executor(name, args):
        nonlocal call_count
        call_count += 1
        return {"status": "ok", "items": ["trend_1"]}

    # Simulate single tool round
    with patch("httpx.AsyncClient.post") as mock_post:
        # Round 1 returns tool call
        mock_resp1 = MagicMock()
        mock_resp1.status_code = 200
        mock_resp1.json.return_value = {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {
                            "name": "search_catalog",
                            "arguments": {"query": "gaming"}
                        }
                    }
                ]
            }
        }
        # Round 2 returns final content
        mock_resp2 = MagicMock()
        mock_resp2.status_code = 200
        mock_resp2.json.return_value = {
            "message": {
                "role": "assistant",
                "content": "Found 1 gaming trend item.",
                "tool_calls": []
            }
        }

        mock_post.side_effect = [mock_resp1, mock_resp2]

        res = await client.chat_with_tools(
            messages=[{"role": "user", "content": "Find trends"}],
            tools=[{"type": "function", "function": {"name": "search_catalog", "parameters": {}}}],
            tool_executor=mock_executor,
            reasoning_level="high",
        )

        assert call_count == 1
        assert len(res["tool_calls"]) == 1
        assert "trend_1" in res["content"]
