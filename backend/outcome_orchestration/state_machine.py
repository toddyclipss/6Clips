# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Outcome State Machine with observable transitions and evidence-backed verifications."""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from backend.outcome_orchestration.models import (
    Blocker,
    OutcomeContract,
    OutcomeState,
    OutputResult,
    OutputState,
    ProductionReport,
    StepEvent,
)

logger = logging.getLogger(__name__)


# Permitted linear forward progression transitions
ALLOWED_TRANSITIONS: Dict[OutcomeState, List[OutcomeState]] = {
    OutcomeState.INTENT_CAPTURED: [
        OutcomeState.SOURCE_DISCOVERY,
        OutcomeState.SOURCE_ACCESS_VERIFIED,
        OutcomeState.WAITING_FOR_INPUT,
        OutcomeState.BLOCKED,
        OutcomeState.CANCELLED,
    ],
    OutcomeState.SOURCE_DISCOVERY: [
        OutcomeState.SOURCE_ACCESS_VERIFIED,
        OutcomeState.BLOCKED,
        OutcomeState.WAITING_FOR_INPUT,
        OutcomeState.CANCELLED,
    ],
    OutcomeState.SOURCE_ACCESS_VERIFIED: [
        OutcomeState.MEDIA_INGESTED,
        OutcomeState.BLOCKED,
        OutcomeState.CANCELLED,
    ],
    OutcomeState.MEDIA_INGESTED: [
        OutcomeState.MEDIA_ANALYZED,
        OutcomeState.BLOCKED,
        OutcomeState.FAILED,
        OutcomeState.CANCELLED,
    ],
    OutcomeState.MEDIA_ANALYZED: [
        OutcomeState.HIGHLIGHTS_SELECTED,
        OutcomeState.BLOCKED,
        OutcomeState.WAITING_FOR_INPUT,
        OutcomeState.CANCELLED,
    ],
    OutcomeState.HIGHLIGHTS_SELECTED: [
        OutcomeState.RESULTS_COMPOSED,
        OutcomeState.BLOCKED,
        OutcomeState.CANCELLED,
    ],
    OutcomeState.RESULTS_COMPOSED: [
        OutcomeState.RENDER_RUNNING,
        OutcomeState.PAUSED,
        OutcomeState.BLOCKED,
        OutcomeState.CANCELLED,
    ],
    OutcomeState.RENDER_RUNNING: [
        OutcomeState.RENDERS_VERIFIED,
        OutcomeState.PARTIAL,
        OutcomeState.PAUSED,
        OutcomeState.BLOCKED,
        OutcomeState.FAILED,
        OutcomeState.CANCELLED,
    ],
    OutcomeState.RENDERS_VERIFIED: [
        OutcomeState.READY_FOR_REVIEW,
        OutcomeState.PARTIAL,
    ],
    OutcomeState.READY_FOR_REVIEW: [
        OutcomeState.PAUSED,
        OutcomeState.CANCELLED,
    ],
    OutcomeState.PARTIAL: [
        OutcomeState.RENDER_RUNNING,  # On retry of pending items
        OutcomeState.PAUSED,
        OutcomeState.CANCELLED,
    ],
    OutcomeState.WAITING_FOR_INPUT: [
        OutcomeState.INTENT_CAPTURED,
        OutcomeState.SOURCE_ACCESS_VERIFIED,
        OutcomeState.MEDIA_INGESTED,
        OutcomeState.RESULTS_COMPOSED,
        OutcomeState.CANCELLED,
    ],
    OutcomeState.PAUSED: [
        OutcomeState.RENDER_RUNNING,
        OutcomeState.RESULTS_COMPOSED,
        OutcomeState.CANCELLED,
    ],
    OutcomeState.BLOCKED: [
        OutcomeState.INTENT_CAPTURED,  # On revised contract / new source
        OutcomeState.SOURCE_DISCOVERY,
        OutcomeState.CANCELLED,
    ],
    OutcomeState.CANCELLED: [],
    OutcomeState.FAILED: [
        OutcomeState.INTENT_CAPTURED,  # On replan
    ],
}


class StateTransitionError(ValueError):
    """Raised when an illegal state transition is attempted."""
    pass


class OutcomeStateMachine:
    """Manages observable state transitions for an OutcomeContract execution run."""

    def __init__(self, contract: OutcomeContract, initial_state: OutcomeState = OutcomeState.INTENT_CAPTURED):
        self.contract = contract
        self.current_state = initial_state
        self.history: List[StepEvent] = [
            StepEvent(
                step_name="INIT",
                status=initial_state.value,
                detail=f"Initialized contract {contract.contract_id} v{contract.contract_version}",
            )
        ]
        self.blocker: Optional[Blocker] = None
        self.evidence_refs: List[str] = []
        self.results: List[OutputResult] = []
        self.job_id: Optional[str] = getattr(contract, "job_id", None)

    def can_transition_to(self, target: OutcomeState) -> bool:
        allowed = ALLOWED_TRANSITIONS.get(self.current_state, [])
        return target in allowed

    def transition_to(
        self,
        target: OutcomeState,
        detail: Optional[str] = None,
        blocker: Optional[Blocker] = None,
        evidence_ref: Optional[str] = None,
    ) -> OutcomeState:
        """Advance the state machine with strict validation and evidence recording."""
        if not self.can_transition_to(target):
            raise StateTransitionError(
                f"Cannot transition from {self.current_state.value} to {target.value}. "
                f"Permitted targets: {[s.value for s in ALLOWED_TRANSITIONS.get(self.current_state, [])]}"
            )

        # Invariant checks
        if target == OutcomeState.BLOCKED and not blocker:
            raise StateTransitionError("Transition to BLOCKED requires a typed Blocker with code and reason.")

        if target in (OutcomeState.RENDERS_VERIFIED, OutcomeState.READY_FOR_REVIEW):
            self._verify_completion_invariants(target)

        old_state = self.current_state
        self.current_state = target
        if blocker:
            self.blocker = blocker
        if evidence_ref:
            self.evidence_refs.append(evidence_ref)

        event = StepEvent(
            step_name=f"{old_state.value}_TO_{target.value}",
            status=target.value,
            detail=detail or f"Advanced state to {target.value}",
        )
        self.history.append(event)
        logger.info(
            "OutcomeStateMachine [contract=%s v%d]: %s -> %s (%s)",
            self.contract.contract_id,
            self.contract.contract_version,
            old_state.value,
            target.value,
            detail or "",
        )
        return self.current_state

    def _verify_completion_invariants(self, target: OutcomeState) -> None:
        """Enforces that completion states strictly have verified outputs."""
        if not self.results:
            raise StateTransitionError(
                f"Cannot enter {target.value} with zero output results. External verifier must produce verified outputs."
            )

        failed_outputs = [r for r in self.results if r.state == OutputState.FAILED]
        if failed_outputs and target == OutcomeState.READY_FOR_REVIEW:
            raise StateTransitionError(
                f"Cannot enter READY_FOR_REVIEW when {len(failed_outputs)} output(s) failed. "
                "System must enter PARTIAL state."
            )

        for res in self.results:
            if res.state == OutputState.SUCCEEDED:
                if res.checks.technical != "PASS" or res.checks.contract != "PASS":
                    raise StateTransitionError(
                        f"Output '{res.output_id}' failed verifier checks (tech: {res.checks.technical}, contract: {res.checks.contract}). "
                        f"Cannot declare {target.value}."
                    )

    def update_from_production_report(self, report: ProductionReport) -> OutcomeState:
        """Update results and determine next state from a MediaProducerPort batch report."""
        self.results = report.outputs
        for ev in report.evidence_refs:
            if ev not in self.evidence_refs:
                self.evidence_refs.append(ev)

        if report.status == "COMPLETE":
            # Check all outputs
            all_succeeded = all(r.state == OutputState.SUCCEEDED for r in report.outputs) and len(report.outputs) >= self.contract.output_count
            if all_succeeded:
                self.transition_to(OutcomeState.RENDERS_VERIFIED, detail="All batch outputs verified successfully")
                return self.transition_to(OutcomeState.READY_FOR_REVIEW, detail="All verified outputs ready for user creative review")
            else:
                return self.transition_to(OutcomeState.PARTIAL, detail="Report marked COMPLETE but output count/states are partial")

        elif report.status == "PARTIAL":
            return self.transition_to(
                OutcomeState.PARTIAL,
                detail=f"Batch yielded partial results ({sum(1 for r in report.outputs if r.state == OutputState.SUCCEEDED)}/{len(report.outputs)} succeeded)",
            )

        elif report.status == "BLOCKED":
            blk = report.blockers[0] if report.blockers else Blocker(
                code="UNKNOWN_BLOCKER", precise_reason="Media producer reported BLOCKED without details", next_action="Inspect logs"
            )
            return self.transition_to(OutcomeState.BLOCKED, detail=blk.precise_reason, blocker=blk)

        elif report.status == "CANCELLED":
            return self.transition_to(OutcomeState.CANCELLED, detail="Media producer batch was cancelled")

        elif report.status == "RUNNING":
            if self.current_state != OutcomeState.RENDER_RUNNING:
                return self.transition_to(OutcomeState.RENDER_RUNNING, detail="Media producer batch is executing")
            return self.current_state

        return self.current_state

    def to_dict(self) -> Dict[str, Any]:
        """Serialize state machine state for durable persistence across restarts."""
        return {
            "current_state": self.current_state.value,
            "contract": self.contract.model_dump(),
            "history": [h.model_dump() for h in self.history],
            "blocker": self.blocker.model_dump() if self.blocker else None,
            "evidence_refs": list(self.evidence_refs),
            "results": [r.model_dump() for r in self.results],
            "job_id": self.job_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OutcomeStateMachine":
        """Reconstruct state machine from durable persistence dictionary."""
        contract = OutcomeContract.model_validate(data["contract"])
        sm = cls(contract, initial_state=OutcomeState(data["current_state"]))
        sm.history = [StepEvent.model_validate(h) for h in data.get("history", [])]
        if data.get("blocker"):
            sm.blocker = Blocker.model_validate(data["blocker"])
        sm.evidence_refs = data.get("evidence_refs", [])
        sm.results = [OutputResult.model_validate(r) for r in data.get("results", [])]
        sm.job_id = data.get("job_id") or getattr(contract, "job_id", None)
        return sm
