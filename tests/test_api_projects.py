# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
import pytest
from starlette.testclient import TestClient

from backend.main import create_app
from backend.database import init_db


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


@pytest.mark.asyncio
async def test_api_projects_crud_and_operations(client):
    await init_db()

    # 1. Create project
    create_resp = client.post("/api/projects", json={"name": "Viral Ad Project", "aspect_ratio": "9:16"})
    assert create_resp.status_code == 200
    p = create_resp.json()
    project_id = p["id"]
    assert p["name"] == "Viral Ad Project"
    assert p["revision"] == 1
    assert "timeline" in p["document"]

    # 2. Get project
    get_resp = client.get(f"/api/projects/{project_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["revision"] == 1

    # 3. Apply operation with correct expected_revision (1 -> 2)
    op_payload = {
        "expected_revision": 1,
        "operation_type": "add_clip",
        "payload": {
            "track_id": "track_video_main",
            "clip": {"id": "c1", "start_seconds": 0.0, "duration_seconds": 15.0},
        },
        "idempotency_key": "add_c1",
    }
    op_resp = client.post(f"/api/projects/{project_id}/operations", json=op_payload)
    assert op_resp.status_code == 200
    op_data = op_resp.json()
    assert op_data["revision"] == 2
    assert op_data["applied"] is True

    # 4. Conflict detection: re-sending with expected_revision=1 returns 409
    bad_op_payload = {
        "expected_revision": 1,
        "operation_type": "set_aspect_ratio",
        "payload": {"aspect_ratio": "16:9"},
    }
    conflict_resp = client.post(f"/api/projects/{project_id}/operations", json=bad_op_payload)
    assert conflict_resp.status_code == 409
    conflict_data = conflict_resp.json()
    assert conflict_data["detail"]["error"] == "revision_conflict"
    assert conflict_data["detail"]["current_revision"] == 2

    # 5. List revisions
    rev_resp = client.get(f"/api/projects/{project_id}/revisions")
    assert rev_resp.status_code == 200
    revs = rev_resp.json()["revisions"]
    assert len(revs) == 2
    assert revs[0]["revision"] == 1
    assert revs[1]["revision"] == 2


@pytest.mark.asyncio
async def test_bench_ranges_persistence_and_preview(client):
    await init_db()

    create_resp = client.post("/api/projects", json={"name": "Bench Test Project", "aspect_ratio": "9:16"})
    assert create_resp.status_code == 200
    p = create_resp.json()
    project_id = p["id"]

    # 1. Commit bench ranges
    ranges_data = [
        {"start": 2.0, "end": 8.5, "meta": {"title": "Hook"}},
        {"start": 12.0, "end": 20.0, "meta": {"title": "Insight"}},
    ]
    set_ranges_resp = client.post(f"/api/projects/{project_id}/operations", json={
        "expected_revision": 1,
        "operation_type": "set_bench_ranges",
        "payload": {
            "source_id": "test_src_video_42",
            "ranges": ranges_data,
        },
        "author": "user",
    })
    assert set_ranges_resp.status_code == 200
    assert set_ranges_resp.json()["revision"] == 2

    # 2. Verify persistence on full reload
    reloaded = client.get(f"/api/projects/{project_id}")
    assert reloaded.status_code == 200
    doc = reloaded.json()["document"]
    assert "bench_ranges" in doc
    assert "test_src_video_42" in doc["bench_ranges"]
    assert len(doc["bench_ranges"]["test_src_video_42"]) == 2

    # 3. Test read-only composition preview route
    preview_resp = client.get(f"/api/projects/{project_id}/preview")
    assert preview_resp.status_code == 200
    assert "text/html" in preview_resp.headers["content-type"]
    html_text = preview_resp.text
    # Proves it is the clean composition player, NOT the HeyGen editor UI
    assert 'id="stage"' in html_text
    assert "vm-runtime" in html_text
    assert "vm-parent" in html_text


@pytest.mark.asyncio
async def test_ingest_trend_into_project(client):
    await init_db()
    from backend.database import AsyncSessionLocal
    from backend.models.trends_result import TrendsResult

    # 1. Seed a TrendResult in DB
    async with AsyncSessionLocal() as db:
        tr = TrendsResult(
            user_id="local",
            platform="youtube",
            video_id="trend_vid_123",
            video_url="https://youtube.com/watch?v=trend_vid_123",
            title="Massive Viral Trend 2026",
            duration_seconds=15.0,
            virality_score=94.5,
            is_downloaded=False,
        )
        db.add(tr)
        await db.commit()
        await db.refresh(tr)
        tr_id = tr.id

    # 2. Create project
    create_resp = client.post("/api/projects", json={"name": "Trend Ingest Project"})
    assert create_resp.status_code == 200
    project_id = create_resp.json()["id"]

    # 3. Ingest trend
    ingest_resp = client.post(f"/api/projects/{project_id}/ingest-trend", json={
        "trend_result_id": tr_id,
        "expected_revision": 1,
    })
    assert ingest_resp.status_code == 200
    data = ingest_resp.json()
    assert data["status"] == "success"
    assert data["verification"]["ok"] is True
    assert data["verification"]["new_revision"] == 2

    # 4. Verify project document now contains asset and lineage
    reloaded = client.get(f"/api/projects/{project_id}")
    assert reloaded.status_code == 200
    doc = reloaded.json()["document"]
    assert "assets" in doc
    assert any(a.get("source_trend_id") == tr_id for a in doc["assets"])

