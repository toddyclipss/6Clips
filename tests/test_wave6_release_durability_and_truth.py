# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 6 Release Durability and Ground Truth Acceptance Test Suite:
- Production default transport safety (zero silent fakes in default paths)
- Fresh process restart persistence and durability (SQLite/JSON stores)
- Corrupted disk file quarantine without process crashes
- Platform support matrix contract verification (YouTube, TikTok, Instagram, X)
- Approval & review security gates (stale revisions, checksum mismatch, consent revoked)
- Non-lossy cross-platform analytics separation and deleted post handling
- Bounded V2 (GT-06) and V3 (GT-07) acceptance harness returning NOT_TESTED for missing media
- Release acceptance auditor reporting truthful release gate status
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import pytest

from backend.analytics.engine import AnalyticsEngine
from backend.analytics.models import (
    AnalyticsProvider,
    MetricObservationSource,
    MetricObservationV1,
    PublishedReceiptV1,
    ReceiptConfirmationStatus,
)
from backend.analytics.providers import MockAnalyticsAdapter
from backend.analytics.repository import AnalyticsRepository
from backend.distribution.job_store import DistributionJobStore
from backend.distribution.models import (
    AccountState,
    ApprovalReceipt,
    DistributionJob,
    DistributionStatus,
    PlatformAccount,
    PlatformSEOMetadata,
)
from backend.distribution.platform_matrix import (
    PLATFORM_SUPPORT_MATRIX,
    PlatformMatrixValidator,
    PublishTargetType,
)
from backend.distribution.scheduler import DistributionScheduler, TimeProvider
from backend.distribution.service import DistributionService
from backend.distribution.transport import (
    InProcessFakeTransport,
    ProductionLiveTransport,
    TransportError,
)
from backend.release_acceptance.validator import (
    ReleaseAcceptanceAuditor,
    V2MultiOutputValidator,
    V3LongFormNarrativeValidator,
)


# ── 1. Production Default Transport Safety ────────────────────────────────────

@pytest.mark.asyncio
async def test_distribution_service_defaults_to_production_transport(tmp_path: Path):
    """
    Verify that the default DistributionService constructor creates a scheduler
    backed by ProductionLiveTransport (not a silent fake transport).
    """
    store = DistributionJobStore(base_dir=tmp_path)
    service = DistributionService(store=store)

    assert service.is_production_transport is True
    assert isinstance(service.scheduler.transport, ProductionLiveTransport)


@pytest.mark.asyncio
async def test_production_transport_blocks_unauthorized_dispatch(tmp_path: Path):
    """
    Verify that ProductionLiveTransport fails fast when credentials are not authorized,
    accurately raising TransportError and refusing to create synthetic receipts.
    """
    transport = ProductionLiveTransport()
    account = PlatformAccount(
        account_id="yt_live_01",
        platform="youtube",
        account_name="Production Channel",
        state=AccountState.READY,
        can_publish=True,
    )
    job = DistributionJob(
        job_id="job_prod_01",
        output_id="out_01",
        project_id="proj_01",
        project_revision=1,
        artifact_path=str(tmp_path / "video.mp4"),
        artifact_sha256="abc123sha",
        approval_receipt_id="appr_01",
        platform="youtube",
        account_id=account.account_id,
        seo_metadata=PlatformSEOMetadata(platform="youtube", title="Real Video"),
        scheduled_time_utc="2026-10-13T12:00:00Z",
    )

    with pytest.raises(TransportError) as exc_info:
        await transport.dispatch_post(job, account)

    assert exc_info.value.code == "LIVE_PUBLISHING_NOT_AUTHORIZED"
    assert "LIVE_PUBLISHING_VERIFIED: NO" in exc_info.value.message

    # Verify that fake receipts are rejected in production
    rejected = await transport.verify_post_receipt(job, account, "fake_youtube_12345")
    assert rejected is None


# ── 2. Durability Across Fresh Process Reconstruction ─────────────────────────

@pytest.mark.asyncio
async def test_distribution_durability_across_fresh_instances(tmp_path: Path):
    """
    Verify that jobs and receipts persisted by one instance are cleanly hydrated
    by a completely fresh DistributionJobStore instance from the same directory.
    """
    store1 = DistributionJobStore(base_dir=tmp_path)
    job = DistributionJob(
        job_id="job_durable_01",
        user_id="creator_alpha",
        output_id="out_durable_01",
        project_id="proj_alpha",
        project_revision=1,
        artifact_path=str(tmp_path / "output.mp4"),
        artifact_sha256="sha_durable_123",
        approval_receipt_id="appr_alpha",
        platform="youtube",
        account_id="acc_yt_01",
        seo_metadata=PlatformSEOMetadata(platform="youtube", title="Durable Video"),
        scheduled_time_utc="2026-10-13T12:00:00Z",
        status=DistributionStatus.SCHEDULED,
    )
    store1.save_job(job)

    # Reconstruct store from the same directory (simulating fresh process startup)
    store2 = DistributionJobStore(base_dir=tmp_path)
    loaded_job = store2.get_job("job_durable_01")

    assert loaded_job is not None
    assert loaded_job.job_id == "job_durable_01"
    assert loaded_job.user_id == "creator_alpha"
    assert loaded_job.status == DistributionStatus.SCHEDULED
    assert loaded_job.artifact_sha256 == "sha_durable_123"


@pytest.mark.asyncio
async def test_analytics_repository_durability_across_fresh_instances(tmp_path: Path):
    """
    Verify that receipts, metric observations, notifications, and backoff states
    hydrated by a fresh AnalyticsRepository instance match what was saved.
    """
    repo1 = AnalyticsRepository(base_dir=tmp_path)
    receipt = PublishedReceiptV1(
        receipt_id="rcpt_durable_01",
        project_id="proj_01",
        provider=AnalyticsProvider.YOUTUBE,
        account_reference="channel_01",
        remote_post_id="yt_vid_999",
        remote_post_url="https://youtube.com/watch?v=yt_vid_999",
        publish_timestamp=datetime(2026, 10, 13, 10, 0, tzinfo=timezone.utc),
        confirmation_status=ReceiptConfirmationStatus.CONFIRMED,
        creator_id="creator_test",
    )
    repo1.save_receipt(receipt)

    obs = MetricObservationV1(
        receipt_id="rcpt_durable_01",
        provider=AnalyticsProvider.YOUTUBE,
        observed_at=datetime(2026, 10, 13, 11, 0, tzinfo=timezone.utc),
        views=4500,
        likes=320,
        comments=45,
        shares=12,
        observation_source=MetricObservationSource.OFFICIAL_API,
    )
    repo1.record_observation(obs)
    future_backoff = datetime.now(timezone.utc) + timedelta(seconds=300)
    repo1.set_rate_limit_backoff(AnalyticsProvider.YOUTUBE, until=future_backoff)

    # Reconstruct repository instance
    repo2 = AnalyticsRepository(base_dir=tmp_path)
    loaded_receipt = repo2.get_receipt("rcpt_durable_01")
    loaded_obs = repo2.get_observations_for_receipt("rcpt_durable_01")
    backoff_time = repo2.get_rate_limit_backoff(AnalyticsProvider.YOUTUBE)

    assert loaded_receipt is not None
    assert loaded_receipt.remote_post_id == "yt_vid_999"
    assert len(loaded_obs) == 1
    assert loaded_obs[0].views == 4500
    assert loaded_obs[0].likes == 320
    assert backoff_time is not None
    assert backoff_time > datetime.now(timezone.utc)


# ── 3. Corrupted File Quarantine ──────────────────────────────────────────────

def test_distribution_store_corrupted_json_quarantine(tmp_path: Path):
    """
    Verify that invalid/malformed JSON in jobs.json does not crash the service,
    is moved to a .corrupted.<timestamp> file, and store initializes cleanly.
    """
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text("{\"corrupted_json\": [INCOMPLETE_SYNTAX...", encoding="utf-8")

    store = DistributionJobStore(base_dir=tmp_path)
    jobs = store.list_jobs()

    assert jobs == []
    # Check that a quarantined file was created
    quarantined_files = list(tmp_path.glob("jobs.corrupted.*.json"))
    assert len(quarantined_files) == 1


def test_analytics_repo_corrupted_json_quarantine(tmp_path: Path):
    """
    Verify that invalid JSON in receipts.json is quarantined and does not cause boot crash.
    """
    receipts_file = tmp_path / "receipts.json"
    receipts_file.write_text("NOT_VALID_JSON_AT_ALL_12345", encoding="utf-8")

    repo = AnalyticsRepository(base_dir=tmp_path)
    receipts = repo.list_receipts()

    assert receipts == []
    quarantined_files = list(tmp_path.glob("receipts.corrupted.*.json"))
    assert len(quarantined_files) == 1


# ── 4. Platform Support Matrix & Offline Contract Verification ────────────────

def test_platform_support_matrix_definitions():
    """Verify official platform support matrix entries and constraints."""
    assert "youtube" in PLATFORM_SUPPORT_MATRIX
    assert "tiktok" in PLATFORM_SUPPORT_MATRIX
    assert "instagram" in PLATFORM_SUPPORT_MATRIX
    assert "x" in PLATFORM_SUPPORT_MATRIX

    yt = PLATFORM_SUPPORT_MATRIX["youtube"]
    assert yt.max_title_length == 100
    assert "https://www.googleapis.com/auth/youtube.upload" in yt.required_scopes

    tt = PLATFORM_SUPPORT_MATRIX["tiktok"]
    assert PublishTargetType.TIKTOK_INBOX_DRAFT in tt.supported_targets
    assert PublishTargetType.PUBLIC_VIDEO_POST in tt.supported_targets

    ig = PLATFORM_SUPPORT_MATRIX["instagram"]
    assert ig.aspect_ratios_supported == ["9:16"]

    x = PLATFORM_SUPPORT_MATRIX["x"]
    assert x.max_description_length == 280


def test_platform_matrix_validation_rules():
    """Verify that illegal metadata is rejected by PlatformMatrixValidator."""
    # Test illegal aspect ratio for Instagram (e.g. 16:9 landscape Reel)
    ig_job = DistributionJob(
        job_id="job_ig_err",
        output_id="out_01",
        project_id="proj_01",
        project_revision=1,
        artifact_path="/tmp/video.mp4",
        artifact_sha256="abc",
        approval_receipt_id="appr_01",
        platform="instagram",
        account_id="ig_acc_01",
        seo_metadata=PlatformSEOMetadata(platform="instagram", aspect_ratio="16:9", description="Reel"),
        scheduled_time_utc="2026-10-13T12:00:00Z",
    )
    errors = PlatformMatrixValidator.validate_job_against_matrix(ig_job)
    assert any("Aspect ratio '16:9' is not supported by instagram" in e for e in errors)

    # Test title length limit for YouTube (>100 characters)
    yt_job = DistributionJob(
        job_id="job_yt_err",
        output_id="out_01",
        project_id="proj_01",
        project_revision=1,
        artifact_path="/tmp/video.mp4",
        artifact_sha256="abc",
        approval_receipt_id="appr_01",
        platform="youtube",
        account_id="yt_acc_01",
        seo_metadata=PlatformSEOMetadata(platform="youtube", title="A" * 105),
        scheduled_time_utc="2026-10-13T12:00:00Z",
    )
    yt_errors = PlatformMatrixValidator.validate_job_against_matrix(yt_job)
    assert any("Title length (105) exceeds youtube maximum of 100" in e for e in yt_errors)


def test_offline_http_contract_builders():
    """
    Verify offline contract verification builds valid requests for YouTube, TikTok,
    Instagram, and X with zero live network calls.
    """
    # YouTube contract
    yt_job = DistributionJob(
        job_id="job_contract_yt",
        output_id="out_01",
        project_id="proj_01",
        project_revision=1,
        artifact_path="/tmp/video.mp4",
        artifact_sha256="sha_yt",
        approval_receipt_id="appr_01",
        platform="youtube",
        account_id="yt_123",
        seo_metadata=PlatformSEOMetadata(platform="youtube", title="Test Title", description="Test Desc", tags=["tag1"]),
        scheduled_time_utc="2026-10-13T12:00:00Z",
    )
    req_yt = PlatformMatrixValidator.build_offline_publication_request(yt_job, token="test_token")
    assert req_yt["method"] == "POST"
    assert "uploadType=resumable" in req_yt["url"]
    assert req_yt["headers"]["Authorization"] == "Bearer test_token"
    assert req_yt["body"]["snippet"]["title"] == "Test Title"

    # TikTok inbox draft contract
    tt_job = DistributionJob(
        job_id="job_contract_tt",
        output_id="out_01",
        project_id="proj_01",
        project_revision=1,
        artifact_path="/tmp/video.mp4",
        artifact_sha256="sha_tt",
        approval_receipt_id="appr_01",
        platform="tiktok",
        account_id="tt_123",
        seo_metadata=PlatformSEOMetadata(platform="tiktok", title="Draft Video", description="TikTok Draft"),
        scheduled_time_utc="2026-10-13T12:00:00Z",
    )
    req_tt = PlatformMatrixValidator.build_offline_publication_request(
        tt_job, token="test_token_tt", target_type=PublishTargetType.TIKTOK_INBOX_DRAFT
    )
    assert req_tt["is_inbox_draft"] is True
    assert req_tt["body"]["post_info"]["privacy_level"] == "SELF_ONLY"

    # Instagram contract
    ig_job = DistributionJob(
        job_id="job_contract_ig",
        output_id="out_01",
        project_id="proj_01",
        project_revision=1,
        artifact_path="/tmp/video.mp4",
        artifact_sha256="sha_ig",
        approval_receipt_id="appr_01",
        platform="instagram",
        account_id="17841400000000",
        seo_metadata=PlatformSEOMetadata(platform="instagram", description="Reel caption", hashtags=["#viral"]),
        scheduled_time_utc="2026-10-13T12:00:00Z",
    )
    req_ig = PlatformMatrixValidator.build_offline_publication_request(ig_job, token="test_token_ig")
    assert req_ig["body"]["media_type"] == "REELS"
    assert "17841400000000" in req_ig["url"]

    # X contract
    x_job = DistributionJob(
        job_id="job_contract_x",
        output_id="out_01",
        project_id="proj_01",
        project_revision=1,
        artifact_path="/tmp/video.mp4",
        artifact_sha256="sha_x",
        approval_receipt_id="appr_01",
        platform="x",
        account_id="x_user_01",
        seo_metadata=PlatformSEOMetadata(platform="x", description="Short Tweet update"),
        scheduled_time_utc="2026-10-13T12:00:00Z",
    )
    req_x = PlatformMatrixValidator.build_offline_publication_request(x_job, token="test_token_x")
    assert req_x["body"]["text"] == "Short Tweet update"


# ── 5. Review & Approval Negative Security Paths ──────────────────────────────

def test_editorial_approval_negative_paths(tmp_path: Path):
    """
    Verify strict refusal when:
    - revision is stale
    - checksum doesn't match artifact
    - user consent is revoked
    """
    from backend.distribution.eligibility import ReleaseEligibilityError

    service = DistributionService(store=DistributionJobStore(base_dir=tmp_path))

    valid_mp4_bytes = b"\x00\x00\x00\x20ftypmp42" + b"AUTHENTIC_VIDEO_BYTES_TEST"
    video_file = tmp_path / "actual_video.mp4"
    video_file.write_bytes(valid_mp4_bytes)
    correct_hash = hashlib.sha256(valid_mp4_bytes).hexdigest()

    # Create signed receipt for revision 1 with correct hash
    receipt = service.create_approval_receipt(
        output_id="out_01",
        project_id="proj_01",
        project_revision=1,
        artifact_sha256=correct_hash,
        approved_by="lead_editor",
        consent_for_external_publish=True,
    )

    # 1. Stale revision test (current revision advanced to 2)
    with pytest.raises(ReleaseEligibilityError) as exc_stale:
        service.check_release_eligibility(
            file_path_str=str(video_file),
            expected_user_id="creator_01",
            actual_user_id="creator_01",
            current_project_revision=2,  # Stale: receipt is for rev 1
            approval_receipt=receipt,
            permitted_uses=["social_distribution"],
            target_platform="youtube",
        )
    assert exc_stale.value.code == "APPROVAL_STALE_REVISION"

    # 2. Checksum mismatch test (video altered on disk)
    tampered_bytes = b"\x00\x00\x00\x20ftypmp42" + b"TAMPERED_VIDEO_BYTES"
    video_file.write_bytes(tampered_bytes)
    with pytest.raises(ReleaseEligibilityError) as exc_hash:
        service.check_release_eligibility(
            file_path_str=str(video_file),
            expected_user_id="creator_01",
            actual_user_id="creator_01",
            current_project_revision=1,
            approval_receipt=receipt,
            permitted_uses=["social_distribution"],
            target_platform="youtube",
        )
    assert exc_hash.value.code == "APPROVAL_STALE_ARTIFACT"

    # 3. Consent revoked test
    video_file.write_bytes(valid_mp4_bytes)
    revoked_receipt = service.create_approval_receipt(
        output_id="out_01",
        project_id="proj_01",
        project_revision=1,
        artifact_sha256=correct_hash,
        approved_by="lead_editor",
        consent_for_external_publish=False,  # Consent revoked
    )
    with pytest.raises(ReleaseEligibilityError) as exc_consent:
        service.check_release_eligibility(
            file_path_str=str(video_file),
            expected_user_id="creator_01",
            actual_user_id="creator_01",
            current_project_revision=1,
            approval_receipt=revoked_receipt,
            permitted_uses=["social_distribution"],
            target_platform="youtube",
        )
    assert exc_consent.value.code == "CONSENT_MISSING"


# ── 6. Analytics Separation & Deleted-Post Handling ───────────────────────────

@pytest.mark.asyncio
async def test_analytics_deleted_post_handling(tmp_path: Path):
    """
    Verify that deleted posts on remote platforms are marked DELETED_ON_PLATFORM,
    their status is preserved across polls, and they do not crash the engine.
    """
    repo = AnalyticsRepository(base_dir=tmp_path)
    engine = AnalyticsEngine(repository=repo)

    receipt = PublishedReceiptV1(
        receipt_id="rcpt_deleted_01",
        project_id="proj_01",
        provider=AnalyticsProvider.YOUTUBE,
        account_reference="channel_01",
        remote_post_id="yt_del_123",
        publish_timestamp=datetime.now(timezone.utc),
        confirmation_status=ReceiptConfirmationStatus.CONFIRMED,
        creator_id="creator_01",
    )
    repo.save_receipt(receipt)

    obs = MetricObservationV1(
        receipt_id="rcpt_deleted_01",
        provider=AnalyticsProvider.YOUTUBE,
        views=1200,
        likes=80,
    )
    repo.record_observation(obs)

    # Mark deleted
    success = engine.mark_post_deleted("rcpt_deleted_01")
    assert success is True

    agg = engine.get_aggregated_metrics("rcpt_deleted_01")
    assert agg is not None
    assert agg.is_deleted_on_platform is True
    assert agg.post_status == "DELETED_ON_PLATFORM"

    # Attempting to poll should recognize deleted status
    poll_obs, err = await engine.poll_post_metrics("rcpt_deleted_01")
    assert poll_obs is None
    assert "DELETED_ON_PLATFORM" in err


def test_multi_platform_summary_preserves_native_metrics(tmp_path: Path):
    """
    Verify get_multi_platform_summary groups observations by provider without
    lossy scalar addition (e.g. YouTube views are kept distinct from TikTok starts).
    """
    repo = AnalyticsRepository(base_dir=tmp_path)
    engine = AnalyticsEngine(repository=repo)

    # 1. YouTube receipt
    r_yt = PublishedReceiptV1(
        receipt_id="rcpt_yt",
        project_id="proj_01",
        provider=AnalyticsProvider.YOUTUBE,
        account_reference="acc_yt",
        remote_post_id="yt_1",
        publish_timestamp=datetime.now(timezone.utc),
        confirmation_status=ReceiptConfirmationStatus.CONFIRMED,
        creator_id="local",
    )
    repo.save_receipt(r_yt)
    repo.record_observation(MetricObservationV1(receipt_id="rcpt_yt", provider=AnalyticsProvider.YOUTUBE, views=5000, likes=300))

    # 2. TikTok receipt
    r_tt = PublishedReceiptV1(
        receipt_id="rcpt_tt",
        project_id="proj_01",
        provider=AnalyticsProvider.TIKTOK,
        account_reference="acc_tt",
        remote_post_id="tt_1",
        publish_timestamp=datetime.now(timezone.utc),
        confirmation_status=ReceiptConfirmationStatus.CONFIRMED,
        creator_id="local",
    )
    repo.save_receipt(r_tt)
    repo.record_observation(MetricObservationV1(receipt_id="rcpt_tt", provider=AnalyticsProvider.TIKTOK, views=12000, likes=1500))

    summary = engine.get_multi_platform_summary(creator_id="local")

    assert summary["total_published_posts"] == 2
    assert "platforms" in summary
    assert "youtube" in summary["platforms"]
    assert "tiktok" in summary["platforms"]

    # Native metrics separated
    assert summary["platforms"]["youtube"]["total_views"] == 5000
    assert summary["platforms"]["youtube"]["metric_definition"] == "30s playback or complete view"
    assert summary["platforms"]["tiktok"]["total_views"] == 12000
    assert summary["platforms"]["tiktok"]["metric_definition"] == "video start"


# ── 7. Bounded V2 (GT-06) and V3 (GT-07) Acceptance Harness ───────────────────

def test_v2_acceptance_validator_synthetic_filler_detection(tmp_path: Path):
    """
    Verify V2MultiOutputValidator detects synthetic null audio/video filler
    and hash duplication across outputs.
    """
    # Create 5 dummy source assets
    source_paths = []
    for i in range(5):
        p = tmp_path / f"source_{i}.mp4"
        p.write_bytes(f"SOURCE_DATA_{i}".encode("utf-8"))
        source_paths.append(str(p))

    # Create 10 outputs where two share identical hash (duplicate content)
    output_specs = []
    for i in range(10):
        out_p = tmp_path / f"output_{i}.mp4"
        # Force outputs 0 and 1 to be identical duplicates
        content = "SAME_CONTENT" if i in (0, 1) else f"UNIQUE_CONTENT_{i}"
        out_p.write_bytes(content.encode("utf-8"))
        output_specs.append({
            "output_id": f"out_{i}",
            "file_path": str(out_p),
            "source_origin_ids": [f"source_{i % 5}"],
        })

    validator = V2MultiOutputValidator()
    result = validator.validate_multi_output_package(
        project_id="proj_test_v2",
        source_asset_paths=source_paths,
        output_specifications=output_specs,
        is_real_user_media=True,
    )

    assert result["status"] == "FAILED"
    assert any("Outputs contain duplicate files" in issue for issue in result["issues"])


def test_v2_acceptance_truth_when_real_user_media_missing():
    """
    Verify that in the absence of authentic user source media, V2 validator
    reports NOT_TESTED and does NOT falsely claim PASSED.
    """
    validator = V2MultiOutputValidator()
    result = validator.validate_multi_output_package(
        project_id="proj_empty",
        source_asset_paths=[],
        output_specifications=[],
    )

    assert result["status"] == "NOT_TESTED"
    assert "Real user media not provided" in result["notes"]


def test_v3_acceptance_validator_narrative_integrity(tmp_path: Path):
    """
    Verify V3LongFormNarrativeValidator validates cut list presence and aspect ratio.
    """
    validator = V3LongFormNarrativeValidator()

    # Empty cut list should fail
    fail_result = validator.validate_long_form_output(
        project_id="proj_v3",
        source_recording_path=str(tmp_path / "long_rec.mp4"),
        output_rendered_path=str(tmp_path / "rendered.mp4"),
        narrative_cut_list=[],  # Empty
        target_aspect_ratio="16:9",
        is_real_user_media=True,
    )
    assert fail_result["status"] == "FAILED"
    assert any("empty" in issue for issue in fail_result["issues"])

    # Wrong aspect ratio should fail
    fail_aspect = validator.validate_long_form_output(
        project_id="proj_v3",
        source_recording_path=str(tmp_path / "long_rec.mp4"),
        output_rendered_path=str(tmp_path / "rendered.mp4"),
        narrative_cut_list=[{"cut_id": "c1", "start": 0, "end": 10}],
        target_aspect_ratio="9:16",  # V3 requires 16:9 narrative
        is_real_user_media=True,
    )
    assert fail_aspect["status"] == "FAILED"
    assert any("16:9" in issue for issue in fail_aspect["issues"])


def test_v3_acceptance_truth_when_real_user_recording_missing():
    """
    Verify that in the absence of authentic 60-min user recording, V3 validator
    reports NOT_TESTED.
    """
    validator = V3LongFormNarrativeValidator()
    result = validator.validate_long_form_output(
        project_id="proj_empty_v3",
        source_recording_path="",
        output_rendered_path="",
        narrative_cut_list=[],
    )

    assert result["status"] == "NOT_TESTED"
    assert "Authentic ~60-minute recording not provided" in result["notes"]


# ── 8. Release Acceptance Auditor Full Truth Table ────────────────────────────

def test_release_acceptance_auditor_reports_truthful_unreleased_status():
    """
    Verify that the ReleaseAcceptanceAuditor evaluates all Ground Truth gates,
    refuses to declare release readiness without live authorization and authentic media,
    and returns PHASE10_11_RELEASE_READY: NO.
    """
    auditor = ReleaseAcceptanceAuditor()
    report = auditor.audit_all()

    assert report["PHASE10_11_RELEASE_READY"] == "NO"
    assert report["LIVE_PUBLISHING_VERIFIED"] == "NO"
    assert report["LIVE_ANALYTICS_VERIFIED"] == "NO"

    gate_statuses = {g["gate_id"]: g["status"] for g in report["gates"]}

    # V2 and V3 media acceptance gates must be NOT_TESTED due to missing user media
    assert gate_statuses["GT-06"] == "NOT_TESTED"
    assert gate_statuses["GT-07"] == "NOT_TESTED"

    # Distribution & Analytics durability and contracts are LOCAL_PIPELINE_READY
    assert gate_statuses["GT-17"] == "LOCAL_PIPELINE_READY"
    assert gate_statuses["GT-18"] == "LOCAL_PIPELINE_READY"
    assert gate_statuses["GT-19"] == "LOCAL_PIPELINE_READY"
    assert gate_statuses["GT-23"] == "LOCAL_PIPELINE_READY"
    assert gate_statuses["GT-28"] == "BLOCKED"
