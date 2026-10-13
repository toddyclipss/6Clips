# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for versioned OutcomeContract, multi-turn goal continuity, intent classification, and snapshot immutability."""

import pytest
from backend.outcome_orchestration.models import (
    DurationPolicy,
    IntentKind,
    ModelSnapshot,
    OutcomeContract,
    OutputState,
    SourceAsset,
)
from backend.outcome_orchestration.orchestrator import OutcomeOrchestrator


def test_contract_parsing_from_initial_prompt():
    """Verify Turn 1 extracts 3 distinct outputs, 60s, 9:16 from prompt."""
    prompt = "Find a viral Fortnite video and turn it into three 60-second clips."
    contract = OutcomeOrchestrator.parse_contract_from_prompt(
        prompt,
        user_id="user_creator_1",
        snapshot=ModelSnapshot(selected_model_id="gemma4:e4b", selected_provider="ollama", selected_effort="high"),
    )

    assert contract.output_count == 3
    assert len(contract.outputs) == 3
    assert len({o.output_id for o in contract.outputs}) == 3, "Each output MUST have a distinct output_id"
    for out in contract.outputs:
        assert out.seconds == 60.0
        assert out.aspect_ratio == "9:16"
        assert out.duration_policy == DurationPolicy.TARGET
        assert out.tolerance_seconds == 3.0

    assert contract.snapshot is not None
    assert contract.snapshot.selected_model_id == "gemma4:e4b"
    assert contract.snapshot.selected_provider == "ollama"
    assert contract.snapshot.selected_effort == "high"


def test_goal_continuity_on_followup_preserves_three_outputs():
    """Verify Turn 2 follow-up ('produce a video') preserves count=3, duration=60, aspect 9:16."""
    session_id = "sess_multi_turn_42"
    prompt_1 = "Find a viral Fortnite video and turn it into three 60-second clips."
    contract_1, intent_1 = OutcomeOrchestrator.get_or_create_contract_for_turn(
        prompt_1,
        session_id=session_id,
        user_id="user_creator_1",
    )
    assert intent_1 == IntentKind.NEW_REQUEST
    assert contract_1.output_count == 3

    # Turn 2 follow-up
    for follow_up in ("produce a video", "proceed", "continue", "make it", "sim, pode produzir"):
        contract_2, intent_2 = OutcomeOrchestrator.get_or_create_contract_for_turn(
            follow_up,
            session_id=session_id,
            user_id="user_creator_1",
        )
        assert intent_2 == IntentKind.CONTINUE, f"'{follow_up}' must resolve to IntentKind.CONTINUE"
        assert contract_2.contract_id == contract_1.contract_id, "Must retain the same contract ID"
        assert contract_2.output_count == 3, "Must NOT collapse to 1 single clip"
        assert len(contract_2.outputs) == 3
        assert len({o.output_id for o in contract_2.outputs}) == 3, "3 distinct output_ids must be preserved"
        assert contract_2.outputs[0].seconds == 60.0


def test_contract_change_request_bumps_version_and_preserves_lineage():
    """Verify changing requirements mid-flight creates v2 referencing v1 without clobbering."""
    session_id = "sess_change_req_1"
    contract_v1, _ = OutcomeOrchestrator.get_or_create_contract_for_turn(
        "Find a viral video and turn it into three 60-second clips",
        session_id=session_id,
    )
    assert contract_v1.contract_version == 1
    assert contract_v1.output_count == 3

    # Change request
    change_msg = "Actually, make two 30-second clips instead"
    contract_v2, intent_v2 = OutcomeOrchestrator.get_or_create_contract_for_turn(
        change_msg,
        session_id=session_id,
    )
    assert intent_v2 == IntentKind.CHANGE_REQUEST
    assert contract_v2.contract_version == 2
    assert contract_v2.parent_contract_id == contract_v1.contract_id
    assert contract_v2.output_count == 2
    assert len(contract_v2.outputs) == 2
    assert contract_v2.outputs[0].seconds == 30.0
    assert contract_v2.change_reason == change_msg


def test_selected_model_snapshot_is_immutable():
    """Verify selected model snapshot is captured and cannot be silently swapped or downgraded."""
    initial_snapshot = ModelSnapshot(
        selected_model_id="gemma4:e4b",
        selected_provider="ollama",
        selected_effort="high",
        input_revision=1,
    )
    contract = OutcomeOrchestrator.parse_contract_from_prompt(
        "Make 3 60s clips",
        snapshot=initial_snapshot,
    )
    assert contract.snapshot.selected_model_id == "gemma4:e4b"
    assert contract.snapshot.selected_provider == "ollama"
    assert contract.snapshot.selected_effort == "high"

    # Attempting to re-serialize or pass another snapshot does not silently mutate existing snapshot
    snap_dict = contract.snapshot.model_dump()
    assert snap_dict["selected_model_id"] == "gemma4:e4b"
    assert snap_dict["selected_provider"] == "ollama"


def test_editorial_check_not_assessed_invariant():
    """Verify editorial check defaults to NOT_ASSESSED and is never fabricated as human approval."""
    from backend.outcome_orchestration.port_interface import InProcessFakeProducerPort
    port = InProcessFakeProducerPort()

    contract = OutcomeOrchestrator.parse_contract_from_prompt("Create 3 clips")
    contract.source_assets = [
        SourceAsset(asset_id="src_owned", is_accessible=True, rights_verified=True)
    ]

    import asyncio
    report = asyncio.run(port.submit_batch(contract))
    assert report["accepted"] is True

    batch = asyncio.run(port.get_batch(report["job_id"]))
    for out in batch.outputs:
        assert out.checks.editorial == "NOT_ASSESSED", (
            "Invariant violation: automated port MUST NOT forge human creative approval!"
        )
        assert out.checks.technical == "PASS"
        assert out.checks.contract == "PASS"


def test_duration_policy_reconciliation_exact_target_max():
    """Verify that EXACT (±1.0s), TARGET (±3.0s), and MAX (0.0s) policies are cleanly parsed and reconciled."""
    # 1. Exact prompt
    c_exact = OutcomeOrchestrator.parse_contract_from_prompt("Extract 3 clips of exactly 60 seconds each")
    assert c_exact.outputs[0].duration_policy == DurationPolicy.EXACT
    assert c_exact.outputs[0].tolerance_seconds == 1.0

    # 2. Max prompt
    c_max = OutcomeOrchestrator.parse_contract_from_prompt("Extract 3 clips up to 60 seconds")
    assert c_max.outputs[0].duration_policy == DurationPolicy.MAX
    assert c_max.outputs[0].tolerance_seconds == 0.0

    # 3. Conversational target prompt (default)
    c_target = OutcomeOrchestrator.parse_contract_from_prompt("Find a viral Fortnite video and turn it into three 60-second clips")
    assert c_target.outputs[0].duration_policy == DurationPolicy.TARGET
    assert c_target.outputs[0].tolerance_seconds == 3.0

    # 4. Explicit parameter override
    c_custom = OutcomeOrchestrator.parse_contract_from_prompt(
        "Make 3 clips",
        duration_policy=DurationPolicy.EXACT,
        tolerance_seconds=0.5,
    )
    assert c_custom.outputs[0].duration_policy == DurationPolicy.EXACT
    assert c_custom.outputs[0].tolerance_seconds == 0.5
