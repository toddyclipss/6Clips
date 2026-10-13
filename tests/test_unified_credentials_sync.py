# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for Unified BYOK Credentials, Provider Isolation, and Model Registry."""
import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.database import AsyncSessionLocal, init_db
from backend.models.user_settings import UserSettings
from backend.core.crypto import encrypt, decrypt_safe
from backend.core.ai_provider import AIProvider, PROVIDER_DEFAULTS, map_reasoning_effort, get_ai_client
from sqlalchemy import select


@pytest.fixture(autouse=True)
async def ensure_db():
    await init_db()


@pytest.mark.asyncio
async def test_model_registry_gemini_models_and_reasoning_levels():
    """Verify Gemini models in config endpoint are strictly gemini-3.8-flash and gemini-3.1-pro-preview with low/medium/high."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/config/model_registry")
        assert res.status_code == 200
        registry = res.json().get("value", {})

        # Native Gemini provider
        assert "gemini" in registry
        gemini_cfg = registry["gemini"]
        assert gemini_cfg["models"] == ["gemini-3.8-flash", "gemini-3.1-pro-preview"]
        assert gemini_cfg["reasoning_levels"] == ["low", "medium", "high"]
        assert gemini_cfg["default_model"] is None

        # Verify all providers have low, medium, high reasoning levels
        for p in ["openai", "anthropic", "openrouter", "ollama"]:
            assert p in registry
            assert registry[p]["reasoning_levels"] == ["low", "medium", "high"]


@pytest.mark.asyncio
async def test_independent_credentials_saving_does_not_mutate_active_provider():
    """Saving an API key must store that credential independently without altering the active ai_provider."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Initial: set active provider to ollama
        res = await ac.post("/api/settings", json={"ai_provider": "ollama", "ai_model": "gemma4:e4b"})
        assert res.status_code == 200
        assert res.json()["ai_provider"] == "ollama"

        # Save an OpenAI key: active provider must remain ollama!
        res2 = await ac.post("/api/settings", json={"openai_api_key": "sk-test-openai-12345"})
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["ai_provider"] == "ollama"
        assert data2["openai_api_key_set"] is True
        assert "sk-test-openai-12345" not in res2.text  # masked!

        # Save a Gemini key: active provider must still remain ollama!
        res3 = await ac.post("/api/settings", json={"gemini_api_key": "AIzaSyTestGeminiKey"})
        assert res3.status_code == 200
        data3 = res3.json()
        assert data3["ai_provider"] == "ollama"
        assert data3["gemini_api_key_set"] is True
        assert "AIzaSyTestGeminiKey" not in res3.text  # masked!

        # Clean up keys
        await ac.post("/api/settings", json={"openai_api_key": "", "gemini_api_key": ""})


@pytest.mark.asyncio
async def test_provider_key_isolation_gemini_vs_openrouter():
    """Verify Google Gemini direct uses gemini key and OpenRouter uses openrouter key."""
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(UserSettings).where(UserSettings.user_id == "local"))
        s = res.scalar_one_or_none()
        if not s:
            s = UserSettings(user_id="local")
            db.add(s)
        s.gemini_api_key_encrypted = encrypt("test-direct-gemini-key")
        s.openrouter_api_key_encrypted = encrypt("test-openrouter-key")
        s.openai_api_key_encrypted = None
        s.anthropic_api_key_encrypted = None
        s.ai_provider = "gemini"
        s.ai_model = "gemini-3.8-flash"
        await db.commit()

    # Resolve client for native Gemini
    client = get_ai_client(user_settings=s)
    assert client.provider == AIProvider.GEMINI
    assert client.api_key == "test-direct-gemini-key"
    assert client.model == "gemini-3.8-flash"

    # Now switch active provider to openrouter with gemini model via openrouter
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(UserSettings).where(UserSettings.user_id == "local"))
        s2 = res.scalar_one()
        s2.ai_provider = "openrouter"
        s2.ai_model = "google/gemini-3.8-flash"
        await db.commit()

    client_or = get_ai_client(user_settings=s2)
    assert client_or.provider == AIProvider.OPENROUTER
    assert client_or.api_key == "test-openrouter-key"
    assert client_or.model == "google/gemini-3.8-flash"

    # Reset
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(UserSettings).where(UserSettings.user_id == "local"))
        s = res.scalar_one()
        s.gemini_api_key_encrypted = None
        s.openrouter_api_key_encrypted = None
        s.ai_provider = "ollama"
        s.ai_model = "gemma4:e4b"
        await db.commit()


def test_reasoning_level_mapping_low_medium_high():
    """map_reasoning_effort must map low, medium, high strictly."""
    assert map_reasoning_effort("low") == "low"
    assert map_reasoning_effort("medium") == "medium"
    assert map_reasoning_effort("high") == "high"
    # Legacy alias compatibility
    assert map_reasoning_effort("hard") == "high"
    assert map_reasoning_effort(None) == "medium"
