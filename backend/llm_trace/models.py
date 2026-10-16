# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Data models and constants for outbound inference event tracking and authorization.
"""
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
import time

# Endpoint categories
ENDPOINT_CATEGORY_GENERATIVE = "generative"
ENDPOINT_CATEGORY_EMBEDDING = "embedding"
ENDPOINT_CATEGORY_DISCOVERY = "discovery"
ENDPOINT_CATEGORY_STATUS = "status"
ENDPOINT_CATEGORY_METADATA = "metadata"

# Trigger types
TRIGGER_EXPLICIT_CHAT_SUBMIT = "explicit_chat_submit"
TRIGGER_USER_CHAT = "user_chat"
TRIGGER_AUTHORIZED_RUN_ID = "authorized_run_id"
TRIGGER_SCHEDULER_JOB_ID = "scheduler_job_id"
TRIGGER_STARTUP = "startup"
TRIGGER_WS_CONNECT = "ws_connect"
TRIGGER_HEALTH_CHECK = "health_check"
TRIGGER_TEST_AUTHORIZED = "test_authorized"
TRIGGER_UNKNOWN = "unknown"

# Provenance sources
SOURCE_WS_CHAT = "ws_chat"
SOURCE_REST_CHAT = "rest_chat"
SOURCE_DEFERRED_JOB = "deferred_job"
SOURCE_SYSTEM_TASK = "system_task"
SOURCE_TEST = "test"
SOURCE_UNKNOWN = "unknown"

# Authorization classes
AUTH_CLASS_USER_AUTHORIZED = "USER_AUTHORIZED"
AUTH_CLASS_TASK_PREVIOUSLY_AUTHORIZED = "TASK_PREVIOUSLY_AUTHORIZED"
AUTH_CLASS_READ_ONLY_HEALTH_DISCOVERY = "READ_ONLY_HEALTH_DISCOVERY"
AUTH_CLASS_UNSOLICITED_INFERENCE = "UNSOLICITED_INFERENCE"
AUTH_CLASS_UNSOLICITED_EXTERNAL_EGRESS = "UNSOLICITED_EXTERNAL_EGRESS"
AUTH_CLASS_BLOCKED_WITH_REASON = "BLOCKED_WITH_REASON"
AUTH_CLASS_NOT_OBSERVED = "NOT_OBSERVED"

# Outcomes
OUTCOME_ALLOWED = "ALLOWED"
OUTCOME_BLOCKED = "BLOCKED"
OUTCOME_SUCCESS = "SUCCESS"
OUTCOME_ERROR = "ERROR"
OUTCOME_DEBOUNCED = "DEBOUNCED"


@dataclass
class InferenceEvent:
    """Sanitized outbound inference or discovery event record."""
    event_id: str
    timestamp_utc: str
    pid: int
    process_name: str
    component: str
    provider: str
    model_id: str
    endpoint_url: str
    http_method: str
    endpoint_category: str
    trigger: str
    authorization_class: str
    user_id_hash: str
    correlation_id: str
    run_id: Optional[str] = None
    job_id: Optional[str] = None
    session_id: Optional[str] = None
    source: str = SOURCE_UNKNOWN
    idempotency_key: Optional[str] = None
    callsite_frames: List[str] = field(default_factory=list)
    outcome: str = OUTCOME_ALLOWED
    status_code: Optional[int] = None
    duration_ms: Optional[float] = None
    error_type: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to sanitized dictionary for JSON serialization."""
        d = asdict(self)
        # Ensure no accidental secret/prompt leaks in metadata
        d["metadata"] = {
            k: v for k, v in d.get("metadata", {}).items()
            if not any(s in k.lower() for s in ("prompt", "message", "secret", "token", "key", "auth", "cookie", "payload"))
        }
        return d
