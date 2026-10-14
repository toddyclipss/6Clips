# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Sanitized diagnostic tracer for outbound LLM and Ollama traffic.

Opt-in via SIXCLIPS_IDLE_NET_AUDIT=1. Never records prompts, completions,
authorization tokens, or cookies. Writes bounded JSONL records to %TEMP%.
"""
import os
import sys
import json
import time
import inspect
import tempfile
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse

from backend.llm_trace.models import (
    InferenceEvent,
    OUTCOME_ALLOWED,
    OUTCOME_BLOCKED,
    OUTCOME_SUCCESS,
    OUTCOME_ERROR,
    OUTCOME_DEBOUNCED,
    ENDPOINT_CATEGORY_GENERATIVE,
    ENDPOINT_CATEGORY_DISCOVERY,
)

# In-memory bounded circular buffer (retained for inspection and fast test asserts)
_IN_MEMORY_EVENTS: deque[InferenceEvent] = deque(maxlen=1000)
_FORCE_AUDIT_ENABLED: Optional[bool] = None


def is_audit_enabled() -> bool:
    """Return True if diagnostic audit collection is enabled."""
    if _FORCE_AUDIT_ENABLED is not None:
        return _FORCE_AUDIT_ENABLED
    env_val = os.environ.get("SIXCLIPS_IDLE_NET_AUDIT", "").strip().lower()
    return env_val in ("1", "true", "yes", "on")


def enable_audit() -> None:
    """Programmatically enable diagnostic auditing for this process."""
    global _FORCE_AUDIT_ENABLED
    _FORCE_AUDIT_ENABLED = True


def disable_audit() -> None:
    """Programmatically disable diagnostic auditing."""
    global _FORCE_AUDIT_ENABLED
    _FORCE_AUDIT_ENABLED = False


def get_audit_log_path() -> Path:
    """Return path to %TEMP%/6clips_wave12_idle_audit/llm_trace.jsonl."""
    base_dir = Path(tempfile.gettempdir()) / "6clips_wave12_idle_audit"
    try:
        base_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return base_dir / "llm_trace.jsonl"


def _clean_stale_audit_files(retention_seconds: float = 86400.0) -> None:
    """Prune trace log files older than 24 hours."""
    base_dir = Path(tempfile.gettempdir()) / "6clips_wave12_idle_audit"
    if not base_dir.is_dir():
        return
    now = time.time()
    try:
        for f in base_dir.glob("*.jsonl"):
            try:
                if f.is_file() and (now - f.stat().st_mtime) > retention_seconds:
                    f.unlink(missing_ok=True)
            except Exception:
                pass
    except Exception:
        pass


def sanitize_url(raw_url: str) -> str:
    """Sanitize URL down to scheme://host:port/path, removing query and auth."""
    try:
        parsed = urlparse(raw_url)
        netloc = parsed.hostname or "localhost"
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"
        return f"{parsed.scheme or 'http'}://{netloc}{parsed.path}"
    except Exception:
        return raw_url.split("?")[0].split("#")[0]


def sanitize_stack_frames(limit: int = 5) -> List[str]:
    """Capture sanitized callsite frames (filename:lineno:function), stripping sensitive arguments."""
    frames = []
    try:
        stack = inspect.stack()
        # Skip the internal llm_trace frames
        for frame_info in stack[2: 2 + limit]:
            filename = frame_info.filename
            # Keep relative path if within repo, or basename
            if "backend" in filename:
                filename = "backend" + filename.split("backend")[-1]
            elif "tests" in filename:
                filename = "tests" + filename.split("tests")[-1]
            else:
                filename = Path(filename).name
            frames.append(f"{filename}:{frame_info.lineno}:{frame_info.function}")
    except Exception:
        pass
    return frames


def record_trace_event(event: InferenceEvent) -> None:
    """Record an outbound event to in-memory buffer and JSONL log if enabled."""
    _IN_MEMORY_EVENTS.append(event)

    if not is_audit_enabled():
        return

    try:
        _clean_stale_audit_files()
        log_path = get_audit_log_path()
        line = json.dumps(event.to_dict()) + "\n"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def get_audit_events() -> List[InferenceEvent]:
    """Return a copy of all in-memory recorded inference events."""
    return list(_IN_MEMORY_EVENTS)


def clear_audit_events() -> None:
    """Clear in-memory recorded events."""
    _IN_MEMORY_EVENTS.clear()


def get_trace_summary() -> Dict[str, Any]:
    """Calculate aggregated metrics over recorded events."""
    events = list(_IN_MEMORY_EVENTS)
    summary = {
        "total_requests": len(events),
        "generative_posts_count": 0,
        "discovery_gets_count": 0,
        "allowed_count": 0,
        "blocked_count": 0,
        "debounced_count": 0,
        "by_trigger": {},
        "by_authorization_class": {},
        "by_outcome": {},
        "by_endpoint_category": {},
    }

    for ev in events:
        if ev.endpoint_category == ENDPOINT_CATEGORY_GENERATIVE:
            summary["generative_posts_count"] += 1
        elif ev.endpoint_category == ENDPOINT_CATEGORY_DISCOVERY:
            summary["discovery_gets_count"] += 1

        if ev.outcome == OUTCOME_ALLOWED or ev.outcome == OUTCOME_SUCCESS:
            summary["allowed_count"] += 1
        elif ev.outcome == OUTCOME_BLOCKED:
            summary["blocked_count"] += 1
        elif ev.outcome == OUTCOME_DEBOUNCED:
            summary["debounced_count"] += 1

        summary["by_trigger"][ev.trigger] = summary["by_trigger"].get(ev.trigger, 0) + 1
        summary["by_authorization_class"][ev.authorization_class] = (
            summary["by_authorization_class"].get(ev.authorization_class, 0) + 1
        )
        summary["by_outcome"][ev.outcome] = summary["by_outcome"].get(ev.outcome, 0) + 1
        summary["by_endpoint_category"][ev.endpoint_category] = (
            summary["by_endpoint_category"].get(ev.endpoint_category, 0) + 1
        )

    return summary
