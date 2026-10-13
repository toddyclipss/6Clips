# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 7 Integration Tests: Release Durability, Idempotency, and API Error Mapping.

Verifies:
- Phase 10 Job Store & Scheduler Idempotency via unique idempotency_key.
- Distribution API HTTP error status mapping (401, 403, 404, 409, 422).
- Scheduler Daemon status and host-offline limitation disclosure.
- Analytics API HTTP error status mapping (404, 409, 422).
- Grounded analytics persistence, missing-vs-zero metrics, and disconnected provider state.
"""
import hashlib
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.analytics import (
    get_analytics_engine,
    reset_analytics_engine,
    router as analytics_router,
)
from backend.api.distribution import router as distribution_router
from backend.analytics.engine import AnalyticsEngine
from backend.analytics.repository import AnalyticsRepository
from backend.analytics.models import (
    AnalyticsProvider,
    MetricObservationSource,
    MetricObservationV1,
    PublishedReceiptV1,
    ReceiptConfirmationStatus,
)
from backend.distribution.account_boundary import AccountBoundaryManager
from backend.distribution.job_store import DistributionJobStore
from backend.distribution.models import (
    AccountState,
    ApprovalReceipt,
    DistributionJob,
    DistributionStatus,
    PlatformAccount,
    PlatformSEOMetadata,
)
from backend.distribution.scheduler import DistributionScheduler


def _create_valid_container_file(path: Path, payload: bytes = b"valid_media") -> Path:
    """Writes a minimal valid MP4 container header to satisfy container checks."""
    header = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41"
    path.write_bytes(header + payload)
    return path


def _compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


@pytest.fixture
def app():
    """FastAPI test app mounting isolated distribution and analytics routers."""
    reset_analytics_engine()
    test_app = FastAPI()
    test_app.include_router(distribution_router)
    test_app.include_router(analytics_router)
    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestPhase10SchedulerIdempotency:
    """Verifies that duplicate schedule attempts with the same idempotency key return the original job."""

    def test_job_store_idempotency_lookup(self, tmp_path: Path):
        store = DistributionJobStore(base_dir=tmp_path)

        job = DistributionJob(
            output_id="out_01",
            project_id="proj_01",
            project_revision=1,
            artifact_path="data/video.mp4",
            artifact_sha256="abc123hash",
            approval_receipt_id="rcpt_01",
            platform="youtube",
            account_id="yt_acc_01",
            seo_metadata=PlatformSEOMetadata(platform="youtube", title="Test Short #viral #shorts"),
            scheduled_time_utc=datetime.now(timezone.utc).isoformat(),
            user_id="local",
            idempotency_key="idemp_key_unique_123",
        )
        store.save_job(job)
        assert job.job_id is not None

        # Lookup by idempotency key
        found = store.get_job_by_idempotency_key("idemp_key_unique_123")
        assert found is not None
        assert found.job_id == job.job_id
        assert found.idempotency_key == "idemp_key_unique_123"

        # Non-existent key returns None
        assert store.get_job_by_idempotency_key("non_existent_key") is None

    @pytest.mark.asyncio
    async def test_scheduler_idempotent_job_creation(self, tmp_path: Path):
        store = DistributionJobStore(base_dir=tmp_path)
        scheduler = DistributionScheduler(store=store)

        account = PlatformAccount(
            account_id="tt_acc_01",
            account_name="TikTok Account",
            platform="tiktok",
            state=AccountState.READY,
            can_publish=True,
            granted_scopes=["video.upload", "video.publish"],
        )

        job = DistributionJob(
            output_id="out_01",
            project_id="proj_01",
            project_revision=1,
            artifact_path="data/video.mp4",
            artifact_sha256="abc123hash",
            approval_receipt_id="rcpt_01",
            platform="tiktok",
            account_id="tt_acc_01",
            seo_metadata=PlatformSEOMetadata(platform="tiktok", title="Dance trend #viral #fyp"),
            scheduled_time_utc=datetime.now(timezone.utc).isoformat(),
            user_id="local",
            idempotency_key="idemp_same_submission",
        )

        # First schedule
        first_job = await scheduler.schedule_job(job, account=account)
        assert first_job.job_id is not None

        # Second schedule with identical job & idempotency key
        second_job = await scheduler.schedule_job(job, account=account)

        # Must return the identical existing job without creating a duplicate
        assert second_job.job_id == first_job.job_id

        # Total jobs in store must remain exactly 1
        all_jobs = store.list_jobs(user_id="local")
        assert len(all_jobs) == 1


class TestDistributionApiStatusHardening:
    """Verifies HTTP status codes on distribution domain errors."""

    def test_get_nonexistent_job_returns_404(self, client: TestClient):
        res = client.get("/api/distribution/jobs/job_does_not_exist_999")
        assert res.status_code == 404

    def test_cancel_nonexistent_job_returns_404(self, client: TestClient):
        res = client.post("/api/distribution/jobs/job_does_not_exist_999/cancel")
        assert res.status_code == 404

    def test_retry_nonexistent_job_returns_404(self, client: TestClient):
        res = client.post("/api/distribution/jobs/job_does_not_exist_999/retry")
        assert res.status_code == 404

    def test_seo_validation_failure_returns_422(self, client: TestClient):
        payload = {
            "metadata": {
                "title": "A" * 120,  # Exceeds YouTube 100 char limit
                "platform": "youtube",
                "aspect_ratio": "9:16",
            }
        }
        res = client.post("/api/distribution/seo/validate", json=payload)
        assert res.status_code == 422

    def test_seo_invalid_aspect_ratio_returns_422(self, client: TestClient):
        payload = {
            "metadata": {
                "title": "Valid title #shorts",
                "platform": "tiktok",
                "aspect_ratio": "4:3",  # TikTok requires 9:16 vertical
            }
        }
        res = client.post("/api/distribution/seo/validate", json=payload)
        assert res.status_code == 422

    def test_eligibility_check_missing_artifact_returns_404(self, client: TestClient):
        payload = {
            "file_path": "non_existent_folder/missing_video.mp4",
            "project_revision": 1,
            "target_platform": "youtube",
            "user_id": "local",
        }
        res = client.post("/api/distribution/eligibility/check", json=payload)
        assert res.status_code == 404

    def test_eligibility_check_stale_approval_returns_409(self, client: TestClient, tmp_path: Path):
        video_file = tmp_path / "valid_container.mp4"
        _create_valid_container_file(video_file)
        sha = _compute_sha256(video_file)

        receipt = ApprovalReceipt(
            approval_id="appr_stale",
            output_id="out_01",
            project_id="proj_01",
            project_revision=1,  # Signed for revision 1 (stale!)
            artifact_sha256=sha,
            approved_by="creator",
            consent_for_external_publish=True,
        )
        receipt.signature = receipt.compute_signature()

        payload = {
            "file_path": str(video_file),
            "project_revision": 2,  # Current revision is 2
            "approval_receipt": receipt.model_dump(),
            "target_platform": "youtube",
            "user_id": "local",
        }
        res = client.post("/api/distribution/eligibility/check", json=payload)
        assert res.status_code == 409

    def test_eligibility_check_missing_consent_returns_403(self, client: TestClient, tmp_path: Path):
        video_file = tmp_path / "valid_container_2.mp4"
        _create_valid_container_file(video_file)
        sha = _compute_sha256(video_file)

        receipt = ApprovalReceipt(
            approval_id="appr_no_consent",
            output_id="out_01",
            project_id="proj_01",
            project_revision=1,
            artifact_sha256=sha,
            approved_by="creator",
            consent_for_external_publish=False,  # Missing consent!
        )
        receipt.signature = receipt.compute_signature()

        payload = {
            "file_path": str(video_file),
            "project_revision": 1,
            "approval_receipt": receipt.model_dump(),
            "target_platform": "youtube",
            "user_id": "local",
        }
        res = client.post("/api/distribution/eligibility/check", json=payload)
        assert res.status_code == 403

    def test_eligibility_check_invalid_signature_returns_401(self, client: TestClient, tmp_path: Path):
        video_file = tmp_path / "valid_container_3.mp4"
        _create_valid_container_file(video_file)
        sha = _compute_sha256(video_file)

        receipt = ApprovalReceipt(
            approval_id="appr_tampered",
            output_id="out_01",
            project_id="proj_01",
            project_revision=1,
            artifact_sha256=sha,
            approved_by="creator",
            consent_for_external_publish=True,
            signature="tampered_invalid_signature_hex",
        )

        payload = {
            "file_path": str(video_file),
            "project_revision": 1,
            "approval_receipt": receipt.model_dump(),
            "target_platform": "youtube",
            "user_id": "local",
        }
        res = client.post("/api/distribution/eligibility/check", json=payload)
        assert res.status_code == 401

    def test_daemon_status_and_offline_disclosure(self, client: TestClient):
        res = client.get("/api/distribution/daemon/status")
        assert res.status_code == 200
        data = res.json()
        assert "daemon_active" in data
        assert "offline_limitation_notice" in data
        assert "host computer" in data["offline_limitation_notice"].lower()


class TestAnalyticsApiStatusAndDurability:
    """Verifies analytics API endpoints and ground-truth behavior."""

    def test_poll_unknown_receipt_returns_404(self, client: TestClient):
        res = client.post("/analytics/poll/non_existent_rcpt_123")
        assert res.status_code == 404

    def test_get_metrics_unknown_receipt_returns_404(self, client: TestClient):
        res = client.get("/analytics/post/non_existent_rcpt_123")
        assert res.status_code == 404

    def test_provider_status_shows_not_connected_without_creds(self, client: TestClient):
        res = client.get("/analytics/status")
        assert res.status_code == 200
        data = res.json()
        assert data["mode"] == "DISCONNECTED"
        assert "providers" in data
        for prov_st in data["providers"].values():
            assert prov_st["status"] == "NOT_CONNECTED"
            assert prov_st["connected"] is False

    def test_missing_vs_zero_metrics_preservation(self, tmp_path: Path):
        """Verifies that unobserved metrics remain None rather than being coerced to 0."""
        repo = AnalyticsRepository(base_dir=tmp_path)
        engine = AnalyticsEngine(repository=repo)

        # Register receipt
        rcpt = PublishedReceiptV1(
            project_id="p1",
            provider=AnalyticsProvider.YOUTUBE,
            account_reference="default",
            remote_post_id="post_yt_1",
            publish_timestamp=datetime.now(timezone.utc),
            confirmation_status=ReceiptConfirmationStatus.SIMULATED_TEST,
        )
        saved_rcpt = engine.register_receipt(rcpt, is_test_fixture=True)

        # Record observation where views=1000, but watch_time_seconds and shares are NOT reported (None)
        obs = MetricObservationV1(
            receipt_id=saved_rcpt.receipt_id,
            provider=AnalyticsProvider.YOUTUBE,
            remote_post_id="post_yt_1",
            views=1000,
            watch_time_seconds=None,  # Not reported
            shares=None,  # Not reported
            observation_source=MetricObservationSource.OFFICIAL_API,
        )
        repo.record_observation(obs)

        agg = engine.get_aggregated_metrics(saved_rcpt.receipt_id)
        assert agg is not None
        assert agg.latest_views == 1000
        # Must remain None, not coerced to 0
        assert agg.latest_watch_time_seconds is None
        assert agg.latest_shares is None
