# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Async-safe context propagation for inference authorization.
"""
import contextvars
import hashlib
import uuid
from dataclasses import dataclass
from typing import Optional, Any
from contextlib import AbstractAsyncContextManager, AbstractContextManager

from backend.llm_trace.models import (
    TRIGGER_EXPLICIT_CHAT_SUBMIT,
    TRIGGER_AUTHORIZED_RUN_ID,
    TRIGGER_SCHEDULER_JOB_ID,
    TRIGGER_TEST_AUTHORIZED,
    TRIGGER_UNKNOWN,
    AUTH_CLASS_USER_AUTHORIZED,
    AUTH_CLASS_TASK_PREVIOUSLY_AUTHORIZED,
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

    def __post_init__(self):
        if not self.correlation_id:
            self.correlation_id = uuid.uuid4().hex[:16]


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
    ):
        if authorization_class is None:
            if trigger == TRIGGER_EXPLICIT_CHAT_SUBMIT:
                authorization_class = AUTH_CLASS_USER_AUTHORIZED
            elif trigger in (TRIGGER_AUTHORIZED_RUN_ID, TRIGGER_SCHEDULER_JOB_ID):
                authorization_class = AUTH_CLASS_TASK_PREVIOUSLY_AUTHORIZED
            else:
                authorization_class = AUTH_CLASS_USER_AUTHORIZED

        self.context = InferenceAuthorizationContext(
            trigger=trigger,
            authorization_class=authorization_class,
            user_id_hash=hash_user_id(user_id),
            correlation_id=correlation_id or uuid.uuid4().hex[:16],
            run_id=run_id,
            job_id=job_id,
            idempotency_key=idempotency_key,
            budget_limit_usd=budget_limit_usd,
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
    )
