# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Live Ollama Gemma 4 E4B Execution Verification.

Runs real local inference against installed Ollama daemon (127.0.0.1:11434).
Compares Low, Medium, and Hard orchestration and execution metrics:
- Sanitized request options and orchestration prompts.
- Latency and token generation metrics (prompt_eval_count, eval_count).
- Presence and characteristics of native Gemma 4 thinking tokens.
- Both ordinary conversation and registered read-only tool usage (search_catalog).
"""
import asyncio
import json
import time
import urllib.request
import pytest

from backend.core.ai_provider import (
    AIProvider,
    AIClient,
    get_ollama_reasoning_profile,
    get_ollama_orchestration_instructions,
)
from backend.core.capabilities import CapabilityRegistry


REPRESENTATIVE_CHAT_PROMPT = (
    "A 6Clips gaming video edit has 3 key segments: Hook (4s), Gameplay (18s), and Call-To-Action (5s). "
    "If the gameplay speed is adjusted to 1.5x while keeping the hook and CTA unchanged, "
    "calculate the exact new total duration and describe how the edit pace is affected."
)


@pytest.mark.asyncio
async def test_live_ollama_gemma4_chat_comparison():
    results = {}

    for lvl in ["low", "medium", "hard"]:
        options = get_ollama_reasoning_profile(lvl)
        orch_instruction = get_ollama_orchestration_instructions(lvl)

        payload = {
            "model": "gemma4:e4b",
            "messages": [
                {"role": "system", "content": f"You are 6Clips video assistant.\n\n{orch_instruction}"},
                {"role": "user", "content": REPRESENTATIVE_CHAT_PROMPT},
            ],
            "stream": False,
            "think": True,
            "options": options,
        }

        t0 = time.time()
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        elapsed = time.time() - t0

        msg = data.get("message", {})
        thinking_text = msg.get("thinking", "")
        content_text = msg.get("content", "")

        metrics = {
            "level": lvl,
            "duration_sec": round(elapsed, 2),
            "prompt_eval_count": data.get("prompt_eval_count", 0),
            "eval_count": data.get("eval_count", 0),
            "num_predict": options["num_predict"],
            "temperature": options["temperature"],
            "top_p": options["top_p"],
            "thinking_chars": len(thinking_text),
            "has_native_thinking": bool(thinking_text),
            "content_chars": len(content_text),
            "done": data.get("done", False),
        }
        results[lvl] = metrics
        print(f"\n[Ollama {lvl.upper()}] {elapsed:.2f}s | eval_tokens: {metrics['eval_count']} | thinking_chars: {len(thinking_text)}")

    # Verify that all profiles completed with native thinking active
    assert results["low"]["done"] is True
    assert results["medium"]["done"] is True
    assert results["hard"]["done"] is True
    assert results["low"]["has_native_thinking"] is True
    assert results["medium"]["has_native_thinking"] is True
    assert results["hard"]["has_native_thinking"] is True

    # Verify distinct bounded options
    assert results["low"]["num_predict"] == 1024
    assert results["medium"]["num_predict"] == 2048
    assert results["hard"]["num_predict"] == 4096

    with open("tests/live_ollama_chat_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)


@pytest.mark.asyncio
async def test_live_ollama_gemma4_tool_usage():
    tool_results = {}
    client = AIClient(provider=AIProvider.OLLAMA, api_key="local", model="gemma4:e4b")
    tools = CapabilityRegistry.to_tool_definitions()

    for lvl in ["low", "hard"]:
        t0 = time.time()
        res = await client.chat_with_tools(
            messages=[{"role": "user", "content": "Find catalog items for speed ramp transitions using search_catalog."}],
            tools=tools,
            system="You are 6Clips assistant.",
            reasoning_level=lvl,
            max_tokens=2048,
        )
        elapsed = time.time() - t0
        tool_results[lvl] = {
            "duration_sec": round(elapsed, 2),
            "rounds": res.get("rounds", 0),
            "tool_calls_count": len(res.get("tool_calls", [])),
            "content_chars": len(res.get("content", "")),
        }
        print(f"\n[Ollama Tool {lvl.upper()}] {elapsed:.2f}s | rounds: {res.get('rounds')} | tool_calls: {len(res.get('tool_calls', []))}")

    with open("tests/live_ollama_tool_results.json", "w", encoding="utf-8") as f:
        json.dump(tool_results, f, indent=2)
