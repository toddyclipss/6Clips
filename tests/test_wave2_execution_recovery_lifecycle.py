# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Deterministic tests for fresh-process recovery, same-text NEW_REQUEST vs RETRY,
idempotent duplicate submits, cancellation boundaries, and truthful partial outcomes."""

import asyncio
from pathlib import Path
import pytest

from backend.media_pipeline.models import (
    BatchStatus,
    DurationPolicy as BDurationPolicy,
    ExecutionLimitsV1,
    OutputSpecV1,
    OutputState,
    ProductionRequestV1,
    SourceAssetV1,
)
from backend.media_pipeline.producer_adapter import MediaProducerPort
from backend.outcome_orchestration.models import (
    IntentKind,
    OutcomeContract,
    OutcomeState,
    OutputResult,
    OutputSpec,
    ProductionReport,
    SourceAsset,
)
from backend.outcome_orchestration.orchestrator import OutcomeOrchestrator
from backend.outcome_orchestration.state_machine import OutcomeStateMachine


import subprocess


def _create_test_gameplay_fixture(target_path: Path, duration_s: int = 10) -> Path:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists() and target_path.stat().st_size > 10000:
        return target_path
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"testsrc=duration={duration_s}:size=1920x1080:rate=30",
        "-f", "lavfi",
        "-i", f"sine=frequency=440:duration={duration_s}",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        str(target_path),
    ]
    res = subprocess.run(cmd, capture_output=True)
    assert res.returncode == 0, f"FFmpeg fixture generation failed: {res.stderr.decode()}"
    return target_path


@pytest.fixture
def sample_source_video(tmp_path: Path) -> Path:
    """Create a minimal real gameplay video fixture via FFmpeg."""
    v_path = tmp_path / "gameplay_source.mp4"
    return _create_test_gameplay_fixture(v_path, duration_s=10)


@pytest.mark.asyncio
async def test_duplicate_submits_are_idempotent(tmp_path: Path, sample_source_video: Path):
    """B07, B13: Duplicate submits of identical requests return existing job with idempotent_replay."""
    storage_dir = tmp_path / "media_prod_idempotent"
    port = MediaProducerPort(storage_dir=storage_dir)

    req = ProductionRequestV1(
        schema_version="production.v1",
        run_id="run_idem_01",
        contract_id="cnt_idem_01",
        contract_version="1.0.0",
        project_id="proj_idem_01",
        user_id="creator_1",
        source_assets=[
            SourceAssetV1(
                asset_id="src_1",
                editorial_role="primary_footage",
                permitted_uses=["clip_extraction", "motion_review"],
                acquisition_route="authorized_fixture",
                local_path=str(sample_source_video),
            )
        ],
        outputs=[
            OutputSpecV1(output_id="clip_1", aspect_ratio="9:16", seconds=10.0, duration_policy=BDurationPolicy.TARGET)
        ],
    )

    # First submit
    res1 = await port.submit_batch(req)
    assert res1["accepted"] is True
    job_id = res1["job_id"]

    # Immediate duplicate submit
    res2 = await port.submit_batch(req)
    assert res2["accepted"] is True
    assert res2["job_id"] == job_id
    assert res2.get("idempotent_replay") is True


@pytest.mark.asyncio
async def test_fresh_process_simulation_recovers_jobs_and_artifacts(tmp_path: Path, sample_source_video: Path):
    """B07, V1, L05: A completely fresh process instance reloads accepted jobs and resolves streamable artifacts."""
    storage_dir = tmp_path / "media_prod_fresh_proc"
    
    # Process A: Submits and records job
    port_a = MediaProducerPort(storage_dir=storage_dir)
    job_id = "job_proc_a_001"
    port_a._ledger.create_job(
        job_id=job_id,
        request_fingerprint="fp_proc_a",
        run_id="run_proc_a",
        immutable_request={"sample": 1},
        output_ids=["clip_a1", "clip_a2"],
        user_id="local",
        status="COMPLETE",
    )

    # Write physical media files
    job_dir = storage_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    out1_file = job_dir / "clip_a1.mp4"
    out1_file.write_bytes(b"sample_encoded_mp4_bytes_clip_1")
    out2_file = job_dir / "clip_a2.mp4"
    out2_file.write_bytes(b"sample_encoded_mp4_bytes_clip_2")

    port_a._ledger.checkpoint_output_success(job_id, "clip_a1", "art_a1", out1_file, "hash1", len(out1_file.read_bytes()))
    port_a._ledger.checkpoint_output_success(job_id, "clip_a2", "art_a2", out2_file, "hash2", len(out2_file.read_bytes()))
    port_a._ledger.record_transition(job_id, "COMPLETE")

    # Simulate process death: delete port_a
    del port_a

    # Process B: Fresh process instance spins up pointing to same storage
    port_b = MediaProducerPort(storage_dir=storage_dir)

    # 1. Fresh process finds and polls the batch
    report = port_b.get_batch(job_id)
    assert report.job_id == job_id
    assert report.status == BatchStatus.COMPLETE
    assert len(report.outputs) == 2
    assert report.outputs[0].state == OutputState.SUCCEEDED
    assert report.outputs[0].checks.technical == "PASS"

    # 2. Fresh process resolves artifact paths for HTTP Range streaming
    resolved_1 = port_b.resolve_artifact_path("art_a1")
    assert resolved_1 is not None
    assert resolved_1.exists()
    assert resolved_1 == out1_file

    resolved_2 = port_b.resolve_artifact_path("art_a2")
    assert resolved_2 is not None
    assert resolved_2.exists()
    assert resolved_2 == out2_file


def test_same_text_new_request_vs_retry():
    """B13: Same prompt text after completed contract creates NEW_REQUEST; 'retry' keyword reuses contract."""
    contract_prompt = "Create 3 clips of gaming highlights 60s"
    
    # 1. Initial turn
    c1, intent1 = OutcomeOrchestrator.get_or_create_contract_for_turn(
        message=contract_prompt,
        session_id="session_user_42",
    )
    assert intent1 == IntentKind.NEW_REQUEST
    assert c1.output_count == 3
    initial_cid = c1.contract_id

    # Simulate completion of turn 1
    sm = OutcomeOrchestrator.get_state_machine(c1)
    sm.results = [
        OutputResult(output_id=o.output_id, state=OutputState.SUCCEEDED)
        for o in c1.outputs
    ]
    # Advance sm to READY_FOR_REVIEW
    if sm.can_transition_to(OutcomeState.SOURCE_ACCESS_VERIFIED):
        sm.transition_to(OutcomeState.SOURCE_ACCESS_VERIFIED, detail="ok")
    if sm.can_transition_to(OutcomeState.MEDIA_INGESTED):
        sm.transition_to(OutcomeState.MEDIA_INGESTED, detail="ok")
    if sm.can_transition_to(OutcomeState.MEDIA_ANALYZED):
        sm.transition_to(OutcomeState.MEDIA_ANALYZED, detail="ok")
    if sm.can_transition_to(OutcomeState.HIGHLIGHTS_SELECTED):
        sm.transition_to(OutcomeState.HIGHLIGHTS_SELECTED, detail="ok")
    if sm.can_transition_to(OutcomeState.RESULTS_COMPOSED):
        sm.transition_to(OutcomeState.RESULTS_COMPOSED, detail="ok")
    if sm.can_transition_to(OutcomeState.RENDER_RUNNING):
        sm.transition_to(OutcomeState.RENDER_RUNNING, detail="ok")
    if sm.can_transition_to(OutcomeState.RENDERS_VERIFIED):
        sm.transition_to(OutcomeState.RENDERS_VERIFIED, detail="ok")
    if sm.can_transition_to(OutcomeState.READY_FOR_REVIEW):
        sm.transition_to(OutcomeState.READY_FOR_REVIEW, detail="ok")

    assert sm.current_state == OutcomeState.READY_FOR_REVIEW

    # 2. User submits EXACT SAME PROMPT TEXT on next turn
    c2, intent2 = OutcomeOrchestrator.get_or_create_contract_for_turn(
        message=contract_prompt,
        session_id="session_user_42",
    )
    # Must be NEW_REQUEST with fresh contract_id and fresh output IDs
    assert intent2 == IntentKind.NEW_REQUEST
    assert c2.contract_id != initial_cid
    assert c2.outputs[0].output_id != c1.outputs[0].output_id

    # 3. User says "retry"
    sm2 = OutcomeOrchestrator.get_state_machine(c2)
    # Put c2 in PARTIAL
    if sm2.can_transition_to(OutcomeState.SOURCE_ACCESS_VERIFIED):
        sm2.transition_to(OutcomeState.SOURCE_ACCESS_VERIFIED, detail="ok")
    if sm2.can_transition_to(OutcomeState.MEDIA_INGESTED):
        sm2.transition_to(OutcomeState.MEDIA_INGESTED, detail="ok")
    if sm2.can_transition_to(OutcomeState.MEDIA_ANALYZED):
        sm2.transition_to(OutcomeState.MEDIA_ANALYZED, detail="ok")
    if sm2.can_transition_to(OutcomeState.HIGHLIGHTS_SELECTED):
        sm2.transition_to(OutcomeState.HIGHLIGHTS_SELECTED, detail="ok")
    if sm2.can_transition_to(OutcomeState.RESULTS_COMPOSED):
        sm2.transition_to(OutcomeState.RESULTS_COMPOSED, detail="ok")
    if sm2.can_transition_to(OutcomeState.RENDER_RUNNING):
        sm2.transition_to(OutcomeState.RENDER_RUNNING, detail="ok")
    if sm2.can_transition_to(OutcomeState.PARTIAL):
        sm2.transition_to(OutcomeState.PARTIAL, detail="some failed")

    c3, intent3 = OutcomeOrchestrator.get_or_create_contract_for_turn(
        message="retry failed clips please",
        session_id="session_user_42",
    )
    assert intent3 == IntentKind.RETRY_SAME_OPERATION
    assert c3.contract_id == c2.contract_id


def test_cancel_batch_reports_effects_already_committed(tmp_path: Path):
    """B26: cancel_batch halts work, marks status CANCELLED, and reports already committed output IDs."""
    storage_dir = tmp_path / "media_prod_cancel"
    port = MediaProducerPort(storage_dir=storage_dir)

    job_id = "job_cancel_test"
    port._ledger.create_job(
        job_id=job_id,
        request_fingerprint="fp_cancel",
        run_id="run_c",
        immutable_request={},
        output_ids=["clip_1", "clip_2"],
        status="RUNNING",
    )

    out1_file = tmp_path / "clip_1.mp4"
    out1_file.write_bytes(b"clip1_bytes")
    port._ledger.checkpoint_output_success(job_id, "clip_1", "art_c1", out1_file, "h1", len(out1_file.read_bytes()))
    port._ledger.checkpoint_output_start(job_id, "clip_2")

    # Cancel job
    res = port.cancel_batch(job_id)
    assert res["acknowledged"] is True
    assert "clip_1" in res["effects_already_committed"]
    assert "clip_2" not in res["effects_already_committed"]

    # Verify report status is CANCELLED
    report = port.get_batch(job_id)
    assert report.status == BatchStatus.CANCELLED


def test_reboot_before_and_after_file_write(tmp_path: Path):
    """B07, B24: Distinguish crash before write (reconciled as interrupted) vs after write (verified and preserved)."""
    storage_dir = tmp_path / "media_prod_reboot"
    port_first_boot = MediaProducerPort(storage_dir=storage_dir)

    job_id = "job_reboot_diff"
    port_first_boot._ledger.create_job(
        job_id=job_id,
        request_fingerprint="fp_reboot_01",
        run_id="run_reb",
        immutable_request={},
        output_ids=["clip_committed", "clip_interrupted"],
        status="RUNNING",
    )

    # 1. Output committed before crash (file written and valid)
    committed_file = storage_dir / "clip_committed.mp4"
    committed_file.write_bytes(b"valid_complete_video_stream")
    port_first_boot._ledger.checkpoint_output_success(
        job_id, "clip_committed", "art_com_1", committed_file, "sha_com", len(committed_file.read_bytes())
    )

    # 2. Output interrupted before file write completed (crash during processing)
    port_first_boot._ledger.checkpoint_output_start(job_id, "clip_interrupted")

    # Simulate reboot: create brand new MediaProducerPort on same disk
    port_rebooted = MediaProducerPort(storage_dir=storage_dir)

    # Reconciled report
    report = port_rebooted.get_batch(job_id)
    assert report.status == BatchStatus.PARTIAL

    outputs_by_id = {o.output_id: o for o in report.outputs}
    assert outputs_by_id["clip_committed"].state == OutputState.SUCCEEDED
    assert outputs_by_id["clip_committed"].checks.technical == "PASS"

    assert outputs_by_id["clip_interrupted"].state == OutputState.FAILED
    assert "restart" in outputs_by_id["clip_interrupted"].error_detail.lower() or "crash" in outputs_by_id["clip_interrupted"].error_detail.lower()


@pytest.mark.asyncio
async def test_orchestrator_reconciliation_of_interrupted_run(tmp_path: Path):
    """B07, B23: OutcomeOrchestrator reconciles interrupted contract from RENDER_RUNNING to READY_FOR_REVIEW."""
    from backend.outcome_orchestration.port_interface import (
        InProcessFakeProducerPort,
        get_media_producer_port,
        set_media_producer_port,
    )

    old_port = get_media_producer_port()
    fake_port = InProcessFakeProducerPort()
    set_media_producer_port(fake_port)

    try:
        # Create contract in RENDER_RUNNING
        contract = OutcomeOrchestrator.parse_contract_from_prompt("Create 3 clips of gameplay")
        contract.job_id = "job_reconcile_fake_01"
        OutcomeOrchestrator._save_contract(contract)

        sm = OutcomeOrchestrator.get_state_machine(contract)
        sm.job_id = contract.job_id
        if sm.can_transition_to(OutcomeState.SOURCE_ACCESS_VERIFIED):
            sm.transition_to(OutcomeState.SOURCE_ACCESS_VERIFIED)
        if sm.can_transition_to(OutcomeState.MEDIA_INGESTED):
            sm.transition_to(OutcomeState.MEDIA_INGESTED)
        if sm.can_transition_to(OutcomeState.MEDIA_ANALYZED):
            sm.transition_to(OutcomeState.MEDIA_ANALYZED)
        if sm.can_transition_to(OutcomeState.HIGHLIGHTS_SELECTED):
            sm.transition_to(OutcomeState.HIGHLIGHTS_SELECTED)
        if sm.can_transition_to(OutcomeState.RESULTS_COMPOSED):
            sm.transition_to(OutcomeState.RESULTS_COMPOSED)
        if sm.can_transition_to(OutcomeState.RENDER_RUNNING):
            sm.transition_to(OutcomeState.RENDER_RUNNING)

        OutcomeOrchestrator._save_state_machine(sm)

        # Mock producer completing the job in backend
        fake_port._jobs[contract.job_id] = ProductionReport(
            job_id=contract.job_id,
            run_id=contract.contract_id,
            status="COMPLETE",
            outputs=[
                OutputResult(output_id=o.output_id, state=OutputState.SUCCEEDED)
                for o in contract.outputs
            ],
        )

        # Reconcile after reboot
        reconciled_sm = await OutcomeOrchestrator.reconcile_contract(contract.contract_id, producer_port=fake_port)
        assert reconciled_sm is not None
        assert reconciled_sm.current_state == OutcomeState.READY_FOR_REVIEW
    finally:
        set_media_producer_port(old_port)
