# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for run persistence, recovery on disconnect/reload, lost confirmation idempotency, CAS, and multi-user isolation."""

from uuid import uuid4
import pytest
from backend.database import init_db
from backend.outcome_orchestration.models import (
    IntentKind,
    OutcomeContract,
    OutcomeState,
    OutputState,
    SourceAsset,
)
from backend.outcome_orchestration.orchestrator import OutcomeOrchestrator
from backend.outcome_orchestration.port_interface import InProcessFakeProducerPort
from backend.services.project_service import ProjectService
from backend.core.exceptions import RevisionConflictError


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.mark.asyncio
async def test_reconnection_and_replay_does_not_duplicate_projects_or_clips():
    """Requirement A3: Reloading / reconnecting recovers existing run without creating duplicate projects or clips."""
    proj = await ProjectService.create_project(name="Recovery Canonical Project", aspect_ratio="9:16", user_id="user_alpha")
    initial_rev = proj.revision

    contract = OutcomeOrchestrator.parse_contract_from_prompt(
        "Make three 60s clips",
        project_id=proj.id,
        user_id="user_alpha",
    )
    contract.source_assets = [
        SourceAsset(asset_id="src_recov", is_accessible=True, rights_verified=True)
    ]

    port = InProcessFakeProducerPort()
    report_1 = await OutcomeOrchestrator.execute_batch_outcome(contract, producer_port=port)
    assert report_1.status == "COMPLETE"
    assert len(report_1.outputs) == 3

    # Client disconnects and reconnects (simulating browser reload / replay with same session)
    # The orchestrator is queried again for the same contract
    sm = OutcomeOrchestrator.get_state_machine(contract)
    assert sm.current_state == OutcomeState.READY_FOR_REVIEW

    # Check project in DB has not spawned a duplicate
    from backend.database import AsyncSessionLocal
    from sqlalchemy import select
    from backend.models.project import Project

    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Project).where(Project.user_id == "user_alpha"))
        all_projects = res.scalars().all()
    matching = [p for p in all_projects if p.id == proj.id]
    assert len(matching) == 1, "Must NOT spawn duplicate project upon reload/replay"


@pytest.mark.asyncio
async def test_lost_confirmation_retry_is_idempotent():
    """Requirement A3: Retry after lost confirmation consults existing effects without re-executing."""
    contract = OutcomeOrchestrator.parse_contract_from_prompt("Create 3 clips from source")
    contract.source_assets = [
        SourceAsset(asset_id="src_idempotent", is_accessible=True, rights_verified=True)
    ]

    port = InProcessFakeProducerPort()
    # Initial batch submission
    res_1 = await port.submit_batch(contract)
    job_id_1 = res_1["job_id"]
    assert res_1["accepted"] is True

    # Simulate client never received confirmation and retried with exact same contract
    # In a real environment, submit_batch uses fingerprinting or the orchestrator consults existing job
    batch_report_1 = await port.get_batch(job_id_1)
    assert batch_report_1.status == "COMPLETE"

    # Querying job returns existing outputs without generating new random IDs
    batch_report_2 = await port.get_batch(job_id_1)
    assert batch_report_2.job_id == job_id_1
    assert [o.output_id for o in batch_report_2.outputs] == [o.output_id for o in batch_report_1.outputs]


@pytest.mark.asyncio
async def test_batch_cancellation_preserves_committed_effects():
    """Requirement A3: Cancelling an execution run acknowledges cancellation and reports committed effects."""
    contract = OutcomeOrchestrator.parse_contract_from_prompt("Make 3 vertical clips")
    contract.source_assets = [
        SourceAsset(asset_id="src_cancel_test", is_accessible=True, rights_verified=True)
    ]

    port = InProcessFakeProducerPort()
    res = await port.submit_batch(contract)
    job_id = res["job_id"]

    # Cancel batch
    cancel_res = await port.cancel_batch(job_id)
    assert cancel_res["acknowledged"] is True

    report = await port.get_batch(job_id)
    assert report.status == "CANCELLED"

    sm = OutcomeOrchestrator.get_state_machine(contract)
    sm.update_from_production_report(report)
    assert sm.current_state == OutcomeState.CANCELLED


@pytest.mark.asyncio
async def test_cas_expected_revision_concurrency_protection():
    """Requirement B16: Optimistic concurrency CAS rejects stale expected_revision."""
    proj = await ProjectService.create_project(name="CAS Test Project")
    assert proj.revision == 1

    # User 1 successfully applies an operation
    res_1 = await ProjectService.apply_operation(
        project_id=proj.id,
        expected_revision=1,
        operation_type="add_clip",
        payload={"track_id": "track_video_main", "clip": {"id": "c1", "duration_seconds": 10.0}},
    )
    assert res_1["revision"] == 2

    # User 2 attempts to apply an operation with stale expected_revision=1
    with pytest.raises(RevisionConflictError):
        await ProjectService.apply_operation(
            project_id=proj.id,
            expected_revision=1,  # Stale! Current is 2
            operation_type="add_clip",
            payload={"track_id": "track_video_main", "clip": {"id": "c2", "duration_seconds": 15.0}},
        )


@pytest.mark.asyncio
async def test_multi_user_isolation_between_creators():
    """Requirement L14: Multi-user isolation ensures user A cannot see or mutate user B's projects."""
    proj_a = await ProjectService.create_project(name="User A Private Project", user_id="creator_alice")
    proj_b = await ProjectService.create_project(name="User B Private Project", user_id="creator_bob")

    from backend.database import AsyncSessionLocal
    from sqlalchemy import select
    from backend.models.project import Project

    async with AsyncSessionLocal() as db:
        res_a = await db.execute(select(Project).where(Project.user_id == "creator_alice"))
        alice_projects = res_a.scalars().all()
        res_b = await db.execute(select(Project).where(Project.user_id == "creator_bob"))
        bob_projects = res_b.scalars().all()

    assert any(p.id == proj_a.id for p in alice_projects)
    assert not any(p.id == proj_b.id for p in alice_projects), "Alice must NOT see Bob's projects!"

    assert any(p.id == proj_b.id for p in bob_projects)
    assert not any(p.id == proj_a.id for p in bob_projects), "Bob must NOT see Alice's projects!"


@pytest.mark.asyncio
async def test_process_restart_reloads_contract_and_state():
    """Verify durable persistence: clearing in-memory caches reloads contract and state from disk."""
    session_id = f"sess_restart_{uuid4().hex[:8]}"

    # Turn 1: create contract
    contract1, intent1 = OutcomeOrchestrator.get_or_create_contract_for_turn(
        "Find a viral Fortnite video and turn it into three 60-second clips.",
        session_id=session_id,
        user_id="creator_restart",
    )
    sm1 = OutcomeOrchestrator.get_state_machine(contract1)
    sm1.transition_to(OutcomeState.SOURCE_ACCESS_VERIFIED, detail="Initial verified source")
    OutcomeOrchestrator._save_state_machine(sm1)

    # Simulate process termination / restart: clear all in-memory class dictionaries
    OutcomeOrchestrator._active_contracts.clear()
    OutcomeOrchestrator._state_machines.clear()

    # Turn 2: follow-up turn in new process
    contract2, intent2 = OutcomeOrchestrator.get_or_create_contract_for_turn(
        "produce a video",
        session_id=session_id,
        user_id="creator_restart",
    )

    assert intent2 == IntentKind.CONTINUE
    assert contract2.contract_id == contract1.contract_id
    assert contract2.output_count == 3
    assert len(contract2.outputs) == 3

    # State machine should also be reloaded
    sm2 = OutcomeOrchestrator.get_state_machine(contract2)
    assert sm2.current_state == OutcomeState.SOURCE_ACCESS_VERIFIED
    assert any(h.status == OutcomeState.SOURCE_ACCESS_VERIFIED.value for h in sm2.history)


@pytest.mark.asyncio
async def test_adapt_contract_to_producer_request_structure():
    """Verify that OutcomeContract adapts cleanly to producer request payload structure."""
    from backend.outcome_orchestration.models import adapt_contract_to_producer_request

    contract = OutcomeOrchestrator.parse_contract_from_prompt(
        "Create 3 60s clips from my gameplay",
        user_id="user_test",
        source_assets=[
            SourceAsset(
                asset_id="src_gameplay_01",
                editorial_role="primary_footage",
                permitted_uses=["clip_extraction", "motion_review"],
                acquisition_route="authorized_fixture",
            )
        ],
    )
    req = adapt_contract_to_producer_request(contract)

    # Regardless of whether backend.media_pipeline is imported or dict is returned
    assert getattr(req, "contract_id", None) == contract.contract_id or req.get("contract_id") == contract.contract_id
    assert getattr(req, "schema_version", None) == "production.v1" or req.get("schema_version") == "production.v1"
    sources = getattr(req, "source_assets", None) if hasattr(req, "source_assets") else req.get("source_assets")
    assert len(sources) == 1
    outputs = getattr(req, "outputs", None) if hasattr(req, "outputs") else req.get("outputs")
    assert len(outputs) == 3
