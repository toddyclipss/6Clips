# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
OAAS Outcomes Package.
Provides Outcome-as-a-Service orchestration: user goal -> autonomous plan -> project ->
render -> physical media verification -> library persistence -> fail-closed distribution handoff.
"""

from backend.oaas_outcomes.models import (
    OutcomeJobState,
    OutcomeRequestContract,
    OutcomePlan,
    MediaVerificationResult,
    Agent5DistributionHandoffContract,
    OutcomeJobRecord,
    DurationPolicy,
)
from backend.oaas_outcomes.state_machine import OutcomeStateMachine, InvalidStateTransitionError
from backend.oaas_outcomes.block_selector import BlockSelector
from backend.oaas_outcomes.media_verifier import MediaVerifier, MediaVerificationError
from backend.oaas_outcomes.distribution_handoff import DistributionHandoffManager
from backend.oaas_outcomes.engine import OutcomeDeliveryEngine
from backend.oaas_outcomes.adapter import OAASOutcomeAdapter

__all__ = [
    "OutcomeJobState",
    "OutcomeRequestContract",
    "OutcomePlan",
    "MediaVerificationResult",
    "Agent5DistributionHandoffContract",
    "OutcomeJobRecord",
    "DurationPolicy",
    "OutcomeStateMachine",
    "InvalidStateTransitionError",
    "BlockSelector",
    "MediaVerifier",
    "MediaVerificationError",
    "DistributionHandoffManager",
    "OutcomeDeliveryEngine",
    "OAASOutcomeAdapter",
]
