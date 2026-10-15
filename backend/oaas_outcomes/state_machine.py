# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Outcome State Machine with strict verification guards and state audit logs."""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone

from backend.oaas_outcomes.models import (
    MediaVerificationResult,
    OutcomeJobRecord,
    OutcomeJobState,
    StateTransitionEvent,
)

logger = logging.getLogger(__name__)

# Strict forward transition mapping
ALLOWED_TRANSITIONS: Dict[OutcomeJobState, List[OutcomeJobState]] = {
    OutcomeJobState.REQUESTED: [
        OutcomeJobState.PLANNED,
        OutcomeJobState.FAILED,
        OutcomeJobState.CANCELLED,
    ],
    OutcomeJobState.PLANNED: [
        OutcomeJobState.PRODUCING,
        OutcomeJobState.FAILED,
        OutcomeJobState.CANCELLED,
    ],
    OutcomeJobState.PRODUCING: [
        OutcomeJobState.RENDERED,
        OutcomeJobState.FAILED,
        OutcomeJobState.CANCELLED,
    ],
    OutcomeJobState.RENDERED: [
        OutcomeJobState.VERIFIED,
        OutcomeJobState.FAILED,
        OutcomeJobState.CANCELLED,
    ],
    OutcomeJobState.VERIFIED: [
        OutcomeJobState.READY_FOR_DELIVERY,
        OutcomeJobState.NEEDS_APPROVAL,
        OutcomeJobState.PENDING_CREDENTIALS,
        OutcomeJobState.FAILED,
        OutcomeJobState.CANCELLED,
    ],
    OutcomeJobState.NEEDS_APPROVAL: [
        OutcomeJobState.READY_FOR_DELIVERY,
        OutcomeJobState.PENDING_CREDENTIALS,
        OutcomeJobState.FAILED,
        OutcomeJobState.CANCELLED,
    ],
    OutcomeJobState.PENDING_CREDENTIALS: [
        OutcomeJobState.READY_FOR_DELIVERY,
        OutcomeJobState.NEEDS_APPROVAL,
        OutcomeJobState.FAILED,
        OutcomeJobState.CANCELLED,
    ],
    OutcomeJobState.READY_FOR_DELIVERY: [
        OutcomeJobState.FAILED,
        OutcomeJobState.CANCELLED,
    ],
    OutcomeJobState.FAILED: [
        OutcomeJobState.REQUESTED,  # Allowed on idempotent retry
        OutcomeJobState.PLANNED,    # Allowed on retry from planning
    ],
    OutcomeJobState.CANCELLED: [],
}


class InvalidStateTransitionError(Exception):
    """Raised when an illegal or unverified state transition is attempted."""
    pass


class OutcomeStateMachine:
    """Manages lifecycle transitions for an OutcomeJobRecord with strict integrity assertions."""

    def __init__(self, job_record: OutcomeJobRecord):
        self.record = job_record

    @property
    def current_state(self) -> OutcomeJobState:
        return self.record.state

    def can_transition_to(self, target_state: OutcomeJobState) -> bool:
        allowed = ALLOWED_TRANSITIONS.get(self.record.state, [])
        return target_state in allowed

    def transition_to(
        self,
        target_state: OutcomeJobState,
        reason: str = "",
        error_detail: Optional[str] = None,
        verification_result: Optional[MediaVerificationResult] = None,
    ) -> OutcomeJobState:
        """
        Transition job to target state.
        Enforces physical media verification before reaching VERIFIED,
        and persistence/approval guards before reaching READY_FOR_DELIVERY.
        """
        if not self.can_transition_to(target_state):
            raise InvalidStateTransitionError(
                f"Illegal transition from {self.record.state.value} to {target_state.value}. "
                f"Allowed destinations: {[s.value for s in ALLOWED_TRANSITIONS.get(self.record.state, [])]}"
            )

        # Strict Reality Lock Guards:
        if target_state == OutcomeJobState.VERIFIED:
            v = verification_result or self.record.media_verification
            if v is None or not v.is_verified:
                raise InvalidStateTransitionError(
                    "Cannot transition to VERIFIED without a valid physical media verification result. "
                    "Media file must exist, decode via ffprobe, and exhibit valid dimensions/duration."
                )
            self.record.media_verification = v

        if target_state == OutcomeJobState.READY_FOR_DELIVERY:
            if not self.record.media_verification or not self.record.media_verification.is_verified:
                raise InvalidStateTransitionError(
                    "Cannot transition to READY_FOR_DELIVERY without prior VERIFIED media status."
                )

        # Record transition
        event = StateTransitionEvent(
            from_state=self.record.state,
            to_state=target_state,
            timestamp=datetime.now(timezone.utc).isoformat(),
            reason=reason,
            error_detail=error_detail,
        )
        self.record.history.append(event)
        self.record.state = target_state
        self.record.updated_at = datetime.now(timezone.utc).isoformat()

        if target_state == OutcomeJobState.FAILED:
            self.record.error_truth = error_detail or reason

        logger.info(
            "OAAS Job %s: %s -> %s (reason=%r)",
            self.record.job_id,
            event.from_state.value,
            target_state.value,
            reason,
        )
        return self.record.state
