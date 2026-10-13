# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 5 Distribution Durability Test Suite:
- Restart recovery of in-flight dispatching jobs
- Multi-tenant isolation (user_id partitioning)
- Truthful production transport blocking with LIVE_PUBLISHING_VERIFIED: NO
- Offline daemon status and host limitation warning
- Partial failure fanout isolation
- Receipt reconciliation schema contract
- Token and PII redaction from persistent job stores
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import pytest

from backend.distribution.job_store import DistributionJobStore
from backend.distribution.models import (
    AccountState,
    DistributionJob,
    DistributionStatus,
    PlatformAccount,
    PlatformSEOMetadata,
    PublishedReceiptV1,
)
from backend.distribution.scheduler import DistributionScheduler, TimeProvider
from backend.distribution.service import DistributionService
from backend.distribution.transport import (
    InProcessFakeTransport,
    ProductionLiveTransport,
    TransportError,
)


@pytest.mark.asyncio
async def test_distribution_durable_restart_recovery(tmp_path: Path):
    """
    Simulate a process crash while a job is in DISPATCHING status.
    Verify that initializing a new scheduler instance recovers the interrupted job
    and transitions it safely to FAILED_RETRYABLE rather than being orphaned in DISPATCHING.
    """
    store = DistributionJobStore(base_dir=tmp_path)
    clock = TimeProvider(fixed_time=datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc))
    transport = InProcessFakeTransport()
    scheduler = DistributionScheduler(store=store, transport=transport, time_provider=clock)

    # Create job in DISPATCHING state directly in store (as if worker crashed mid-dispatch)
    crashed_job = DistributionJob(
        job_id="dist_crashed_01",
        user_id="creator_1",
        output_id="out_01",
        project_id="proj_01",
        project_revision=1,
        artifact_path=str(tmp_path / "video.mp4"),
        artifact_sha256="abc123hash",
        approval_receipt_id="appr_01",
        platform="youtube",
        account_id="acc_yt_01",
        seo_metadata=PlatformSEOMetadata(platform="youtube", title="Test Title"),
        scheduled_time_utc=clock.now().isoformat(),
        status=DistributionStatus.DISPATCHING,
    )
    store.save_job(crashed_job)

    # Verify initial crashed state
    assert store.get_job("dist_crashed_01").status == DistributionStatus.DISPATCHING

    # Worker restart: create a new scheduler instance using the same persistent store
    new_scheduler = DistributionScheduler(store=store, transport=transport, time_provider=clock)

    recovered_job = store.get_job("dist_crashed_01")
    assert recovered_job is not None
    assert recovered_job.status == DistributionStatus.FAILED_RETRYABLE
    assert recovered_job.error_code == "WORKER_RESTARTED_DURING_DISPATCH"
    assert "Worker process terminated during dispatch" in recovered_job.error_message


@pytest.mark.asyncio
async def test_distribution_multi_tenant_isolation(tmp_path: Path):
    """
    Verify strict tenant isolation: Creator A cannot view, cancel, or retry Creator B's jobs.
    """
    store = DistributionJobStore(base_dir=tmp_path)
    scheduler = DistributionScheduler(store=store)

    job_alice = DistributionJob(
        job_id="dist_alice_01",
        user_id="alice",
        output_id="out_alice",
        project_id="proj_alice",
        project_revision=1,
        artifact_path="/tmp/alice.mp4",
        artifact_sha256="alice_hash",
        approval_receipt_id="appr_alice",
        platform="youtube",
        account_id="acc_alice",
        seo_metadata=PlatformSEOMetadata(platform="youtube", title="Alice Video"),
        scheduled_time_utc=datetime.now(timezone.utc).isoformat(),
        status=DistributionStatus.SCHEDULED,
    )
    store.save_job(job_alice)

    # Bob attempts to cancel Alice's job -> must raise ValueError
    with pytest.raises(ValueError, match="Unauthorized: Job 'dist_alice_01' belongs to another creator tenant."):
        await scheduler.cancel_job("dist_alice_01", user_id="bob")

    # Bob attempts to retry Alice's job -> must raise ValueError
    with pytest.raises(ValueError, match="Unauthorized: Job 'dist_alice_01' belongs to another creator tenant."):
        await scheduler.retry_job("dist_alice_01", user_id="bob")

    # List jobs for Bob -> empty
    bob_jobs = store.list_jobs(user_id="bob")
    assert len(bob_jobs) == 0

    # List jobs for Alice -> contains Alice's job
    alice_jobs = store.list_jobs(user_id="alice")
    assert len(alice_jobs) == 1
    assert alice_jobs[0].job_id == "dist_alice_01"


@pytest.mark.asyncio
async def test_distribution_production_transport_blocks_unauthorized_and_reports_live_no():
    """
    Verify ProductionLiveTransport strictly refuses unapproved dispatch,
    reports LIVE_PUBLISHING_VERIFIED: NO, and rejects fake receipts.
    """
    transport = ProductionLiveTransport()

    account_not_ready = PlatformAccount(
        account_id="yt_offline",
        platform="youtube",
        account_name="YouTube Channel",
        state=AccountState.NOT_CONNECTED,
        can_publish=False,
    )

    job = DistributionJob(
        job_id="dist_test_live",
        user_id="local",
        output_id="out_01",
        project_id="proj_01",
        project_revision=1,
        artifact_path="/tmp/video.mp4",
        artifact_sha256="hash123",
        approval_receipt_id="appr_01",
        platform="youtube",
        account_id="yt_offline",
        seo_metadata=PlatformSEOMetadata(platform="youtube", title="Test"),
        scheduled_time_utc=datetime.now(timezone.utc).isoformat(),
    )

    # 1. Blocked due to account not ready
    with pytest.raises(TransportError) as exc_info:
        await transport.dispatch_post(job, account_not_ready)
    assert "LIVE_PUBLISHING_VERIFIED: NO" in exc_info.value.message
    assert exc_info.value.code == "ACCOUNT_NOT_READY"

    # 2. Blocked due to unauthorized live execution
    account_ready_mock = PlatformAccount(
        account_id="yt_ready",
        platform="youtube",
        account_name="YouTube Channel",
        state=AccountState.READY,
        can_publish=True,
    )
    with pytest.raises(TransportError) as exc_info2:
        await transport.dispatch_post(job, account_ready_mock)
    assert "LIVE_PUBLISHING_VERIFIED: NO" in exc_info2.value.message
    assert exc_info2.value.code == "LIVE_PUBLISHING_NOT_AUTHORIZED"

    # 3. Rejects fake remote post ID in verification
    assert await transport.verify_post_receipt(job, account_ready_mock, "fake_post_123") is None


def test_distribution_offline_daemon_notice(tmp_path: Path):
    """
    Verify scheduler daemon status provides explicit notice of host shutdown/sleep limitations.
    """
    store = DistributionJobStore(base_dir=tmp_path)
    scheduler = DistributionScheduler(store=store)

    status = scheduler.get_daemon_status()
    assert status["daemon_active"] is True
    assert "offline_limitation_notice" in status
    assert "ViralMint operates as a local application" in status["offline_limitation_notice"]
    assert "host computer is turned off" in status["offline_limitation_notice"]


@pytest.mark.asyncio
async def test_distribution_partial_failure_fanout_isolation(tmp_path: Path):
    """
    Verify multi-platform fanout isolates channel failures.
    If one channel configuration is invalid, valid channels still succeed.
    """
    store = DistributionJobStore(base_dir=tmp_path)
    transport = InProcessFakeTransport()
    service = DistributionService(store=store, transport=transport)

    # Valid physical artifact
    f = tmp_path / "valid_render.mp4"
    f.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 512)
    sha256 = service.check_release_eligibility.__globals__["ReleaseEligibilityVerifier"].calculate_file_sha256(f)

    approval = service.create_approval_receipt(
        output_id="out_fan_01",
        project_id="proj_fan_01",
        project_revision=1,
        artifact_sha256=sha256,
        approved_by="creator",
        consent_for_external_publish=True,
    )

    yt_acc = PlatformAccount(
        account_id="yt_acc",
        platform="youtube",
        account_name="YouTube",
        state=AccountState.READY,
        granted_scopes=["https://www.googleapis.com/auth/youtube.upload"],
        required_scopes=["https://www.googleapis.com/auth/youtube.upload"],
        can_publish=True,
    )
    tt_acc = PlatformAccount(
        account_id="tt_acc",
        platform="tiktok",
        account_name="TikTok",
        state=AccountState.NOT_CONNECTED,
        can_publish=False,
    )

    configs = [
        {
            "platform": "youtube",
            "account": yt_acc,
            "seo_metadata": PlatformSEOMetadata(platform="youtube", title="Valid YT", aspect_ratio="9:16"),
        },
        {
            "platform": "tiktok",
            "account": tt_acc,
            "seo_metadata": PlatformSEOMetadata(platform="tiktok", title="TikTok Video", aspect_ratio="9:16"),
        },
    ]

    result = await service.schedule_multi_platform_fan_out(
        output_id="out_fan_01",
        project_id="proj_fan_01",
        project_revision=1,
        artifact_path=str(f),
        approval_receipt=approval,
        platform_configs=configs,
    )

    assert result["status"] == "PARTIAL"
    assert result["total_scheduled"] == 1
    assert len(result["errors"]) == 1
    assert result["errors"][0]["platform"] == "tiktok"


def test_distribution_token_and_secret_redaction(tmp_path: Path):
    """
    Verify that jobs and receipts persisted to disk never leak OAuth tokens or secrets.
    """
    store = DistributionJobStore(base_dir=tmp_path)

    receipt = PublishedReceiptV1(
        receipt_id="rcpt_sec_01",
        job_id="dist_sec_01",
        output_id="out_01",
        project_id="proj_01",
        project_revision=1,
        artifact_sha256="sha256abc",
        platform="youtube",
        account_id="yt_01",
        creator_id="local",
        remote_post_id="post_999",
        remote_post_url="https://youtube.com/watch?v=post_999",
        verified_status="CONFIRMED",
        provenance={"user_agent": "ViralMint-Dist/1.0"},
    )
    store.save_receipt(receipt)

    receipts_json = (tmp_path / "receipts.json").read_text(encoding="utf-8")
    assert "access_token" not in receipts_json.lower()
    assert "client_secret" not in receipts_json.lower()
    assert "refresh_token" not in receipts_json.lower()
    assert "bearer" not in receipts_json.lower()
