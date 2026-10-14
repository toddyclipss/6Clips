# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Unified Cross-Domain Activity Recorder and Sanitized Trace Collector.

Opt-in via SIXCLIPS_IDLE_NET_AUDIT=1. Never records prompt body, completion text,
image/media bytes, Authorization headers, cookies, tokens, query strings, or PII.
Persists bounded JSONL logs outside repository in %TEMP%/6clips_wave12_idle_audit/.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import inspect
import json
import logging
import os
from pathlib import Path
import re
import tempfile
import threading
import time
from typing import Any, Deque, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

ENV_VAR_NAME = "SIXCLIPS_IDLE_NET_AUDIT"
DEFAULT_SUBDIR = "6clips_wave12_idle_audit"
MAX_MEMORY_RECORDS = 1000
MAX_LOG_AGE_HOURS = 24

# Standardized endpoint classes
ENDPOINT_CLASS_USER_AUTHORIZED = "USER_AUTHORIZED"
ENDPOINT_CLASS_TASK_PREVIOUSLY_AUTHORIZED = "TASK_PREVIOUSLY_AUTHORIZED"
ENDPOINT_CLASS_READ_ONLY_HEALTH_DISCOVERY = "READ_ONLY_HEALTH_DISCOVERY"
ENDPOINT_CLASS_UNSOLICITED_INFERENCE = "UNSOLICITED_INFERENCE"
ENDPOINT_CLASS_UNSOLICITED_EXTERNAL_EGRESS = "UNSOLICITED_EXTERNAL_EGRESS"
ENDPOINT_CLASS_UNATTRIBUTED_OTHER_PROCESS = "UNATTRIBUTED_OTHER_PROCESS"
ENDPOINT_CLASS_NOT_OBSERVED = "NOT_OBSERVED"
ENDPOINT_CLASS_BLOCKED_WITH_REASON = "BLOCKED_WITH_REASON"

# Standardized component tags
COMPONENT_HTTP_INBOUND = "http_inbound"
COMPONENT_LLM_OLLAMA = "llm_ollama"
COMPONENT_LLM_CLOUD = "llm_cloud"
COMPONENT_DISTRIBUTION_SCHEDULER = "distribution_scheduler"
COMPONENT_ANALYTICS_WORKER = "analytics_worker"
COMPONENT_WEBSOCKET_INBOUND = "websocket_inbound"
COMPONENT_FRONTEND_CLIENT = "frontend_client"

# Standardized trigger sources
TRIGGER_EXPLICIT_CHAT_SUBMIT = "explicit_chat_submit"
TRIGGER_AUTHORIZED_RUN_ID = "authorized_run_id"
TRIGGER_SCHEDULER_JOB_ID = "scheduler_job_id"
TRIGGER_STARTUP = "startup_bootstrap"
TRIGGER_WS_CONNECT = "ws_connect"
TRIGGER_HEALTH_CHECK = "health_check"
TRIGGER_TEST_AUTHORIZED = "test_authorized"
TRIGGER_UNKNOWN = "unknown_idle_trigger"

# Standardized outcomes
OUTCOME_ALLOWED = "ALLOWED"
OUTCOME_BLOCKED = "BLOCKED"
OUTCOME_SUCCESS = "SUCCESS"
OUTCOME_ERROR = "ERROR"
OUTCOME_DEBOUNCED = "DEBOUNCED"
OUTCOME_ZERO_REQUESTS = "ZERO_REQUESTS"


def is_audit_enabled() -> bool:
    """Return True if diagnostic audit collection is enabled via env or override."""
    return ActivityRecorder.get_instance().is_enabled()


def sanitize_url_path(raw_url: str) -> str:
    """Strip query parameters, fragments, passwords, and tokens from URL/path."""
    if not raw_url:
        return "/"
    try:
        parsed = urlparse(raw_url)
        path = parsed.path or "/"
        # Redact raw hex / UUID tokens if found in URL segments
        path = re.sub(r"/[a-f0-9]{32,64}(?=/|$)", "/[REDACTED_HASH]", path)
        return path
    except Exception:
        return raw_url.split("?")[0].split("#")[0]


def sanitize_host(raw_url_or_host: str) -> str:
    """Extract host:port without credentials."""
    if not raw_url_or_host:
        return "NONE_LOCAL"
    try:
        if "://" in raw_url_or_host:
            parsed = urlparse(raw_url_or_host)
            host = parsed.hostname or "127.0.0.1"
            if parsed.port:
                return f"{host}:{parsed.port}"
            return host
        return raw_url_or_host.split("/")[0].split("?")[0]
    except Exception:
        return "unknown_host"


def sanitize_error_message(err_msg: str) -> str:
    """Redact prompt text, bearer tokens, passwords, cookies, or secrets from error."""
    if not err_msg:
        return ""
    clean = str(err_msg)
    clean = re.sub(r"(Bearer\s+)[A-Za-z0-9_\-\.]+", r"\1[REDACTED_TOKEN]", clean, flags=re.IGNORECASE)
    clean = re.sub(r"(key=|token=|api_key=|password=)[^&\s]+", r"\1[REDACTED]", clean, flags=re.IGNORECASE)
    clean = re.sub(r"(prompt|messages)[\"']?\s*:\s*(\[[^\]]+\]|['\"][^'\"]+['\"])", r"\1: [REDACTED_PAYLOAD]", clean, flags=re.IGNORECASE)
    return clean[:200]


def sanitize_callsite(limit: int = 4) -> str:
    """Capture sanitized callsite frame (file:lineno:function), never arguments."""
    try:
        stack = inspect.stack()
        for frame in stack[2: 2 + limit]:
            fn = frame.filename
            if "backend" in fn:
                fn = "backend" + fn.split("backend")[-1]
            elif "tests" in fn:
                fn = "tests" + fn.split("tests")[-1]
            else:
                fn = Path(fn).name
            if not fn.startswith("backend/diagnostics") and not fn.startswith("backend\\diagnostics"):
                return f"{fn}:{frame.lineno}:{frame.function}"
    except Exception:
        pass
    return "unknown:0:unknown"


class ActivityRecorder:
    """Thread-safe, bounded, nonblocking activity recorder for local forensics."""

    _instance: Optional[ActivityRecorder] = None
    _singleton_lock = threading.Lock()

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: Deque[Dict[str, Any]] = deque(maxlen=MAX_MEMORY_RECORDS)
        self._force_enabled: Optional[bool] = None
        self._cleaned_old_logs = False

    @classmethod
    def get_instance(cls) -> ActivityRecorder:
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def is_enabled(self) -> bool:
        if self._force_enabled is not None:
            return self._force_enabled
        env_val = os.environ.get(ENV_VAR_NAME, "").strip().lower()
        return env_val in ("1", "true", "yes", "on")

    def enable(self) -> None:
        self._force_enabled = True

    def disable(self) -> None:
        self._force_enabled = False

    def reset_override(self) -> None:
        self._force_enabled = None

    def get_audit_dir(self) -> Path:
        base_temp = Path(tempfile.gettempdir()) / DEFAULT_SUBDIR
        try:
            base_temp.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return base_temp

    def _clean_old_logs_if_needed(self, audit_dir: Path) -> None:
        if self._cleaned_old_logs:
            return
        self._cleaned_old_logs = True
        try:
            now_ts = time.time()
            cutoff_ts = now_ts - (MAX_LOG_AGE_HOURS * 3600)
            if audit_dir.is_dir():
                for entry in audit_dir.glob("*.jsonl"):
                    if entry.is_file() and entry.stat().st_mtime < cutoff_ts:
                        entry.unlink(missing_ok=True)
        except Exception as exc:
            logger.debug("Auto-clean audit logs failed: %s", exc)

    def record_activity(
        self,
        *,
        component: str,
        destination_host: str,
        sanitized_path: str,
        method: str,
        endpoint_class: str,
        trigger_authorization: str,
        correlation_id: Optional[str] = None,
        callsite: Optional[str] = None,
        outcome_status: str = OUTCOME_ALLOWED,
        duration_ms: float = 0.0,
        test_phase: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Record an activity event if enabled. Guaranteed sanitized metadata only."""
        if not self.is_enabled():
            return None

        clean_path = sanitize_url_path(sanitized_path)
        clean_host = sanitize_host(destination_host)
        clean_callsite = callsite or sanitize_callsite()
        now_utc = datetime.now(timezone.utc).isoformat()
        pid = os.getpid()

        event = {
            "timestamp_utc": now_utc,
            "pid": pid,
            "component": component,
            "destination_host": clean_host,
            "sanitized_path": clean_path,
            "method": method.upper() if method else "UNKNOWN",
            "endpoint_class": endpoint_class,
            "trigger_authorization": trigger_authorization,
            "correlation_id": correlation_id or "NONE",
            "callsite": clean_callsite,
            "outcome_status": outcome_status,
            "duration_ms": round(float(duration_ms), 2),
            "test_phase": test_phase or "RUNTIME",
        }

        if extra_metadata:
            safe_keys = {
                "provider", "model", "status_code", "error_code", "job_id",
                "platform", "account_id", "is_retryable", "requester_pid", "dest_pid",
            }
            safe_extra = {}
            for k, v in extra_metadata.items():
                if k in safe_keys:
                    if k == "error_code" or "error" in k:
                        safe_extra[k] = sanitize_error_message(str(v))
                    else:
                        safe_extra[k] = v
            if safe_extra:
                event["extra"] = safe_extra

        with self._lock:
            self._records.append(event)
            try:
                audit_dir = self.get_audit_dir()
                self._clean_old_logs_if_needed(audit_dir)
                log_file = audit_dir / "unified_activity.jsonl"
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event) + "\n")
            except Exception as exc:
                logger.debug("Failed writing activity event to disk: %s", exc)

        return event

    def get_records(
        self,
        component: Optional[str] = None,
        endpoint_class: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            items = list(self._records)

        if component:
            items = [x for x in items if x.get("component") == component]
        if endpoint_class:
            items = [x for x in items if x.get("endpoint_class") == endpoint_class]

        return items[-limit:]

    def clear(self) -> None:
        with self._lock:
            self._records.clear()

    def get_summary(self) -> Dict[str, Any]:
        """Aggregate summary of all activity events in memory."""
        with self._lock:
            events = list(self._records)

        summary = {
            "total_events": len(events),
            "by_endpoint_class": {},
            "by_component": {},
            "by_outcome": {},
            "unsolicited_inference_count": 0,
            "unsolicited_external_egress_count": 0,
            "blocked_count": 0,
            "allowed_count": 0,
        }

        for ev in events:
            ep_class = ev.get("endpoint_class", "UNKNOWN")
            comp = ev.get("component", "UNKNOWN")
            outcome = ev.get("outcome_status", "UNKNOWN")

            summary["by_endpoint_class"][ep_class] = summary["by_endpoint_class"].get(ep_class, 0) + 1
            summary["by_component"][comp] = summary["by_component"].get(comp, 0) + 1
            summary["by_outcome"][outcome] = summary["by_outcome"].get(outcome, 0) + 1

            if ep_class == ENDPOINT_CLASS_UNSOLICITED_INFERENCE:
                summary["unsolicited_inference_count"] += 1
            elif ep_class == ENDPOINT_CLASS_UNSOLICITED_EXTERNAL_EGRESS:
                summary["unsolicited_external_egress_count"] += 1

            if outcome == OUTCOME_BLOCKED:
                summary["blocked_count"] += 1
            elif outcome in (OUTCOME_ALLOWED, OUTCOME_SUCCESS):
                summary["allowed_count"] += 1

        return summary


def get_activity_recorder() -> ActivityRecorder:
    return ActivityRecorder.get_instance()


def record_activity(*args, **kwargs) -> Optional[Dict[str, Any]]:
    return ActivityRecorder.get_instance().record_activity(*args, **kwargs)


def enable_audit() -> None:
    ActivityRecorder.get_instance().enable()


def disable_audit() -> None:
    ActivityRecorder.get_instance().disable()


def get_audit_events(*args, **kwargs) -> List[Dict[str, Any]]:
    return ActivityRecorder.get_instance().get_records(*args, **kwargs)


def clear_audit_events() -> None:
    ActivityRecorder.get_instance().clear()


def get_audit_summary() -> Dict[str, Any]:
    return ActivityRecorder.get_instance().get_summary()
