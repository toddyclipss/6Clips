# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Truthful State Machine for Knowledge-First OAAS Orchestration.
Enforces strictly validated linear progression, explicit blocker states,
and bounded self-repair loops with traceable audit history.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Set

from .models import KnowledgeOrchestratorState

logger = logging.getLogger(__name__)


class InvalidStateTransitionError(Exception):
    """Raised when an illegal or unsupported state transition is attempted."""
    pass


class KnowledgeOrchestratorStateMachine:
    """
    Finite state machine governing the lifecycle of a knowledge-first video generation run.
    """

    ALLOWED_TRANSITIONS: Dict[KnowledgeOrchestratorState, Set[KnowledgeOrchestratorState]] = {
        KnowledgeOrchestratorState.REQUESTED: {
            KnowledgeOrchestratorState.PLANNING,
            KnowledgeOrchestratorState.BLOCKED_RIGHTS,
            KnowledgeOrchestratorState.NEEDS_AUTHORIZATION,
            KnowledgeOrchestratorState.BLOCKED,
            KnowledgeOrchestratorState.FAILED_TERMINAL,
        },
        KnowledgeOrchestratorState.PLANNING: {
            KnowledgeOrchestratorState.RETRIEVING_KNOWLEDGE,
            KnowledgeOrchestratorState.BLOCKED_RIGHTS,
            KnowledgeOrchestratorState.NEEDS_AUTHORIZATION,
            KnowledgeOrchestratorState.BLOCKED,
            KnowledgeOrchestratorState.FAILED_RETRYABLE,
            KnowledgeOrchestratorState.FAILED_TERMINAL,
        },
        KnowledgeOrchestratorState.RETRIEVING_KNOWLEDGE: {
            KnowledgeOrchestratorState.COMPOSING,
            KnowledgeOrchestratorState.BLOCKED_RIGHTS,
            KnowledgeOrchestratorState.BLOCKED,
            KnowledgeOrchestratorState.FAILED_RETRYABLE,
            KnowledgeOrchestratorState.FAILED_TERMINAL,
        },
        KnowledgeOrchestratorState.COMPOSING: {
            KnowledgeOrchestratorState.VALIDATING,
            KnowledgeOrchestratorState.FAILED_RETRYABLE,
            KnowledgeOrchestratorState.FAILED_TERMINAL,
        },
        KnowledgeOrchestratorState.VALIDATING: {
            KnowledgeOrchestratorState.RENDERING,
            KnowledgeOrchestratorState.COMPOSING,  # Bounded self-repair loop
            KnowledgeOrchestratorState.FAILED_RETRYABLE,
            KnowledgeOrchestratorState.FAILED_TERMINAL,
            KnowledgeOrchestratorState.BLOCKED,
        },
        KnowledgeOrchestratorState.RENDERING: {
            KnowledgeOrchestratorState.VIDEO_VERIFIED,
            KnowledgeOrchestratorState.FAILED_RETRYABLE,
            KnowledgeOrchestratorState.FAILED_TERMINAL,
        },
        KnowledgeOrchestratorState.VIDEO_VERIFIED: {
            KnowledgeOrchestratorState.REVIEW_READY,
            KnowledgeOrchestratorState.PENDING_CREDENTIALS,
            KnowledgeOrchestratorState.NEEDS_AUTHORIZATION,
        },
        KnowledgeOrchestratorState.REVIEW_READY: {
            # Terminal success state, or can be re-planned for revision
            KnowledgeOrchestratorState.PLANNING,
        },
        KnowledgeOrchestratorState.PENDING_CREDENTIALS: {
            # Terminal delivery state awaiting external connection
            KnowledgeOrchestratorState.PLANNING,
        },
        KnowledgeOrchestratorState.FAILED_RETRYABLE: {
            KnowledgeOrchestratorState.PLANNING,
            KnowledgeOrchestratorState.COMPOSING,
            KnowledgeOrchestratorState.RENDERING,
            KnowledgeOrchestratorState.FAILED_TERMINAL,
        },
        KnowledgeOrchestratorState.FAILED_TERMINAL: set(),
        KnowledgeOrchestratorState.BLOCKED_RIGHTS: set(),
        KnowledgeOrchestratorState.NEEDS_AUTHORIZATION: {
            KnowledgeOrchestratorState.PLANNING,
        },
        KnowledgeOrchestratorState.BLOCKED: set(),
    }

    def __init__(
        self,
        initial_state: KnowledgeOrchestratorState = KnowledgeOrchestratorState.REQUESTED,
        max_retries: int = 3,
    ):
        self._current_state = initial_state
        self._max_retries = max_retries
        self._retry_count = 0
        self._history: List[Dict[str, Any]] = [
            {
                "from_state": None,
                "to_state": initial_state.value,
                "reason": "Initial state",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": {},
            }
        ]
        self._repair_log: List[Dict[str, Any]] = []

    @property
    def current_state(self) -> KnowledgeOrchestratorState:
        return self._current_state

    @property
    def history(self) -> List[Dict[str, Any]]:
        return list(self._history)

    @property
    def repair_log(self) -> List[Dict[str, Any]]:
        return list(self._repair_log)

    @property
    def retry_count(self) -> int:
        return self._retry_count

    def can_transition_to(self, target: KnowledgeOrchestratorState) -> bool:
        allowed = self.ALLOWED_TRANSITIONS.get(self._current_state, set())
        return target in allowed

    def transition_to(
        self,
        target: KnowledgeOrchestratorState,
        reason: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Transition to target state with validation, history logging, and retry budgeting.
        """
        if not self.can_transition_to(target):
            raise InvalidStateTransitionError(
                f"Cannot transition from {self._current_state.value} to {target.value}. "
                f"Allowed: {[s.value for s in self.ALLOWED_TRANSITIONS.get(self._current_state, set())]}"
            )

        # Track self-repair iterations
        if target == KnowledgeOrchestratorState.FAILED_RETRYABLE or (
            self._current_state == KnowledgeOrchestratorState.VALIDATING
            and target == KnowledgeOrchestratorState.COMPOSING
        ):
            self._retry_count += 1
            repair_entry = {
                "iteration": self._retry_count,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._repair_log.append(repair_entry)
            if self._retry_count > self._max_retries:
                logger.warning(
                    "Self-repair retry limit (%d) exceeded. Escalating to FAILED_TERMINAL.",
                    self._max_retries,
                )
                self._current_state = KnowledgeOrchestratorState.FAILED_TERMINAL
                self._history.append({
                    "from_state": self._current_state.value,
                    "to_state": KnowledgeOrchestratorState.FAILED_TERMINAL.value,
                    "reason": f"Retry budget exhausted: {reason}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "metadata": metadata or {},
                })
                return

        prev = self._current_state
        self._current_state = target
        self._history.append({
            "from_state": prev.value,
            "to_state": target.value,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        })
        logger.info("KnowledgeOrchestrator state: %s -> %s (%s)", prev.value, target.value, reason)
