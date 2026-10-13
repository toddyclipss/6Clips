# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Deterministic tests for durable job ledger, atomic writes, physical verification, and crash recovery."""

import json
from pathlib import Path
import pytest

from backend.production_jobs.ledger import (
    PersistentJobLedger,
    compute_sha256,
    verify_physical_media_file,
)
from backend.production_jobs.types import (
    ErrorClassification,
    JobRecord,
    RecoveryClassification,
)


def test_ledger_atomic_writes_and_structure(tmp_path: Path):
    """B07, L16: Ledger uses isolated directory, atomic writes, and persists job records without corruption."""
    ledger_dir = tmp_path / "prod_jobs_isolated"
    ledger = PersistentJobLedger(storage_dir=ledger_dir)

    job_id = "job_test_atomic_01"
    fingerprint = "fp_abc123"
    rec = ledger.create_job(
        job_id=job_id,
        request_fingerprint=fingerprint,
        run_id="run_01",
        immutable_request={"sample": "data", "contract_version": "1.0.0"},
        output_ids=["clip_1", "clip_2", "clip_3"],
        user_id="creator_test",
        status="RUNNING",
    )

    assert rec.job_id == job_id
    assert rec.status == "RUNNING"
    assert len(rec.output_checkpoints) == 3

    # Verify physical file on disk is valid JSON and not a dangling temp file
    job_file = ledger_dir / "jobs" / f"{job_id}.json"
    assert job_file.exists()
    loaded_data = json.loads(job_file.read_text(encoding="utf-8"))
    assert loaded_data["job_id"] == job_id
    assert loaded_data["status"] == "RUNNING"

    # Verify fingerprint index
    fp_job_id = ledger.get_job_id_by_fingerprint(fingerprint)
    assert fp_job_id == job_id


def test_physical_media_file_verification(tmp_path: Path):
    """B24, GT-05: Non-existent or 0-byte truncated files fail verification; valid files compute real SHA-256."""
    missing_file = tmp_path / "missing.mp4"
    ok, sha, size = verify_physical_media_file(missing_file)
    assert not ok
    assert sha is None

    empty_file = tmp_path / "empty.mp4"
    empty_file.write_bytes(b"")
    ok, sha, size = verify_physical_media_file(empty_file)
    assert not ok
    assert size == 0

    valid_file = tmp_path / "valid.mp4"
    valid_content = b"\x00\x00\x00\x20ftypmp42" + b"video_sample_data" * 100
    valid_file.write_bytes(valid_content)
    ok, sha, size = verify_physical_media_file(valid_file)
    assert ok
    assert size == len(valid_content)
    assert sha == compute_sha256(valid_file)


def test_crash_recovery_during_render(tmp_path: Path):
    """B07, B21: Simulates process crash mid-flight: cleans partial 0-byte files, marks interrupted outputs."""
    ledger_dir = tmp_path / "ledger_crash_test"
    ledger = PersistentJobLedger(storage_dir=ledger_dir)

    job_id = "job_crash_01"
    ledger.create_job(
        job_id=job_id,
        request_fingerprint="fp_crash_01",
        run_id="run_crash_01",
        immutable_request={},
        output_ids=["clip_1", "clip_2", "clip_3"],
        status="RUNNING",
    )

    # Output 1 succeeded before crash
    out1_path = tmp_path / "clip_1.mp4"
    out1_path.write_bytes(b"valid_clip_1_bytes_12345")
    _, sha1, sz1 = verify_physical_media_file(out1_path)
    ledger.checkpoint_output_success(job_id, "clip_1", "art_1", out1_path, sha1, sz1)

    # Output 2 was in-flight (crash happened mid-render leaving 0-byte file)
    out2_path = tmp_path / "clip_2.mp4"
    out2_path.write_bytes(b"")  # 0 bytes truncated file from kill/crash
    ledger.checkpoint_output_start(job_id, "clip_2")
    job_rec = ledger.get_job(job_id)
    job_rec.output_checkpoints["clip_2"].file_path = str(out2_path)
    ledger.save_job(job_rec)

    # Reconcile on restart!
    reconciled_jobs = ledger.reconcile_active_jobs()
    assert len(reconciled_jobs) >= 1

    rec_after = ledger.get_job(job_id)
    # Aggregate status degraded from RUNNING to PARTIAL
    assert rec_after.status == "PARTIAL"
    assert rec_after.output_checkpoints["clip_1"].state == "SUCCEEDED"
    assert rec_after.output_checkpoints["clip_2"].state == "FAILED"
    assert rec_after.output_checkpoints["clip_2"].error_classification == ErrorClassification.INTERRUPTED_CRASH.value
    assert rec_after.output_checkpoints["clip_2"].recovery_action == RecoveryClassification.RESUME.value

    # Verify corrupt 0-byte file was pruned
    assert not out2_path.exists()


def test_missing_artifacts_degradation(tmp_path: Path):
    """B04, B26: Completed jobs whose physical files are missing or deleted are degraded to PARTIAL."""
    ledger_dir = tmp_path / "ledger_degrade_test"
    ledger = PersistentJobLedger(storage_dir=ledger_dir)

    job_id = "job_degrade_01"
    ledger.create_job(
        job_id=job_id,
        request_fingerprint="fp_deg_01",
        run_id="run_deg_01",
        immutable_request={},
        output_ids=["clip_1"],
        status="COMPLETE",
    )

    out_path = tmp_path / "clip_del.mp4"
    out_path.write_bytes(b"valid_bytes")
    _, sha, sz = verify_physical_media_file(out_path)
    ledger.checkpoint_output_success(job_id, "clip_1", "art_deg_1", out_path, sha, sz)

    # Delete physical file from disk
    out_path.unlink()

    # Reconcile detects physical evidence is missing
    reconciled = ledger.reconcile_active_jobs()
    rec = ledger.get_job(job_id)
    assert rec.status == "PARTIAL"
    assert rec.output_checkpoints["clip_1"].state == "FAILED"
    assert rec.output_checkpoints["clip_1"].error_classification == ErrorClassification.CORRUPTED_ARTIFACT.value


def test_multi_user_isolation_in_ledger(tmp_path: Path):
    """L14: Jobs from distinct users are segregated and cannot leak across creator boundaries."""
    ledger_dir = tmp_path / "ledger_multiuser"
    ledger = PersistentJobLedger(storage_dir=ledger_dir)

    ledger.create_job(
        job_id="job_alice_1",
        request_fingerprint="fp_a",
        run_id="run_a",
        immutable_request={},
        output_ids=["c1"],
        user_id="user_alice",
        status="COMPLETE",
    )
    ledger.create_job(
        job_id="job_bob_1",
        request_fingerprint="fp_b",
        run_id="run_b",
        immutable_request={},
        output_ids=["c2"],
        user_id="user_bob",
        status="COMPLETE",
    )

    alice_jobs = ledger.list_jobs(user_id="user_alice")
    bob_jobs = ledger.list_jobs(user_id="user_bob")
    all_jobs = ledger.list_jobs()

    assert len(alice_jobs) == 1
    assert alice_jobs[0].job_id == "job_alice_1"
    assert len(bob_jobs) == 1
    assert bob_jobs[0].job_id == "job_bob_1"
    assert len(all_jobs) == 2
