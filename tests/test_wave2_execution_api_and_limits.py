# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Deterministic tests for public API routes, multi-user job listings, and execution limit compliance."""

from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.media_pipeline.models import (
    DurationPolicy as BDurationPolicy,
    OutputSpecV1,
    ProductionRequestV1,
    SourceAssetV1,
)
from backend.media_pipeline.producer_adapter import get_media_producer


@pytest.mark.asyncio
async def test_production_jobs_listing_api_multi_user_isolation(tmp_path: Path):
    """L14, B07: /api/media/production/jobs isolates jobs per user_id."""
    producer = get_media_producer()
    producer._ledger.create_job(
        job_id="job_api_alice_1",
        request_fingerprint="fp_alice_api",
        run_id="run_a1",
        immutable_request={},
        output_ids=["c1"],
        user_id="alice_creator",
        status="COMPLETE",
    )
    producer._ledger.create_job(
        job_id="job_api_bob_1",
        request_fingerprint="fp_bob_api",
        run_id="run_b1",
        immutable_request={},
        output_ids=["c2"],
        user_id="bob_creator",
        status="COMPLETE",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Alice's jobs
        res_alice = await client.get("/api/media/production/jobs", params={"user_id": "alice_creator"})
        assert res_alice.status_code == 200
        alice_data = res_alice.json()
        assert len(alice_data) >= 1
        assert all(j["user_id"] == "alice_creator" for j in alice_data)
        assert any(j["job_id"] == "job_api_alice_1" for j in alice_data)

        # 2. Bob's jobs
        res_bob = await client.get("/api/media/production/jobs", params={"user_id": "bob_creator"})
        assert res_bob.status_code == 200
        bob_data = res_bob.json()
        assert len(bob_data) >= 1
        assert all(j["user_id"] == "bob_creator" for j in bob_data)
        assert any(j["job_id"] == "job_api_bob_1" for j in bob_data)


@pytest.mark.asyncio
async def test_cancel_api_endpoint(tmp_path: Path):
    """B26: POST /api/media/production/batch/{job_id}/cancel invokes producer cancellation cleanly."""
    producer = get_media_producer()
    job_id = "job_api_cancel_test"
    producer._ledger.create_job(
        job_id=job_id,
        request_fingerprint="fp_cancel_api",
        run_id="run_cancel_api",
        immutable_request={},
        output_ids=["c1", "c2"],
        user_id="local",
        status="RUNNING",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.post(f"/api/media/production/batch/{job_id}/cancel")
        assert res.status_code == 200
        data = res.json()
        assert data["acknowledged"] is True

        # Polling batch reflects CANCELLED
        poll_res = await client.get(f"/api/media/production/batch/{job_id}")
        assert poll_res.status_code == 200
        poll_data = poll_res.json()
        assert poll_data["status"] == "CANCELLED"
