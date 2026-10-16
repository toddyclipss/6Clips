# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Unit and Contract Tests for Wave 20 Agent 1 Models and State Machine.
"""

import pytest
from pydantic import ValidationError

from backend.oaas_knowledge_orchestrator.models import (
    CreativeRationale,
    ImmutableRunEvidence,
    KnowledgeCitation,
    KnowledgeOrchestratorResponse,
    KnowledgeOrchestratorState,
    NativeMotionElement,
    NativeMotionScene,
    NativeMotionSpecContract,
    RevisionRequestContract,
    VideoRequestContract,
)
from backend.oaas_knowledge_orchestrator.state_machine import (
    InvalidStateTransitionError,
    KnowledgeOrchestratorStateMachine,
)


def test_video_request_contract_defaults_and_validation():
    req = VideoRequestContract(message="Make a 3-second kinetic video")
    assert req.message == "Make a 3-second kinetic video"
    assert req.user_id == "local"
    assert req.session_id == "default_session"
    assert req.allow_test_fixture is True

    with pytest.raises(ValidationError):
        VideoRequestContract(message="")


def test_revision_request_contract_validation():
    rev = RevisionRequestContract(
        run_id="krun-12345",
        user_feedback="Make it faster",
        expected_revision=2,
    )
    assert rev.run_id == "krun-12345"
    assert rev.expected_revision == 2

    with pytest.raises(ValidationError):
        RevisionRequestContract(run_id="", user_feedback="fast", expected_revision=1)

    with pytest.raises(ValidationError):
        RevisionRequestContract(run_id="krun-1", user_feedback="fast", expected_revision=0)


def test_state_machine_linear_happy_path():
    sm = KnowledgeOrchestratorStateMachine(initial_state=KnowledgeOrchestratorState.REQUESTED)
    assert sm.current_state == KnowledgeOrchestratorState.REQUESTED

    sm.transition_to(KnowledgeOrchestratorState.PLANNING, reason="Parsed goal")
    assert sm.current_state == KnowledgeOrchestratorState.PLANNING

    sm.transition_to(KnowledgeOrchestratorState.RETRIEVING_KNOWLEDGE, reason="Query corpus")
    assert sm.current_state == KnowledgeOrchestratorState.RETRIEVING_KNOWLEDGE

    sm.transition_to(KnowledgeOrchestratorState.COMPOSING, reason="Generate spec")
    assert sm.current_state == KnowledgeOrchestratorState.COMPOSING

    sm.transition_to(KnowledgeOrchestratorState.VALIDATING, reason="Verify bounds")
    assert sm.current_state == KnowledgeOrchestratorState.VALIDATING

    sm.transition_to(KnowledgeOrchestratorState.RENDERING, reason="Physical FFmpeg")
    assert sm.current_state == KnowledgeOrchestratorState.RENDERING

    sm.transition_to(KnowledgeOrchestratorState.VIDEO_VERIFIED, reason="FFprobe ok")
    assert sm.current_state == KnowledgeOrchestratorState.VIDEO_VERIFIED

    sm.transition_to(KnowledgeOrchestratorState.REVIEW_READY, reason="Ready for user")
    assert sm.current_state == KnowledgeOrchestratorState.REVIEW_READY

    assert len(sm.history) == 8


def test_state_machine_invalid_transition_raises():
    sm = KnowledgeOrchestratorStateMachine(initial_state=KnowledgeOrchestratorState.REQUESTED)
    with pytest.raises(InvalidStateTransitionError):
        sm.transition_to(KnowledgeOrchestratorState.RENDERING, reason="Skip steps")


def test_state_machine_bounded_self_repair_budget():
    sm = KnowledgeOrchestratorStateMachine(
        initial_state=KnowledgeOrchestratorState.VALIDATING,
        max_retries=2,
    )

    # Retry 1
    sm.transition_to(KnowledgeOrchestratorState.COMPOSING, reason="Repair 1")
    sm.transition_to(KnowledgeOrchestratorState.VALIDATING, reason="Re-validate 1")

    # Retry 2
    sm.transition_to(KnowledgeOrchestratorState.COMPOSING, reason="Repair 2")
    sm.transition_to(KnowledgeOrchestratorState.VALIDATING, reason="Re-validate 2")

    # Retry 3 -> should exhaust budget and escalate to FAILED_TERMINAL
    sm.transition_to(KnowledgeOrchestratorState.COMPOSING, reason="Repair 3")
    assert sm.current_state == KnowledgeOrchestratorState.FAILED_TERMINAL
    assert len(sm.repair_log) == 3
