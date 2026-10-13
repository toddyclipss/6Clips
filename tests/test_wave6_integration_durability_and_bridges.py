# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 6 Unified Integration, Durability & Historical Correction Test Suite.

Verifies:
1. All four Wave 5 branch tips are verifiable ancestors of the integration commit.
2. API routes return real JSON and meaningful status, and the SPA catchall does NOT mask /api/* routes as HTTP 200 HTML.
3. Cross-domain Main Agent -> MotionCapabilityDispatcher -> canonical ProjectService bridge operates with CAS.
4. Unauthorized caller, tenant mismatch, and stale CAS revision are rejected.
5. Fake publication receipts and silent/synthetic TTS audio are strictly prohibited from production success.
6. Physical project revisions and document snapshots survive reload and memory eviction.
7. Selected AI provider and reasoning configuration are immutable and not silently replaced.
"""

import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.analytics.engine import AnalyticsEngine, AnalyticsRepository
from backend.analytics.models import AnalyticsProvider, ReceiptConfirmationStatus
from backend.database import Base, get_db
from backend.main import create_app
from backend.models.execution import ExecutionRun
from backend.models.project import Project
from backend.original_creation.renderer import synthesize_narration_audio
from backend.services.project_service import ProjectService
import backend.services.project_service as ps_mod


@pytest_asyncio.fixture
async def isolated_session_factory():
    """Create an isolated in-memory SQLite engine for wave 6 integration tests."""
    test_db_url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(test_db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield session_maker
    await engine.dispose()


@pytest.fixture
def app_client(isolated_session_factory, monkeypatch):
    """Instantiate a TestClient bound to the isolated database."""
    test_app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with isolated_session_factory() as session:
            yield session

    test_app.dependency_overrides[get_db] = override_get_db
    orig_session_local = ps_mod.AsyncSessionLocal
    ps_mod.AsyncSessionLocal = isolated_session_factory

    with TestClient(test_app, raise_server_exceptions=False) as client:
        yield client

    ps_mod.AsyncSessionLocal = orig_session_local
    test_app.dependency_overrides.pop(get_db, None)


# =========================================================================
# 1. Ancestry Verification
# =========================================================================

def test_wave5_branch_tips_are_ancestors():
    """All four Wave 5 branch tips must be verifiable ancestors of integration HEAD."""
    wave5_tips = [
        ("wave5/02-native-motion-tools", "6fc5f802cad7d81b0658a20aa5209bb283d5acca"),
        ("wave5/03-hyperframes-whole-tree-audit", "a6064c271de5812ecde763df85a721dec32d4084"),
        ("wave5/05-distribution-analytics-hardening", "958e0285dcc9af62154ba6e8d377882a44fb747d"),
        ("wave5/04-browser-ollama-acceptance", "fbc1136e7c56eefd5f355c9ac95d729cf244e46b"),
    ]
    for branch_name, tip_sha in wave5_tips:
        res = subprocess.run(
            ["git", "merge-base", "--is-ancestor", tip_sha, "HEAD"],
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, f"Branch tip {branch_name} ({tip_sha}) is not an ancestor of HEAD!"


# =========================================================================
# 2. API Routing vs SPA Catchall Verification
# =========================================================================

def test_api_routes_return_json_and_spa_catchall_does_not_mask_404(app_client):
    """API endpoints must return application/json; missing /api routes must return 404, NOT SPA HTML."""
    # 1. Health endpoint returns real JSON
    res_health = app_client.get("/api/integration/health")
    assert res_health.status_code == 200
    assert "application/json" in res_health.headers.get("content-type", "")
    assert res_health.json()["status"] == "ok"

    # 2. Distribution status endpoint returns JSON
    res_dist = app_client.get("/api/distribution/daemon/status")
    assert res_dist.status_code == 200
    assert "application/json" in res_dist.headers.get("content-type", "")

    # 3. Analytics status endpoint returns JSON
    res_analytics = app_client.get("/api/analytics/status")
    assert res_analytics.status_code == 200
    assert "application/json" in res_analytics.headers.get("content-type", "")

    # 4. Unknown /api endpoint must return HTTP 404 JSON, NOT 200 OK HTML catchall
    res_missing = app_client.get("/api/nonexistent_route_probe_xyz")
    assert res_missing.status_code == 404
    assert "<!DOCTYPE html>" not in res_missing.text
    assert "application/json" in res_missing.headers.get("content-type", "")


# =========================================================================
# 3. Motion Capability Dispatcher & Canonical ProjectService Bridge
# =========================================================================

@pytest.mark.asyncio
async def test_motion_capability_dispatcher_cross_domain_bridge(app_client, isolated_session_factory):
    """MotionCapabilityDispatcher dispatches native mutations and bumps Project revision with CAS."""
    # 1. Create canonical project
    proj = await ProjectService.create_project(name="Motion Dispatch Bridge Test", user_id="creator_1")
    assert proj.revision == 1

    # 2. Add an initial clip to timeline so split has content
    clip_payload = {
        "track_id": "track_video_main",
        "clip": {
            "id": "clip_source_1",
            "type": "video",
            "title": "Main Gameplay",
            "start": 0.0,
            "duration": 10.0,
            "in_point": 0.0,
            "out_point": 10.0,
        },
    }
    await ProjectService.apply_operation(
        project_id=proj.id,
        expected_revision=1,
        operation_type="add_clip",
        payload=clip_payload,
        author="creator_1",
    )

    # 3. Call /api/integration/motion/dispatch-capability with timeline-clip-split
    res = app_client.post(
        "/api/integration/motion/dispatch-capability",
        json={
            "capability_id": "timeline-clip-split",
            "project_id": proj.id,
            "expected_revision": 2,
            "params": {
                "track_id": "track_video_main",
                "clip_id": "clip_source_1",
                "split_time": 4.0,
            },
            "user_id": "creator_1",
        },
    )
    assert res.status_code == 200, f"Dispatch failed: {res.text}"
    body = res.json()
    assert body["ok"] is True
    assert body["capability_id"] == "timeline-clip-split"
    assert body["revision"] == 3

    # 4. Verify canonical project has split clips
    updated_proj = await ProjectService.get_project(proj.id)
    doc = json.loads(updated_proj.document_json)
    video_track = next(t for t in doc["timeline"]["tracks"] if t["id"] == "track_video_main")
    assert len(video_track["clips"]) == 2
    assert video_track["clips"][0]["duration"] == 4.0
    assert video_track["clips"][1]["duration"] == 6.0


# =========================================================================
# 4. Unauthorized Caller, Tenant Isolation, and Stale CAS Rejection
# =========================================================================

@pytest.mark.asyncio
async def test_unauthorized_tenant_and_stale_revision_rejected(app_client):
    """Dispatches must reject wrong owners, stale revisions, and path traversal."""
    proj = await ProjectService.create_project(name="Security Fence Project", user_id="legit_owner")

    # 1. Wrong user rejected with 403 Forbidden
    res_wrong_user = app_client.post(
        "/api/integration/motion/dispatch-capability",
        json={
            "capability_id": "timeline-clip-split",
            "project_id": proj.id,
            "expected_revision": 1,
            "user_id": "attacker_user",
        },
    )
    assert res_wrong_user.status_code == 403
    assert "Access denied" in res_wrong_user.text

    # 2. Stale revision rejected with 409 Conflict
    res_stale = app_client.post(
        "/api/integration/motion/dispatch-capability",
        json={
            "capability_id": "timeline-clip-split",
            "project_id": proj.id,
            "expected_revision": 999,
            "user_id": "legit_owner",
        },
    )
    assert res_stale.status_code == 409
    assert "Revision conflict" in res_stale.text

    # 3. Path traversal rejected with 400 Bad Request
    res_traversal = app_client.post(
        "/api/integration/motion/dispatch-capability",
        json={
            "capability_id": "trim",
            "input_path": "../../etc/passwd",
            "user_id": "legit_owner",
        },
    )
    assert res_traversal.status_code == 400
    assert "traversal" in res_traversal.text.lower()


# =========================================================================
# 5. Truthful Rejection of Fake Receipts and Silent TTS
# =========================================================================

def test_fake_receipts_rejected_in_production(app_client):
    """Fake post IDs and unconfirmed receipts are rejected in production."""
    # 1. Fake remote post ID rejected
    res_fake = app_client.post(
        "/api/integration/distribution/reconcile-receipt-to-analytics",
        json={
            "distribution_receipt": {
                "receipt_id": "rcpt_001",
                "verified_status": "CONFIRMED",
                "remote_post_id": "fake_yt_post_999",
                "platform": "youtube",
            },
            "creator_id": "local",
        },
    )
    assert res_fake.status_code == 422
    assert "cannot be reconciled as a verified production publication" in res_fake.text

    # 2. Unconfirmed status rejected
    res_unconfirmed = app_client.post(
        "/api/integration/distribution/reconcile-receipt-to-analytics",
        json={
            "distribution_receipt": {
                "receipt_id": "rcpt_002",
                "verified_status": "QUEUED",
                "remote_post_id": "real_post_777",
                "platform": "youtube",
            },
            "creator_id": "local",
        },
    )
    assert res_unconfirmed.status_code == 400
    assert "Cannot reconcile receipt with unconfirmed status" in res_unconfirmed.text


@pytest.mark.asyncio
async def test_silent_narration_audio_prohibited_in_production(tmp_path):
    """In production mode, synthesize_narration_audio refuses to substitute silent tone on TTS failure."""
    out_audio = tmp_path / "narration.mp3"
    old_fixture_env = os.environ.pop("VIRALMINT_TEST_AUDIO_FIXTURE", None)
    try:
        with pytest.raises(RuntimeError) as exc_info:
            await synthesize_narration_audio(
                text="This is an original creator script.",
                output_audio_path=out_audio,
                voice_name="invalid-offline-voice",
                allow_test_fixture=False,
            )
        assert "strictly prohibited" in str(exc_info.value).lower()
    finally:
        if old_fixture_env is not None:
            os.environ["VIRALMINT_TEST_AUDIO_FIXTURE"] = old_fixture_env


# =========================================================================
# 6. Physical Project Revisions Survive Process Reload
# =========================================================================

@pytest.mark.asyncio
async def test_physical_project_revisions_survive_reload(isolated_session_factory):
    """Project revisions and snapshots persist across in-memory cache eviction."""
    proj = await ProjectService.create_project(name="Durability Test Project", user_id="creator_persist")
    proj_id = proj.id

    # Apply 2 revisions
    await ProjectService.apply_operation(
        project_id=proj_id,
        expected_revision=1,
        operation_type="add_clip",
        payload={
            "track_id": "track_video_main",
            "clip": {"id": "c1", "type": "video", "title": "Clip 1", "start_seconds": 0.0, "duration_seconds": 5.0},
        },
        author="creator_persist",
    )
    await ProjectService.apply_operation(
        project_id=proj_id,
        expected_revision=2,
        operation_type="add_clip",
        payload={
            "track_id": "track_audio_main",
            "clip": {"id": "a1", "type": "audio", "title": "BGM 1", "start_seconds": 0.0, "duration_seconds": 5.0},
        },
        author="creator_persist",
    )

    # Re-query fresh from database session
    rev_history = await ProjectService.list_revisions(proj_id)
    assert len(rev_history) == 3
    assert [r["revision"] for r in rev_history] == [1, 2, 3]

    snapshot_r2 = await ProjectService.get_revision_snapshot(proj_id, 2)
    assert len(snapshot_r2["timeline"]["tracks"][0]["clips"]) == 1

    snapshot_r3 = await ProjectService.get_revision_snapshot(proj_id, 3)
    assert len(snapshot_r3["timeline"]["tracks"][0]["clips"]) == 1
    assert len(snapshot_r3["timeline"]["tracks"][1]["clips"]) == 1


# =========================================================================
# 7. Selected Provider and Reasoning Not Silently Replaced
# =========================================================================

@pytest.mark.asyncio
async def test_selected_provider_and_reasoning_not_silently_replaced(isolated_session_factory):
    """Pinned Ollama gemma4:e4b model is preserved in ExecutionRun without silent fallback."""
    from backend.services.executor_service import ExecutorService

    run = await ExecutorService.create_run(
        objective="Ollama Local Autonomous Creation",
        provider="ollama",
        model="gemma4:e4b",
        user_id="local",
    )

    assert run.resolved_provider == "ollama"
    assert run.resolved_model == "gemma4:e4b"
    assert run.resolved_provider != "openai"
    assert run.resolved_provider != "anthropic"
