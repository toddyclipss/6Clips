# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
AI client factory — BYOK (Bring Your Own Key).

Supports Anthropic, OpenAI, and OpenRouter. Keys come from `.env`
(system-wide default) or per-user `UserSettings` (overrides env). No
cloud-managed keys.

OpenRouter is a unified gateway that resells access to Claude / GPT /
Gemini / Llama / Mistral / etc. behind a single key. We talk to it via
the OpenAI-compatible chat-completions endpoint at
`https://openrouter.ai/api/v1`, with `model` set to a vendor-prefixed
slug like `anthropic/claude-opus-4.7`.
"""
import asyncio
import inspect
from enum import Enum
import json
from typing import AsyncIterator, Optional, Callable, Any
import logging

from backend.config import settings
from backend.core.crypto import decrypt_safe
from backend.core.exceptions import AIKeyMissingError

logger = logging.getLogger(__name__)


class AIProvider(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OPENROUTER = "openrouter"
    OLLAMA = "ollama"


PROVIDER_DEFAULTS = {
    AIProvider.ANTHROPIC:  "claude-sonnet-4-6",
    AIProvider.OPENAI:     "gpt-5.4-mini",
    # OpenRouter BYOK users pay their own bill — default to a premium
    # model so the experience matches the gateway's value prop. Users
    # can pick a cheaper model in Settings → Model dropdown.
    AIProvider.OPENROUTER: "anthropic/claude-opus-4.7",
    AIProvider.OLLAMA:     "gemma4:e4b",
}

# OpenRouter's optional analytics headers — show up on the public model
# leaderboard at openrouter.ai/rankings. Harmless to send; helps us
# track how much OSS-variant traffic flows through the gateway.
_OPENROUTER_HEADERS = {
    "HTTP-Referer": "https://github.com/openclaw-easy/ViralMint",
    "X-Title": "ViralMint (OSS)",
}


class AIClient:
    """Universal AI client — same interface regardless of underlying provider."""

    def __init__(self, provider: AIProvider, api_key: str, model: Optional[str] = None):
        self.provider = provider
        self.api_key = api_key
        self.model = model or PROVIDER_DEFAULTS[provider]

    async def chat_stream(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 2048,
        think: Optional[bool | str] = None,
        on_status: Optional[Callable[[str], Any]] = None,
    ) -> AsyncIterator[str]:
        """Yield text chunks as they stream in."""
        if self.provider == AIProvider.ANTHROPIC:
            async for chunk in self._anthropic_stream(messages, system, max_tokens):
                yield chunk
        elif self.provider == AIProvider.OPENAI:
            async for chunk in self._openai_stream(messages, system, max_tokens):
                yield chunk
        elif self.provider == AIProvider.OPENROUTER:
            async for chunk in self._openrouter_stream(messages, system, max_tokens):
                yield chunk
        elif self.provider == AIProvider.OLLAMA:
            async for chunk in self._ollama_stream(messages, system, max_tokens, think=think, on_status=on_status):
                yield chunk

    async def chat(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 2048,
        think: Optional[bool | str] = None,
    ) -> str:
        """Non-streaming — returns full response string."""
        chunks = []
        async for chunk in self.chat_stream(messages, system, max_tokens, think=think):
            chunks.append(chunk)
        return "".join(chunks)

    # ── Provider implementations ──────────────────────────────────────────────

    async def _anthropic_stream(self, messages, system, max_tokens):
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=self.api_key)
        async with client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            system=system or "",
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def _openai_stream(self, messages, system, max_tokens):
        import openai
        client = openai.AsyncOpenAI(api_key=self.api_key, timeout=55.0)
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        # GPT-5+ and o-series reasoning models reject `max_tokens` and require
        # `max_completion_tokens` (OpenAI API change, late 2024). Older models
        # accept either, but we only ship gpt-5.x in the registry, so this
        # branch is the common path.
        m = self.model.lower()
        uses_completion_tokens = (
            m.startswith(("gpt-5", "o1", "o3", "o4"))
        )
        token_kwargs = (
            {"max_completion_tokens": max_tokens}
            if uses_completion_tokens
            else {"max_tokens": max_tokens}
        )

        stream = await client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            stream=True,
            **token_kwargs,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def _openrouter_stream(self, messages, system, max_tokens):
        """OpenRouter is OpenAI-compatible — same client, different base URL."""
        import openai
        client = openai.AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers=_OPENROUTER_HEADERS,
            timeout=55.0,
        )
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        # OpenRouter normalises max_tokens vs max_completion_tokens internally
        # for downstream models, so we always send max_tokens here regardless
        # of which underlying provider is being routed to.
        stream = await client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            stream=True,
            max_tokens=max_tokens,
        )
        async for chunk in stream:
            # Defensive: OpenRouter sometimes emits keepalive chunks with
            # an empty `choices` array before real tokens start flowing.
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def _ollama_stream(self, messages, system, max_tokens, think=None, on_status=None):
        """Native Ollama chat streaming via POST /api/chat.

        Disables thinking trace leakage, handles text chunks, and bridges
        native Ollama tool_calls into canonical <action> blocks.
        """
        import httpx
        base_url = getattr(settings, "OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        payload = {
            "model": self.model,
            "messages": full_messages,
            "stream": True,
            "options": {
                "num_predict": max_tokens,
            },
        }
        if think is not None:
            payload["think"] = think

        timeout = httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=5.0)
        has_signaled_thinking = False
        async with httpx.AsyncClient(timeout=timeout) as client:
            url = f"{base_url.rstrip('/')}/api/chat"
            async with client.stream("POST", url, json=payload) as resp:
                if resp.status_code != 200:
                    err_body = await resp.aread()
                    logger.error(
                        "Ollama stream error (%d): %s",
                        resp.status_code,
                        err_body.decode(errors="ignore")[:200],
                    )
                    yield f"Ollama error ({resp.status_code}): {err_body.decode(errors='ignore')[:120]}"
                    return

                async for line in resp.aiter_lines():
                    if not line or not line.strip():
                        continue
                    try:
                        chunk_data = json.loads(line)
                    except Exception:
                        continue

                    msg = chunk_data.get("message", {})
                    # If model is emitting reasoning tokens, signal thinking status once and suppress traces
                    thinking_delta = msg.get("thinking")
                    if thinking_delta and on_status and not has_signaled_thinking:
                        has_signaled_thinking = True
                        try:
                            s_res = on_status("thinking")
                            if inspect.isawaitable(s_res):
                                await s_res
                        except Exception:
                            pass

                    delta = msg.get("content", "")
                    if delta:
                        yield delta

                    tool_calls = msg.get("tool_calls")
                    if tool_calls and isinstance(tool_calls, list):
                        for tc in tool_calls:
                            fn = tc.get("function", {})
                            fn_name = fn.get("name")
                            fn_args = fn.get("arguments", {})
                            if isinstance(fn_args, str):
                                try:
                                    fn_args = json.loads(fn_args)
                                except Exception:
                                    fn_args = {}
                            if fn_name:
                                action_dict = (
                                    {"type": fn_name, **fn_args}
                                    if isinstance(fn_args, dict)
                                    else {"type": fn_name}
                                )
                                yield f"\n<action>{json.dumps(action_dict)}</action>\n"

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 1024,
        think: Optional[bool | str] = None,
        tool_executor: Optional[Callable[[str, dict], Any]] = None,
        max_tool_rounds: int = 5,
        on_status: Optional[Callable[[str], Any]] = None,
        on_token: Optional[Callable[[str], Any]] = None,
    ) -> dict:
        """Native multi-turn tool calling execution loop.

        Sends tools schema to the provider, captures returned tool_calls,
        validates against CapabilityRegistry, executes via tool_executor,
        appends tool result messages (`{"role": "tool", "content": ...}`),
        and loops back to model for the final contextual response.
        """
        import httpx
        import asyncio
        import re
        from backend.core.capabilities import CapabilityRegistry

        current_messages = []
        if system:
            current_messages.append({"role": "system", "content": system})
        current_messages.extend(messages)

        executed_tool_calls = []

        if self.provider == AIProvider.OLLAMA:
            base_url = getattr(settings, "OLLAMA_BASE_URL", "http://127.0.0.1:11434")
            timeout = httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=5.0)

            async with httpx.AsyncClient(timeout=timeout) as client:
                url = f"{base_url.rstrip('/')}/api/chat"

                for round_idx in range(max_tool_rounds):
                    send_messages = list(current_messages)
                    if round_idx > 0:
                        synthesis_system = (
                            "You are 6Clips, a gaming-first Outcomes-as-a-Service video creation assistant. "
                            "A tool has been executed to answer the user request. Present and summarize the returned "
                            "tool results and specific item IDs directly and concisely to the user. "
                            "Do not output a new-session greeting, introductory pitch, or generic menu options."
                        )
                        if send_messages and send_messages[0].get("role") == "system":
                            send_messages[0] = {"role": "system", "content": synthesis_system}
                        else:
                            send_messages.insert(0, {"role": "system", "content": synthesis_system})

                    payload = {
                        "model": self.model,
                        "messages": send_messages,
                        "stream": False,
                        "options": {"num_predict": max_tokens},
                    }
                    # Send tools on initial round to invoke capabilities; omit on subsequent
                    # rounds so the model synthesizes natural language rather than looping.
                    if round_idx == 0 and tools:
                        payload["tools"] = tools
                    if think is not None:
                        payload["think"] = think
                    if round_idx == 0 and think is not False and on_status:
                        stat_res = on_status("thinking")
                        if inspect.isawaitable(stat_res):
                            await stat_res

                    resp = await client.post(url, json=payload)
                    if resp.status_code != 200:
                        err_text = resp.text[:200]
                        logger.error("Ollama tool round error (%d): %s", resp.status_code, err_text)
                        return {
                            "content": f"Ollama error ({resp.status_code}): {err_text}",
                            "tool_calls": executed_tool_calls,
                            "rounds": round_idx + 1,
                            "messages": current_messages,
                        }

                    resp_data = resp.json()
                    msg = resp_data.get("message", {})
                    tool_calls = msg.get("tool_calls", [])

                    if not tool_calls:
                        final_content = msg.get("content", "").strip()
                        needs_synthesis_fallback = False
                        if executed_tool_calls:
                            if not final_content:
                                needs_synthesis_fallback = True
                            elif any(etc.get("name") == "search_catalog" for etc in executed_tool_calls):
                                sc_items = [
                                    it.get("id")
                                    for etc in executed_tool_calls
                                    if etc.get("name") == "search_catalog"
                                    for it in etc.get("result", {}).get("items", [])
                                    if it.get("id")
                                ]
                                if sc_items and not any(sid.lower() in final_content.lower() for sid in sc_items[:3]):
                                    needs_synthesis_fallback = True

                        if needs_synthesis_fallback:
                            summaries = []
                            for etc in executed_tool_calls:
                                res = etc.get("result", {})
                                is_err = bool(res.get("error") or res.get("status") == "error")
                                if etc.get("name") == "search_catalog":
                                    if is_err:
                                        summaries.append(f"Catalog search failed: {res.get('error', 'unknown error')}")
                                    else:
                                        items = res.get("items", [])
                                        if items:
                                            lines = [f"Found {len(items)} matching catalog block(s):"]
                                            for it in items[:6]:
                                                lines.append(f"- **{it.get('title') or it.get('name')}** (`{it.get('id')}`)")
                                            summaries.append("\n".join(lines))
                                        else:
                                            summaries.append("Found 0 matching catalog blocks.")
                                elif etc.get("name") == "project_operation":
                                    if is_err:
                                        summaries.append(f"Project operation failed: {res.get('error', 'unknown error')}")
                                    else:
                                        status = res.get("status", "unknown")
                                        summaries.append(f"Project operation applied ({status}).")
                                elif etc.get("name") in ("suggest_clips", "extract_clips"):
                                    if is_err:
                                        summaries.append(f"Clip operation failed: {res.get('error', 'unknown error')}")
                                    else:
                                        count = res.get("count") or len(res.get("suggestions", []) or res.get("clips", []))
                                        summaries.append(f"Clip operation completed: {count} clip candidate(s) processed.")
                                else:
                                    if is_err:
                                        summaries.append(f"Capability {etc.get('name')} failed: {res.get('error', 'unknown error')}")
                                    else:
                                        summaries.append(f"Executed capability: {etc.get('name')}.")
                            final_content = "\n\n".join(summaries)

                        if on_token and final_content:
                            tokens = re.findall(r'\S+|\s+', final_content)
                            for tok in tokens:
                                res = on_token(tok)
                                if inspect.isawaitable(res):
                                    await res
                                await asyncio.sleep(0.005)
                        return {
                            "content": final_content,
                            "tool_calls": executed_tool_calls,
                            "rounds": round_idx + 1,
                            "messages": current_messages + [msg],
                        }

                    current_messages.append(msg)

                    for tc in tool_calls:
                        fn = tc.get("function", {})
                        fn_name = fn.get("name")
                        fn_args = fn.get("arguments", {})
                        if isinstance(fn_args, str):
                            try:
                                fn_args = json.loads(fn_args)
                            except Exception:
                                fn_args = {}

                        if on_status:
                            stat_res = on_status(f"calling_tool:{fn_name}")
                            if inspect.isawaitable(stat_res):
                                await stat_res

                        cap = CapabilityRegistry.get(fn_name)
                        if not cap:
                            result = {"error": f"Unauthorized or unknown capability '{fn_name}'"}
                        else:
                            try:
                                CapabilityRegistry.validate_input(fn_name, fn_args)
                                if tool_executor:
                                    exec_res = tool_executor(fn_name, fn_args)
                                    if inspect.isawaitable(exec_res):
                                        result = await exec_res
                                    else:
                                        result = exec_res
                                else:
                                    result = {"status": "success", "capability": fn_name, "data": fn_args}
                            except Exception as ex:
                                result = {"error": str(ex)}

                        executed_tool_calls.append({
                            "name": fn_name,
                            "arguments": fn_args,
                            "result": result,
                        })

                        tool_msg = {
                            "role": "tool",
                            "content": json.dumps(result) if not isinstance(result, str) else result,
                        }
                        if tc.get("id"):
                            tool_msg["tool_call_id"] = tc.get("id")
                        current_messages.append(tool_msg)

                return {
                    "content": "Max tool execution rounds reached.",
                    "tool_calls": executed_tool_calls,
                    "rounds": max_tool_rounds,
                    "messages": current_messages,
                }

        # Fallback for standard text chat
        res = await self.chat(messages, system=system, max_tokens=max_tokens, think=think)
        return {
            "content": res,
            "tool_calls": [],
            "rounds": 1,
            "messages": current_messages + [{"role": "assistant", "content": res}],
        }


# ── Factory ───────────────────────────────────────────────────────────────────

def _resolve_user_provider_and_key(user_settings) -> tuple[Optional[AIProvider], Optional[str]]:
    """Read provider preference and decrypted API key from UserSettings, if set."""
    if not user_settings:
        return None, None

    provider_str = (getattr(user_settings, "ai_provider", None) or "").lower().strip()
    encrypted_key = getattr(user_settings, "ai_api_key_encrypted", None)
    if not provider_str:
        return None, None

    try:
        provider = AIProvider(provider_str)
    except ValueError:
        return None, None

    if provider == AIProvider.OLLAMA:
        api_key = decrypt_safe(encrypted_key) if encrypted_key else "ollama_local"
        return provider, api_key or "ollama_local"

    if not encrypted_key:
        return None, None

    api_key = decrypt_safe(encrypted_key) or ""
    return provider, api_key or None


def is_model_compatible_with_provider(model: Optional[str], provider: AIProvider) -> bool:
    """Check if a model name is structurally compatible with the provider."""
    if not model or not isinstance(model, str):
        return True
    m = model.strip().lower()
    # Vendor-prefixed slugs (e.g. "anthropic/claude-...", "google/...") only work with OpenRouter
    if "/" in m and provider != AIProvider.OPENROUTER:
        return False
    if provider == AIProvider.ANTHROPIC:
        # OpenAI or other vendor prefixes sent to Anthropic will fail
        if m.startswith(("gpt-", "o1", "o3", "o4", "openai", "text-davinci")):
            return False
    elif provider == AIProvider.OPENAI:
        # Anthropic claude models sent to OpenAI will fail
        if m.startswith(("claude-", "anthropic")):
            return False
    elif provider == AIProvider.OLLAMA:
        # Proprietary cloud model IDs sent to Ollama will fail
        if m.startswith(("gpt-", "o1", "o3", "o4", "claude-", "anthropic/")):
            return False
    return True


def sanitize_model_for_provider(model: Optional[str], provider: AIProvider) -> str:
    """Ensure the model is valid for the provider; fallback to provider default if mismatched."""
    if model and is_model_compatible_with_provider(model, provider):
        return model
    default_m = PROVIDER_DEFAULTS.get(provider, "default")
    if model:
        logger.warning(
            "Model '%s' is incompatible with provider '%s'; defaulting to '%s'",
            model, provider.value, default_m
        )
    return default_m


def _is_ollama_available() -> bool:
    """Fast check whether local Ollama server is responding."""
    import socket
    from urllib.parse import urlparse
    url = getattr(settings, "OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    try:
        parsed = urlparse(url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme == "https" else 11434)
        sock = socket.create_connection((host, port), timeout=0.3)
        sock.close()
        return True
    except Exception:
        return False


def get_ai_client(
    user_settings=None,
    pinned_provider: Optional[AIProvider | str] = None,
    pinned_model: Optional[str] = None,
    **_kwargs,
) -> AIClient:
    """
    Return a configured AI client.

    Resolution order:
      1. If pinned_provider is provided, honor pinned execution configuration.
      2. UserSettings.ai_provider + UserSettings.ai_api_key_encrypted (BYOK from UI / local Ollama)
      3. .env keys (ANTHROPIC_API_KEY → OPENAI_API_KEY → OPENROUTER_API_KEY)
      4. Local Ollama fallback if running on OLLAMA_BASE_URL
      5. Raise AIKeyMissingError with setup instructions.
    """
    user_model = getattr(user_settings, "ai_model", None) if user_settings else None
    effective_model = pinned_model or user_model

    # Pinned provider execution
    if pinned_provider:
        try:
            target_prov = AIProvider(str(pinned_provider).lower().strip())
        except ValueError:
            target_prov = None

        if target_prov:
            if target_prov == AIProvider.OLLAMA:
                resolved_model = sanitize_model_for_provider(effective_model, target_prov)
                return AIClient(provider=target_prov, api_key="ollama_local", model=resolved_model)

            # Check user key first for this provider
            user_provider, user_key = _resolve_user_provider_and_key(user_settings)
            key = None
            if user_provider == target_prov and user_key:
                key = user_key
            elif target_prov == AIProvider.ANTHROPIC and settings.ANTHROPIC_API_KEY:
                key = settings.ANTHROPIC_API_KEY
            elif target_prov == AIProvider.OPENAI and settings.OPENAI_API_KEY:
                key = settings.OPENAI_API_KEY
            elif target_prov == AIProvider.OPENROUTER and settings.OPENROUTER_API_KEY:
                key = settings.OPENROUTER_API_KEY

            if not key:
                raise AIKeyMissingError(
                    f"No API key configured for pinned provider '{target_prov.value}'."
                )
            resolved_model = sanitize_model_for_provider(effective_model, target_prov)
            return AIClient(provider=target_prov, api_key=key, model=resolved_model)

    # 1. User-configured provider in Settings (strict: never silently fall back)
    configured_provider_str = (getattr(user_settings, "ai_provider", None) or "").lower().strip() if user_settings else ""
    if configured_provider_str:
        try:
            cfg_prov = AIProvider(configured_provider_str)
        except ValueError:
            cfg_prov = None

        if cfg_prov:
            if cfg_prov == AIProvider.OLLAMA:
                resolved_model = sanitize_model_for_provider(effective_model, cfg_prov)
                return AIClient(provider=cfg_prov, api_key="ollama_local", model=resolved_model)

            # Cloud provider explicitly chosen in settings: must find valid key or fail
            encrypted_key = getattr(user_settings, "ai_api_key_encrypted", None)
            key = decrypt_safe(encrypted_key) if encrypted_key else None
            if not key:
                if cfg_prov == AIProvider.ANTHROPIC and settings.ANTHROPIC_API_KEY:
                    key = settings.ANTHROPIC_API_KEY
                elif cfg_prov == AIProvider.OPENAI and settings.OPENAI_API_KEY:
                    key = settings.OPENAI_API_KEY
                elif cfg_prov == AIProvider.OPENROUTER and settings.OPENROUTER_API_KEY:
                    key = settings.OPENROUTER_API_KEY

            if not key:
                raise AIKeyMissingError(
                    f"Provider '{cfg_prov.value}' selected in Settings, but no API key configured. "
                    f"Set {cfg_prov.value.upper()}_API_KEY in .env or enter your key in Settings."
                )
            resolved_model = sanitize_model_for_provider(effective_model, cfg_prov)
            return AIClient(provider=cfg_prov, api_key=key, model=resolved_model)

    # 2. Unpinned & unconfigured: check .env in priority order
    if settings.ANTHROPIC_API_KEY:
        resolved_model = sanitize_model_for_provider(effective_model, AIProvider.ANTHROPIC)
        return AIClient(
            provider=AIProvider.ANTHROPIC,
            api_key=settings.ANTHROPIC_API_KEY,
            model=resolved_model,
        )
    if settings.OPENAI_API_KEY:
        resolved_model = sanitize_model_for_provider(effective_model, AIProvider.OPENAI)
        return AIClient(
            provider=AIProvider.OPENAI,
            api_key=settings.OPENAI_API_KEY,
            model=resolved_model,
        )
    if settings.OPENROUTER_API_KEY:
        resolved_model = sanitize_model_for_provider(effective_model, AIProvider.OPENROUTER)
        return AIClient(
            provider=AIProvider.OPENROUTER,
            api_key=settings.OPENROUTER_API_KEY,
            model=resolved_model,
        )

    # 3. Local Ollama fallback if running (strictly when no cloud provider was requested)
    if _is_ollama_available():
        resolved_model = sanitize_model_for_provider(effective_model, AIProvider.OLLAMA)
        return AIClient(
            provider=AIProvider.OLLAMA,
            api_key="ollama_local",
            model=resolved_model,
        )

    raise AIKeyMissingError(
        "No AI provider configured. Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or "
        "OPENROUTER_API_KEY in your .env, run Ollama locally, or configure your provider in Settings."
    )

