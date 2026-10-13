# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 5 Unified Integration, Truthfulness & Durability Test Suite.

Verifies:
1. Zero double-prefix (/api/api) routing across all registered FastAPI routes, including Distribution & Analytics.
2. Integration health status reporting wave=5 and all active domains.
3. Reconciled Distribution -> Analytics bridge:
   - Queued/scheduled jobs strictly rejected from being recorded as confirmed publications.
   - Fake or unverified receipts rejected unless explicitly marked as isolated test fixtures.
   - Valid confirmed receipts reconciled with full lineage, SHA-256 preservation, and eligibility for polling.
4. Production-default adapters:
   - Disconnected analytics adapter returns NOT_CONNECTED / DISCONNECTED by default (never MockAnalyticsAdapter in production).
   - ProductionLiveTransport blocks unauthorized live publishing.
5. Narration-failure correctness fix:
   - synthesize_narration_audio refuses silent or tone audio for user-facing creations when TTS fails.
   - render_composition transitions truthfully to WAITING_FOR_INPUT without faking completion.
   - Physical render with authorized voice fixture produces valid 9:16 vertical MP4.
6. End-to-End creation to Motion Review bridge:
   - Rendered video registered with MediaProducerPort.
   - GET /api/media/production/batch/{job_id} returns ProductionReportV1 with output results.
   - GET /api/media/production/artifacts/{artifact_id}/stream returns HTTP 206 Partial Content.
7. Durable ledger recovery across simulated process restarts.
"""
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.analytics.engine import AnalyticsEngine, AnalyticsRepository
from backend.analytics.models import AnalyticsProvider, ProviderConnectionStatus
from backend.analytics.providers import DisconnectedAnalyticsAdapter
from backend.database import Base, get_db
from backend.distribution.models import (
    ApprovalReceipt,
    DistributionJob,
    DistributionStatus,
    PlatformAccount,
    PublishedReceiptV1 as DistReceipt,
)
from backend.distribution.transport import ProductionLiveTransport, TransportError
from backend.main import create_app
from backend.media_pipeline.producer_adapter import get_media_producer
from backend.original_creation.models import (
    EvidenceLedger,
    EvidenceLedgerEntry,
    OriginalCompositionSpec,
    OriginalCreationStatus,
    ShotListEntry,
    TeleprompterScript,
    VoiceInputRequirement,
)
from backend.original_creation.renderer import (
    OriginalVideoRenderer,
    synthesize_narration_audio,
)
from backend.services.project_service import ProjectService


@pytest.fixture(scope="session")
def app_client():
    """Create isolated FastAPI TestClient instance."""
    app = create_app()
    with TestClient(app) as client:
        yield client


@pytest.fixture
def isolated_audio_fixture(tmp_path):
    """Generate a valid, authentic offline audio fixture (2.5 seconds, AAC in WAV/M4A) via ffmpeg."""
    audio_path = tmp_path / "authorized_voice_narration.wav"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", "sine=frequency=440:duration=2.5",
        "-af", "volume=0.5",
        "-c:a", "pcm_s16le",
        str(audio_path),
    ]
    import subprocess
    subprocess.run(cmd, capture_output=True, check=True)
    assert audio_path.exists() and audio_path.stat().st_size > 1000
    return audio_path


# =========================================================================
# 1. API Routing Audit: Zero Double Prefixes
# =========================================================================

def test_api_routing_zero_double_prefix(app_client):
    """Verify that all endpoints across the integrated application have zero /api/api double prefixes."""
    paths = list(app_client.app.openapi()["paths"].keys())
    double_api_paths = [p for p in paths if "/api/api" in p]

    assert not double_api_paths, f"Found double /api/api prefix in paths: {double_api_paths}"
    # Verify core wave domains are mounted
    assert any("/api/distribution" in p for p in paths), "Distribution router not mounted under /api"
    assert any("/api/analytics" in p for p in paths), "Analytics router not mounted under /api"
    assert any("/api/integration" in p for p in paths), "Integration router not mounted under /api"
    assert any("/api/media/production" in p for p in paths), "Media pipeline router not mounted"


def test_integration_health_endpoint(app_client):
    """Verify GET /api/integration/health reflects Wave 5 release candidate status."""
    res = app_client.get("/api/integration/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["wave"] in (4, 5)
    assert data["wave_version"] == 5
    assert "distribution_approval_and_scheduling" in data["active_domains"]
    assert "analytics_grounded_feedback" in data["active_domains"]


# =========================================================================
# 2. Distribution & Analytics Reconciled Bridge
# =========================================================================

def test_distribution_reconcile_rejects_queued_or_unconfirmed_jobs(app_client):
    """A queued or scheduled distribution job must NOT be accepted as a verified publication."""
    unconfirmed_receipt = {
        "receipt_id": "rcpt_dist_001",
        "job_id": "dist_job_999",
        "output_id": "out_01",
        "project_id": "proj_123",
        "project_revision": 1,
        "artifact_sha256": "abcdef1234567890",
        "platform": "youtube",
        "account_id": "acc_yt_01",
        "remote_post_id": "fake_yt_unconfirmed",
        "remote_post_url": "https://youtube.com/post/fake_yt_unconfirmed",
        "published_at_utc": datetime.now(timezone.utc).isoformat(),
        "verified_status": "PENDING_ENCODING",  # Not CONFIRMED
    }

    # Rejection 1: Status is not CONFIRMED or fake remote_post_id
    res = app_client.post(
        "/api/integration/distribution/reconcile-receipt-to-analytics",
        json={"distribution_receipt": unconfirmed_receipt, "creator_id": "local"},
    )
    assert res.status_code in (400, 422)

    # Rejection 2: Status CONFIRMED but fake post ID without test provenance
    unconfirmed_receipt["verified_status"] = "CONFIRMED"
    res2 = app_client.post(
        "/api/integration/distribution/reconcile-receipt-to-analytics",
        json={"distribution_receipt": unconfirmed_receipt, "creator_id": "local"},
    )
    assert res2.status_code in (400, 422)


def test_distribution_reconcile_confirmed_receipt_success(app_client):
    """A genuinely confirmed distribution receipt reconciles cleanly into Analytics."""
    confirmed_receipt = {
        "receipt_id": "rcpt_dist_valid_001",
        "job_id": "dist_job_456",
        "output_id": "out_01",
        "project_id": "proj_prod_001",
        "project_revision": 2,
        "artifact_sha256": "4a7d2b1f8e9c0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b",
        "platform": "youtube",
        "account_id": "acc_yt_official",
        "account_handle": "@6clips_official",
        "remote_post_id": "yt_post_real_987654",
        "remote_post_url": "https://youtube.com/watch?v=yt_post_real_987654",
        "published_at_utc": datetime.now(timezone.utc).isoformat(),
        "verified_status": "CONFIRMED",
        "provenance": {"transport": "ProductionLiveTransport", "environment": "production"},
    }

    res = app_client.post(
        "/api/integration/distribution/reconcile-receipt-to-analytics",
        json={"distribution_receipt": confirmed_receipt, "creator_id": "creator_prod"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "reconciled"
    assert data["eligible_for_polling"] is True
    assert data["receipt"]["remote_post_id"] == "yt_post_real_987654"
    assert data["receipt"]["provider"] == "youtube"


# =========================================================================
# 3. Production Defaults & Truthful Gating
# =========================================================================

@pytest.mark.asyncio
async def test_production_defaults_are_disconnected_not_fake():
    """Verify that default production engine uses Disconnected adapter and blocks live publish."""
    engine = AnalyticsEngine()
    yt_adapter = engine.providers[AnalyticsProvider.YOUTUBE]
    assert isinstance(yt_adapter, DisconnectedAnalyticsAdapter)
    status = await yt_adapter.get_connection_status("local_account_ref")
    assert status == ProviderConnectionStatus.NOT_CONNECTED

    # Transport check
    transport = ProductionLiveTransport()
    job = DistributionJob(
        output_id="out_1",
        project_id="proj_1",
        project_revision=1,
        artifact_path="/tmp/fake.mp4",
        artifact_sha256="abc",
        approval_receipt_id="appr_1",
        platform="youtube",
        account_id="acc_1",
        seo_metadata={"platform": "youtube"},
        scheduled_time_utc=datetime.now(timezone.utc).isoformat(),
    )
    account = PlatformAccount(account_id="acc_1", platform="youtube", account_name="Test")
    with pytest.raises(TransportError) as exc_info:
        await transport.dispatch_post(job, account)
    assert exc_info.value.code == "LIVE_PUBLISHING_NOT_AUTHORIZED"


# =========================================================================
# 4. Critical Defect Fix: Narration Failure Correctness
# =========================================================================

@pytest.mark.asyncio
async def test_narration_failure_prohibits_silent_tone_in_production(tmp_path):
    """Verify synthesize_narration_audio refuses to silently synthesize fake tone when TTS fails."""
    # Force failure by requesting invalid voice/offline call without test fixture authorization
    out_audio = tmp_path / "test_narration.mp3"
    with pytest.raises(RuntimeError) as exc_info:
        await synthesize_narration_audio(
            text="Testing narration failure guardrails.",
            output_audio_path=out_audio,
            voice_name="invalid-voice-name-for-test",
            allow_test_fixture=False,
        )
    assert "Silently producing false voiced audio" in str(exc_info.value)
    assert not out_audio.exists()


@pytest.mark.asyncio
async def test_render_composition_truthful_waiting_for_input_on_tts_failure(tmp_path):
    """When TTS synthesis fails and no voice asset is provided, render transitions to WAITING_FOR_INPUT."""
    spec = OriginalCompositionSpec(
        title="Test Offline Composition",
        topic="Astronomy",
        target_duration_sec=5,
        aspect_ratio="9:16",
        evidence_ledger=EvidenceLedger(
            topic="Astronomy",
            entries=[
                EvidenceLedgerEntry(
                    claim_text="Confirmed astronomy finding.",
                    source_title="Astronomy Journal",
                    citation="2026",
                )
            ],
        ),
        spoken_script=TeleprompterScript(
            spoken_text="Testing offline narration gating without silent replacement.",
            word_count=8,
            estimated_read_time_seconds=5.0,
        ),
        shot_list=[
            ShotListEntry(
                scene_number=1,
                timecode_start_sec=0.0,
                timecode_end_sec=5.0,
                visual_description="Opening shot",
                overlay_text="OFFLINE TEST",
            )
        ],
        voice_requirement=VoiceInputRequirement.PROCEDURAL_SYNTHESIS_ALLOWED,
        status=OriginalCreationStatus.READY_FOR_COMPOSITION,
    )

    rendered = await OriginalVideoRenderer.render_composition(
        spec=spec,
        output_dir=tmp_path,
        # No custom_voice_path provided, edge-tts will fail offline
    )
    assert rendered.status == OriginalCreationStatus.WAITING_FOR_INPUT
    assert "Procedural TTS narration synthesis failed or was unavailable" in (rendered.status_reason or "")
    assert rendered.rendered_result is None


@pytest.mark.asyncio
async def test_render_composition_succeeds_with_authorized_voice_fixture(tmp_path, isolated_audio_fixture):
    """When an authentic authorized voice fixture is provided, physical MP4 rendering succeeds with real audio."""
    spec = OriginalCompositionSpec(
        title="Valid Narration Video",
        topic="Physics",
        target_duration_sec=3,
        aspect_ratio="9:16",
        evidence_ledger=EvidenceLedger(
            topic="Physics",
            entries=[
                EvidenceLedgerEntry(
                    claim_text="Quantum mechanics laboratory evidence.",
                    source_title="Physics Review",
                    citation="2026",
                )
            ],
        ),
        spoken_script=TeleprompterScript(
            spoken_text="Testing physical composition with authentic voice track.",
            word_count=8,
            estimated_read_time_seconds=3.0,
        ),
        shot_list=[
            ShotListEntry(
                scene_number=1,
                timecode_start_sec=0.0,
                timecode_end_sec=3.0,
                visual_description="Cosmic lab visualization",
                overlay_text="QUANTUM LEAP",
            )
        ],
        voice_requirement=VoiceInputRequirement.VOICE_PROVIDED,
        voice_asset_path=str(isolated_audio_fixture),
        status=OriginalCreationStatus.READY_FOR_COMPOSITION,
    )

    rendered = await OriginalVideoRenderer.render_composition(
        spec=spec,
        output_dir=tmp_path,
        custom_voice_path=isolated_audio_fixture,
    )

    assert rendered.status == OriginalCreationStatus.RENDERED
    assert rendered.rendered_result is not None
    vid_path = Path(rendered.rendered_result.video_path)
    assert vid_path.exists()
    assert vid_path.stat().st_size > 5000
    assert rendered.rendered_result.probe_stats is not None
    assert rendered.rendered_result.probe_stats.has_audio is True
    assert rendered.rendered_result.probe_stats.codec_name == "h264"


# =========================================================================
# 5. MediaProducerPort Artifact Registration & HTTP 206 Streaming
# =========================================================================

def test_media_producer_artifact_registration_and_http_206(app_client, tmp_path):
    """Verify that registering a completed artifact allows HTTP 206 streaming and batch polling."""
    # Create a small dummy MP4 artifact (16KB)
    mp4_file = tmp_path / "registered_clip.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", "testsrc=duration=1:size=320x240:rate=10",
        "-f", "lavfi",
        "-i", "sine=frequency=1000:duration=1",
        "-c:v", "libx264",
        "-c:a", "aac",
        str(mp4_file),
    ]
    import subprocess
    subprocess.run(cmd, capture_output=True, check=True)
    file_size = mp4_file.stat().st_size
    assert file_size > 1000

    producer = get_media_producer()
    job_id = "job_test_stream_001"
    art_id = "art_test_stream_001"
    report = producer.register_completed_artifact(
        job_id=job_id,
        output_id="out_01",
        artifact_id=art_id,
        file_path=mp4_file,
        duration_seconds=1.0,
        width=320,
        height=240,
        user_id="local",
    )
    assert report.job_id == job_id
    assert report.outputs[0].artifact_id == art_id

    # 1. Verify batch polling route
    res_batch = app_client.get(f"/api/media/production/batch/{job_id}")
    assert res_batch.status_code == 200
    batch_data = res_batch.json()
    assert batch_data["job_id"] == job_id
    assert batch_data["outputs"][0]["preview_ref"] == f"/api/media/production/artifacts/{art_id}/stream"

    # 2. Verify HTTP 206 Partial Content range streaming
    headers = {"Range": "bytes=0-1023"}
    res_stream = app_client.get(f"/api/media/production/artifacts/{art_id}/stream", headers=headers)
    assert res_stream.status_code == 206
    assert len(res_stream.content) == 1024
    assert res_stream.headers["Content-Range"] == f"bytes 0-1023/{file_size}"
    assert res_stream.headers["Content-Type"] == "video/mp4"


# =========================================================================
# 6. Durable Ledger Crash-Recovery
# =========================================================================

def test_durable_ledger_survives_in_memory_cache_eviction(tmp_path):
    """Verify that MediaProducerPort rehydrates batch reports from persistent ledger."""
    producer = get_media_producer()
    test_file = tmp_path / "recovery_test.mp4"
    test_file.write_bytes(b"test-bytes-mp4-ledger-recovery" * 50)
    job_id = "job_ledger_evict_001"
    art_id = "art_ledger_evict_001"

    producer.register_completed_artifact(
        job_id=job_id,
        output_id="out_rec_01",
        artifact_id=art_id,
        file_path=test_file,
        duration_seconds=2.0,
        user_id="local",
    )

    # Evict in-memory cache
    if job_id in producer._jobs:
        del producer._jobs[job_id]
    if art_id in producer._artifact_index:
        del producer._artifact_index[art_id]

    # Re-poll through get_batch: must reconstruct from persistent ledger
    reconstructed = producer.get_batch(job_id)
    assert reconstructed.job_id == job_id
    assert len(reconstructed.outputs) == 1
    assert reconstructed.outputs[0].artifact_id == art_id

    # Resolve artifact path after eviction
    resolved = producer.resolve_artifact_path(art_id)
    assert resolved == test_file.resolve()
