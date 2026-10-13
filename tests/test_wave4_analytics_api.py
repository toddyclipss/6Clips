# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Tests for Analytics FastAPI Endpoints (Wave 4 Role 5).

Verifies:
- GET  /api/analytics/status returns truthful NOT_CONNECTED
- POST /api/analytics/receipts records published receipts
- POST /api/analytics/fixtures/seed populates explicit test fixture with visual watermark
- GET  /api/analytics/post/{receipt_id} returns VERIFIED_METRICS_PRESENT or NO_VERIFIED_METRICS
- GET  /api/analytics/feedback/{receipt_id} returns non-destructive creative feedback
- GET  /api/analytics/events returns downstream messaging notifications
"""
import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from backend.api.analytics import router


@pytest.fixture
def app():
    fastapi_app = FastAPI()
    fastapi_app.include_router(router, prefix="/api")
    return fastapi_app


@pytest.mark.asyncio
async def test_api_analytics_status_disconnected_default(app):
    """Verify status endpoint reports DISCONNECTED truthfully when no credentials exist."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/analytics/status")
        assert res.status_code == 200
        data = res.json()
        assert data["mode"] == "DISCONNECTED"
        assert data["providers"]["youtube"]["status"] == "NOT_CONNECTED"
        assert data["providers"]["tiktok"]["status"] == "NOT_CONNECTED"


@pytest.mark.asyncio
async def test_api_receipt_registration_and_empty_metrics(app):
    """Verify newly registered receipt without observations returns NO_VERIFIED_METRICS."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register receipt
        post_res = await client.post(
            "/api/analytics/receipts",
            json={
                "project_id": "proj-empty-test",
                "provider": "youtube",
                "account_reference": "chan_empty",
                "remote_post_id": "vid_empty_123",
            },
        )
        assert post_res.status_code == 200
        receipt_data = post_res.json()["receipt"]
        receipt_id = receipt_data["receipt_id"]

        # Check post metrics
        metrics_res = await client.get(f"/api/analytics/post/{receipt_id}")
        assert metrics_res.status_code == 200
        m_data = metrics_res.json()
        assert m_data["status"] == "NO_VERIFIED_METRICS"
        assert m_data["aggregate"] is None


@pytest.mark.asyncio
async def test_api_fixture_seed_and_feedback(app):
    """Verify explicitly seeded test fixture produces observable metrics and creative feedback."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Seed test fixture
        seed_res = await client.post(
            "/api/analytics/fixtures/seed",
            json={
                "project_id": "proj-fixture-1",
                "provider": "youtube",
                "views": 2500,
                "likes": 180,
                "comments": 25,
                "shares": 15,
                "completion_rate": 0.28,
            },
        )
        assert seed_res.status_code == 200
        seed_data = seed_res.json()
        assert seed_data["status"] == "FIXTURE_SEEDED"
        receipt_id = seed_data["receipt"]["receipt_id"]
        assert seed_data["receipt"]["metadata"]["watermark"] == "TEST_DATA"

        # Query post metrics
        post_res = await client.get(f"/api/analytics/post/{receipt_id}")
        assert post_res.status_code == 200
        p_data = post_res.json()
        assert p_data["status"] == "VERIFIED_METRICS_PRESENT"
        assert p_data["aggregate"]["latest_views"] == 2500
        assert p_data["aggregate"]["is_test_fixture"] is True

        # Query creative feedback
        fbk_res = await client.get(f"/api/analytics/feedback/{receipt_id}")
        assert fbk_res.status_code == 200
        fbk_data = fbk_res.json()["feedback"]
        assert len(fbk_data["hypotheses"]) > 0
        assert any(h["dimension"] == "hook_pacing" for h in fbk_data["hypotheses"])

        # Query analytics events
        evt_res = await client.get("/api/analytics/events")
        assert evt_res.status_code == 200
        e_data = evt_res.json()
        assert e_data["total"] >= 1
