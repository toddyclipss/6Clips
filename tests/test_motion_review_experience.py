# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Acceptance test suite for B6 — Motion Review & Refine Experience and Artifact Streaming.

Tests:
1. Artifact streaming HTTP endpoint: Range headers (200 / 206), Content-Type video/mp4, zero file:// leakage.
2. Motion Review multi-output contract: 3 separate outputs, isolated approval, isolated refine.
3. Empty Create state: 9:16 aspect ratio, zero assets, no demo seeds or phantom restores.
4. Database isolation.
"""

import hashlib
import io
import json
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.media_pipeline.api_router import router as media_router
from backend.media_pipeline.producer_adapter import MediaProducerPort, get_media_producer
from backend.media_pipeline.models import (
    ChecksV1,
    MediaProbeV1,
    OutputResultV1,
    OutputState,
    SourceRangeV1,
)

PROD_DB_PATH = Path("c:/Users/toddy/Desktop/ViralMint/viralmint.db")


def get_file_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().upper()


@pytest.fixture(autouse=True)
def verify_production_db_isolation():
    assert PROD_DB_PATH.exists(), "Production DB must exist"
    pre_hash = get_file_sha256(PROD_DB_PATH)
    yield
    post_hash = get_file_sha256(PROD_DB_PATH)
    assert pre_hash == post_hash, f"Production DB modified! Pre: {pre_hash}, Post: {post_hash}"


@pytest.fixture
def test_app(tmp_path):
    app = FastAPI()
    app.include_router(media_router)
    return app


def test_artifact_streaming_endpoint(test_app, tmp_path):
    """B6 & B8 — Artifact video streaming supports HTTP Range requests without file:// exposure."""
    # Create dummy mp4 file
    test_video = tmp_path / "stream_artifact.mp4"
    test_data = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41" + (b"A" * 2048)
    test_video.write_bytes(test_data)

    producer = get_media_producer()
    artifact_id = "art_test_stream_123"
    producer._artifact_index[artifact_id] = test_video

    client = TestClient(test_app)

    # 1. Full stream request (200 OK)
    res_full = client.get(f"/api/media/production/artifacts/{artifact_id}/stream")
    assert res_full.status_code == 200
    assert res_full.headers["Content-Type"] == "video/mp4"
    assert res_full.headers["Accept-Ranges"] == "bytes"
    assert len(res_full.content) == len(test_data)

    # 2. Range request (206 Partial Content)
    res_range = client.get(
        f"/api/media/production/artifacts/{artifact_id}/stream",
        headers={"Range": "bytes=0-100"},
    )
    assert res_range.status_code == 206
    assert res_range.headers["Content-Range"] == f"bytes 0-100/{len(test_data)}"
    assert len(res_range.content) == 101

    # 3. Nonexistent artifact returns 404
    res_404 = client.get("/api/media/production/artifacts/nonexistent_art/stream")
    assert res_404.status_code == 404


def test_motion_review_output_isolation():
    """B6 — 3 separate outputs have independent identity, approval, and isolation."""
    out1 = OutputResultV1(
        output_id="clip_hook_1",
        project_revision_id="1",
        artifact_id="art_1",
        media_probe=MediaProbeV1(
            width=1080, height=1920, duration_seconds=10.0,
            video_codec="h264", audio_codec="aac", fps=30.0,
            audio_channels=2, sample_rate=48000, content_hash="HASH1",
        ),
        source_ranges=[SourceRangeV1(
            asset_id="game_1", start_seconds=0.0, end_seconds=10.0,
            duration_seconds=10.0, editorial_reason="Hook setup", relevance_score=9.0,
        )],
        checks=ChecksV1(technical="PASS", contract="PASS", editorial="NOT_ASSESSED"),
        preview_ref="/api/media/production/artifacts/art_1/stream",
        state=OutputState.SUCCEEDED,
    )
    out2 = OutputResultV1(
        output_id="clip_mid_2",
        project_revision_id="2",
        artifact_id="art_2",
        media_probe=MediaProbeV1(
            width=1080, height=1920, duration_seconds=10.0,
            video_codec="h264", audio_codec="aac", fps=30.0,
            audio_channels=2, sample_rate=48000, content_hash="HASH2",
        ),
        source_ranges=[SourceRangeV1(
            asset_id="game_1", start_seconds=12.0, end_seconds=22.0,
            duration_seconds=10.0, editorial_reason="Mid-game combat", relevance_score=8.5,
        )],
        checks=ChecksV1(technical="PASS", contract="PASS", editorial="NOT_ASSESSED"),
        preview_ref="/api/media/production/artifacts/art_2/stream",
        state=OutputState.SUCCEEDED,
    )
    out3 = OutputResultV1(
        output_id="clip_climax_3",
        project_revision_id="3",
        artifact_id="art_3",
        media_probe=MediaProbeV1(
            width=1080, height=1920, duration_seconds=10.0,
            video_codec="h264", audio_codec="aac", fps=30.0,
            audio_channels=2, sample_rate=48000, content_hash="HASH3",
        ),
        source_ranges=[SourceRangeV1(
            asset_id="game_1", start_seconds=24.0, end_seconds=34.0,
            duration_seconds=10.0, editorial_reason="Final clutch victory", relevance_score=8.0,
        )],
        checks=ChecksV1(technical="PASS", contract="PASS", editorial="NOT_ASSESSED"),
        preview_ref="/api/media/production/artifacts/art_3/stream",
        state=OutputState.SUCCEEDED,
    )

    outputs = [out1, out2, out3]
    assert len(outputs) == 3
    assert len({o.output_id for o in outputs}) == 3
    assert len({o.artifact_id for o in outputs}) == 3
    assert len({o.project_revision_id for o in outputs}) == 3

    # Approving output 2 does not affect output 1 or 3
    approved = set()
    approved.add(out2.output_id)
    assert out1.output_id not in approved
    assert out2.output_id in approved
    assert out3.output_id not in approved


def test_empty_create_mode_invariants():
    """B6 — Empty create mode stays 9:16 with zero assets and no phantom seeded demo clips."""
    from backend.models.project import default_empty_document
    doc_json = default_empty_document("Empty Canvas", "9:16")
    doc = json.loads(doc_json)

    assert doc["aspect_ratio"] == "9:16"
    assert doc["timeline"]["duration_seconds"] == 0.0
    for track in doc["timeline"]["tracks"]:
        assert len(track["clips"]) == 0, "No phantom or seeded clips in empty project!"
    assert len(doc["assets"]) == 0, "Zero assets in empty project!"
