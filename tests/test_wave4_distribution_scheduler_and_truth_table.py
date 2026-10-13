# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for Phase 10 Distribution Scheduler and Publishing Truth Table."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from backend.distribution.job_store import DistributionJobStore
from backend.distribution.models import (
    AccountState,
    DistributionJob,
    DistributionStatus,
    PlatformAccount,
    PlatformSEOMetadata,
)
from backend.distribution.scheduler import DistributionScheduler, TimeProvider
from backend.distribution.transport import (
    InProcessFakeTransport,
    ProductionLiveTransport,
    TransportError,
)


@pytest.fixture
def mock_account():
    return PlatformAccount(
        account_id="acc_yt_01",
        platform="youtube",
        account_name="Official YouTube",
        state=AccountState.READY,
        granted_scopes=["https://www.googleapis.com/auth/youtube.upload"],
        required_scopes=["https://www.googleapis.com/auth/youtube.upload"],
        can_publish=True,
    )


@pytest.fixture
def sample_job():
    return DistributionJob(
        job_id="job_test_01",
        output_id="out_01",
        project_id="proj_01",
        project_revision=1,
        artifact_path="/storage/videos/test.mp4",
        artifact_sha256="testsha256",
        approval_receipt_id="appr_01",
        platform="youtube",
        account_id="acc_yt_01",
        seo_metadata=PlatformSEOMetadata(
            platform="youtube",
            title="Scheduled Viral Video #Shorts",
            description="Detailed description",
        ),
        scheduled_time_utc=(datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
    )


@pytest.mark.asyncio
async def test_scheduler_lifecycle_and_clock_advance(tmp_path: Path, mock_account, sample_job):
    store = DistributionJobStore(base_dir=tmp_path)
    transport = InProcessFakeTransport()
    start_time = datetime(2026, 10, 13, 12, 0, 0, tzinfo=timezone.utc)
    clock = TimeProvider(fixed_time=start_time)

    scheduler = DistributionScheduler(
        store=store,
        transport=transport,
        time_provider=clock,
        account_resolver=lambda aid, plat: mock_account,
    )

    # 1. Schedule for 2 hours in the future
    sample_job.scheduled_time_utc = (start_time + timedelta(hours=2)).isoformat()
    await scheduler.schedule_job(sample_job, mock_account)
    assert sample_job.status == DistributionStatus.SCHEDULED

    # 2. Tick at start_time: job is not due
    tick_1 = await scheduler.process_tick()
    assert tick_1["due_count"] == 0
    assert store.get_job(sample_job.job_id).status == DistributionStatus.SCHEDULED

    # 3. Advance clock by 2 hours and 1 minute: job becomes due and executes
    clock.advance(timedelta(hours=2, minutes=1))
    tick_2 = await scheduler.process_tick()
    assert tick_2["due_count"] == 1
    assert tick_2["published"] == 1

    final_job = store.get_job(sample_job.job_id)
    assert final_job.status == DistributionStatus.PUBLISHED_VERIFIED
    assert final_job.remote_post_id.startswith("fake_youtube_")
    assert final_job.receipt_id is not None


@pytest.mark.asyncio
async def test_truth_table_unverified_stage_does_not_declare_published(tmp_path: Path, mock_account, sample_job):
    store = DistributionJobStore(base_dir=tmp_path)
    transport = InProcessFakeTransport()
    # Emulate platform accepting upload (HTTP 202) but not yet confirming publication
    transport.simulate_unverified_stage = True

    start_time = datetime(2026, 10, 13, 12, 0, 0, tzinfo=timezone.utc)
    clock = TimeProvider(fixed_time=start_time)
    scheduler = DistributionScheduler(
        store=store,
        transport=transport,
        time_provider=clock,
        account_resolver=lambda aid, plat: mock_account,
    )

    sample_job.scheduled_time_utc = start_time.isoformat()
    await scheduler.schedule_job(sample_job, mock_account)

    await scheduler.process_tick()

    job_state = store.get_job(sample_job.job_id)
    # MUST NOT be PUBLISHED_VERIFIED without confirmed receipt
    assert job_state.status != DistributionStatus.PUBLISHED_VERIFIED
    assert job_state.status == DistributionStatus.DISPATCHING


@pytest.mark.asyncio
async def test_production_transport_blocks_unauthorized_live_publish(tmp_path: Path, mock_account, sample_job):
    store = DistributionJobStore(base_dir=tmp_path)
    prod_transport = ProductionLiveTransport()
    start_time = datetime(2026, 10, 13, 12, 0, 0, tzinfo=timezone.utc)
    clock = TimeProvider(fixed_time=start_time)

    scheduler = DistributionScheduler(
        store=store,
        transport=prod_transport,
        time_provider=clock,
        account_resolver=lambda aid, plat: mock_account,
    )

    sample_job.scheduled_time_utc = start_time.isoformat()
    await scheduler.schedule_job(sample_job, mock_account)

    await scheduler.process_tick()

    job_state = store.get_job(sample_job.job_id)
    assert job_state.status == DistributionStatus.BLOCKED
    assert "Live external publishing" in job_state.error_message


@pytest.mark.asyncio
async def test_cancel_scheduled_job(tmp_path: Path, mock_account, sample_job):
    store = DistributionJobStore(base_dir=tmp_path)
    scheduler = DistributionScheduler(store=store, account_resolver=lambda aid, plat: mock_account)

    await scheduler.schedule_job(sample_job, mock_account)
    cancelled = await scheduler.cancel_job(sample_job.job_id, reason="User changed mind")
    assert cancelled.status == DistributionStatus.CANCELLED
    assert "User changed mind" in cancelled.error_message


@pytest.mark.asyncio
async def test_retry_backoff_budget_and_fatal_blocking(tmp_path: Path, mock_account, sample_job):
    store = DistributionJobStore(base_dir=tmp_path)
    transport = InProcessFakeTransport()
    transport.simulate_network_failure = True  # Network 503 retryable
    start_time = datetime(2026, 10, 13, 12, 0, 0, tzinfo=timezone.utc)
    clock = TimeProvider(fixed_time=start_time)

    scheduler = DistributionScheduler(
        store=store,
        transport=transport,
        time_provider=clock,
        account_resolver=lambda aid, plat: mock_account,
    )

    sample_job.scheduled_time_utc = start_time.isoformat()
    sample_job.max_retries = 2
    await scheduler.schedule_job(sample_job, mock_account)

    # Attempt 1: Fails with retryable error
    await scheduler.process_tick()
    j1 = store.get_job(sample_job.job_id)
    assert j1.status == DistributionStatus.FAILED_RETRYABLE
    assert j1.retry_count == 1

    # Advance clock to next backoff time and tick: Attempt 2
    clock.set_time(datetime.fromisoformat(j1.scheduled_time_utc.replace("Z", "+00:00")))
    await scheduler.process_tick()
    j2 = store.get_job(sample_job.job_id)
    assert j2.status == DistributionStatus.FAILED_RETRYABLE
    assert j2.retry_count == 2

    # Advance clock to next backoff time: Attempt 3 exceeds max_retries (2) -> BLOCKED
    clock.set_time(datetime.fromisoformat(j2.scheduled_time_utc.replace("Z", "+00:00")))
    await scheduler.process_tick()
    j3 = store.get_job(sample_job.job_id)
    assert j3.status == DistributionStatus.BLOCKED
    assert j3.error_category == "FATAL"
