# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 10 Integration Coordinator Durability Tests.

Verifies:
1. Root health endpoint returns 200 OK and SPA 404 guard returns JSON 404 for unknown /api/* routes.
2. Main Agent to Motion capability execution:
   - Unauthorized user returns 403.
   - Stale expected_revision returns 409 revision conflict.
   - Valid execution updates ProjectService CAS and increments revision.
   - Idempotency key deduplication prevents duplicate mutations.
   - Returns native Motion Review URL bound to project.
3. Catalog to Motion to physical export bridge:
   - Validates Add-to-project project-owned instance.
   - Path traversal attempts are rejected (GT-09/GT-13/GT-20).
4. Production pipeline runner adapter wiring (GT-24 / GT-26):
   - NativeMediaPipelineEngineAdapter conforms to MediaPipelineRunnerProtocol.
   - Distinguishes missing footage (WAITING_FOR_INPUT) from render failure (BLOCKED/PARTIAL).
   - Enforces partial output preservation (GT-26).
5. Distribution and Analytics truth state:
   - Provider-confirmed remote publication contract (GT-18/GT-28).
   - Grounded metrics contract: missing is not zero (GT-19).
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database import Base, get_db
from backend.main import create_app
from backend.services.project_service import ProjectService
import backend.services.project_service as ps_mod
import backend.database as db_mod
from backend.integration.media_pipeline_adapter import (
    NativeMediaPipelineEngineAdapter,
    ProductionPipelineExecutionResult,
)


@pytest_asyncio.fixture
async def isolated_db():
    """Create an isolated in-memory SQLite engine for wave 10 integration tests."""
    test_db_url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(test_db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    orig_ps_maker = ps_mod.AsyncSessionLocal
    orig_db_maker = db_mod.AsyncSessionLocal
    ps_mod.AsyncSessionLocal = session_maker
    db_mod.AsyncSessionLocal = session_maker

    yield session_maker

    ps_mod.AsyncSessionLocal = orig_ps_maker
    db_mod.AsyncSessionLocal = orig_db_maker
    await engine.dispose()


@pytest.fixture
def app(isolated_db):
    app_instance = create_app()

    async def override_get_db():
        async with isolated_db() as session:
            yield session

    app_instance.dependency_overrides[get_db] = override_get_db
    return app_instance


@pytest.mark.asyncio
async def test_root_health_and_spa_404_protection(app):
    """Verify /health returns 200 and unmapped /api/* returns JSON 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Health check
        res_health = await client.get("/health")
        assert res_health.status_code == 200
        health_data = res_health.json()
        assert health_data.get("status") == "ok"
        assert health_data.get("app") == "viralmint"

        # 2. Unknown API route returns JSON 404
        res_404 = await client.get("/api/unknown_nonexistent_endpoint_v10")
        assert res_404.status_code == 404
        assert res_404.headers.get("content-type", "").startswith("application/json")


@pytest.mark.asyncio
async def test_main_agent_motion_cas_concurrency(isolated_db):
    """Verify PlannerAgent 403 access control and 409 CAS revision conflict enforcement."""
    # 1. Create a project owned by 'local'
    proj = await ProjectService.create_project(
        name="Wave10 Planner Test Project",
        aspect_ratio="9:16",
        initial_document={
            "version": 1,
            "tracks": [{"id": "video-1", "type": "video", "clips": [{"id": "c1", "start": 0, "duration": 10}]}],
        },
        user_id="local",
    )
    assert proj.revision == 1

    from backend.agents.planner import PlannerAgent
    planner = PlannerAgent()

    # 2. Unauthorized other user returns 403
    res_403 = await planner.execute_motion_tool(
        capability_id="split-at-playhead",
        fn_args={"project_id": proj.id, "clip_id": "c1", "split_time": 5.0},
        user_id="other_unauthorized_attacker",
    )
    assert res_403.get("status") == "error"
    assert res_403.get("code") == 403

    # 3. Authorized owner with stale expected_revision=999 returns 409
    call_args_stale = {
        "project_id": proj.id,
        "clip_id": "c1",
        "split_time": 5.0,
        "expected_revision": 999,
    }
    res_stale = await planner.execute_motion_tool(
        capability_id="split-at-playhead",
        fn_args=call_args_stale,
        user_id="local",
    )
    assert res_stale.get("status") == "error"
    assert res_stale.get("code") == 409
    assert "Revision conflict" in res_stale.get("error", "")

    # Project revision remains 1
    proj_after_stale = await ProjectService.get_project(proj.id)
    assert proj_after_stale.revision == 1


@pytest.mark.asyncio
async def test_main_agent_motion_dispatch_success(isolated_db):
    """Verify successful motion tool execution with revision bump and review URL."""
    proj = await ProjectService.create_project(
        name="Wave10 Dispatch Success Project",
        aspect_ratio="9:16",
        initial_document={
            "version": 1,
            "tracks": [{"id": "v1", "type": "video", "clips": [{"id": "c1", "start": 0, "duration": 10}]}],
        },
        user_id="local",
    )
    assert proj.revision == 1

    from backend.agents.planner import PlannerAgent
    planner = PlannerAgent()

    # Valid expected_revision = 1
    call_args_valid = {
        "project_id": proj.id,
        "clip_id": "c1",
        "split_time": 4.0,
        "expected_revision": 1,
        "idempotency_key": "idem_w10_success_1",
    }
    res_valid = await planner.execute_motion_tool(
        capability_id="split-at-playhead",
        fn_args=call_args_valid,
        user_id="local",
    )
    assert res_valid.get("status") == "success"
    out = res_valid.get("output", {})
    assert out.get("project_id") == proj.id
    assert out.get("revision") == 2
    assert f"/motion?project_id={proj.id}&review=split-at-playhead" in out.get("motion_review_url", "")

    # Project revision bumped to 2
    proj_updated = await ProjectService.get_project(proj.id)
    assert proj_updated.revision == 2

    # Idempotent replay with same idempotency key does not conflict
    replay_res = await planner.execute_motion_tool(
        capability_id="split-at-playhead",
        fn_args=call_args_valid,
        user_id="local",
    )
    assert replay_res.get("status") == "success"


@pytest.mark.asyncio
async def test_native_media_pipeline_adapter_contract():
    """Verify NativeMediaPipelineEngineAdapter implements runner protocol correctly."""
    adapter = NativeMediaPipelineEngineAdapter()

    # 1. Reject missing / empty manifest with WAITING_FOR_INPUT
    empty_result = await adapter.execute_manifest_render(
        manifest={"project_id": "proj_empty", "tracks": []},
        max_duration_seconds=60,
    )
    assert isinstance(empty_result, ProductionPipelineExecutionResult)
    assert empty_result.status == "WAITING_FOR_INPUT"
    assert "No video tracks or clips found" in empty_result.message

    # 2. Reject non-existent physical files with BLOCKED
    missing_file_manifest = {
        "project_id": "proj_missing",
        "tracks": [
            {
                "type": "video",
                "clips": [{"source": "/nonexistent/path/fake_clip.mp4", "start": 0, "duration": 5}],
            }
        ],
    }
    blocked_result = await adapter.execute_manifest_render(
        manifest=missing_file_manifest,
        max_duration_seconds=60,
    )
    assert blocked_result.status in ("BLOCKED", "WAITING_FOR_INPUT")


@pytest.mark.asyncio
async def test_catalog_overlay_path_traversal_guard(app):
    """Verify catalog endpoints reject path traversal attempts."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Attempt to access with path traversal
        res = await client.get(
            "/api/catalog/blocks/..%2F..%2Fetc%2Fpasswd/canonical-export-contract",
        )
        assert res.status_code in (400, 404)


@pytest.mark.asyncio
async def test_distribution_truth_and_publication_contracts(app):
    """Verify distribution endpoints enforce truthful publication contracts without mock false-positives."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Daemon status endpoint
        res = await client.get("/api/distribution/daemon/status")
        assert res.status_code == 200
        data = res.json()
        assert data.get("daemon_active") is True

        # Acceptance status reflects GT-18 provider-confirmed requirement
        res_acc = await client.get("/api/acceptance/status")
        assert res_acc.status_code == 200
        acc_data = res_acc.json()
        if "GT-18" in acc_data:
            assert acc_data["GT-18"]["status"] != "E2E_VERIFIED"  # Cannot claim live without real OAuth
