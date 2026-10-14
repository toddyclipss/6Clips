# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Opt-In Read-Only Forensic Diagnostics Router.

Strict localhost-bound security check: non-local requests receive 403 Forbidden.
Dev-only / opt-in: querying diagnostics NEVER triggers LLM inference or egress.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from backend.config import settings
from backend.diagnostics.recorder import (
    ActivityRecorder,
    is_audit_enabled,
    enable_audit,
    disable_audit,
    get_audit_events,
    clear_audit_events,
    get_audit_summary,
)
from backend.llm_trace.tracer import get_trace_summary, get_audit_events as get_llm_events
from backend.distribution.egress_audit import get_recent_audit_events as get_egress_events

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])

LOCALHOST_IPS = {"127.0.0.1", "::1", "localhost", "testclient"}


def _assert_localhost_security(request: Request) -> None:
    """Enforce localhost-only access for forensic diagnostic endpoints."""
    client_host = request.client.host if request.client else "unknown"
    if client_host not in LOCALHOST_IPS and not client_host.startswith("127."):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Diagnostics API is restricted to loopback localhost only.",
        )


class DiagnosticStatusResponse(BaseModel):
    audit_enabled: bool
    server_time_utc: str
    pid: int
    summary: Dict[str, Any]


class DiagnosticToggleRequest(BaseModel):
    enabled: bool


@router.get("/status", response_model=DiagnosticStatusResponse)
async def get_diagnostic_status(request: Request):
    """
    Read-only status of opt-in idle network audit.
    Restricted to localhost. Never initiates inference or network calls.
    """
    _assert_localhost_security(request)
    recorder = ActivityRecorder.get_instance()
    summary = recorder.get_summary()

    # Also augment with LLM trace summary if available
    try:
        llm_sum = get_trace_summary()
        summary["llm_trace"] = llm_sum
    except Exception:
        pass

    return DiagnosticStatusResponse(
        audit_enabled=recorder.is_enabled(),
        server_time_utc=datetime.now(timezone.utc).isoformat(),
        pid=os.getpid(),
        summary=summary,
    )


@router.get("/events")
async def get_diagnostic_events(
    request: Request,
    component: Optional[str] = Query(None, description="Filter by component name"),
    endpoint_class: Optional[str] = Query(None, description="Filter by endpoint class"),
    limit: int = Query(50, ge=1, le=500, description="Max events to return"),
):
    """
    Retrieve sanitized recent diagnostic events.
    Localhost-only. Never logs or returns prompt text or credentials.
    """
    _assert_localhost_security(request)
    recorder = ActivityRecorder.get_instance()
    records = recorder.get_records(component=component, endpoint_class=endpoint_class, limit=limit)
    return {
        "count": len(records),
        "events": records,
    }


@router.get("/trace_matrix")
async def get_trace_matrix(request: Request):
    """
    Return forensic route-level trace matrix showing all observed route classes and counts.
    Localhost-only.
    """
    _assert_localhost_security(request)
    recorder = ActivityRecorder.get_instance()
    summary = recorder.get_summary()

    # Consolidate counts across all modules
    trace_matrix = {
        "USER_AUTHORIZED": summary["by_endpoint_class"].get("USER_AUTHORIZED", 0),
        "TASK_PREVIOUSLY_AUTHORIZED": summary["by_endpoint_class"].get("TASK_PREVIOUSLY_AUTHORIZED", 0),
        "READ_ONLY_HEALTH_DISCOVERY": summary["by_endpoint_class"].get("READ_ONLY_HEALTH_DISCOVERY", 0),
        "UNSOLICITED_INFERENCE": summary.get("unsolicited_inference_count", 0),
        "UNSOLICITED_EXTERNAL_EGRESS": summary.get("unsolicited_external_egress_count", 0),
        "BLOCKED_WITH_REASON": summary.get("blocked_count", 0),
        "NOT_OBSERVED": summary["by_endpoint_class"].get("NOT_OBSERVED", 0),
        "UNATTRIBUTED_OTHER_PROCESS": summary["by_endpoint_class"].get("UNATTRIBUTED_OTHER_PROCESS", 0),
    }

    return {
        "audit_enabled": recorder.is_enabled(),
        "trace_matrix": trace_matrix,
        "total_observed": summary["total_events"],
    }


@router.post("/toggle")
async def toggle_diagnostic_audit(req: DiagnosticToggleRequest, request: Request):
    """
    Toggle diagnostic audit mode dynamically for automated test runs.
    Localhost-only.
    """
    _assert_localhost_security(request)
    recorder = ActivityRecorder.get_instance()
    if req.enabled:
        recorder.enable()
        from backend.llm_trace.tracer import enable_audit as enable_llm
        enable_llm()
    else:
        recorder.disable()
        from backend.llm_trace.tracer import disable_audit as disable_llm
        disable_llm()

    return {"audit_enabled": recorder.is_enabled()}


@router.post("/clear")
async def clear_diagnostic_events(request: Request):
    """
    Clear in-memory diagnostic buffer for test isolation.
    Localhost-only.
    """
    _assert_localhost_security(request)
    ActivityRecorder.get_instance().clear()
    try:
        from backend.llm_trace.tracer import clear_audit_events as clear_llm
        clear_llm()
    except Exception:
        pass
    try:
        from backend.distribution.egress_audit import clear_audit_events as clear_egress
        clear_egress()
    except Exception:
        pass
    return {"status": "cleared"}
