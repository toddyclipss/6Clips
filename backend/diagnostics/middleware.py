# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Correlation & Diagnostics Request Context Middleware.

Propagates request correlation IDs across services, synchronizes with LLM trace context,
and provides sanitized metadata recording for inbound HTTP requests when audit is active.
"""
from __future__ import annotations

import time
import uuid
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.diagnostics.recorder import (
    ActivityRecorder,
    COMPONENT_HTTP_INBOUND,
    ENDPOINT_CLASS_READ_ONLY_HEALTH_DISCOVERY,
    ENDPOINT_CLASS_USER_AUTHORIZED,
    ENDPOINT_CLASS_TASK_PREVIOUSLY_AUTHORIZED,
    ENDPOINT_CLASS_UNSOLICITED_INFERENCE,
    OUTCOME_SUCCESS,
    OUTCOME_ERROR,
    TRIGGER_EXPLICIT_CHAT_SUBMIT,
    TRIGGER_AUTHORIZED_RUN_ID,
    TRIGGER_HEALTH_CHECK,
    TRIGGER_UNKNOWN,
    sanitize_url_path,
)
from backend.llm_trace.context import (
    inference_authorization_context,
)
from backend.llm_trace.models import (
    TRIGGER_EXPLICIT_CHAT_SUBMIT as LLM_TRIGGER_CHAT,
    TRIGGER_AUTHORIZED_RUN_ID as LLM_TRIGGER_RUN,
    TRIGGER_HEALTH_CHECK as LLM_TRIGGER_HEALTH,
    TRIGGER_UNKNOWN as LLM_TRIGGER_UNKNOWN,
)


def _classify_inbound_route(path: str, method: str, user_intent: str | None, run_id: str | None) -> tuple[str, str]:
    """Return (endpoint_class, trigger_authorization)."""
    p = path.lower()
    m = method.upper()

    # Diagnostics and health queries are always read-only discovery
    if (
        p.startswith("/api/diagnostics")
        or p in ("/health", "/api/settings/health", "/api/config/model_registry")
        or p.startswith("/api/catalog")
        or p.startswith("/api/projects/catalog")
        or p.startswith("/api/library")
        or p.startswith("/api/trends")
        or (m == "GET" and not p.startswith("/api/tools/transcribe"))
    ):
        return ENDPOINT_CLASS_READ_ONLY_HEALTH_DISCOVERY, TRIGGER_HEALTH_CHECK

    # Generative or tool execution routes
    is_generative = (
        p.startswith("/api/chat")
        or p.startswith("/api/generate")
        or "script" in p
        or p.startswith("/api/tools")
    )

    if is_generative:
        if user_intent:
            return ENDPOINT_CLASS_USER_AUTHORIZED, TRIGGER_EXPLICIT_CHAT_SUBMIT
        elif run_id:
            return ENDPOINT_CLASS_TASK_PREVIOUSLY_AUTHORIZED, TRIGGER_AUTHORIZED_RUN_ID
        else:
            return ENDPOINT_CLASS_UNSOLICITED_INFERENCE, TRIGGER_UNKNOWN

    if user_intent:
        return ENDPOINT_CLASS_USER_AUTHORIZED, TRIGGER_EXPLICIT_CHAT_SUBMIT
    if run_id:
        return ENDPOINT_CLASS_TASK_PREVIOUSLY_AUTHORIZED, TRIGGER_AUTHORIZED_RUN_ID

    return (ENDPOINT_CLASS_USER_AUTHORIZED if m in ("POST", "PUT", "DELETE") else ENDPOINT_CLASS_READ_ONLY_HEALTH_DISCOVERY), TRIGGER_UNKNOWN


class CorrelationAndAuditMiddleware(BaseHTTPMiddleware):
    """FastAPI/Starlette middleware for correlation injection and sanitized inbound HTTP audit."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        recorder = ActivityRecorder.get_instance()

        # 1. Extract or generate Correlation ID
        cid = (
            request.headers.get("x-correlation-id")
            or request.headers.get("x-request-id")
            or request.headers.get("x-audit-correlation-id")
            or f"c_{uuid.uuid4().hex[:12]}"
        )
        request.state.correlation_id = cid

        user_intent_id = request.headers.get("x-user-intent-id")
        run_id = request.headers.get("x-authorized-run-id")
        auth_sig = request.headers.get("x-auth-signature")

        # 2. Determine trigger and endpoint class
        path = request.url.path
        method = request.method
        endpoint_class, trigger_auth = _classify_inbound_route(path, method, user_intent_id, run_id)

        # 3. Synchronize with downstream LLM authorization context
        llm_trigger = LLM_TRIGGER_HEALTH
        if endpoint_class == ENDPOINT_CLASS_USER_AUTHORIZED:
            llm_trigger = LLM_TRIGGER_CHAT
        elif endpoint_class == ENDPOINT_CLASS_TASK_PREVIOUSLY_AUTHORIZED:
            llm_trigger = LLM_TRIGGER_RUN
        elif endpoint_class == ENDPOINT_CLASS_UNSOLICITED_INFERENCE:
            llm_trigger = LLM_TRIGGER_UNKNOWN

        start_time = time.monotonic()
        response: Response | None = None
        status_code = 500

        try:
            with inference_authorization_context(
                correlation_id=cid,
                trigger=llm_trigger,
                user_id="local_user",
                run_id=run_id,
            ):
                response = await call_next(request)
                status_code = response.status_code
                return response
        except Exception:
            status_code = 500
            raise
        finally:
            duration_ms = (time.monotonic() - start_time) * 1000.0

            # Attach correlation ID to outbound response headers if response was constructed
            if response is not None:
                response.headers["x-correlation-id"] = cid

            # Record sanitized activity if audit is enabled
            if recorder.is_enabled():
                client_host = request.client.host if request.client else "127.0.0.1"
                outcome = OUTCOME_SUCCESS if status_code < 400 else OUTCOME_ERROR
                recorder.record_activity(
                    component=COMPONENT_HTTP_INBOUND,
                    destination_host=f"127.0.0.1:{request.url.port or 16888}",
                    sanitized_path=path,
                    method=method,
                    endpoint_class=endpoint_class,
                    trigger_authorization=trigger_auth,
                    correlation_id=cid,
                    callsite="CorrelationAndAuditMiddleware.dispatch",
                    outcome_status=outcome,
                    duration_ms=duration_ms,
                    extra_metadata={
                        "status_code": status_code,
                        "client_host": client_host,
                    },
                )
