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
        # Models verified May 2026. Anthropic / OpenAI defaults pick the
        # best price/perf tier; OpenRouter defaults to a premium model
        # because BYOK users routing through OpenRouter typically want
        # access to the top tier without juggling multiple provider keys.
        "anthropic": {
            "default_model": "claude-sonnet-4-6",
            "models": [
                "claude-haiku-4-5",
                "claude-sonnet-4-6",
                "claude-opus-4-6",
                "claude-opus-4-7",
            ],
        },
        "openai": {
            "default_model": "gpt-5.4-mini",
            "models": [
                "gpt-5.4-nano",
                "gpt-5.4-mini",
                "gpt-5.4",
                "gpt-5.5",
            ],
        },
        # OpenRouter slugs use the vendor/model format. Verified live
        # against https://openrouter.ai/api/v1/models on 2026-05-07. If
        # you want a model that isn't here, OpenRouter accepts any of its
        # published slugs — but the dropdown only exposes this curated
        # set so users don't have to guess.
        "openrouter": {
            "default_model": "anthropic/claude-opus-4.7",
            "models": [
                "anthropic/claude-opus-4.7",
                "anthropic/claude-opus-4.6-fast",
                "anthropic/claude-sonnet-4.6",
                "openai/gpt-5.5",
                "openai/gpt-5.4",
                "openai/gpt-5.4-mini",
                "google/gemini-3.1-pro-preview",
                "google/gemini-3.1-flash-lite",
            ],
        },
        # Local Ollama models — dynamically updated from local Ollama daemon
        "ollama": {
            "default_model": "gemma4:e4b",
            "models": [
                "gemma4:e4b",
            ],
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


@router.get("/config/ollama/status")
async def get_ollama_status():
    """Discover local Ollama service health, loaded models, and installed tags."""
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
            return {
                "ok": True,
                "status": "online",
                "base_url": base_url,
                "models": models,
                "running": running,
            }
    except Exception as e:
        return {
            "ok": False,
            "status": "offline",
            "base_url": base_url,
            "error": str(e),
            "models": [],
            "running": [],
        }


@router.get("/config/{key}")
async def get_config(key: str):
    """Return config for a given key."""
    if key == "model_registry":
        import copy
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
                            "default_model": models[0],
                            "models": models,
                            "model_metadata": model_metadata,
                        }
        except Exception as e:
            logger.debug("Ollama model discovery skipped: %s", e)
        return {"key": key, "value": registry}

    value = _DEFAULTS.get(key)
    if value is None:
        raise HTTPException(status_code=404, detail=f"Unknown config key: {key}")
    return {"key": key, "value": value}
