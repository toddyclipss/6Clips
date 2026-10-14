# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""REST /api/config — serve app config defaults to frontend."""
import logging
from fastapi import APIRouter, HTTPException
from backend.config import settings as app_settings

logger = logging.getLogger(__name__)
router = APIRouter()

_DEFAULTS = {
    "model_registry": {
        "anthropic": {
            "default_model": None,
            "models": [
                "claude-fable-5-1",
                "claude-opus-5-5",
                "claude-sonnet-5-5",
                "claude-haiku-5-5",
            ],
            "reasoning_levels": ["low", "medium", "high"],
        },
        "openai": {
            "default_model": None,
            "models": [
                "gpt-6-astra",
                "gpt-6.1-sol",
                "gpt-6-luna",
            ],
            "reasoning_levels": ["low", "medium", "high"],
        },
        "gemini": {
            "default_model": None,
            "models": [
                "gemini-3.8-flash",
                "gemini-3.1-pro-preview",
            ],
            "reasoning_levels": ["low", "medium", "high"],
        },
        "openrouter": {
            "default_model": None,
            "models": [
                "anthropic/claude-fable-5.1",
                "anthropic/claude-opus-5.5",
                "anthropic/claude-sonnet-5.5",
                "anthropic/claude-haiku-5.5",
                "openai/gpt-6-astra",
                "openai/gpt-6.1-sol",
                "openai/gpt-6.1-luna",
                "google/gemini-3.8-flash",
                "google/gemini-3.1-pro-preview",
            ],
            "reasoning_levels": ["low", "medium", "high"],
        },
        # Local Ollama models — dynamically updated from local Ollama daemon
        "ollama": {
            "default_model": None,
            "models": [
                "gemma4:e4b",
            ],
            "reasoning_levels": ["low", "medium", "high"],
        },
    },
    "tts_providers": {
        "edge_tts":   {"label": "Edge TTS — Free",          "cost_1k": 0.0,   "requires_key": False},
        "openai_tts": {"label": "OpenAI TTS — Standard",    "cost_1k": 0.015, "requires_key": True},
    },
    # Mirrors caption_service.CAPTION_STYLES (minus `brainrot`, which is a
    # pipeline look rather than a picker option) plus the "none" sentinel.
    # This list used to stop at the original three, so Smart Video offered 3 of
    # the engine's 10 styles. tests/test_caption_styles_parity.py pins it.
    "caption_styles": {
        "viral":   {"label": "Viral — yellow word highlight",   "words_per_group": 6},
        "classic": {"label": "Classic — full sentence",         "words_per_group": 8},
        "bold":    {"label": "Bold — green word highlight",     "words_per_group": 4},
        "neon":    {"label": "Neon — pink text, yellow pop",    "words_per_group": 6},
        "minimal": {"label": "Minimal — plain, no highlight",   "words_per_group": 10},
        "karaoke": {"label": "Karaoke — words light up",        "words_per_group": 6},
        "glow":    {"label": "Glow — soft orange glow",         "words_per_group": 6},
        "urban":   {"label": "Bold Urban — punchy bursts",      "words_per_group": 3},
        "warm":    {"label": "Warm Glow — serif, cream tone",   "words_per_group": 6},
        "mono":    {"label": "Monochrome — understated grey",   "words_per_group": 6},
        "none":    {"label": "No captions"},
    },
}


@router.get("/config/voices/{provider}")
async def get_voices(provider: str):
    """Available voices for a TTS provider.

    The frontend has always called this route; it did not exist, so both voice
    pickers fell back to a hand-typed list on EVERY load — and those lists had
    drifted from what the engines accept (see the comment on the fallbacks in
    Voiceover.jsx). Serving the real vocabulary is what stops that class of
    bug: one source, the engine itself.

    Declared before `/config/{key}` for readability; the two path shapes do not
    collide.
    """
    from backend.services.tts_service import TTSProvider, list_voices

    try:
        tts_provider = TTSProvider(provider)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown TTS provider: {provider}")

    voices = await list_voices(tts_provider)
    return {"provider": provider, "voices": voices}


import copy
import os
import time
from typing import Optional, Dict, Any

_MODEL_REGISTRY_CACHE: Optional[Dict[str, Any]] = None
_MODEL_REGISTRY_CACHE_TIME: float = 0.0

_OLLAMA_STATUS_CACHE: Optional[Dict[str, Any]] = None
_OLLAMA_STATUS_CACHE_TIME: float = 0.0


MODEL_REGISTRY_CACHE_TTL_DEFAULT_SEC: float = 60.0


def _get_cache_ttl_sec() -> float:
    try:
        return float(os.getenv("SIXCLIPS_MODEL_REGISTRY_CACHE_TTL_SEC", str(MODEL_REGISTRY_CACHE_TTL_DEFAULT_SEC)))
    except (ValueError, TypeError):
        return MODEL_REGISTRY_CACHE_TTL_DEFAULT_SEC


def clear_model_registry_cache() -> None:
    """Clear in-memory cache for model registry and Ollama status (for unit tests / forced invalidation)."""
    global _MODEL_REGISTRY_CACHE, _MODEL_REGISTRY_CACHE_TIME, _OLLAMA_STATUS_CACHE, _OLLAMA_STATUS_CACHE_TIME
    _MODEL_REGISTRY_CACHE = None
    _MODEL_REGISTRY_CACHE_TIME = 0.0
    _OLLAMA_STATUS_CACHE = None
    _OLLAMA_STATUS_CACHE_TIME = 0.0


@router.get("/config/ollama/status")
async def get_ollama_status(refresh: bool = False):
    """Discover local Ollama service health, loaded models, and installed tags with TTL caching."""
    global _OLLAMA_STATUS_CACHE, _OLLAMA_STATUS_CACHE_TIME
    now = time.monotonic()
    ttl = _get_cache_ttl_sec()

    if not refresh and _OLLAMA_STATUS_CACHE is not None and (now - _OLLAMA_STATUS_CACHE_TIME < ttl):
        return copy.deepcopy(_OLLAMA_STATUS_CACHE)

    import httpx
    base_url = getattr(app_settings, "OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            tags_resp = await client.get(f"{base_url.rstrip('/')}/api/tags")
            ps_resp = await client.get(f"{base_url.rstrip('/')}/api/ps")
            tags_data = tags_resp.json() if tags_resp.status_code == 200 else {}
            ps_data = ps_resp.json() if ps_resp.status_code == 200 else {}
            models = [m["name"] for m in tags_data.get("models", []) if "name" in m]
            running = ps_data.get("models", [])
            result = {
                "ok": True,
                "status": "online",
                "base_url": base_url,
                "models": models,
                "running": running,
            }
            _OLLAMA_STATUS_CACHE = copy.deepcopy(result)
            _OLLAMA_STATUS_CACHE_TIME = now
            return result
    except Exception as e:
        err_res = {
            "ok": False,
            "status": "offline",
            "base_url": base_url,
            "error": str(e),
            "models": [],
            "running": [],
        }
        _OLLAMA_STATUS_CACHE = copy.deepcopy(err_res)
        _OLLAMA_STATUS_CACHE_TIME = now
        return err_res


@router.get("/config/{key}")
async def get_config(key: str, refresh: bool = False):
    """Return config for a given key with TTL caching for model_registry."""
    global _MODEL_REGISTRY_CACHE, _MODEL_REGISTRY_CACHE_TIME

    if key == "model_registry":
        now = time.monotonic()
        ttl = _get_cache_ttl_sec()

        if not refresh and _MODEL_REGISTRY_CACHE is not None and (now - _MODEL_REGISTRY_CACHE_TIME < ttl):
            return {"key": key, "value": copy.deepcopy(_MODEL_REGISTRY_CACHE)}

        registry = copy.deepcopy(_DEFAULTS["model_registry"])
        try:
            import httpx
            base_url = getattr(app_settings, "OLLAMA_BASE_URL", "http://127.0.0.1:11434")
            async with httpx.AsyncClient(timeout=1.5) as client:
                resp = await client.get(f"{base_url.rstrip('/')}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m["name"] for m in data.get("models", []) if "name" in m]
                    if models:
                        model_metadata = {}
                        for m_name in models:
                            try:
                                show_resp = await client.post(
                                    f"{base_url.rstrip('/')}/api/show",
                                    json={"model": m_name},
                                    timeout=1.5,
                                )
                                if show_resp.status_code == 200:
                                    s_data = show_resp.json()
                                    model_metadata[m_name] = {
                                        "capabilities": s_data.get("capabilities", []),
                                        "thinking": s_data.get("thinking", None),
                                    }
                            except Exception:
                                pass
                        registry["ollama"] = {
                            "default_model": None,
                            "models": models,
                            "model_metadata": model_metadata,
                            "reasoning_levels": ["low", "medium", "high"],
                        }
        except Exception as e:
            logger.debug("Ollama model discovery skipped: %s", e)

        _MODEL_REGISTRY_CACHE = copy.deepcopy(registry)
        _MODEL_REGISTRY_CACHE_TIME = now
        return {"key": key, "value": registry}

    value = _DEFAULTS.get(key)
    if value is None:
        raise HTTPException(status_code=404, detail=f"Unknown config key: {key}")
    return {"key": key, "value": value}
