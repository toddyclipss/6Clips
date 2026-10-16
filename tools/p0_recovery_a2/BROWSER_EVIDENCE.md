# AGENT 2 — BROWSER & NETWORK TRACE EVIDENCE

## Test Execution Environment

- **OS:** Windows 11 (Local)
- **Browser:** Microsoft Edge Headless (`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`)
- **Backend Port:** 16892 (disposable test server)
- **Python Environment:** `C:\Users\toddy\AppData\Local\Programs\Python\Python311\python.exe`
- **Timestamp:** 2026-10-16 22:30:38 UTC
- **Strict Egress Guard Active:** `SIXCLIPS_REQUIRE_EXPLICIT_AUTH=1`
- **Model Registry Status:** Local Ollama on port 11434 with model `gemma4:e4b` (ID: `bb027d30ecf5`, 10 GB) confirmed installed and reachable.

---

## 1. Model Discovery & Registry Queries

During UI model listing (on mount and model selection in `LiquidMultimodalInput.jsx`), network requests are strictly confined to read-only discovery endpoints:
- `GET /api/config/model_registry` (cached for 5 minutes via `frontend/src/api/modelRegistry.js`)
- Ollama endpoint queried: `GET http://127.0.0.1:11434/api/tags`
- Wave 12 Category: `ENDPOINT_CATEGORY_DISCOVERY` (classified as `AUTH_CLASS_READ_ONLY_HEALTH_DISCOVERY`, non-generative, no inference trigger required).

---

## 2. WebSocket Client Submission Frame

When the user enters the prompt and submits via `LiquidMultimodalInput` / `ChatPanel`, the client transmits the following normalized payload over `/ws/chat`:

```json
{
  "type": "chat_message",
  "content": "analise e edite esse video em ingles https://www.youtube.com/watch?v=FV93IVwJP_4",
  "provider": "ollama",
  "model": "gemma4:e4b",
  "reasoning_level": "high",
  "client_message_id": "cmsg_browser_1792189813210",
  "correlation_id": "corr_browser_1792189813210",
  "user_intent_id": "corr_browser_1792189813210"
}
```

### Key Security & Integrity Invariants Verified in Payload:
1. **Zero Client Bypass Claims**: No `authorized: true` or `trigger=...` flags. The server ignores any client attempt to claim authorization.
2. **Exact URL Casing**: YouTube URL preserves uppercase `I`: `https://www.youtube.com/watch?v=FV93IVwJP_4` (not lowercased to `fv93ivwjp_4` or `FV93lVwJP_4`).
3. **Exact Model Identification**: Provider `ollama` and model `gemma4:e4b` are forwarded intact without fallback to another provider.
4. **Reasoning Level**: `reasoning_level: high` is forwarded intact.

---

## 3. Server-Authored Execution Provenance & Egress Guard Passage

Upon receipt of `chat_message`, `backend/api/chat.py` activates:

```python
async with server_inference_authorization_context(
    user_id="local",
    correlation_id="corr_browser_1792189813210",
    run_id=None,
):
    ko_resp = await KnowledgeChatOrchestrator.handle_video_request(...)
```

Inside this execution block:
- `get_current_inference_context()` is active with `trigger="explicit_chat_submit"` (`TRIGGER_EXPLICIT_CHAT_SUBMIT`).
- `backend/llm_trace/guard.py` checks outbound inference to `http://127.0.0.1:11434/api/chat`.
- The call is **ALLOWED** (`OUTCOME_ALLOWED`) under strict `SIXCLIPS_REQUIRE_EXPLICIT_AUTH=1`.
- Zero `BLOCKED_UNAUTHORIZED_BACKGROUND_AI` errors occur.

---

## 4. Server Response Frames via WebSocket

```json
[
  {
    "type": "oaas_outcome_update",
    "session_id": "sess_browser_live",
    "run_id": "krun-d81b041012",
    "project_id": "97375501-9652-462e-acd3-df5de48114b0",
    "revision": 6,
    "state": "REVIEW_READY",
    "message": "Original video successfully generated at revision 6 (Project ID: 97375501-9652-462e-acd3-df5de48114b0, Library ID: baad3bdd-6b20-4533-8766-19884d8b85ef). Physical MP4 verified (6.8s, 9:16, codec: h264). Distribution status: NOT_REQUESTED.",
    "deliverable_url": "/api/projects/97375501-9652-462e-acd3-df5de48114b0/export/download",
    "duration_seconds": 6.83,
    "media_probe": {
      "duration_seconds": 6.833333,
      "width": 1080,
      "height": 1920,
      "video_codec": "h264",
      "audio_codec": "aac"
    },
    "publication_requested": false,
    "publication_status": "NOT_REQUESTED",
    "blocker_code": null,
    "blocker_reason": null
  },
  {
    "type": "chat_done",
    "full_response": "Original video successfully generated at revision 6.",
    "session_id": "sess_browser_live"
  }
]
```

---

## 5. Summary of Network & Browser Verification Gates

| Gate | Status | Evidence / Log Ref |
|---|---|---|
| Model Discovery Read-Only | **PASS** | `/api/config/model_registry` returns cached model tags; no generative calls triggered on mount |
| Edge Browser WS Handshake | **PASS** | Headless Edge successfully connects to `/ws/chat` |
| Exact URL & Model in WS Payload | **PASS** | `FV93IVwJP_4`, `ollama`, `gemma4:e4b`, `high` sent intact |
| Server-Authored Provenance | **PASS** | Context manager establishes `TRIGGER_EXPLICIT_CHAT_SUBMIT` |
| Wave 12 Guard Compliance | **PASS** | Egress guard allows Ollama inference under `SIXCLIPS_REQUIRE_EXPLICIT_AUTH=1` |
| Fail-Closed on Unselected Model | **PASS** | Verified in automated contract test suite (Test 2) |
| Duplicate Message Suppression | **PASS** | Verified via in-memory deduplicator (Test 4) |
| Stale Outcome Isolation | **PASS** | Inactive session messages filtered out by `useWebSocket.js` |
