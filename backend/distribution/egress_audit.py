# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Opt-in Local Egress and Idle Network Audit for Phase 10/11 Distribution & Analytics.

Safety and Privacy Contract:
- Local-only, off by default, opt-in via environment variable SIXCLIPS_IDLE_NET_AUDIT=1.
- Zero overhead when disabled.
- Audit evidence persisted outside the repository in %TEMP%/6clips_wave12_idle_audit/.
- Automated auto-clean retention: audit logs older than 24 hours are safely removed.
- NEVER captures prompt text, response bodies, image/media bytes, Authorization headers,
  cookies, bearer tokens, full URL query strings, OAuth codes, or PII.
- Captures metadata only: timestamp (UTC), pid, component, destination host, sanitized path,
  method, endpoint class, trigger authorization, correlation ID, callsite, outcome status, duration.
- Includes in-memory bounded ring buffer for live in-process test assertion.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)

ENV_VAR_NAME = "SIXCLIPS_IDLE_NET_AUDIT"
DEFAULT_SUBDIR = "6clips_wave12_idle_audit"
MAX_MEMORY_RECORDS = 500
MAX_LOG_AGE_HOURS = 24

_lock = threading.Lock()
_in_memory_records: Deque[Dict[str, Any]] = deque(maxlen=MAX_MEMORY_RECORDS)
_cleaned_old_logs = False

# Official outbound platform allowlist for chosen social distribution providers
OFFICIAL_OUTBOUND_ALLOWLIST: Dict[str, List[str]] = {
    "youtube": ["www.googleapis.com", "oauth2.googleapis.com"],
    "tiktok": ["open.tiktokapis.com", "auth.tiktok-us.com"],
    "instagram": ["graph.facebook.com", "api.instagram.com"],
    "x": ["api.twitter.com", "api.x.com"],
    "ollama": ["127.0.0.1", "localhost"],
}


def is_audit_enabled() -> bool:
    """Return True strictly if opt-in audit flag is active."""
    return os.environ.get(ENV_VAR_NAME, "").strip() == "1"


def get_audit_dir() -> Path:
    """Return the secure external audit directory outside the repository."""
    base_temp = Path(tempfile.gettempdir())
    audit_dir = base_temp / DEFAULT_SUBDIR
    audit_dir.mkdir(parents=True, exist_ok=True)
    return audit_dir


def _clean_old_logs(audit_dir: Path) -> None:
    """Remove audit log files older than 24 hours."""
    global _cleaned_old_logs
    if _cleaned_old_logs:
        return
    _cleaned_old_logs = True
    try:
        now_ts = time.time()
        cutoff_ts = now_ts - (MAX_LOG_AGE_HOURS * 3600)
        for entry in audit_dir.glob("*.jsonl"):
            if entry.is_file():
                try:
                    if entry.stat().st_mtime < cutoff_ts:
                        entry.unlink(missing_ok=True)
                except OSError:
                    pass
    except Exception as exc:
        logger.debug("Failed auto-cleaning old audit logs: %s", exc)


def get_current_log_path() -> Path:
    """Get today's audit JSONL path."""
    audit_dir = get_audit_dir()
    _clean_old_logs(audit_dir)
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    return audit_dir / f"idle_net_audit_{today}.jsonl"


def check_outbound_allowlist(platform: str, host: str) -> bool:
    """Validate whether an outbound destination host is in the official platform allowlist."""
    norm_plat = platform.lower().strip()
    norm_host = host.lower().strip()
    allowed = OFFICIAL_OUTBOUND_ALLOWLIST.get(norm_plat, [])
    return norm_host in allowed


def record_egress_event(
    *,
    component: str,
    destination_host: str,
    sanitized_path: str,
    method: str,
    endpoint_class: str,
    trigger_authorization: str,
    outcome_status: str,
    correlation_id: Optional[str] = None,
    callsite: Optional[str] = None,
    duration_ms: float = 0.0,
    test_phase: Optional[str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Record a single network egress or blocked attempt event.
    Guaranteed sanitized metadata only.
    Returns the event dict if recorded, or None if audit is disabled.
    """
    if not is_audit_enabled():
        return None

    now_utc = datetime.now(timezone.utc).isoformat()
    pid = os.getpid()

    # Redact / sanitize any path query strings or trailing IDs
    clean_path = sanitized_path.split("?")[0]

    event = {
        "timestamp_utc": now_utc,
        "pid": pid,
        "component": component,
        "destination_host": destination_host,
        "sanitized_path": clean_path,
        "method": method.upper(),
        "endpoint_class": endpoint_class,
        "trigger_authorization": trigger_authorization,
        "correlation_id": correlation_id or "NONE",
        "callsite": callsite or "unknown",
        "outcome_status": outcome_status,
        "duration_ms": round(duration_ms, 2),
        "test_phase": test_phase or "RUNTIME",
    }

    if extra_metadata:
        # Only copy whitelisted safe keys
        safe_keys = {"job_id", "platform", "provider", "account_id", "error_code", "is_retryable"}
        filtered = {k: v for k, v in extra_metadata.items() if k in safe_keys}
        event["extra"] = filtered

    with _lock:
        _in_memory_records.append(event)
        try:
            log_path = get_current_log_path()
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as exc:
            logger.debug("Failed appending audit event to disk: %s", exc)

    return event


def get_recent_audit_events(
    component: Optional[str] = None,
    endpoint_class: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Fetch recent recorded events matching optional filters."""
    with _lock:
        events = list(_in_memory_records)

    if component:
        events = [e for e in events if e.get("component") == component]
    if endpoint_class:
        events = [e for e in events if e.get("endpoint_class") == endpoint_class]

    return events[-limit:]


def clear_audit_events() -> None:
    """Clear in-memory audit records (useful for test isolation)."""
    with _lock:
        _in_memory_records.clear()
