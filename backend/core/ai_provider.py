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
from backend.core.exceptions import AIKeyMissingError, AIProviderUnselectedError

logger = logging.getLogger(__name__)


class AIProvider(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OPENROUTER = "openrouter"
    OLLAMA = "ollama"
    GEMINI = "gemini"


PROVIDER_DEFAULTS = {
    AIProvider.ANTHROPIC:  "claude-sonnet-5-5",
    AIProvider.OPENAI:     "gpt-6-astra",
    AIProvider.OPENROUTER: "anthropic/claude-opus-5.5",
    AIProvider.OLLAMA:     "gemma4:e4b",
    AIProvider.GEMINI:     "gemini-3.8-flash",
}

# OpenRouter's optional analytics headers — show up on the public model
# leaderboard at openrouter.ai/rankings. Harmless to send; helps us
# track how much OSS-variant traffic flows through the gateway.
_OPENROUTER_HEADERS = {
    "HTTP-Referer": "https://github.com/openclaw-easy/ViralMint",
    "X-Title": "ViralMint (OSS)",
}


def map_reasoning_effort(level: Optional[str]) -> str:
    """Map canonical reasoning level ('low', 'medium', 'high') to provider effort string ('low', 'medium', 'high')."""
    if not level:
        return "medium"
    norm = str(level).strip().lower()
    if norm in ("hard", "high"):
        return "high"
    elif norm == "low":
        return "low"
    return "medium"


def get_ollama_reasoning_profile(reasoning_level: Optional[str], max_tokens: int = 1024) -> dict:
    """Distinct bounded execution profiles for Ollama Gemma 4 / local models.

    Ensures ample token generation budget so internal reasoning never starves final answer:
    - low: 1024 predict tokens, temp 0.2, top_p 0.8 (focused, fast)
    - medium: 2048 predict tokens, temp 0.5, top_p 0.9 (balanced standard)
    - high: 4096 predict tokens, temp 0.7, top_p 0.95 (thorough verification)
    """
    lvl = (reasoning_level or "medium").strip().lower()
    if lvl == "low":
        return {
            "num_predict": min(max_tokens, 1024) if max_tokens else 1024,
            "temperature": 0.2,
            "top_p": 0.8,
        }
    elif lvl in ("hard", "high"):
        return {
            "num_predict": max(max_tokens, 4096) if max_tokens else 4096,
            "temperature": 0.7,
            "top_p": 0.95,
        }
    else:  # medium
        return {
            "num_predict": 2048,
            "temperature": 0.5,
            "top_p": 0.9,
        }


def get_ollama_orchestration_instructions(reasoning_level: Optional[str]) -> str:
    """Distinct 6Clips orchestration policies for local Ollama execution."""
    lvl = (reasoning_level or "medium").strip().lower()
    if lvl == "low":
        return "ORCHESTRATION POLICY [LOW]: Provide a direct, concise, and focused response with minimal deliberation."
    elif lvl in ("hard", "high"):
        return (
            "ORCHESTRATION POLICY [HIGH]: CRITICAL VERIFICATION MODE. Systematically analyze constraints, "
            "verify intermediate calculations and tool parameters, and validate edge cases before formulating the final answer."
        )
    else:  # medium
        return "ORCHESTRATION POLICY [MEDIUM]: Carefully plan and synthesize a well-structured response."


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
        reasoning_level: Optional[str] = None,
        on_status: Optional[Callable[[str], Any]] = None,
    ) -> AsyncIterator[str]:
        """Yield text chunks as they stream in."""
        if self.provider == AIProvider.ANTHROPIC:
            kwargs = {"reasoning_level": reasoning_level} if "reasoning_level" in inspect.signature(self._anthropic_stream).parameters else {}
            async for chunk in self._anthropic_stream(messages, system, max_tokens, **kwargs):
                yield chunk
        elif self.provider == AIProvider.OPENAI:
            kwargs = {"reasoning_level": reasoning_level} if "reasoning_level" in inspect.signature(self._openai_stream).parameters else {}
            async for chunk in self._openai_stream(messages, system, max_tokens, **kwargs):
                yield chunk
        elif self.provider == AIProvider.OPENROUTER:
            kwargs = {"reasoning_level": reasoning_level} if "reasoning_level" in inspect.signature(self._openrouter_stream).parameters else {}
            async for chunk in self._openrouter_stream(messages, system, max_tokens, **kwargs):
                yield chunk
        elif self.provider == AIProvider.OLLAMA:
            kwargs = {"think": think, "on_status": on_status}
            if "reasoning_level" in inspect.signature(self._ollama_stream).parameters:
                kwargs["reasoning_level"] = reasoning_level
            async for chunk in self._ollama_stream(messages, system, max_tokens, **kwargs):
                yield chunk
        elif self.provider == AIProvider.GEMINI:
            kwargs = {"reasoning_level": reasoning_level} if "reasoning_level" in inspect.signature(self._gemini_stream).parameters else {}
            async for chunk in self._gemini_stream(messages, system, max_tokens, **kwargs):
                yield chunk

    async def chat(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 2048,
        think: Optional[bool | str] = None,
        reasoning_level: Optional[str] = None,
    ) -> str:
        """Non-streaming — returns full response string."""
        chunks = []
        async for chunk in self.chat_stream(messages, system, max_tokens, think=think, reasoning_level=reasoning_level):
            chunks.append(chunk)
        return "".join(chunks)

    # ── Provider implementations ──────────────────────────────────────────────

    async def _anthropic_stream(self, messages, system, max_tokens, reasoning_level=None):
        from backend.llm_trace.guard import check_outbound_authorization
        check_outbound_authorization(
            provider=self.provider.value,
            model=self.model,
            url="https://api.anthropic.com/v1/messages",
            method="POST",
            component="AIClient._anthropic_stream",
        )
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=self.api_key)
        extra_kwargs = {}
        if reasoning_level:
            extra_kwargs["extra_body"] = {
                "output_config": {"effort": map_reasoning_effort(reasoning_level)}
            }
        async with client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            system=system or "",
            messages=messages,
            **extra_kwargs,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def _openai_stream(self, messages, system, max_tokens, reasoning_level=None):
        from backend.llm_trace.guard import check_outbound_authorization
        check_outbound_authorization(
            provider=self.provider.value,
            model=self.model,
            url="https://api.openai.com/v1/chat/completions",
            method="POST",
            component="AIClient._openai_stream",
        )
        import openai
        client = openai.AsyncOpenAI(api_key=self.api_key, timeout=55.0)

        m = self.model.lower()
        if m.startswith("gpt-6"):
            input_items = []
            if system:
                input_items.append({"role": "system", "content": system})
            input_items.extend(messages)
            resp_kwargs = {}
            if reasoning_level:
                resp_kwargs["reasoning"] = {"effort": map_reasoning_effort(reasoning_level)}
            if max_tokens:
                resp_kwargs["max_output_tokens"] = max_tokens
            stream = await client.responses.create(
                model=self.model,
                input=input_items,
                stream=True,
                **resp_kwargs,
            )
            async for event in stream:
                if getattr(event, "type", None) == "response.output_text.delta":
                    yield event.delta
                elif hasattr(event, "delta") and isinstance(event.delta, str):
                    yield event.delta
            return

        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        uses_completion_tokens = (
            m.startswith(("gpt-5", "o1", "o3", "o4"))
        )
        token_kwargs = (
            {"max_completion_tokens": max_tokens}
            if uses_completion_tokens
            else {"max_tokens": max_tokens}
        )
        extra_kwargs = {}
        if reasoning_level:
            extra_kwargs["reasoning_effort"] = map_reasoning_effort(reasoning_level)

        stream = await client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            stream=True,
            **token_kwargs,
            **extra_kwargs,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def _openrouter_stream(self, messages, system, max_tokens, reasoning_level=None):
        """OpenRouter is OpenAI-compatible — same client, different base URL."""
        from backend.llm_trace.guard import check_outbound_authorization
        check_outbound_authorization(
            provider=self.provider.value,
            model=self.model,
            url="https://openrouter.ai/api/v1/chat/completions",
            method="POST",
            component="AIClient._openrouter_stream",
        )
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

        extra_body = {
            "provider": {
                "require_parameters": True,
                "allow_fallbacks": False,
            }
        }
        if reasoning_level:
            extra_body["reasoning"] = {
                "effort": map_reasoning_effort(reasoning_level)
            }
        extra_kwargs = {"extra_body": extra_body}

        # OpenRouter normalises max_tokens vs max_completion_tokens internally
        # for downstream models, so we always send max_tokens here regardless
        # of which underlying provider is being routed to.
        stream = await client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            stream=True,
            max_tokens=max_tokens,
            **extra_kwargs,
        )
        async for chunk in stream:
            # Defensive: OpenRouter sometimes emits keepalive chunks with
            # an empty `choices` array before real tokens start flowing.
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def _ollama_stream(self, messages, system, max_tokens, think=None, reasoning_level=None, on_status=None):
        """Native Ollama chat streaming via POST /api/chat.

        Disables thinking trace leakage, handles text chunks, and bridges
        native Ollama tool_calls into canonical <action> blocks.
        """
        import httpx
        base_url = getattr(settings, "OLLAMA_BASE_URL", "http://127.0.0.1:11434")

        orch_system = system or ""
        orch_instruction = get_ollama_orchestration_instructions(reasoning_level)
        if orch_system:
            orch_system = f"{orch_system}\n\n{orch_instruction}"
        else:
            orch_system = orch_instruction

        full_messages = []
        if orch_system:
            full_messages.append({"role": "system", "content": orch_system})
        full_messages.extend(messages)

        options = get_ollama_reasoning_profile(reasoning_level, max_tokens)
        payload = {
            "model": self.model,
            "messages": full_messages,
            "stream": True,
            "options": options,
        }
        if think is not None:
            payload["think"] = bool(think)
        elif reasoning_level is not None:
            payload["think"] = True

        timeout = httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=5.0)
        has_signaled_thinking = False
        url = f"{base_url.rstrip('/')}/api/chat"

        import hashlib
        import asyncio
        req_sig = hashlib.sha256(
            f"{self.model}:{len(full_messages)}:{full_messages[-1].get('content', '') if full_messages else ''}".encode("utf-8")
        ).hexdigest()[:16]

        from backend.llm_trace.guard import (
            check_outbound_authorization,
            debouncer,
            UnauthorizedInferenceError,
            DebouncedDuplicateError,
        )

        try:
            event = check_outbound_authorization(
                provider=self.provider.value,
                model=self.model,
                url=url,
                method="POST",
                component="AIClient._ollama_stream",
                request_signature=req_sig,
            )
        except DebouncedDuplicateError as deb_err:
            logger.warning("Ollama stream debounced: %s", deb_err)
            return
        except UnauthorizedInferenceError:
            raise

        sig_key = f"{event.user_id_hash}:{self.provider.value}:{self.model}:{req_sig}"

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
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
        except asyncio.CancelledError:
            logger.info("Ollama stream cancelled by caller; closing cleanly.")
            raise
        finally:
            debouncer.release(sig_key)

    async def _gemini_stream(self, messages, system, max_tokens, reasoning_level=None):
        """Native Google Gemini chat streaming using official google.genai SDK."""
        from backend.llm_trace.guard import check_outbound_authorization
        check_outbound_authorization(
            provider=self.provider.value,
            model=self.model,
            url="https://generativelanguage.googleapis.com/v1beta/models",
            method="POST",
            component="AIClient._gemini_stream",
        )
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)

        contents = []
        for msg in messages:
            role = "model" if msg.get("role") == "assistant" else "user"
            content_text = msg.get("content") or ""
            contents.append(types.Content(role=role, parts=[types.Part.from_text(text=content_text)]))

        config_kwargs = {}
        if system:
            config_kwargs["system_instruction"] = system
        if max_tokens:
            config_kwargs["max_output_tokens"] = max_tokens

        effort = map_reasoning_effort(reasoning_level)
        config_kwargs["thinking_config"] = types.ThinkingConfig(
            thinking_level=effort,
            include_thoughts=True,
        )

        config = types.GenerateContentConfig(**config_kwargs)

        response_stream = await client.aio.models.generate_content_stream(
            model=self.model,
            contents=contents,
            config=config,
        )
        async for chunk in response_stream:
            text = chunk.text
            if text:
                yield text


    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 1024,
        think: Optional[bool | str] = None,
        reasoning_level: Optional[str] = None,
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
                    if round_idx == 0:
                        orch_inst = get_ollama_orchestration_instructions(reasoning_level)
                        if send_messages and send_messages[0].get("role") == "system":
                            send_messages[0] = {
                                "role": "system",
                                "content": f"{send_messages[0].get('content', '')}\n\n{orch_inst}"
                            }
                        else:
                            send_messages.insert(0, {"role": "system", "content": orch_inst})
                    elif round_idx > 0:
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

                    options = get_ollama_reasoning_profile(reasoning_level, max_tokens)
                    payload = {
                        "model": self.model,
                        "messages": send_messages,
                        "stream": False,
                        "options": options,
                    }
                    # Send tools on initial round to invoke capabilities; omit on subsequent
                    # rounds so the model synthesizes natural language rather than looping.
                    if round_idx == 0 and tools:
                        payload["tools"] = tools
                    if think is not None:
                        payload["think"] = bool(think)
                    elif reasoning_level is not None:
                        payload["think"] = True
                    if round_idx == 0 and payload.get("think") is not False and on_status:
                        stat_res = on_status("thinking")
                        if inspect.isawaitable(stat_res):
                            await stat_res

                    from backend.llm_trace.guard import check_outbound_authorization, debouncer
                    import hashlib
                    req_sig = hashlib.sha256(f"{self.model}:{len(send_messages)}:{round_idx}".encode("utf-8")).hexdigest()[:16]
                    event = check_outbound_authorization(
                        provider=self.provider.value,
                        model=self.model,
                        url=url,
                        method="POST",
                        component="AIClient.chat_with_tools",
                        request_signature=req_sig,
                    )

                    try:
                        resp = await client.post(url, json=payload)
                    finally:
                        debouncer.release(f"{event.user_id_hash}:{self.provider.value}:{self.model}:{req_sig}")
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
                        user_texts = [m.get("content", "") for m in current_messages if m.get("role") == "user"]
                        last_user = (user_texts[-1] if user_texts else "").strip().lower()

                        # Goal Continuity Check: Check for pending editable source confirmation
                        has_pending_source = False
                        recommended_source_title = ""
                        for m in current_messages:
                            if m.get("role") == "assistant":
                                c = m.get("content", "")
                                if (
                                    "Recommended Editable Source" in c
                                    or "Fonte Editável Recomendada" in c
                                ):
                                    has_pending_source = True
                                    m_title = re.search(r'(?:Recommended Editable Source|Fonte Editável Recomendada):\s*\[?([^\]\n]+)', c)
                                    if m_title:
                                        raw_t = m_title.group(1).split("—")[0].split("-")[0].strip()
                                        recommended_source_title = re.sub(r'[*_\[\]]', '', raw_t).strip()

                        is_confirmation = False
                        if last_user in (
                            "produce a video", "proceed", "yes", "confirm", "make it",
                            "sim", "pode produzir", "sim, pode produzir", "continue", "go ahead"
                        ) or any(
                            k in last_user for k in ("produce a video", "pode produzir", "make the video", "make the clips")
                        ):
                            is_confirmation = True

                        if has_pending_source and is_confirmation and tool_executor and not executed_tool_calls:
                            proj_name = f"{recommended_source_title} Highlights" if recommended_source_title else "Gaming Highlights"
                            proj_args = {"name": proj_name, "aspect_ratio": "9:16"}
                            if on_status:
                                s_res = on_status("calling_tool:create_project")
                                if inspect.isawaitable(s_res):
                                    await s_res
                            try:
                                proj_res = tool_executor("create_project", proj_args)
                                if inspect.isawaitable(proj_res):
                                    p_out = await proj_res
                                else:
                                    p_out = proj_res
                            except Exception as ex:
                                p_out = {"error": str(ex)}

                            executed_tool_calls.append({
                                "name": "create_project",
                                "arguments": proj_args,
                                "result": p_out,
                            })

                            p_info = p_out.get("output", {}) if isinstance(p_out, dict) else {}
                            pid = p_info.get("project_id", "active")
                            prev = p_info.get("revision", 1)

                            is_pt = _is_portuguese(last_user)
                            if is_pt:
                                final_content = (
                                    f"Dando continuidade à produção do vídeo. Criei o projeto canônico **{proj_name}** (formato 9:16, ID: `{pid}`, Revisão {prev}) "
                                    f"para o conteúdo selecionado.\n\n"
                                    f"Prosseguindo com a aquisição do material de origem para extrair os 3 clipes de 60 segundos com enquadramento vertical. "
                                    f"Você pode acompanhar o progresso aqui ou refinar na linha do tempo em `/motion`."
                                )
                            else:
                                final_content = (
                                    f"Continuing video production. Autonomously created canonical project **{proj_name}** (aspect ratio 9:16, Project ID: `{pid}`, Revision {prev}) "
                                    f"for our selected source.\n\n"
                                    f"Advancing to footage acquisition to extract the 3 distinct 60-second clips. "
                                    f"You can monitor the workflow here or review and refine the timeline in `/motion`."
                                )

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

                        final_content = msg.get("content", "").strip()
                        needs_synthesis_fallback = False
                        if executed_tool_calls:
                            if not final_content:
                                needs_synthesis_fallback = True
                            elif any(etc.get("name") == "search_catalog" for etc in executed_tool_calls):
                                sc_items = [
                                    (it.get("id") if isinstance(it, dict) else str(it))
                                    for etc in executed_tool_calls
                                    if etc.get("name") == "search_catalog"
                                    for it in (etc.get("result", {}).get("items", []) if isinstance(etc.get("result"), dict) else [])
                                    if (it.get("id") if isinstance(it, dict) else it)
                                ]
                                if sc_items and not any(sid.lower() in final_content.lower() for sid in sc_items[:3]):
                                    needs_synthesis_fallback = True

                            elif any(etc.get("name") == "search_youtube_trends" for etc in executed_tool_calls):
                                yt_items = [
                                    (it.get("title") if isinstance(it, dict) else str(it))
                                    for etc in executed_tool_calls
                                    if etc.get("name") == "search_youtube_trends"
                                    for it in (
                                        etc.get("result", {}).get("output", {}).get("results", [])
                                        if isinstance(etc.get("result"), dict)
                                        else []
                                    )
                                ]
                                if yt_items and not any(title[:15].lower() in final_content.lower() for title in yt_items[:2]):
                                    needs_synthesis_fallback = True

                        if needs_synthesis_fallback:
                            summaries = []
                            yt_calls = [etc for etc in executed_tool_calls if etc.get("name") == "search_youtube_trends"]
                            user_texts = [m.get("content", "") for m in current_messages if m.get("role") == "user"]
                            last_user_text = user_texts[-1] if user_texts else ""

                            if len(yt_calls) >= 2:
                                summaries.append(format_combined_trend_synthesis(
                                    last_user_text,
                                    yt_calls[0].get("result", {}),
                                    yt_calls[1].get("result", {})
                                ))
                            elif len(yt_calls) == 1:
                                summaries.append(format_trend_synthesis(last_user_text, yt_calls[0].get("result", {})))

                            for etc in executed_tool_calls:
                                if etc.get("name") == "search_youtube_trends":
                                    continue
                                res = etc.get("result", {})
                                is_err = bool(res.get("error") or res.get("status") == "error")
                                if etc.get("name") == "search_catalog":
                                    if is_err:
                                        summaries.append(f"Catalog search failed: {res.get('error', 'unknown error')}")
                                    else:
                                        items = res.get("items", []) if isinstance(res, dict) else []
                                        if items:
                                            lines = [f"Found {len(items)} matching catalog block(s):"]
                                            for it in items[:6]:
                                                if isinstance(it, dict):
                                                    lines.append(f"- **{it.get('title') or it.get('name')}** (`{it.get('id')}`)")
                                                else:
                                                    lines.append(f"- `{it}`")
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

                    # Autonomous continuation: if initial search returned no suitable source for multi-clip editing,
                    # immediately chain the targeted long-form search capability.
                    if (
                        tool_executor
                        and len(executed_tool_calls) == 1
                        and executed_tool_calls[0].get("name") == "search_youtube_trends"
                    ):
                        first_out = (
                            executed_tool_calls[0].get("result", {}).get("output", {})
                            if isinstance(executed_tool_calls[0].get("result"), dict)
                            else {}
                        )
                        if first_out.get("source_acquisition_status") == "no_suitable_source_found":
                            first_args = executed_tool_calls[0].get("arguments", {})
                            q_target = first_args.get("query") or first_args.get("niche") or "Fortnite"
                            long_form_args = {
                                "query": q_target,
                                "video_duration": "medium",
                                "purpose": "editable_source_search",
                                "target_clips": int(first_args.get("target_clips") or 3),
                                "clip_duration_sec": int(first_args.get("clip_duration_sec") or 60),
                            }
                            if on_status:
                                s_res = on_status("calling_tool:search_youtube_trends")
                                if inspect.isawaitable(s_res):
                                    await s_res
                            try:
                                long_exec_res = tool_executor("search_youtube_trends", long_form_args)
                                if inspect.isawaitable(long_exec_res):
                                    long_res = await long_exec_res
                                else:
                                    long_res = long_exec_res
                            except Exception as ex:
                                long_res = {"error": str(ex)}

                            executed_tool_calls.append({
                                "name": "search_youtube_trends",
                                "arguments": long_form_args,
                                "result": long_res,
                            })
                            current_messages.append({
                                "role": "tool",
                                "content": json.dumps(long_res) if not isinstance(long_res, str) else long_res,
                            })

                return {
                    "content": "Max tool execution rounds reached.",
                    "tool_calls": executed_tool_calls,
                    "rounds": max_tool_rounds,
                    "messages": current_messages,
                }

        elif self.provider == AIProvider.OPENAI and self.model.lower().startswith("gpt-6"):
            import openai
            client = openai.AsyncOpenAI(api_key=self.api_key, timeout=55.0)

            input_items = []
            if system:
                input_items.append({"role": "system", "content": system})
            input_items.extend(messages)

            resp_tools = [
                {
                    "type": "function",
                    "name": t.get("function", {}).get("name", t.get("name")),
                    "description": t.get("function", {}).get("description", t.get("description", "")),
                    "parameters": t.get("function", {}).get("parameters", t.get("parameters", {})),
                }
                for t in tools
            ]

            for round_idx in range(max_tool_rounds):
                resp_kwargs = {}
                if reasoning_level:
                    resp_kwargs["reasoning"] = {"effort": map_reasoning_effort(reasoning_level)}
                if max_tokens:
                    resp_kwargs["max_output_tokens"] = max_tokens
                if round_idx == 0 and resp_tools:
                    resp_kwargs["tools"] = resp_tools

                resp = await client.responses.create(
                    model=self.model,
                    input=input_items,
                    **resp_kwargs,
                )

                tool_calls_found = []
                final_text = ""
                for out_item in getattr(resp, "output", []):
                    item_type = getattr(out_item, "type", None) or (out_item.get("type") if isinstance(out_item, dict) else None)
                    if item_type == "function_call":
                        tool_calls_found.append(out_item)
                    elif item_type == "message":
                        content_list = getattr(out_item, "content", []) if hasattr(out_item, "content") else out_item.get("content", [])
                        for c in content_list:
                            c_type = getattr(c, "type", None) if hasattr(c, "type") else c.get("type")
                            if c_type == "text":
                                final_text += getattr(c, "text", "") if hasattr(c, "text") else c.get("text", "")

                if not tool_calls_found:
                    if on_token and final_text:
                        for tok in re.findall(r'\S+|\s+', final_text):
                            res = on_token(tok)
                            if inspect.isawaitable(res):
                                await res
                    return {
                        "content": final_text,
                        "tool_calls": executed_tool_calls,
                        "rounds": round_idx + 1,
                        "messages": current_messages,
                    }

                for tc in tool_calls_found:
                    call_id = getattr(tc, "call_id", None) or getattr(tc, "id", None) or (tc.get("call_id") or tc.get("id"))
                    fn_name = getattr(tc, "name", None) or (tc.get("name") if isinstance(tc, dict) else None)
                    fn_args = getattr(tc, "arguments", {}) or (tc.get("arguments") if isinstance(tc, dict) else {})
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
                        result = {"error": f"Unauthorized capability {fn_name}"}
                    else:
                        try:
                            CapabilityRegistry.validate_input(fn_name, fn_args)
                            if tool_executor:
                                exec_res = tool_executor(fn_name, fn_args)
                                result = await exec_res if inspect.isawaitable(exec_res) else exec_res
                            else:
                                result = {"status": "success", "data": fn_args}
                        except Exception as ex:
                            result = {"error": str(ex)}

                    executed_tool_calls.append({"name": fn_name, "arguments": fn_args, "result": result})
                    input_items.append({
                        "type": "function_call",
                        "call_id": call_id,
                        "name": fn_name,
                        "arguments": json.dumps(fn_args),
                    })
                    input_items.append({
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": json.dumps(result),
                    })

            return {
                "content": "Max tool execution rounds reached.",
                "tool_calls": executed_tool_calls,
                "rounds": max_tool_rounds,
                "messages": current_messages,
            }

        elif self.provider == AIProvider.GEMINI:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)

            gemini_tools = []
            if tools:
                func_decls = []
                for t in tools:
                    fn = t.get("function", t)
                    fn_name = fn.get("name")
                    fn_desc = fn.get("description", "")
                    fn_params = fn.get("parameters", {})
                    func_decls.append(
                        types.FunctionDeclaration(
                            name=fn_name,
                            description=fn_desc,
                            parameters=fn_params if fn_params else None,
                        )
                    )
                if func_decls:
                    gemini_tools.append(types.Tool(function_declarations=func_decls))

            effort = map_reasoning_effort(reasoning_level)
            config_kwargs = {}
            if system:
                config_kwargs["system_instruction"] = system
            if max_tokens:
                config_kwargs["max_output_tokens"] = max_tokens
            config_kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_level=effort,
                include_thoughts=True,
            )
            if gemini_tools:
                config_kwargs["tools"] = gemini_tools

            config = types.GenerateContentConfig(**config_kwargs)

            contents = []
            for msg in messages:
                m_role = msg.get("role")
                if m_role in ("assistant", "model"):
                    contents.append(types.Content(role="model", parts=[types.Part.from_text(text=msg.get("content") or "")]))
                elif m_role == "tool":
                    contents.append(types.Content(role="user", parts=[types.Part.from_function_response(name=msg.get("name", "tool"), response={"result": msg.get("content")})]))
                else:
                    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=msg.get("content") or "")]))

            for round_idx in range(max_tool_rounds):
                resp = await client.aio.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=config,
                )

                candidate = resp.candidates[0] if getattr(resp, "candidates", None) else None
                if not candidate or not candidate.content or not candidate.content.parts:
                    break

                # Preserve the candidate content (including thought signatures) in the history
                contents.append(candidate.content)

                tool_calls_found = []
                final_text = ""
                for part in candidate.content.parts:
                    if getattr(part, "function_call", None):
                        tool_calls_found.append(part.function_call)
                    elif getattr(part, "text", None) and not getattr(part, "thought", False):
                        final_text += part.text

                if not tool_calls_found:
                    if on_token and final_text:
                        for tok in re.findall(r'\S+|\s+', final_text):
                            res = on_token(tok)
                            if inspect.isawaitable(res):
                                await res
                    return {
                        "content": final_text,
                        "tool_calls": executed_tool_calls,
                        "rounds": round_idx + 1,
                        "messages": current_messages,
                    }

                response_parts = []
                for fc in tool_calls_found:
                    fn_name = getattr(fc, "name", None)
                    fn_args = getattr(fc, "args", {}) or {}
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
                        result = {"error": f"Unauthorized capability {fn_name}"}
                    else:
                        try:
                            CapabilityRegistry.validate_input(fn_name, fn_args)
                            if tool_executor:
                                exec_res = tool_executor(fn_name, fn_args)
                                result = await exec_res if inspect.isawaitable(exec_res) else exec_res
                            else:
                                result = {"status": "success", "data": fn_args}
                        except Exception as ex:
                            result = {"error": str(ex)}

                    executed_tool_calls.append({"name": fn_name, "arguments": fn_args, "result": result})
                    response_parts.append(
                        types.Part.from_function_response(
                            name=fn_name,
                            response=result if isinstance(result, dict) else {"result": result},
                        )
                    )

                contents.append(types.Content(role="user", parts=response_parts))

            return {
                "content": "Max tool execution rounds reached.",
                "tool_calls": executed_tool_calls,
                "rounds": max_tool_rounds,
                "messages": current_messages,
            }

        # Fallback for standard text chat
        res = await self.chat(
            messages,
            system=system,
            max_tokens=max_tokens,
            think=think,
            reasoning_level=reasoning_level,
        )
        return {
            "content": res,
            "tool_calls": [],
            "rounds": 1,
            "messages": current_messages + [{"role": "assistant", "content": res}],
        }


def _is_portuguese(text: str) -> bool:
    pt_markers = ("procure", "vídeo", "video viral", "transforme", "clipes", "você", "encontre", "buscar", "tendência", "jogos", "olá", "sim", "não", "pode")
    return any(w in (text or "").lower() for w in pt_markers)


def format_combined_trend_synthesis(last_user_text: str, res_ref: dict, res_edit: dict) -> str:
    """Format combined synthesis joining creative research references (Shorts) and editable long-form source footage."""
    is_pt = _is_portuguese(last_user_text)

    out_ref = res_ref.get("output", {}) if isinstance(res_ref, dict) else {}
    out_edit = res_edit.get("output", {}) if isinstance(res_edit, dict) else {}

    refs = out_ref.get("results", []) or out_ref.get("references", [])
    q = out_ref.get("query") or out_edit.get("query") or "Fortnite"

    rec = out_edit.get("recommended_editable_source") or out_edit.get("recommended_source")
    alt_edits = out_edit.get("editable_sources", [])
    creative_refs = out_ref.get("creative_references", []) or [r for r in refs if not r.get("suitability_for_3x60s", {}).get("is_editable_source")]

    def _fmt_dur(sec):
        if not sec:
            return "duração não verificada" if is_pt else "duration unverified"
        m, s = divmod(int(sec), 60)
        return f"{m}m {s:02d}s"

    if is_pt:
        lines = [f"Encontrei referências virais e selecionei uma fonte editável para '{q}':\n"]
        if rec:
            r_dur = _fmt_dur(rec.get("duration_seconds"))
            r_v = rec.get("views", 0)
            r_sc = rec.get("virality_score")
            r_sc_str = f"Score de Tendência: {r_sc:.1f}/100" if r_sc is not None else "Não pontuado"
            r_reason = rec.get("suitability_for_3x60s", {}).get("reason", "Conteúdo adequado para extração.")
            lines.append(f"**Fonte Editável Recomendada:** [{rec.get('title')}]({rec.get('video_url')}) — *{rec.get('author')}* ({r_v:,} views, {r_dur}, {r_sc_str})")
            lines.append(f"*Adequação Editorial:* {r_reason}")
            lines.append(f"Selecionada autonomamente com base na duração contínua ({r_dur}) e relevância para extração de 3 clipes de 60 segundos com margem editorial.\n")

        if creative_refs:
            lines.append("**Referências Criativas e Ganchos em Alta (Inspiração & Ritmo):**")
            for cr in creative_refs[:3]:
                cr_dur = _fmt_dur(cr.get("duration_seconds"))
                cr_sc = cr.get("virality_score")
                cr_sc_str = f"Score: {cr_sc:.1f}/100" if cr_sc is not None else "Não pontuado"
                lines.append(f"- **[{cr.get('title')}]({cr.get('video_url')})** — *{cr.get('author')}* ({cr.get('views', 0):,} views, {cr_dur}, {cr_sc_str}) [Referência de Formato]")
            lines.append("")

        if alt_edits and len(alt_edits) > 1:
            lines.append("**Outras Fontes Longas Disponíveis:**")
            for alt in alt_edits[1:4]:
                alt_dur = _fmt_dur(alt.get("duration_seconds"))
                alt_sc = alt.get("virality_score")
                alt_sc_str = f"Score: {alt_sc:.1f}/100" if alt_sc is not None else "Não pontuado"
                lines.append(f"- **[{alt.get('title')}]({alt.get('video_url')})** — *{alt.get('author')}* ({alt.get('views', 0):,} views, {alt_dur}, {alt_sc_str})")

        lines.append("\n**Próximo Passo:** Fonte selecionada pronta para verificação de acessibilidade e preparação dos 3 clipes de 60 segundos. Você pode prosseguir com a produção ou enviar material próprio pelo `/motion`.")
    else:
        lines = [f"Found trending viral references and selected an editable source for '{q}':\n"]
        if rec:
            r_dur = _fmt_dur(rec.get("duration_seconds"))
            r_v = rec.get("views", 0)
            r_sc = rec.get("virality_score")
            r_sc_str = f"Trend Score: {r_sc:.1f}/100" if r_sc is not None else "Not scored"
            r_reason = rec.get("suitability_for_3x60s", {}).get("reason", "Suitable long-form footage.")
            lines.append(f"**Recommended Editable Source:** [{rec.get('title')}]({rec.get('video_url')}) — *{rec.get('author')}* ({r_v:,} views, {r_dur}, {r_sc_str})")
            lines.append(f"*Source Suitability:* {r_reason}")
            lines.append(f"Selected autonomously based on continuous runtime ({r_dur}), viral trend metrics, and editorial buffer for 3 distinct 60-second clips.\n")

        if creative_refs:
            lines.append("**Trending Creative References (Hooks & Pacing):**")
            for cr in creative_refs[:3]:
                cr_dur = _fmt_dur(cr.get("duration_seconds"))
                cr_sc = cr.get("virality_score")
                cr_sc_str = f"Trend Score: {cr_sc:.1f}/100" if cr_sc is not None else "Not scored"
                lines.append(f"- **[{cr.get('title')}]({cr.get('video_url')})** — *{cr.get('author')}* ({cr.get('views', 0):,} views, {cr_dur}, {cr_sc_str}) [Reference Only]")
            lines.append("")

        if alt_edits and len(alt_edits) > 1:
            lines.append("**Alternative Editable Sources:**")
            for alt in alt_edits[1:4]:
                alt_dur = _fmt_dur(alt.get("duration_seconds"))
                alt_sc = alt.get("virality_score")
                alt_sc_str = f"Trend Score: {alt_sc:.1f}/100" if alt_sc is not None else "Not scored"
                lines.append(f"- **[{alt.get('title')}]({alt.get('video_url')})** — *{alt.get('author')}* ({alt.get('views', 0):,} views, {alt_dur}, {alt_sc_str})")

        lines.append("\n**Next Step:** Selected source candidate is ready for media verification and 3x 60-second clip preparation. Proceed with video production or upload custom footage anytime in `/motion`.")

    return "\n".join(lines)


def format_trend_synthesis(last_user_text: str, res: dict) -> str:
    """Format grounded trend discovery synthesis according to user language and editing intent."""
    is_pt = _is_portuguese(last_user_text)

    if not isinstance(res, dict):
        return "Nenhum resultado de tendências encontrado." if is_pt else "No trend results found."

    if res.get("error") or res.get("status") == "error":
        err_msg = res.get("error") or "erro desconhecido" if is_pt else "unknown error"
        return (
            f"A busca de tendências no YouTube falhou: {err_msg}" if is_pt
            else f"YouTube trend search encountered an error: {err_msg}"
        )

    step_out = res.get("output", {}) if isinstance(res, dict) else {}
    results = step_out.get("results", [])
    q = step_out.get("query", "Fortnite")
    rec = step_out.get("recommended_editable_source") or step_out.get("recommended_source")

    def _fmt_dur(sec):
        if not sec:
            return "duração não verificada" if is_pt else "duration unverified"
        m, s = divmod(int(sec), 60)
        return f"{m}m {s:02d}s"

    is_editing_request = any(w in (last_user_text or "").lower() for w in ("clip", "clips", "transform", "corte", "turn into", "extract", "60-second", "60s"))

    if results:
        creative_refs = [r for r in results if not r.get("suitability_for_3x60s", {}).get("is_editable_source")]
        editable_sources = [r for r in results if r.get("suitability_for_3x60s", {}).get("is_editable_source")]

        if is_pt:
            if is_editing_request:
                lines = [f"Encontrei {len(results)} referências virais em alta para '{q}':\n"]
                if rec:
                    r_dur = _fmt_dur(rec.get("duration_seconds"))
                    r_v = rec.get("views", 0)
                    r_sc = rec.get("virality_score")
                    r_sc_str = f"Score de Tendência: {r_sc:.1f}/100" if r_sc is not None else "Não pontuado"
                    r_reason = rec.get("suitability_for_3x60s", {}).get("reason", "Conteúdo adequado para extração.")
                    lines.append(f"**Fonte Editável Recomendada:** [{rec.get('title')}]({rec.get('video_url')}) — *{rec.get('author')}* ({r_v:,} views, {r_dur}, {r_sc_str})")
                    lines.append(f"*Adequação Editorial:* {r_reason}")
                    lines.append(f"Selecionada autonomamente com base na duração contínua ({r_dur}) e adequação para extração de 3 clipes de 60 segundos com margem editorial.\n")
                else:
                    lines.append("*Status de Aquisição:* Nenhuma fonte longa editável (>= 240s) foi identificada entre as referências iniciais. Iniciando busca direcionada por fontes longas de gameplay.\n")

                if creative_refs:
                    lines.append("**Referências Criativas e Ganchos em Alta (Inspiração & Ritmo):**")
                    for cr in creative_refs[:3]:
                        cr_dur = _fmt_dur(cr.get("duration_seconds"))
                        cr_sc = cr.get("virality_score")
                        cr_sc_str = f"Score: {cr_sc:.1f}/100" if cr_sc is not None else "Não pontuado"
                        lines.append(f"- **[{cr.get('title')}]({cr.get('video_url')})** — *{cr.get('author')}* ({cr.get('views', 0):,} views, {cr_dur}, {cr_sc_str}) [Referência de Formato]")
                    lines.append("")

                if editable_sources and len(editable_sources) > 1:
                    lines.append("**Outras Fontes Longas Disponíveis:**")
                    for alt in editable_sources[1:4]:
                        alt_dur = _fmt_dur(alt.get("duration_seconds"))
                        alt_sc = alt.get("virality_score")
                        alt_sc_str = f"Score: {alt_sc:.1f}/100" if alt_sc is not None else "Não pontuado"
                        lines.append(f"- **[{alt.get('title')}]({alt.get('video_url')})** — *{alt.get('author')}* ({alt.get('views', 0):,} views, {alt_dur}, {alt_sc_str})")

                lines.append("\n**Próximo Passo:** Fonte selecionada pronta para verificação de acessibilidade e preparação dos 3 clipes de 60 segundos. Você pode prosseguir com a produção ou enviar material próprio pelo `/motion`.")
            else:
                lines = [f"Encontrei {len(results)} referências e tendências virais para '{q}':\n"]
                for it in results[:6]:
                    dur_str = _fmt_dur(it.get("duration_seconds"))
                    sc = it.get("virality_score")
                    sc_str = f"Score: {sc:.1f}/100" if sc is not None else "Não pontuado"
                    role_tag = "[Fonte Longa]" if it.get("suitability_for_3x60s", {}).get("is_editable_source") else "[Referência / Short]"
                    lines.append(f"- **[{it.get('title')}]({it.get('video_url')})** — *{it.get('author')}* ({it.get('views', 0):,} views, {dur_str}, {sc_str}) {role_tag}")
                lines.append("\n*Resultados rotulados como referências de pesquisa para análise de tópicos, ganchos e interesse do público.*")
        else:
            if is_editing_request:
                lines = [f"Found {len(results)} trending viral references for '{q}':\n"]
                if rec:
                    r_dur = _fmt_dur(rec.get("duration_seconds"))
                    r_v = rec.get("views", 0)
                    r_sc = rec.get("virality_score")
                    r_sc_str = f"Trend Score: {r_sc:.1f}/100" if r_sc is not None else "Not scored"
                    r_reason = rec.get("suitability_for_3x60s", {}).get("reason", "Suitable long-form footage.")
                    lines.append(f"**Recommended Editable Source:** [{rec.get('title')}]({rec.get('video_url')}) — *{rec.get('author')}* ({r_v:,} views, {r_dur}, {r_sc_str})")
                    lines.append(f"*Source Suitability:* {r_reason}")
                    lines.append(f"Selected autonomously based on continuous runtime ({r_dur}), viral trend metrics, and editorial buffer for 3 distinct 60-second clips.\n")
                else:
                    lines.append("*Source Acquisition Status:* No suitable long-form source footage (>= 240s) was identified among initial trend references. Initiating targeted search for substantial editable footage.\n")

                if creative_refs:
                    lines.append("**Trending Creative References (Hooks & Pacing):**")
                    for cr in creative_refs[:3]:
                        cr_dur = _fmt_dur(cr.get("duration_seconds"))
                        cr_sc = cr.get("virality_score")
                        cr_sc_str = f"Trend Score: {cr_sc:.1f}/100" if cr_sc is not None else "Not scored"
                        lines.append(f"- **[{cr.get('title')}]({cr.get('video_url')})** — *{cr.get('author')}* ({cr.get('views', 0):,} views, {cr_dur}, {cr_sc_str}) [Reference Only]")
                    lines.append("")

                if editable_sources and len(editable_sources) > 1:
                    lines.append("**Alternative Editable Sources:**")
                    for alt in editable_sources[1:4]:
                        alt_dur = _fmt_dur(alt.get("duration_seconds"))
                        alt_sc = alt.get("virality_score")
                        alt_sc_str = f"Trend Score: {alt_sc:.1f}/100" if alt_sc is not None else "Not scored"
                        lines.append(f"- **[{alt.get('title')}]({alt.get('video_url')})** — *{alt.get('author')}* ({alt.get('views', 0):,} views, {alt_dur}, {alt_sc_str})")

                lines.append("\n**Next Step:** Selected source candidate is ready for media verification and 3x 60-second clip preparation. Proceed with video production or upload custom footage anytime in `/motion`.")
            else:
                lines = [f"Found {len(results)} trending viral references for '{q}':\n"]
                for it in results[:6]:
                    dur_str = _fmt_dur(it.get("duration_seconds"))
                    sc = it.get("virality_score")
                    sc_str = f"Trend Score: {sc:.1f}/100" if sc is not None else "Not scored"
                    role_tag = "[Long-form]" if it.get("suitability_for_3x60s", {}).get("is_editable_source") else "[Reference / Short]"
                    lines.append(f"- **[{it.get('title')}]({it.get('video_url')})** — *{it.get('author')}* ({it.get('views', 0):,} views, {dur_str}, {sc_str}) {role_tag}")
                lines.append("\n*Results labeled as research references for content trends, hooks, and audience interest.*")
        return "\n".join(lines)
    else:
        return (
            f"Nenhum vídeo em alta encontrado para '{q}'." if is_pt
            else f"No trending videos found for '{q}'."
        )


# ── Factory ───────────────────────────────────────────────────────────────────

def _resolve_user_provider_and_key(user_settings, target_provider: Optional[AIProvider] = None) -> tuple[Optional[AIProvider], Optional[str]]:
    """Read provider preference and decrypted API key from UserSettings, if set.

    Checks independent per-provider keys (openai_api_key_encrypted, anthropic_api_key_encrypted,
    gemini_api_key_encrypted, openrouter_api_key_encrypted), with legacy fallback to
    ai_api_key_encrypted when matching active provider.
    """
    if not user_settings:
        return None, None

    provider = target_provider
    if not provider:
        provider_str = (getattr(user_settings, "ai_provider", None) or "").lower().strip()
        if not provider_str:
            return None, None
        try:
            provider = AIProvider(provider_str)
        except ValueError:
            return None, None

    if provider == AIProvider.OLLAMA:
        base_url = getattr(user_settings, "ollama_base_url", None)
        return provider, base_url or "ollama_local"

    # 1. Independent per-provider key
    col_name = f"{provider.value}_api_key_encrypted"
    encrypted_key = getattr(user_settings, col_name, None)
    if encrypted_key:
        api_key = decrypt_safe(encrypted_key)
        if api_key:
            return provider, api_key

    # 2. Legacy fallback to ai_api_key_encrypted if active provider matches
    active_prov_str = (getattr(user_settings, "ai_provider", None) or "").lower().strip()
    if active_prov_str == provider.value:
        enc_legacy = getattr(user_settings, "ai_api_key_encrypted", None)
        if enc_legacy:
            api_key = decrypt_safe(enc_legacy)
            if api_key:
                return provider, api_key

    return None, None


def is_model_compatible_with_provider(model: Optional[str], provider: AIProvider) -> bool:
    """Check if a model name is structurally compatible with the provider."""
    if not model or not isinstance(model, str):
        return True
    m = model.strip().lower()
    # Vendor-prefixed slugs (e.g. "anthropic/claude-...", "google/...") only work with OpenRouter
    if "/" in m and provider != AIProvider.OPENROUTER:
        return False
    if provider == AIProvider.ANTHROPIC:
        if m.startswith(("gpt-", "o1", "o3", "o4", "openai", "text-davinci", "gemini-", "gemma")):
            return False
    elif provider == AIProvider.OPENAI:
        if m.startswith(("claude-", "anthropic", "gemini-", "gemma")):
            return False
    elif provider == AIProvider.GEMINI:
        if m.startswith(("gpt-", "o1", "o3", "o4", "claude-", "anthropic", "google/")):
            return False
        if not m.startswith("gemini-"):
            return False
    elif provider == AIProvider.OLLAMA:
        if m.startswith(("gpt-", "o1", "o3", "o4", "claude-", "anthropic/", "google/")):
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
    require_explicit: bool = False,
    **_kwargs,
) -> AIClient:
    """
    Return a configured AI client.

    Resolution order:
      1. If pinned_provider is provided, honor pinned execution configuration.
      2. UserSettings.ai_provider + UserSettings per-provider independent encrypted key.
      3. .env keys (ANTHROPIC_API_KEY → OPENAI_API_KEY → OPENROUTER_API_KEY → GEMINI_API_KEY)
      4. Local Ollama fallback if running on OLLAMA_BASE_URL (strictly when no cloud provider was requested)
      5. Raise AIKeyMissingError with setup instructions.
    """
    user_prov = getattr(user_settings, "ai_provider", None) if user_settings else None
    user_model = getattr(user_settings, "ai_model", None) if user_settings else None
    effective_prov = pinned_provider or user_prov
    effective_model = pinned_model or user_model

    if require_explicit:
        if not effective_prov or not effective_model:
            raise AIProviderUnselectedError("No AI model selected. Choose a model in Global Chat to continue.")

    # 1. Pinned provider execution
    if pinned_provider:
        prov_str = str(pinned_provider).lower().strip()
        if prov_str in ("google_gemini", "google"):
            prov_str = "gemini"
        try:
            target_prov = AIProvider(prov_str)
        except ValueError:
            target_prov = None

        if target_prov:
            if target_prov == AIProvider.OLLAMA:
                resolved_model = sanitize_model_for_provider(effective_model, target_prov)
                raw_base_url = getattr(user_settings, "ollama_base_url", None) if user_settings else None
                base_url = raw_base_url.strip() if isinstance(raw_base_url, str) and raw_base_url.strip() else None
                return AIClient(provider=target_prov, api_key=base_url or "ollama_local", model=resolved_model)

            # Check independent user key for this specific provider first
            _, user_key = _resolve_user_provider_and_key(user_settings, target_provider=target_prov)
            key = user_key
            if not key:
                if target_prov == AIProvider.ANTHROPIC and settings.ANTHROPIC_API_KEY:
                    key = settings.ANTHROPIC_API_KEY
                elif target_prov == AIProvider.OPENAI and settings.OPENAI_API_KEY:
                    key = settings.OPENAI_API_KEY
                elif target_prov == AIProvider.OPENROUTER and settings.OPENROUTER_API_KEY:
                    key = settings.OPENROUTER_API_KEY
                elif target_prov == AIProvider.GEMINI and getattr(settings, "GEMINI_API_KEY", None):
                    key = settings.GEMINI_API_KEY

            if not key:
                raise AIKeyMissingError(
                    f"No API key configured for pinned provider '{target_prov.value}'."
                )
            resolved_model = sanitize_model_for_provider(effective_model, target_prov)
            return AIClient(provider=target_prov, api_key=key, model=resolved_model)

    # 2. User-configured provider in Settings (strict: never silently fall back)
    configured_provider_str = (getattr(user_settings, "ai_provider", None) or "").lower().strip() if user_settings else ""
    if configured_provider_str:
        if configured_provider_str in ("google_gemini", "google"):
            configured_provider_str = "gemini"
        try:
            cfg_prov = AIProvider(configured_provider_str)
        except ValueError:
            cfg_prov = None

        if cfg_prov:
            if cfg_prov == AIProvider.OLLAMA:
                resolved_model = sanitize_model_for_provider(effective_model, cfg_prov)
                raw_base_url = getattr(user_settings, "ollama_base_url", None) if user_settings else None
                base_url = raw_base_url.strip() if isinstance(raw_base_url, str) and raw_base_url.strip() else None
                return AIClient(provider=cfg_prov, api_key=base_url or "ollama_local", model=resolved_model)

            # Cloud provider explicitly chosen in settings: must find valid key or fail
            _, user_key = _resolve_user_provider_and_key(user_settings, target_provider=cfg_prov)
            key = user_key
            if not key:
                if cfg_prov == AIProvider.ANTHROPIC and settings.ANTHROPIC_API_KEY:
                    key = settings.ANTHROPIC_API_KEY
                elif cfg_prov == AIProvider.OPENAI and settings.OPENAI_API_KEY:
                    key = settings.OPENAI_API_KEY
                elif cfg_prov == AIProvider.OPENROUTER and settings.OPENROUTER_API_KEY:
                    key = settings.OPENROUTER_API_KEY
                elif cfg_prov == AIProvider.GEMINI and getattr(settings, "GEMINI_API_KEY", None):
                    key = settings.GEMINI_API_KEY

            if not key:
                raise AIKeyMissingError(
                    f"Provider '{cfg_prov.value}' selected in Settings, but no API key configured. "
                    f"Set {cfg_prov.value.upper()}_API_KEY in .env or enter your key in Settings."
                )
            resolved_model = sanitize_model_for_provider(effective_model, cfg_prov)
            return AIClient(provider=cfg_prov, api_key=key, model=resolved_model)

    # 3. Unpinned & unconfigured: check .env in priority order
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
    if getattr(settings, "GEMINI_API_KEY", None):
        resolved_model = sanitize_model_for_provider(effective_model, AIProvider.GEMINI)
        return AIClient(
            provider=AIProvider.GEMINI,
            api_key=settings.GEMINI_API_KEY,
            model=resolved_model,
        )

    # 4. Local Ollama fallback if running (strictly when no cloud provider was requested)
    if _is_ollama_available():
        resolved_model = sanitize_model_for_provider(effective_model, AIProvider.OLLAMA)
        return AIClient(
            provider=AIProvider.OLLAMA,
            api_key="ollama_local",
            model=resolved_model,
        )

    raise AIKeyMissingError(
        "No AI provider configured. Set ANTHROPIC_API_KEY, OPENAI_API_KEY, "
        "OPENROUTER_API_KEY, or GEMINI_API_KEY in your .env, run Ollama locally, or configure your provider in Settings."
    )

