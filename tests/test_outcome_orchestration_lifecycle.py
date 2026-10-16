# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for end-to-end outcome orchestration lifecycle, state transitions, fault isolation, and blockers."""

import pytest
from backend.database import init_db
from backend.outcome_orchestration.models import (
    Blocker,
    OutcomeContract,
    OutcomeState,
    OutputState,
    SourceAsset,
)
from backend.outcome_orchestration.orchestrator import OutcomeOrchestrator
from backend.outcome_orchestration.port_interface import InProcessFakeProducerPort
from backend.outcome_orchestration.state_machine import StateTransitionError


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.mark.asyncio
async def test_direct_source_bypasses_trends_and_reaches_ready_for_review():
    """Requirement A4 / Scenario PROD: Directly uploaded / authorized source bypasses Trends discovery."""
    contract = OutcomeOrchestrator.parse_contract_from_prompt("Turn my gameplay video into three 60-second clips.")
    contract.source_assets = [
        SourceAsset(
            asset_id="src_user_recording_1",
            editorial_role="primary_footage",
            permitted_uses=["clip_extraction", "motion_review"],
            acquisition_route="authorized_upload",
            is_accessible=True,
        )
    ]

    port = InProcessFakeProducerPort()
    report = await OutcomeOrchestrator.execute_batch_outcome(contract, producer_port=port)

    assert report.status == "COMPLETE"
    assert len(report.outputs) == 3
    for out in report.outputs:
        assert out.state == OutputState.SUCCEEDED
        assert out.media_probe is not None
        assert out.media_probe.duration_seconds == 60.0
        assert out.checks.technical == "PASS"
        assert out.checks.contract == "PASS"
        assert out.checks.editorial == "NOT_ASSESSED"

    sm = OutcomeOrchestrator.get_state_machine(contract)
    assert sm.current_state == OutcomeState.READY_FOR_REVIEW
    # Ensure SOURCE_DISCOVERY was NOT entered (bypassed)
    step_names = [e.step_name for e in sm.history]
    assert not any("SOURCE_DISCOVERY" in s for s in step_names), "Direct source MUST bypass Trends discovery!"


@pytest.mark.asyncio
async def test_create_project_does_not_terminate_run():
    """Requirement A2: create_project is strictly an intermediate step; next state is observable."""
    from backend.services.project_service import ProjectService

    proj = await ProjectService.create_project(name="Orchestration Intermediate Test", aspect_ratio="9:16")
    assert proj.id is not None
    assert proj.revision == 1

    contract = OutcomeOrchestrator.parse_contract_from_prompt(
        "Make 3 60-second clips",
        project_id=proj.id,
    )
    contract.source_assets = [
        SourceAsset(asset_id="src_fixture", is_accessible=True)
    ]

    sm = OutcomeOrchestrator.get_state_machine(contract)
    assert sm.current_state == OutcomeState.INTENT_CAPTURED

    # Execute workflow after project creation
    port = InProcessFakeProducerPort()
    report = await OutcomeOrchestrator.execute_batch_outcome(contract, producer_port=port)

    assert sm.current_state == OutcomeState.READY_FOR_REVIEW
    assert sm.current_state != OutcomeState.INTENT_CAPTURED
    assert len(sm.history) > 2


@pytest.mark.asyncio
async def test_inaccessible_or_unpermitted_source_terminates_in_blocked():
    """Requirement A4 / Scenario DISC: Without verified lawful bytes, ends in BLOCKED with specific blocker, NOT PASS."""
    contract = OutcomeOrchestrator.parse_contract_from_prompt("Find a viral Fortnite video and make three 60-second clips")
    # Candidate discovered on YouTube but bytes not downloaded/authorized
    contract.source_assets = [
        SourceAsset(
            asset_id="yt_cand_100facts",
            editorial_role="primary_footage",
            permitted_uses=["clip_extraction"],
            acquisition_route="trend_candidate",
            is_accessible=False,
        )
    ]

    port = InProcessFakeProducerPort()
    report = await OutcomeOrchestrator.execute_batch_outcome(contract, producer_port=port)

    assert report.status == "BLOCKED"
    assert len(report.blockers) > 0
    blk = report.blockers[0]
    assert blk.code == "SOURCE_ACCESS_DENIED"
    assert "not physically accessible" in blk.precise_reason or "permissions" in blk.precise_reason
    assert len(blk.next_action) > 0

    sm = OutcomeOrchestrator.get_state_machine(contract)
    assert sm.current_state == OutcomeState.BLOCKED
    assert sm.blocker is not None
    assert sm.current_state != OutcomeState.READY_FOR_REVIEW


@pytest.mark.asyncio
async def test_failure_of_third_output_preserves_two_valid_as_partial():
    """Requirement A3: Failure of 3rd output preserves outputs 1 and 2 as PARTIAL without failing batch or claiming COMPLETE."""
    contract = OutcomeOrchestrator.parse_contract_from_prompt("Produce three 60-second clips")
    contract.source_assets = [
        SourceAsset(asset_id="src_multi_output", is_accessible=True)
    ]

    port = InProcessFakeProducerPort()
    # Simulate encoder crash specifically on output index 2 (the 3rd output)
    report = await OutcomeOrchestrator.execute_batch_outcome(
        contract,
        producer_port=port,
        simulate_failure_index=2,
    )

    assert report.status == "PARTIAL"
    assert len(report.outputs) == 3

    # Output 1 and Output 2 must be intact and SUCCEEDED
    assert report.outputs[0].state == OutputState.SUCCEEDED
    assert report.outputs[0].media_probe is not None
    assert report.outputs[1].state == OutputState.SUCCEEDED
    assert report.outputs[1].media_probe is not None

    # Output 3 must be FAILED with error detail
    assert report.outputs[2].state == OutputState.FAILED
    assert "Simulated render encoder timeout" in report.outputs[2].error_detail

    sm = OutcomeOrchestrator.get_state_machine(contract)
    assert sm.current_state == OutcomeState.PARTIAL, "State machine must be PARTIAL, not READY_FOR_REVIEW and not FAILED!"


def test_illegal_state_transition_is_rejected():
    """State machine strictly rejects jumping from INTENT_CAPTURED to READY_FOR_REVIEW without evidence."""
    contract = OutcomeOrchestrator.parse_contract_from_prompt("Make clips")
    sm = OutcomeOrchestrator.get_state_machine(contract)

    with pytest.raises(StateTransitionError):
        sm.transition_to(OutcomeState.READY_FOR_REVIEW)
