# 6CLIPS / VIRALMINT — P0 DEFECT RECOVERY REPORT
## Agent 2: Main Agent Chat, WebSocket, Provider/Model & User Intent Provenance

- **Agent:** Agent 2 (A2) of 5
- **Branch:** `p0fix/02-ws-chat-provider-intent`
- **Base Commit SHA:** `7a76da6ec7bb0fce8e95a38941ab4e7ac8fa68a1`
- **Repository Root:** `c:\Users\toddy\Desktop\ViralMint`
- **Dedicated Worktree:** `c:\Users\toddy\Desktop\ViralMint-p0fix-02-ws`
- **Execution Date:** 2026-10-16

---

## 1. Executive Summary & Incident Reproduction

### The User-Observed Failure
In the 6Clips Main Agent UI, the user selected **Ollama → Gemma 4 E4B · High** and submitted the exact prompt:
```text
analise e edite esse video em ingles https://www.youtube.com/watch?v=FV93IVwJP_4
```
The production application terminated with:
```text
Outcome Status: FAILED_TERMINAL
AI model inference failed on ollama/gemma4:e4b:
BLOCKED_UNAUTHORIZED_BACKGROUND_AI: Outbound generative call to
'ollama/gemma4:e4b' blocked at boundary — missing active authorization
context (trigger=unknown).
```

### Root Cause Analysis (Source-Level Line References)
1. **Unwrapped Knowledge Orchestrator Call**:
   In `backend/api/chat.py` (lines 337–363 on baseline commit `7a76da6`), when `is_knowledge_first` is enabled (default `settings.KNOWLEDGE_FIRST = True`), incoming WebSocket `chat_message` calls were dispatched directly to `KnowledgeChatOrchestrator.handle_video_request()` and `KnowledgeChatOrchestrator.revise_deliverable()`.
2. **Context Var Absence**:
   Unlike the legacy `planner.handle_message()` path (which was wrapped in `inference_authorization_context(trigger=TRIGGER_EXPLICIT_CHAT_SUBMIT)` inside `backend/agents/planner.py`), the knowledge orchestrator path did not establish the `InferenceAuthorizationContext`. Consequently, `_CURRENT_CONTEXT` in `backend/llm_trace/context.py` evaluated to `None`.
3. **Fail-Closed Boundary Guard**:
   When downstream inference was invoked (`backend/llm_trace/guard.py` line 215), the guard correctly observed `active_context is None` with `trigger=unknown`, raising `UnauthorizedInferenceError: BLOCKED_UNAUTHORIZED_BACKGROUND_AI`.
4. **Untrusted Client Artifacts**:
   The frontend composer (`ChatPanel.jsx`, `LiquidMultimodalInput.jsx`) had previously sent client flags such as `authorized: true`. These client flags cannot and must not be trusted as authorization proof by the server.

---

## 2. Implemented Architecture & Scope

### Scope of Exclusive Write Ownership
All changes were strictly confined to Agent 2's assigned boundaries:
- `backend/api/chat.py`
- `frontend/src/components/chat/ChatPanel.jsx`
- `frontend/src/components/chat/LiquidMultimodalInput.jsx`
- `frontend/src/hooks/useWebSocket.js`
- `tests/p0_recovery/a2/**`
- `tools/p0_recovery_a2/**`

**Zero modifications** were made to peer files (`backend/llm_trace/**` [A1], `backend/core/ai_provider.py` [A1], `backend/oaas_knowledge_orchestrator/**` [A5], `backend/services/**` [A3], `frontend/src/pages/**` [A4]).

### Core Technical Changes

#### A. Server-Authored Execution Provenance Adapter Seam (`backend/api/chat.py`)
- Created `server_inference_authorization_context(user_id, correlation_id, run_id, job_id)`.
- Authoritatively binds `trigger = TRIGGER_EXPLICIT_CHAT_SUBMIT` (`"explicit_chat_submit"`) for direct user chat turns.
- Wraps both `KnowledgeChatOrchestrator.handle_video_request()`, `KnowledgeChatOrchestrator.revise_deliverable()`, and legacy planner turns.
- Client-supplied `authorized` or `trigger` fields are ignored; execution provenance is strictly authored by the server.

#### B. In-Flight Idempotency & Duplicate Suppression (`backend/api/chat.py`)
- Implemented `MessageDeduplicator` (30s TTL, thread/async-safe).
- Keyed by `(user_id, client_message_id)` or `(user_id, user_intent_id)`.
- Automatically suppresses duplicate submissions caused by double clicks, network retries, or WebSocket reconnect resends without triggering duplicate inference.

#### C. Model & Effort Propagation & Fail-Closed Validation (`backend/api/chat.py`)
- Enforces explicit selection of provider, model, and reasoning effort.
- Rejects unselected model before invoking inference with `"No AI model selected. Choose a model in Global Chat to continue."`
- Rejects unselected effort before invoking inference with `"No reasoning effort selected. Choose Low, Medium, or High in Global Chat to continue."`
- Preserves exact installed runtime tag (`ollama/gemma4:e4b`) without silent provider fallback or mock generation.
- Preserves exact YouTube URL with uppercase `I` (`https://www.youtube.com/watch?v=FV93IVwJP_4`) verbatim.

#### D. Fail-Closed Error Reporting (`backend/api/chat.py`)
- In case of an orchestrator exception, the handler immediately transmits an `oaas_outcome_update` with `state="FAILED_TERMINAL"` and a `chat_error` referencing stable `run_id` and `correlation_id`.
- The user UI is unlocked and permitted to retry; no synthetic title cards over black or silent fallback providers are dispatched.

#### E. Client Payload Normalization (`ChatPanel.jsx`, `LiquidMultimodalInput.jsx`)
- Generates unique `client_message_id` and `correlation_id`.
- Forwards `provider`, `model`, `reasoning_level`, `user_intent_id`, `project_id`, `revision_id`.
- Completely removed `authorized: true` bypass flag from client payloads.

#### F. Stale Outcome Isolation (`useWebSocket.js`)
- Filtered `oaas_outcome_update` and `chat_error` handlers so events from older or inactive chat sessions do not pollute or overwrite the active session state.

---

## 3. Automated Test Execution

The test suite in `tests/p0_recovery/a2/` was executed against Python 3.11 with `SIXCLIPS_REQUIRE_EXPLICIT_AUTH=1`.

```text
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\toddy\Desktop\ViralMint-p0fix-02-ws
configfile: pyproject.toml
plugins: anyio-4.15.1, asyncio-1.4.0
collected 9 items

tests/p0_recovery/a2/test_frontend_chat_contract.py::test_frontend_payload_contract_and_outcome_filter PASSED [ 11%]
tests/p0_recovery/a2/test_ws_chat_contract.py::test_ollama_gemma4_propagation_and_server_context PASSED       [ 22%]
tests/p0_recovery/a2/test_ws_chat_contract.py::test_unselected_model_or_effort_rejected_fail_closed PASSED  [ 33%]
tests/p0_recovery/a2/test_ws_chat_contract.py::test_untrusted_client_bypass_ignored PASSED                   [ 44%]
tests/p0_recovery/a2/test_ws_chat_contract.py::test_duplicate_submission_suppressed PASSED                   [ 55%]
tests/p0_recovery/a2/test_ws_chat_contract.py::test_exact_youtube_url_preservation PASSED                    [ 66%]
tests/p0_recovery/a2/test_ws_chat_contract.py::test_revision_request_server_provenance PASSED               [ 77%]
tests/p0_recovery/a2/test_ws_chat_contract.py::test_fail_closed_error_handling PASSED                        [ 88%]
tests/p0_recovery/a2/test_ws_chat_contract.py::test_e2e_user_observed_incident_with_strict_guard PASSED     [100%]

======================== 9 passed, 1 warning in 4.43s =========================
```

### Frontend Build Verification
`npm run build` executed in `frontend/`:
```text
✓ built in 19.38s
dist/assets/index-CyKXfPl8.js 900.30 kB │ gzip: 283.22 kB
```
Zero build errors, zero bundle regressions.

---

## 4. Real Runtime Execution & Browser Evidence

### Real Ollama Inference Execution
In an isolated live stack with local Ollama (`gemma4:e4b`, 10 GB, ID `bb027d30ecf5`) and `SIXCLIPS_REQUIRE_EXPLICIT_AUTH=1`:
1. The WebSocket request was submitted via Microsoft Edge.
2. Server established `TRIGGER_EXPLICIT_CHAT_SUBMIT` context.
3. Outbound inference to `http://127.0.0.1:11434/api/chat` was **ALLOWED** by `backend/llm_trace/guard.py`.
4. Inference succeeded and generated native motion scenes:
   ```text
   INFO backend.oaas_knowledge_orchestrator.motion_generator_adapter | Committed native_motion_v1 spec to project 97375501-9652-462e-acd3-df5de48114b0 at revision 6
   INFO backend.oaas_knowledge_orchestrator.state_machine | KnowledgeOrchestrator state: VALIDATING -> RENDERING (Rendering 1 physical MP4 deliverable(s))
   INFO backend.original_creation.renderer | ORIGINAL_RENDER complete | path=..._final.mp4 | size=175757 bytes | dur=6.86s
   INFO backend.oaas_knowledge_orchestrator.state_machine | KnowledgeOrchestrator state: RENDERING -> VIDEO_VERIFIED (Verified 1 physical MP4(s) via ffprobe and SHA-256 fingerprint)
   INFO backend.oaas_knowledge_orchestrator.state_machine | KnowledgeOrchestrator state: VIDEO_VERIFIED -> REVIEW_READY
   ```
5. WebSocket emitted `oaas_outcome_update` with `state="REVIEW_READY"` and `chat_done`.

---

## 5. Gate Ledger

| Gate | Target / Requirement | Status | Proof / Evidence Reference |
|---|---|---|---|
| **P0-A2-01** | Exact Ollama `gemma4:e4b` propagation | **PASS** | `test_ws_chat_contract.py::test_ollama_gemma4_propagation_and_server_context` |
| **P0-A2-02** | Strict explicit model/effort selection | **PASS** | `test_ws_chat_contract.py::test_unselected_model_or_effort_rejected_fail_closed` |
| **P0-A2-03** | Server-authored execution provenance | **PASS** | `test_ws_chat_contract.py::test_untrusted_client_bypass_ignored` |
| **P0-A2-04** | Duplicate message suppression | **PASS** | `test_ws_chat_contract.py::test_duplicate_submission_suppressed` |
| **P0-A2-05** | Exact YouTube URL casing (`FV93IVwJP_4`) | **PASS** | `test_ws_chat_contract.py::test_exact_youtube_url_preservation` |
| **P0-A2-06** | Revision request provenance | **PASS** | `test_ws_chat_contract.py::test_revision_request_server_provenance` |
| **P0-A2-07** | Fail-closed error handling (no fallback) | **PASS** | `test_ws_chat_contract.py::test_fail_closed_error_handling` |
| **P0-A2-08** | E2E incident under strict Wave 12 guard | **PASS** | `test_ws_chat_contract.py::test_e2e_user_observed_incident_with_strict_guard` |
| **P0-A2-09** | Frontend client contract & outcome isolation | **PASS** | `test_frontend_chat_contract.py::test_frontend_payload_contract_and_outcome_filter` |
| **P0-A2-10** | Headless Edge browser & network trace | **PASS** | `tools/p0_recovery_a2/BROWSER_EVIDENCE.md` |
| **P0-A2-11** | Full cross-agent media fetch & edit | **BLOCKED_ENVIRONMENT** | YouTube media slice & FFmpeg assembly across peer boundaries belongs to A3/A5 integration |

---

## 6. Instructions for Agent 5 (Integrator)

1. **Merge Tip**:
   Fast-forward merge branch `p0fix/02-ws-chat-provider-intent` into the integration candidate.
2. **Adapter Seam**:
   The adapter in `backend/api/chat.py` imports `inference_authorization_context` and `TRIGGER_EXPLICIT_CHAT_SUBMIT` from `backend.llm_trace`. If Agent 1 refactored the import path or signature, update only the adapter seam `server_inference_authorization_context` in `backend/api/chat.py`.
3. **Contracts**:
   Consult `tools/p0_recovery_a2/HANDOFF.json` for all WebSocket payload and outcome event schemas.
