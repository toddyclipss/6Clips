# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Outcome Orchestration package — versioned contracts, state machine, and MediaProducerPort."""

from backend.outcome_orchestration.models import (
    Blocker,
    Checks,
    DurationPolicy,
    ExecutionLimits,
    IntentKind,
    MediaProbe,
    ModelSnapshot,
    OutcomeContract,
    OutcomeState,
    OutputResult,
    OutputSpec,
    OutputState,
    ProductionReport,
    SourceAsset,
    SourceRange,
    StepEvent,
)
from backend.outcome_orchestration.port_interface import (
    InProcessFakeProducerPort,
    MediaProducerPort,
    get_media_producer_port,
    set_media_producer_port,
)
from backend.outcome_orchestration.state_machine import (
    OutcomeStateMachine,
    StateTransitionError,
)
from backend.outcome_orchestration.orchestrator import OutcomeOrchestrator

__all__ = [
    "Blocker",
    "Checks",
    "DurationPolicy",
    "ExecutionLimits",
    "IntentKind",
    "MediaProbe",
    "ModelSnapshot",
    "OutcomeContract",
    "OutcomeState",
    "OutputResult",
    "OutputSpec",
    "OutputState",
    "ProductionReport",
    "SourceAsset",
    "SourceRange",
    "StepEvent",
    "MediaProducerPort",
    "InProcessFakeProducerPort",
    "get_media_producer_port",
    "set_media_producer_port",
    "OutcomeStateMachine",
    "StateTransitionError",
    "OutcomeOrchestrator",
]
