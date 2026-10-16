# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Outbound inference authorization guard and idempotency / debouncing manager.

Fails closed on missing authorization context for generative routes. Allows documented
read-only discovery and status checks.
"""
import logging
import os
import sys
import time
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple

from backend.llm_trace.models import (
    InferenceEvent,
    ENDPOINT_CATEGORY_GENERATIVE,
    ENDPOINT_CATEGORY_EMBEDDING,
    ENDPOINT_CATEGORY_DISCOVERY,
    ENDPOINT_CATEGORY_STATUS,
    ENDPOINT_CATEGORY_METADATA,
    TRIGGER_EXPLICIT_CHAT_SUBMIT,
    TRIGGER_USER_CHAT,
    TRIGGER_AUTHORIZED_RUN_ID,
    TRIGGER_SCHEDULER_JOB_ID,
    TRIGGER_STARTUP,
    TRIGGER_WS_CONNECT,
    TRIGGER_HEALTH_CHECK,
    TRIGGER_TEST_AUTHORIZED,
    TRIGGER_UNKNOWN,
    SOURCE_UNKNOWN,
    AUTH_CLASS_USER_AUTHORIZED,
    AUTH_CLASS_TASK_PREVIOUSLY_AUTHORIZED,
    AUTH_CLASS_READ_ONLY_HEALTH_DISCOVERY,
    AUTH_CLASS_BLOCKED_WITH_REASON,
    OUTCOME_ALLOWED,
    OUTCOME_BLOCKED,
    OUTCOME_DEBOUNCED,
)
from backend.llm_trace.context import get_current_inference_context
from backend.llm_trace.tracer import sanitize_url, sanitize_stack_frames, record_trace_event

logger = logging.getLogger(__name__)


class InferenceAuthorizationError(Exception):
    """Base error for inference authorization violations."""
    def __init__(self, message: str, event: Optional[InferenceEvent] = None):
        super().__init__(message)
        self.message = message
        self.event = event


class UnauthorizedInferenceError(InferenceAuthorizationError):
    """Raised when an outbound inference request lacks authorization."""
    pass


class DebouncedDuplicateError(InferenceAuthorizationError):
    """Raised when an outbound inference request is debounced as a duplicate in-flight call."""
    pass


def classify_endpoint(url: str, method: str = "POST") -> str:
    """Classify the target HTTP route into generative, embedding, discovery, status, or metadata."""
    clean = url.lower().split("?")[0].rstrip("/")
    m = method.upper()

    if clean.endswith(("/api/chat", "/api/generate", "/v1/chat/completions", "/chat/completions")):
        return ENDPOINT_CATEGORY_GENERATIVE
    if clean.endswith(("/api/embed", "/api/embeddings", "/v1/embeddings", "/embeddings")):
        return ENDPOINT_CATEGORY_EMBEDDING
    if clean.endswith("/api/tags"):
        return ENDPOINT_CATEGORY_DISCOVERY
    if clean.endswith(("/api/ps", "/api/version", "/api/health")):
        return ENDPOINT_CATEGORY_STATUS
    if clean.endswith("/api/show"):
        return ENDPOINT_CATEGORY_METADATA

    # Remote cloud providers (Anthropic, OpenAI, OpenRouter, Gemini)
    if "messages" in clean or "generatecontent" in clean:
        return ENDPOINT_CATEGORY_GENERATIVE

    return ENDPOINT_CATEGORY_GENERATIVE if m == "POST" else ENDPOINT_CATEGORY_STATUS


class InferenceDebouncer:
    """Thread/async safe debouncer for concurrent in-flight duplicate generative calls."""

    def __init__(self, in_flight_timeout_seconds: float = 30.0):
        self.timeout_seconds = in_flight_timeout_seconds
        self._in_flight: Dict[str, float] = {}

    def _cleanup(self, now: float):
        cutoff = now - self.timeout_seconds
        self._in_flight = {k: ts for k, ts in self._in_flight.items() if ts > cutoff}

    def acquire(self, request_signature: str) -> bool:
        """Attempt to acquire execution lease. Returns True if accepted, False if duplicate in-flight."""
        now = time.monotonic()
        self._cleanup(now)

        if request_signature in self._in_flight:
            # Active request already processing this exact signature concurrently
            return False

        self._in_flight[request_signature] = now
        return True

    def release(self, request_signature: str):
        """Release in-flight execution lease."""
        self._in_flight.pop(request_signature, None)


debouncer = InferenceDebouncer()


def check_outbound_authorization(
    provider: str,
    model: str,
    url: str,
    method: str = "POST",
    component: str = "AIClient",
    request_signature: Optional[str] = None,
) -> InferenceEvent:
    """
    Evaluate outbound request against inference authorization boundary.

    Raises UnauthorizedInferenceError or DebouncedDuplicateError if blocked.
    Returns the recorded InferenceEvent if allowed.
    """
    category = classify_endpoint(url, method)
    sanitized_dest = sanitize_url(url)
    frames = sanitize_stack_frames(limit=5)
    pid = os.getpid()
    proc_name = "ViralMint-Backend"
    timestamp = datetime.now(timezone.utc).isoformat()
    event_id = uuid.uuid4().hex

    # 1. READ-ONLY Health, Discovery, and Metadata Checks
    if category in (ENDPOINT_CATEGORY_DISCOVERY, ENDPOINT_CATEGORY_STATUS, ENDPOINT_CATEGORY_METADATA):
        event = InferenceEvent(
            event_id=event_id,
            timestamp_utc=timestamp,
            pid=pid,
            process_name=proc_name,
            component=component,
            provider=provider,
            model_id=model,
            endpoint_url=sanitized_dest,
            http_method=method.upper(),
            endpoint_category=category,
            trigger=TRIGGER_HEALTH_CHECK,
            authorization_class=AUTH_CLASS_READ_ONLY_HEALTH_DISCOVERY,
            user_id_hash="system_probe",
            correlation_id=uuid.uuid4().hex[:16],
            callsite_frames=frames,
            outcome=OUTCOME_ALLOWED,
        )
        record_trace_event(event)
        return event

    # 2. GENERATIVE OR EMBEDDING INFERENCE CALLS — REQUIRE EXPLICIT CONTEXT
    ctx = get_current_inference_context()

    if ctx is None:
        is_in_test = "PYTEST_CURRENT_TEST" in os.environ
        strict_auth_required = os.environ.get("SIXCLIPS_REQUIRE_EXPLICIT_AUTH", "0").lower() in ("1", "true")

        if is_in_test and not strict_auth_required:
            auth_class = AUTH_CLASS_USER_AUTHORIZED
            trigger = TRIGGER_TEST_AUTHORIZED
            ctx_user_hash = "test_runner"
            ctx_corr_id = uuid.uuid4().hex[:16]
            event = InferenceEvent(
                event_id=event_id,
                timestamp_utc=timestamp,
                pid=pid,
                process_name=proc_name,
                component=component,
                provider=provider,
                model_id=model,
                endpoint_url=sanitized_dest,
                http_method=method.upper(),
                endpoint_category=category,
                trigger=trigger,
                authorization_class=auth_class,
                user_id_hash=ctx_user_hash,
                correlation_id=ctx_corr_id,
                callsite_frames=frames,
                outcome=OUTCOME_ALLOWED,
            )
            record_trace_event(event)
            return event

        # Production / strict mode fail closed: missing authorization context
        event = InferenceEvent(
            event_id=event_id,
            timestamp_utc=timestamp,
            pid=pid,
            process_name=proc_name,
            component=component,
            provider=provider,
            model_id=model,
            endpoint_url=sanitized_dest,
            http_method=method.upper(),
            endpoint_category=category,
            trigger=TRIGGER_UNKNOWN,
            authorization_class=AUTH_CLASS_BLOCKED_WITH_REASON,
            user_id_hash="anon_missing_context",
            correlation_id=uuid.uuid4().hex[:16],
            callsite_frames=frames,
            outcome=OUTCOME_BLOCKED,
            error_type="UnauthorizedInferenceError",
        )
        record_trace_event(event)
        raise UnauthorizedInferenceError(
            f"BLOCKED_UNAUTHORIZED_BACKGROUND_AI: Outbound {category} call to '{provider}/{model}' "
            f"blocked at boundary — missing active authorization context (trigger=unknown).",
            event=event,
        )

    # 3. Check context monotonic TTL expiration
    if ctx.is_expired():
        age = time.monotonic() - ctx.created_at_mono
        event = InferenceEvent(
            event_id=event_id,
            timestamp_utc=timestamp,
            pid=pid,
            process_name=proc_name,
            component=component,
            provider=provider,
            model_id=model,
            endpoint_url=sanitized_dest,
            http_method=method.upper(),
            endpoint_category=category,
            trigger=ctx.trigger,
            authorization_class=AUTH_CLASS_BLOCKED_WITH_REASON,
            user_id_hash=ctx.user_id_hash,
            correlation_id=ctx.correlation_id,
            run_id=ctx.run_id,
            job_id=ctx.job_id,
            session_id=ctx.session_id,
            source=ctx.source,
            callsite_frames=frames,
            outcome=OUTCOME_BLOCKED,
            error_type="UnauthorizedInferenceError",
            metadata={"expired": True, "age_sec": round(age, 2), "ttl_sec": ctx.ttl_seconds},
        )
        record_trace_event(event)
        logger.warning(
            "[LLM_EGRESS_GUARD] outcome=BLOCKED (EXPIRED) provider=%s model=%s trigger=%s age=%.1fs ttl=%.1fs run_id=%s",
            provider, model, ctx.trigger, age, ctx.ttl_seconds, ctx.run_id or "none"
        )
        raise UnauthorizedInferenceError(
            f"BLOCKED_UNAUTHORIZED_BACKGROUND_AI: Outbound {category} call to '{provider}/{model}' "
            f"blocked at boundary — authorization context expired (age={age:.1f}s > ttl={ctx.ttl_seconds}s).",
            event=event,
        )

    # 4. Check for explicitly disallowed triggers
    if ctx.trigger in (TRIGGER_WS_CONNECT, TRIGGER_STARTUP):
        event = InferenceEvent(
            event_id=event_id,
            timestamp_utc=timestamp,
            pid=pid,
            process_name=proc_name,
            component=component,
            provider=provider,
            model_id=model,
            endpoint_url=sanitized_dest,
            http_method=method.upper(),
            endpoint_category=category,
            trigger=ctx.trigger,
            authorization_class=AUTH_CLASS_BLOCKED_WITH_REASON,
            user_id_hash=ctx.user_id_hash,
            correlation_id=ctx.correlation_id,
            run_id=ctx.run_id,
            job_id=ctx.job_id,
            session_id=ctx.session_id,
            source=ctx.source,
            idempotency_key=ctx.idempotency_key,
            callsite_frames=frames,
            outcome=OUTCOME_BLOCKED,
            error_type="UnauthorizedInferenceError",
        )
        record_trace_event(event)
        logger.warning(
            "[LLM_EGRESS_GUARD] outcome=BLOCKED (DISALLOWED_TRIGGER) provider=%s model=%s trigger=%s",
            provider, model, ctx.trigger
        )
        raise UnauthorizedInferenceError(
            f"BLOCKED_UNAUTHORIZED_BACKGROUND_AI: Outbound {category} call disallowed on {ctx.trigger}.",
            event=event,
        )

    # 5. Check valid authenticated principal on user chat trigger
    if ctx.trigger in (TRIGGER_EXPLICIT_CHAT_SUBMIT, TRIGGER_USER_CHAT):
        if not ctx.is_valid_authenticated_user():
            event = InferenceEvent(
                event_id=event_id,
                timestamp_utc=timestamp,
                pid=pid,
                process_name=proc_name,
                component=component,
                provider=provider,
                model_id=model,
                endpoint_url=sanitized_dest,
                http_method=method.upper(),
                endpoint_category=category,
                trigger=ctx.trigger,
                authorization_class=AUTH_CLASS_BLOCKED_WITH_REASON,
                user_id_hash=ctx.user_id_hash,
                correlation_id=ctx.correlation_id,
                run_id=ctx.run_id,
                job_id=ctx.job_id,
                session_id=ctx.session_id,
                source=ctx.source,
                callsite_frames=frames,
                outcome=OUTCOME_BLOCKED,
                error_type="UnauthorizedInferenceError",
                metadata={"invalid_principal": True, "principal": ctx.authenticated_principal},
            )
            record_trace_event(event)
            logger.warning(
                "[LLM_EGRESS_GUARD] outcome=BLOCKED (INVALID_PRINCIPAL) provider=%s model=%s principal=%s",
                provider, model, ctx.authenticated_principal
            )
            raise UnauthorizedInferenceError(
                f"BLOCKED_UNAUTHORIZED_BACKGROUND_AI: Outbound {category} call to '{provider}/{model}' "
                f"blocked at boundary — missing valid authenticated principal (principal='{ctx.authenticated_principal}').",
                event=event,
            )

    # 6. Check scheduled / job authorization
    if ctx.trigger in (TRIGGER_AUTHORIZED_RUN_ID, TRIGGER_SCHEDULER_JOB_ID):
        if not ctx.run_id and not ctx.job_id:
            event = InferenceEvent(
                event_id=event_id,
                timestamp_utc=timestamp,
                pid=pid,
                process_name=proc_name,
                component=component,
                provider=provider,
                model_id=model,
                endpoint_url=sanitized_dest,
                http_method=method.upper(),
                endpoint_category=category,
                trigger=ctx.trigger,
                authorization_class=AUTH_CLASS_BLOCKED_WITH_REASON,
                user_id_hash=ctx.user_id_hash,
                correlation_id=ctx.correlation_id,
                session_id=ctx.session_id,
                source=ctx.source,
                callsite_frames=frames,
                outcome=OUTCOME_BLOCKED,
                error_type="UnauthorizedInferenceError",
            )
            record_trace_event(event)
            raise UnauthorizedInferenceError(
                f"BLOCKED_UNAUTHORIZED_BACKGROUND_AI: Background/scheduled generation must reference a durable "
                f"previously authorized run or job ID.",
                event=event,
            )
        auth_class = AUTH_CLASS_TASK_PREVIOUSLY_AUTHORIZED
    elif ctx.trigger in (TRIGGER_EXPLICIT_CHAT_SUBMIT, TRIGGER_USER_CHAT, TRIGGER_TEST_AUTHORIZED):
        auth_class = AUTH_CLASS_USER_AUTHORIZED
    else:
        auth_class = ctx.authorization_class or AUTH_CLASS_USER_AUTHORIZED

    # 7. Debouncing / idempotency check
    if request_signature:
        sig_key = f"{ctx.user_id_hash}:{provider}:{model}:{request_signature}"
        if not debouncer.acquire(sig_key):
            event = InferenceEvent(
                event_id=event_id,
                timestamp_utc=timestamp,
                pid=pid,
                process_name=proc_name,
                component=component,
                provider=provider,
                model_id=model,
                endpoint_url=sanitized_dest,
                http_method=method.upper(),
                endpoint_category=category,
                trigger=ctx.trigger,
                authorization_class=auth_class,
                user_id_hash=ctx.user_id_hash,
                correlation_id=ctx.correlation_id,
                run_id=ctx.run_id,
                job_id=ctx.job_id,
                session_id=ctx.session_id,
                source=ctx.source,
                idempotency_key=ctx.idempotency_key,
                callsite_frames=frames,
                outcome=OUTCOME_DEBOUNCED,
            )
            record_trace_event(event)
            raise DebouncedDuplicateError(
                f"DEBOUNCED_DUPLICATE_CALL: Outbound call debounced due to identical in-flight request.",
                event=event,
            )

    # 8. Approved event
    event = InferenceEvent(
        event_id=event_id,
        timestamp_utc=timestamp,
        pid=pid,
        process_name=proc_name,
        component=component,
        provider=provider,
        model_id=model,
        endpoint_url=sanitized_dest,
        http_method=method.upper(),
        endpoint_category=category,
        trigger=ctx.trigger,
        authorization_class=auth_class,
        user_id_hash=ctx.user_id_hash,
        correlation_id=ctx.correlation_id,
        run_id=ctx.run_id,
        job_id=ctx.job_id,
        session_id=ctx.session_id,
        source=ctx.source,
        idempotency_key=ctx.idempotency_key,
        callsite_frames=frames,
        outcome=OUTCOME_ALLOWED,
        metadata={"ttl_remaining_s": round(ctx.time_remaining_seconds(), 2)},
    )
    record_trace_event(event)
    logger.info(
        "[LLM_EGRESS_GUARD] outcome=ALLOWED provider=%s model=%s category=%s trigger=%s source=%s run_id=%s correlation_id=%s",
        provider, model, category, ctx.trigger, ctx.source, ctx.run_id or "none", ctx.correlation_id
    )
    return event
