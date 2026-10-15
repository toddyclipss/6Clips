# Wave 19 Agent 1 Integration Handoff Guide

## Overview
This document specifies the integration contract and exact usage hooks provided by **Agent 1** (Chat-First OAAS Orchestration + Agent-Operated URL Ingestion) for **Agent 5** (Main Router & Integration) and **Agent 2** (Frontend & Chat UI).

---

## 1. Backend Chat Integration Hook (For Agent 5)

**Module**: `backend.oaas_chat_ingestion.chat_orchestrator.ChatOutcomeOrchestrator`

### Primary Function Call
```python
from backend.oaas_chat_ingestion.chat_orchestrator import ChatOutcomeOrchestrator
from backend.oaas_chat_ingestion.models import ChatGoalOutcomeResponse, ChatGoalStatus

response: ChatGoalOutcomeResponse = await ChatOutcomeOrchestrator.handle_video_goal(
    chat_context={
        "user_id": current_user.id,        # Persistent user ID
        "session_id": session_id,          # Chat conversation session ID
        "project_id": active_project_id,   # Optional: Existing project ID, or None for auto-create
    },
    message=user_chat_message,            # e.g. "Create 3 vertical clips from https://authorized.com/video.mp4"
    user_authorizations={
        "user_authorized": True,           # Boolean confirmation that user owns/has rights to remote stream
    },
    allow_test_fixture=False,             # Set True in test environments, False in production
)
```

### Response Contract (`ChatGoalOutcomeResponse`)
- `job_id: str`: Unique outcome job ID.
- `project_id: str`: Canonical Project ID (persisted in `ProjectService`).
- `revision_id: int`: Monotonically incremented project revision number.
- `status: ChatGoalStatus`:
  - `ChatGoalStatus.READY_FOR_DELIVERY`: Completed and published / ready.
  - `ChatGoalStatus.PENDING_CREDENTIALS`: Physical MP4 produced and verified; distribution awaiting channel connection (never fake success).
  - `ChatGoalStatus.BLOCKED`: Halted fail-closed (SSRF, unauthorized URL, retired block consent).
- `message: str`: Human-readable summary for chat response.
- `artifact_links: List[Dict[str, str]]`: Produced physical media paths, durations, and SHA-256 hashes.
- `preview_details: Dict[str, Any]`: Block ID, preview status, aspect ratio, revisions count.
- `blocker_code: Optional[str]`: Machine-readable code when status is `BLOCKED` (e.g. `BLOCKED_SSRF_PRIVATE_IP`, `BLOCKED_UNAUTHORIZED_STREAM`, `BLOCKED_RETIRED_6CLIPS`).
- `history: List[ChatGoalProgressEvent]`: Sequential progress timeline for streaming updates.

---

## 2. Minimal Chat API Contract (For Agent 2 Frontend)

When a user submits a prompt in the existing persistent Chat (at left), the chat client emits the existing message payload:

```json
{
  "message": "Take this video and create 3 vertical clips with captions",
  "project_id": null,
  "user_authorizations": {
    "user_authorized": true
  }
}
```

### UI Behavior Rules for Agent 2:
1. **No wizard redirects**: If `project_id` is null, the chat orchestrator auto-provisions a canonical project. Do NOT redirect user to an onboarding wizard or project creation modal.
2. **No goal form in player**: The player is exclusively for playback. Do not render a goal composer or onboarding overlay inside the player viewport.
3. **Retired block reconciliation**: When `status == "BLOCKED"` with `blocker_code == "BLOCKED_RETIRED_6CLIPS"`, render the message directly in chat with an interactive button to consent to the suggested verified donor block (e.g., `aurora`).

---

## 3. Remote URL Ingestion Security Policy
- Non-HTTP/HTTPS schemes (`file://`, `ftp://`, `gopher://`, `data:`, `javascript:`) are rejected immediately.
- SSRF private ranges (`127.0.0.1`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.169.254`, `::1`) are blocked.
- Hostnames matching `localhost`, `*.local`, `*.internal` are blocked.
- External video streams require affirmative user rights confirmation (`user_authorized=True`). If missing, halts fail-closed without downloading.
