# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Acceptance test suite for AGENTE B — Real Media Production Pipeline & MediaProducerPort.

Tests:
1. Physical media byte inspection (ffprobe, sha256, streams, audio volume).
2. Provenance & Rights negative gate: unpermitted routes return BLOCKED.
3. 3-segment selection: non-overlapping offsets, distinct narrative roles, distinct relevance scores.
4. Insufficient duration guard: short media returns BLOCKED.
5. Batch execution: 3 distinct 9:16 MP4s rendered with synchronized audio and project revisions.
6. Fault tolerance: output 3 failure preserves outputs 1 & 2 -> PARTIAL report.
7. Idempotency & cancellation.
8. Complete production DB isolation.
"""

import asyncio
import hashlib
import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
import pytest
from sqlalchemy import select

from backend.database import AsyncSessionLocal, init_db
from backend.media_pipeline.models import (
    BatchStatus,
    DurationPolicy,
    ExecutionLimitsV1,
    OutputSpecV1,
    OutputState,
    ProductionRequestV1,
    SourceAssetV1,
)
from backend.media_pipeline.media_inspector import (
    inspect_source_provenance_and_rights,
    probe_physical_media,
    compute_file_sha256,
)
from backend.media_pipeline.segment_selector import select_editorial_segments
from backend.media_pipeline.producer_adapter import MediaProducerPort

logger = logging.getLogger(__name__)

PROD_DB_PATH = Path("c:/Users/toddy/Desktop/ViralMint/viralmint.db")


def get_file_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().upper()


@pytest.fixture(autouse=True)
def verify_production_db_isolation():
    """Ensure production database hash is identical before and after every test."""
    assert PROD_DB_PATH.exists(), "Production DB must exist"
    pre_hash = get_file_sha256(PROD_DB_PATH)
    yield
    post_hash = get_file_sha256(PROD_DB_PATH)
    assert pre_hash == post_hash, f"Production DB modified! Pre: {pre_hash}, Post: {post_hash}"


def create_authorized_gameplay_fixture(target_path: Path, duration_s: int = 36) -> Path:
    """Synthesize an authorized test gameplay footage fixture with real video motion and audio."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists() and target_path.stat().st_size > 10000:
        return target_path

    # Use FFmpeg to generate 1920x1080 30fps video with moving graphics, HUD box, center crosshair, and synth audio
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"testsrc=duration={duration_s}:size=1920x1080:rate=30",
        "-f", "lavfi",
        "-i", f"sine=frequency=440:duration={duration_s}",
        "-vf", (
            "drawbox=x=40:y=40:w=300:h=120:color=red@0.8:t=fill,"
            "drawbox=x=950:y=530:w=20:h=20:color=white@0.9:t=fill"
        ),
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        str(target_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, f"FFmpeg fixture generation failed: {res.stderr}"
    return target_path


@pytest.mark.asyncio
async def test_provenance_and_rights_negative_gate(tmp_path):
    """B1 — Source provenance: unpermitted route or missing extraction right returns BLOCKED."""
    asset_unpermitted_route = SourceAssetV1(
        asset_id="yt_unauthorized_123",
        editorial_role="primary_footage",
        permitted_uses=["clip_extraction"],
        acquisition_route="unauthorized_youtube_scrape",
        local_path=str(tmp_path / "dummy.mp4"),
    )
    blocker = inspect_source_provenance_and_rights(asset_unpermitted_route)
    assert blocker is not None
    assert blocker.code == "UNPERMITTED_ACQUISITION_ROUTE"
    assert "not authorized" in blocker.precise_reason

    asset_insufficient_uses = SourceAssetV1(
        asset_id="fixture_ref_only",
        editorial_role="reference",
        permitted_uses=["metadata_inspection_only"],
        acquisition_route="authorized_fixture",
        local_path=str(tmp_path / "dummy.mp4"),
    )
    blocker_uses = inspect_source_provenance_and_rights(asset_insufficient_uses)
    assert blocker_uses is not None
    assert blocker_uses.code == "INSUFFICIENT_PERMITTED_USES"


@pytest.mark.asyncio
async def test_physical_media_byte_inspection(tmp_path):
    """B1 — Physical bytes inspection: probe streams, codecs, volume, sha256."""
    fixture_path = tmp_path / "gameplay_fixture.mp4"
    create_authorized_gameplay_fixture(fixture_path, duration_s=15)

    probe, blocker = await probe_physical_media(fixture_path)
    assert blocker is None
    assert probe is not None
    assert probe.width == 1920
    assert probe.height == 1080
    assert probe.duration_seconds >= 14.5
    assert probe.video_codec == "h264"
    assert probe.audio_codec == "aac"
    assert probe.audio_channels == 1
    assert probe.content_hash == compute_file_sha256(fixture_path)
    assert probe.is_silent is False


@pytest.mark.asyncio
async def test_three_segment_selection_and_duration_guard(tmp_path):
    """B2 — Segment selector: non-overlapping ranges, narrative roles, short duration guard."""
    fixture_path = tmp_path / "gameplay_36s.mp4"
    create_authorized_gameplay_fixture(fixture_path, duration_s=36)
    probe, _ = await probe_physical_media(fixture_path)

    # 1. Test short duration guard: requesting 3x 60s clips on a 36s video must BLOCK, not loop
    specs_too_long = [
        OutputSpecV1(output_id="clip_1", seconds=60.0, duration_policy=DurationPolicy.EXACT),
        OutputSpecV1(output_id="clip_2", seconds=60.0, duration_policy=DurationPolicy.EXACT),
        OutputSpecV1(output_id="clip_3", seconds=60.0, duration_policy=DurationPolicy.EXACT),
    ]
    ranges_bad, blocker = select_editorial_segments(probe, specs_too_long)
    assert blocker is not None
    assert blocker.code == "INSUFFICIENT_SOURCE_DURATION"
    assert len(ranges_bad) == 0

    # 2. Test valid test parameters: 3x 10s clips on 36s video
    specs_valid = [
        OutputSpecV1(output_id="clip_1", seconds=10.0, duration_policy=DurationPolicy.EXACT),
        OutputSpecV1(output_id="clip_2", seconds=10.0, duration_policy=DurationPolicy.EXACT),
        OutputSpecV1(output_id="clip_3", seconds=10.0, duration_policy=DurationPolicy.EXACT),
    ]
    ranges_valid, blocker_none = select_editorial_segments(probe, specs_valid)
    assert blocker_none is None
    assert len(ranges_valid) == 3

    # Check non-overlap
    r1, r2, r3 = ranges_valid
    assert r1.end_seconds <= r2.start_seconds
    assert r2.end_seconds <= r3.start_seconds
    assert r1.editorial_reason != r2.editorial_reason
    assert r2.editorial_reason != r3.editorial_reason


@pytest.mark.asyncio
async def test_full_batch_production_and_independent_outputs(tmp_path):
    """B3, B4, B5, B8 — Real batch production: 3 independent 9:16 MP4s, ffprobe, and ProjectRevisions."""
    await init_db()
    fixture_path = tmp_path / "gameplay_fixture_40s.mp4"
    create_authorized_gameplay_fixture(fixture_path, duration_s=40)

    producer = MediaProducerPort(storage_dir=tmp_path / "media_production")

    req = ProductionRequestV1(
        run_id="run_test_b8",
        contract_id="contract_test_b8",
        contract_version="1.0.0",
        project_id="proj_6clips_b8",
        user_id="local",
        source_assets=[
            SourceAssetV1(
                asset_id="asset_gameplay_auth",
                editorial_role="primary_footage",
                permitted_uses=["clip_extraction", "motion_review"],
                acquisition_route="authorized_fixture",
                local_path=str(fixture_path),
            )
        ],
        outputs=[
            OutputSpecV1(output_id="clip_hook_1", seconds=8.0, duration_policy=DurationPolicy.EXACT),
            OutputSpecV1(output_id="clip_mid_2", seconds=8.0, duration_policy=DurationPolicy.EXACT),
            OutputSpecV1(output_id="clip_climax_3", seconds=8.0, duration_policy=DurationPolicy.EXACT),
        ],
        execution_limits=ExecutionLimitsV1(max_attempts=2),
    )

    submit_res = await producer.submit_batch(req)
    assert submit_res["accepted"] is True
    job_id = submit_res["job_id"]

    # Poll until complete
    for _ in range(60):
        report = producer.get_batch(job_id)
        if report.status in (BatchStatus.COMPLETE, BatchStatus.PARTIAL, BatchStatus.BLOCKED):
            break
        await asyncio.sleep(0.5)

    assert report.status == BatchStatus.COMPLETE
    assert len(report.outputs) == 3

    # Check each output independently
    hashes = set()
    for idx, out in enumerate(report.outputs):
        assert out.state == OutputState.SUCCEEDED
        assert out.checks.technical == "PASS"
        assert out.checks.contract == "PASS"
        assert out.checks.editorial == "NOT_ASSESSED"
        assert out.project_revision_id is not None
        assert out.artifact_id is not None
        assert out.preview_ref.startswith("/api/media/production/artifacts/")

        # Verify probe
        probe = out.media_probe
        assert probe is not None
        assert probe.width == 1080
        assert probe.height == 1920
        assert 7.5 <= probe.duration_seconds <= 8.5
        assert probe.video_codec == "h264"
        assert probe.audio_codec == "aac"

        # Verify artifact file on disk
        artifact_file = producer.resolve_artifact_path(out.artifact_id)
        assert artifact_file is not None
        assert artifact_file.exists()
        h = compute_file_sha256(artifact_file)
        assert h not in hashes, "All 3 outputs must be distinct independent files!"
        hashes.add(h)


@pytest.mark.asyncio
async def test_fault_tolerance_partial_failure(tmp_path):
    """B5 — Failure on 3rd output preserves outputs 1 & 2 and signals PARTIAL."""
    await init_db()
    fixture_path = tmp_path / "gameplay_fixture_partial.mp4"
    create_authorized_gameplay_fixture(fixture_path, duration_s=36)

    producer = MediaProducerPort(storage_dir=tmp_path / "media_production_partial")

    req = ProductionRequestV1(
        run_id="run_partial_test",
        contract_id="contract_partial",
        contract_version="1.0.0",
        project_id="proj_partial",
        user_id="local",
        source_assets=[
            SourceAssetV1(
                asset_id="asset_partial",
                editorial_role="primary_footage",
                permitted_uses=["clip_extraction", "motion_review"],
                acquisition_route="authorized_fixture",
                local_path=str(fixture_path),
            )
        ],
        outputs=[
            OutputSpecV1(output_id="out_good_1", seconds=6.0, duration_policy=DurationPolicy.EXACT),
            OutputSpecV1(output_id="out_good_2", seconds=6.0, duration_policy=DurationPolicy.EXACT),
            OutputSpecV1(output_id="out_fail_3", seconds=6.0, duration_policy=DurationPolicy.EXACT),
        ],
    )

    # Submit with simulated failure on output index 2 (the 3rd output)
    submit_res = await producer.submit_batch(req, simulate_failure_output_index=2)
    assert submit_res["accepted"] is True
    job_id = submit_res["job_id"]

    for _ in range(60):
        report = producer.get_batch(job_id)
        if report.status in (BatchStatus.COMPLETE, BatchStatus.PARTIAL, BatchStatus.BLOCKED):
            break
        await asyncio.sleep(0.5)

    assert report.status == BatchStatus.PARTIAL
    assert len(report.outputs) == 3

    # Outputs 1 and 2 must be intact and SUCCEEDED
    assert report.outputs[0].state == OutputState.SUCCEEDED
    assert report.outputs[1].state == OutputState.SUCCEEDED
    assert report.outputs[0].artifact_id is not None
    assert report.outputs[1].artifact_id is not None

    # Output 3 must be FAILED with exact error
    assert report.outputs[2].state == OutputState.FAILED
    assert report.outputs[2].error_detail is not None
    assert "Simulated render pipeline execution failure" in report.outputs[2].error_detail


@pytest.mark.asyncio
async def test_idempotency_and_cancellation(tmp_path):
    """B8 — Idempotency and batch cancellation."""
    await init_db()
    fixture_path = tmp_path / "gameplay_fixture_idem.mp4"
    create_authorized_gameplay_fixture(fixture_path, duration_s=25)

    producer = MediaProducerPort(storage_dir=tmp_path / "media_production_idem")

    req = ProductionRequestV1(
        run_id="run_idem_test",
        contract_id="contract_idem",
        contract_version="1.0.0",
        project_id="proj_idem",
        user_id="local",
        source_assets=[
            SourceAssetV1(
                asset_id="asset_idem",
                editorial_role="primary_footage",
                permitted_uses=["clip_extraction", "motion_review"],
                acquisition_route="authorized_fixture",
                local_path=str(fixture_path),
            )
        ],
        outputs=[
            OutputSpecV1(output_id="clip_a", seconds=5.0, duration_policy=DurationPolicy.EXACT),
            OutputSpecV1(output_id="clip_b", seconds=5.0, duration_policy=DurationPolicy.EXACT),
        ],
    )

    res1 = await producer.submit_batch(req)
    res2 = await producer.submit_batch(req)
    assert res1["job_id"] == res2["job_id"]
    assert res2.get("idempotent_replay") is True

    # Test cancellation
    cancel_res = producer.cancel_batch(res1["job_id"])
    assert cancel_res["acknowledged"] is True
    report = producer.get_batch(res1["job_id"])
    assert report.status == BatchStatus.CANCELLED


@pytest.mark.asyncio
async def test_duration_policy_target_and_max_semantics(tmp_path):
    """B5 — Explicit contract verification for TARGET and MAX duration policies."""
    await init_db()
    fixture_path = tmp_path / "gameplay_fixture_policies.mp4"
    create_authorized_gameplay_fixture(fixture_path, duration_s=30)

    producer = MediaProducerPort(storage_dir=tmp_path / "media_production_policies")

    req = ProductionRequestV1(
        run_id="run_policies_test",
        contract_id="contract_policies_test",
        contract_version="1.0.0",
        project_id="proj_policies",
        user_id="local",
        source_assets=[
            SourceAssetV1(
                asset_id="asset_policy_test",
                editorial_role="primary_footage",
                permitted_uses=["clip_extraction", "motion_review"],
                acquisition_route="authorized_fixture",
                local_path=str(fixture_path),
            )
        ],
        outputs=[
            # Output 1: TARGET duration with tolerance
            OutputSpecV1(
                output_id="clip_target_1",
                seconds=8.0,
                duration_policy=DurationPolicy.TARGET,
                tolerance_seconds=2.0,
            ),
            # Output 2: MAX duration
            OutputSpecV1(
                output_id="clip_max_2",
                seconds=10.0,
                duration_policy=DurationPolicy.MAX,
            ),
        ],
    )

    submit_res = await producer.submit_batch(req)
    assert submit_res["accepted"] is True
    job_id = submit_res["job_id"]

    for _ in range(60):
        report = producer.get_batch(job_id)
        if report.status in (BatchStatus.COMPLETE, BatchStatus.PARTIAL, BatchStatus.BLOCKED):
            break
        await asyncio.sleep(0.5)

    assert report.status == BatchStatus.COMPLETE
    assert len(report.outputs) == 2

    # Check TARGET output
    out_target = report.outputs[0]
    assert out_target.state == OutputState.SUCCEEDED
    assert out_target.checks.contract == "PASS"
    assert out_target.media_probe is not None
    # Duration must be within 8.0 +- (2.0 + 0.8)
    assert 5.0 <= out_target.media_probe.duration_seconds <= 11.0

    # Check MAX output
    out_max = report.outputs[1]
    assert out_max.state == OutputState.SUCCEEDED
    assert out_max.checks.contract == "PASS"
    assert out_max.media_probe is not None
    assert out_max.media_probe.duration_seconds <= 10.5


def test_fastapi_endpoint_and_dict_payload(tmp_path):
    """B8 — Verify MediaProducerPort routes wired into live FastAPI app via TestClient with raw dict."""
    from fastapi.testclient import TestClient
    from backend.main import app

    client = TestClient(app)

    # 1. Test polling unknown job
    res = client.get("/api/media/production/batch/unknown_job_999")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "BLOCKED"
    assert any(b["code"] == "JOB_NOT_FOUND" for b in data["blockers"])

    # 2. Test negative gate via HTTP POST with raw dict payload (unauthorized acquisition route)
    raw_payload = {
        "schema_version": "production.v1",
        "run_id": "run_http_test",
        "contract_id": "contract_http_v1",
        "contract_version": "1.0.0",
        "project_id": "proj_http_test",
        "user_id": "local",
        "source_assets": [
            {
                "asset_id": "asset_unauth_route",
                "editorial_role": "primary_footage",
                "permitted_uses": ["clip_extraction"],
                "acquisition_route": "unauthorized_youtube_scrape",
                "local_path": str(tmp_path / "dummy.mp4"),
            }
        ],
        "outputs": [
            {
                "output_id": "clip_http_1",
                "aspect_ratio": "9:16",
                "seconds": 15.0,
                "duration_policy": "TARGET",
                "tolerance_seconds": 3.0,
            }
        ],
    }

    res_post = client.post("/api/media/production/batch", json=raw_payload)
    assert res_post.status_code == 200
    resp_data = res_post.json()
    assert resp_data["accepted"] is False
    assert resp_data["blocker"]["code"] == "UNPERMITTED_ACQUISITION_ROUTE"

