# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Async-safe context propagation for inference authorization.

Provides server-authored user-action inference scopes, monotonic TTL bounding,
secure task/thread propagation adapters, and fail-closed context guarantees.
"""
import asyncio
import contextvars
import hashlib
import inspect
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional, Any, Callable
from contextlib import AbstractAsyncContextManager, AbstractContextManager

from backend.llm_trace.models import (
    TRIGGER_EXPLICIT_CHAT_SUBMIT,
    TRIGGER_USER_CHAT,
    TRIGGER_AUTHORIZED_RUN_ID,
    TRIGGER_SCHEDULER_JOB_ID,
    TRIGGER_TEST_AUTHORIZED,
    TRIGGER_UNKNOWN,
    AUTH_CLASS_USER_AUTHORIZED,
    AUTH_CLASS_TASK_PREVIOUSLY_AUTHORIZED,
    SOURCE_WS_CHAT,
    SOURCE_REST_CHAT,
    SOURCE_UNKNOWN,
)


def hash_user_id(user_id: Optional[str]) -> str:
    """Return a salted/truncated sha256 hash of user ID to prevent PII logging."""
    if not user_id:
        return "anon_unknown"
    digest = hashlib.sha256(f"vm_uid_salt_{user_id}".encode("utf-8")).hexdigest()
    return f"usr_{digest[:12]}"


@dataclass
class InferenceAuthorizationContext:
    """Active authorization context for downstream inference operations."""
    trigger: str = TRIGGER_UNKNOWN
    authorization_class: str = AUTH_CLASS_USER_AUTHORIZED
    user_id_hash: str = "anon_unknown"
    correlation_id: str = ""
    run_id: Optional[str] = None
    job_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    budget_limit_usd: float = 0.0
    authenticated_principal: Optional[str] = None
    session_id: Optional[str] = None
    source: str = SOURCE_UNKNOWN
    created_at_mono: float = field(default_factory=time.monotonic)
    ttl_seconds: float = 300.0
    scope_token: str = field(default_factory=lambda: uuid.uuid4().hex)
    parent_scope_token: Optional[str] = None

    def __post_init__(self):
        if not self.correlation_id:
            self.correlation_id = uuid.uuid4().hex[:16]
        if not self.scope_token:
            self.scope_token = uuid.uuid4().hex

    def is_expired(self) -> bool:
        """Check if monotonic context lifetime exceeded TTL."""
        if self.ttl_seconds <= 0:
            return False
        return (time.monotonic() - self.created_at_mono) > self.ttl_seconds

    def time_remaining_seconds(self) -> float:
        """Return remaining monotonic lifetime in seconds."""
        if self.ttl_seconds <= 0:
            return float("inf")
        rem = self.ttl_seconds - (time.monotonic() - self.created_at_mono)
        return max(0.0, rem)

    def is_valid_authenticated_user(self) -> bool:
        """Check if authenticated principal is a genuine user (not anonymous or missing)."""
        if not self.authenticated_principal:
            return False
        p = str(self.authenticated_principal).strip().lower()
        return p not in ("anon_unknown", "anonymous", "none", "", "unknown", "null")


_CURRENT_CONTEXT: contextvars.ContextVar[Optional[InferenceAuthorizationContext]] = contextvars.ContextVar(
    "sixclips_inference_authorization_context",
    default=None,
)


def get_current_inference_context() -> Optional[InferenceAuthorizationContext]:
    """Retrieve the active inference authorization context."""
    return _CURRENT_CONTEXT.get()


def set_inference_context(context: Optional[InferenceAuthorizationContext]) -> contextvars.Token:
    """Set the active context directly and return the reset token."""
    return _CURRENT_CONTEXT.set(context)


def clear_inference_context(token: contextvars.Token) -> None:
    """Reset the context using its token."""
    _CURRENT_CONTEXT.reset(token)


class UserChatExecutionScope(AbstractContextManager, AbstractAsyncContextManager):
    """
    Server-authored, bounded user-action inference scope.

    Must be created only at authenticated, validated server-controlled entry points
    (e.g. WebSocket receive loop or REST chat handler).
    Binds:
      - authenticated_principal (e.g. user_id 'local' or UUID)
      - session_id (chat session ID)
      - run_id (optional execution run ID)
      - correlation_id (tracing correlation ID)
      - source ('ws_chat', 'rest_chat', etc.)
      - ttl_seconds (bounded lifetime, default 300.0 seconds)

    Features:
      - Async/await safe (backed by Python contextvars)
      - Supports nested scopes cleanly, restoring the outer scope upon exit
      - Enforces that authenticated_principal is non-empty and non-anonymous
      - Enforces monotonic TTL expiration to prevent zombie/replayed scopes
      - Cleans up token via try/finally on exit, exception, or cancellation
    """

    def __init__(
        self,
        authenticated_principal: str,
        session_id: str,
        run_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        source: str = SOURCE_WS_CHAT,
        ttl_seconds: float = 300.0,
        budget_limit_usd: float = 0.0,
        idempotency_key: Optional[str] = None,
    ):
        if not authenticated_principal or str(authenticated_principal).strip().lower() in ("anon_unknown", "anonymous", "none", "", "unknown", "null"):
            raise ValueError(f"UserChatExecutionScope requires a valid authenticated principal, got {authenticated_principal!r}")
        if not session_id or not str(session_id).strip():
            raise ValueError("UserChatExecutionScope requires a non-empty session_id")

        parent = get_current_inference_context()
        parent_token = parent.scope_token if parent else None

        self.context = InferenceAuthorizationContext(
            trigger=TRIGGER_EXPLICIT_CHAT_SUBMIT,
            authorization_class=AUTH_CLASS_USER_AUTHORIZED,
            user_id_hash=hash_user_id(authenticated_principal),
            correlation_id=correlation_id or (parent.correlation_id if parent else uuid.uuid4().hex[:16]),
            run_id=run_id or (parent.run_id if parent else None),
            job_id=None,
            idempotency_key=idempotency_key,
            budget_limit_usd=budget_limit_usd,
            authenticated_principal=str(authenticated_principal).strip(),
            session_id=str(session_id).strip(),
            source=source,
            created_at_mono=time.monotonic(),
            ttl_seconds=max(0.001, float(ttl_seconds)),
            parent_scope_token=parent_token,
        )
        self._token: Optional[contextvars.Token] = None

    def __enter__(self) -> InferenceAuthorizationContext:
        self._token = _CURRENT_CONTEXT.set(self.context)
        return self.context

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._token is not None:
            _CURRENT_CONTEXT.reset(self._token)
            self._token = None

    async def __aenter__(self) -> InferenceAuthorizationContext:
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self.__exit__(exc_type, exc_val, exc_tb)


def user_chat_execution_scope(
    authenticated_principal: str,
    session_id: str,
    run_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    source: str = SOURCE_WS_CHAT,
    ttl_seconds: float = 300.0,
    budget_limit_usd: float = 0.0,
    idempotency_key: Optional[str] = None,
) -> UserChatExecutionScope:
    """Create a scoped server-authored user chat execution context."""
    return UserChatExecutionScope(
        authenticated_principal=authenticated_principal,
        session_id=session_id,
        run_id=run_id,
        correlation_id=correlation_id,
        source=source,
        ttl_seconds=ttl_seconds,
        budget_limit_usd=budget_limit_usd,
        idempotency_key=idempotency_key,
    )


class InferenceContextManager(AbstractContextManager, AbstractAsyncContextManager):
    """Context manager supporting both synchronous and asynchronous usage."""

    def __init__(
        self,
        trigger: str = TRIGGER_EXPLICIT_CHAT_SUBMIT,
        authorization_class: Optional[str] = None,
        user_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        run_id: Optional[str] = None,
        job_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        budget_limit_usd: float = 0.0,
        authenticated_principal: Optional[str] = None,
        session_id: Optional[str] = None,
        source: str = SOURCE_UNKNOWN,
        ttl_seconds: float = 300.0,
    ):
        if authorization_class is None:
            if trigger in (TRIGGER_EXPLICIT_CHAT_SUBMIT, TRIGGER_USER_CHAT):
                authorization_class = AUTH_CLASS_USER_AUTHORIZED
            elif trigger in (TRIGGER_AUTHORIZED_RUN_ID, TRIGGER_SCHEDULER_JOB_ID):
                authorization_class = AUTH_CLASS_TASK_PREVIOUSLY_AUTHORIZED
            else:
                authorization_class = AUTH_CLASS_USER_AUTHORIZED

        eff_principal = authenticated_principal or user_id
        parent = get_current_inference_context()
        parent_token = parent.scope_token if parent else None

        self.context = InferenceAuthorizationContext(
            trigger=trigger,
            authorization_class=authorization_class,
            user_id_hash=hash_user_id(eff_principal),
            correlation_id=correlation_id or (parent.correlation_id if parent else uuid.uuid4().hex[:16]),
            run_id=run_id or (parent.run_id if parent else None),
            job_id=job_id,
            idempotency_key=idempotency_key,
            budget_limit_usd=budget_limit_usd,
            authenticated_principal=eff_principal,
            session_id=session_id or (parent.session_id if parent else None),
            source=source or (parent.source if parent else SOURCE_UNKNOWN),
            created_at_mono=time.monotonic(),
            ttl_seconds=max(0.001, float(ttl_seconds)),
            parent_scope_token=parent_token,
        )
        self._token: Optional[contextvars.Token] = None

    def __enter__(self) -> InferenceAuthorizationContext:
        self._token = _CURRENT_CONTEXT.set(self.context)
        return self.context

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._token is not None:
            _CURRENT_CONTEXT.reset(self._token)
            self._token = None

    async def __aenter__(self) -> InferenceAuthorizationContext:
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self.__exit__(exc_type, exc_val, exc_tb)


def inference_authorization_context(
    trigger: str = TRIGGER_EXPLICIT_CHAT_SUBMIT,
    authorization_class: Optional[str] = None,
    user_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    run_id: Optional[str] = None,
    job_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    budget_limit_usd: float = 0.0,
    authenticated_principal: Optional[str] = None,
    session_id: Optional[str] = None,
    source: str = SOURCE_UNKNOWN,
    ttl_seconds: float = 300.0,
) -> InferenceContextManager:
    """Create a scoped authorization context manager."""
    return InferenceContextManager(
        trigger=trigger,
        authorization_class=authorization_class,
        user_id=user_id,
        correlation_id=correlation_id,
        run_id=run_id,
        job_id=job_id,
        idempotency_key=idempotency_key,
        budget_limit_usd=budget_limit_usd,
        authenticated_principal=authenticated_principal,
        session_id=session_id,
        source=source,
        ttl_seconds=ttl_seconds,
    )


def run_with_inference_context(context: InferenceAuthorizationContext, func: Callable, *args: Any, **kwargs: Any) -> Any:
    """Run a sync function in a thread with the specified inference authorization context active."""
    token = _CURRENT_CONTEXT.set(context)
    try:
        return func(*args, **kwargs)
    finally:
        _CURRENT_CONTEXT.reset(token)


def propagate_inference_context(func: Callable) -> Callable:
    """
    Wrap a callable to capture the active inference authorization context
    and apply it inside worker threads or detached tasks.
    """
    captured_ctx = get_current_inference_context()
    if inspect.iscoroutinefunction(func):
        async def async_wrapper(*args: Any, **kwargs: Any):
            token = _CURRENT_CONTEXT.set(captured_ctx)
            try:
                return await func(*args, **kwargs)
            finally:
                _CURRENT_CONTEXT.reset(token)
        return async_wrapper
    else:
        def sync_wrapper(*args: Any, **kwargs: Any):
            token = _CURRENT_CONTEXT.set(captured_ctx)
            try:
                return func(*args, **kwargs)
            finally:
                _CURRENT_CONTEXT.reset(token)
        return sync_wrapper

