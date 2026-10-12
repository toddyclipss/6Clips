# Rule: Native Local AI Provider Integration ("Hardware-Aware, Not Hardware-Limited")

## 1. Local-First Provider Support & Strict Provider Selection
- Local model runtimes (such as Ollama on `http://127.0.0.1:11434`) must be supported natively alongside cloud BYOK providers without requiring external paid credentials or API keys.
- When an external cloud provider (OpenAI, Anthropic, OpenRouter) is explicitly selected or pinned, missing API keys must immediately raise `AIKeyMissingError` and MUST NEVER silently fall back to Ollama.
- Local Ollama fallback applies strictly when no specific cloud provider is pinned or configured.
- When a user selects `ollama` as their provider or pins it via execution headers/websockets, API key presence checks must be bypassed using local credentials (`ollama_local`).

## 2. Dynamic Discovery ("Hardware-Aware, Not Hardware-Limited")
- Never hardcode hardware constraints (RAM, VRAM, context length, parameter counts, or quantization limits) into application code or model registries.
- Available models and model metadata must be discovered dynamically via local endpoints (e.g., `GET /api/tags`, `GET /api/ps`, and `POST /api/show`) with short, non-blocking timeouts (<= 2.0s).
- The system must never automatically install, download, delete, replace, or quantize models without explicit user command.

## 3. Capability-Aware Thinking Control & Monologue Suppression
- Models with reasoning/thinking capabilities must have their thinking controls discovered dynamically via `POST /api/show` (`thinking.values`, `thinking.default`) rather than hardcoding `"think": false`.
- The user may toggle thinking on or off in the Global Chat UI or Settings. When explicitly configured, pass native `think: True/False` in requests; if unset, honor the model's discovered default.
- Stream chunks must be strictly filtered to `message.content` (ignoring internal monologue tokens from `message.thinking` or raw thought blocks) so that raw thought traces never leak into user-facing chat response text, while allowing an optional neutral thinking status indicator.

## 4. Structured Tool-Call Translation & Native Multi-Turn Tooling
- When local models emit structured function/tool calls (e.g. `tool_calls: [...]`), the provider client must translate them into canonical agent action blocks (`<action>{"type": name, ...args}</action>`) and support multi-turn native tool loops (`tools: [...]` -> `tool_calls` -> validation against `CapabilityRegistry` -> execution -> tool result message `{"role": "tool", "content": ...}` -> final contextual answer).
- Tool calls must validate against `CapabilityRegistry`, reject unauthorized tools, and enforce `ProjectService` CAS with `expected_revision`.
