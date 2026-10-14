# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 9 Integration Coordinator Durability Tests.

Verifies:
1. Root health endpoint returns 200 OK.
2. Direct REST capability execution `POST /api/projects/{project_id}/capabilities/{capability_id}`:
   - Enforces 403 on unowned project.
   - Enforces 409 on revision conflict.
   - Enforces 404 on non-existent capability or project.
   - Executes valid capability with ProjectService CAS optimistic concurrency and revision bump.
3. Creative recipe application and reversible undo:
   - `POST /api/projects/{project_id}/recipes/{recipe_id}/apply` mutates timeline with revision bump.
   - `POST /api/projects/{project_id}/recipes/{recipe_id}/undo` reversibly cleans up recipe clips.
4. Production acceptance API routes:
   - `GET /api/acceptance/status` and `GET /api/acceptance/protocol`.
   - Truthful rejection of non-existent media with 404.
5. SPA catch-all retains JSON 404 for `/api/*` routes.
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


@pytest_asyncio.fixture
async def isolated_db():
    """Create an isolated in-memory SQLite engine for wave 9 integration tests."""
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
async def test_root_health_endpoint(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "ok"
        assert data.get("app") == "viralmint"


@pytest.mark.asyncio
async def test_acceptance_routes_status_and_protocol(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_status = await client.get("/api/acceptance/status")
        assert res_status.status_code == 200
        data_status = res_status.json()
        assert "GT-05" in data_status
        assert "GT-06" in data_status
        assert "GT-07" in data_status
        assert data_status["GT-05"]["status"] == "NOT_TESTED"

        res_proto = await client.get("/api/acceptance/protocol")
        assert res_proto.status_code == 200
        data_proto = res_proto.json()
        assert "gates" in data_proto


@pytest.mark.asyncio
async def test_acceptance_routes_missing_media_404(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/acceptance/gt05",
            json={"source_file_path": "non_existent_gameplay.mp4"},
        )
        assert res.status_code == 404

        res_gt06 = await client.post(
            "/api/acceptance/gt06",
            json={"source_file_path": "non_existent_longform.mp4"},
        )
        assert res_gt06.status_code == 404

        res_gt07 = await client.post(
            "/api/acceptance/gt07",
            json={"source_file_paths": ["non_existent_source.mp4"]},
        )
        assert res_gt07.status_code == 404


@pytest.mark.asyncio
async def test_project_capability_cas_and_execution(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create a fresh project
        proj = await ProjectService.create_project(
            name="Test Capability Project",
            user_id="test_owner",
        )
        proj_id = proj.id
        initial_rev = proj.revision

        # Add a test clip to the project
        await ProjectService.apply_operation(
            project_id=proj_id,
            expected_revision=initial_rev,
            operation_type="add_clip",
            payload={"clip": {"id": "clip_main", "type": "video", "start_seconds": 0.0, "duration_seconds": 10.0}},
            author="test_owner",
        )
        cur_rev = initial_rev + 1

        # 1. 403 Forbidden for unauthorized user
        res_403 = await client.post(
            f"/api/projects/{proj_id}/capabilities/audio-framing-parity",
            json={
                "expected_revision": cur_rev,
                "user_id": "intruder_user",
                "params": {"clip_id": "clip_main", "framing_preset": "center_crop"},
            },
        )
        assert res_403.status_code == 403

        # 2. 409 Conflict on revision mismatch
        res_409 = await client.post(
            f"/api/projects/{proj_id}/capabilities/audio-framing-parity",
            json={
                "expected_revision": cur_rev + 99,
                "user_id": "test_owner",
                "params": {"clip_id": "clip_main", "framing_preset": "center_crop"},
            },
        )
        assert res_409.status_code == 409

        # 3. 404 Not Found on unknown capability
        res_404 = await client.post(
            f"/api/projects/{proj_id}/capabilities/non_existent_cap",
            json={
                "expected_revision": cur_rev,
                "user_id": "test_owner",
            },
        )
        assert res_404.status_code == 404

        # 4. Successful capability execution with mutation and CAS revision bump
        res_ok = await client.post(
            f"/api/projects/{proj_id}/capabilities/audio-framing-parity",
            json={
                "expected_revision": cur_rev,
                "user_id": "test_owner",
                "params": {"clip_id": "clip_main", "framing_preset": "center_crop"},
            },
        )
        assert res_ok.status_code == 200
        ok_data = res_ok.json()
        assert ok_data.get("ok") is True
        assert ok_data.get("revision") == cur_rev + 1


@pytest.mark.asyncio
async def test_project_recipe_apply_and_undo_cas(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create project
        proj = await ProjectService.create_project(
            name="Test Recipe Project",
            user_id="recipe_user",
        )
        proj_id = proj.id
        rev0 = proj.revision

        # 1. Apply recipe
        res_apply = await client.post(
            f"/api/projects/{proj_id}/recipes/recipe_kinetic_hook_5s/apply",
            json={
                "expected_revision": rev0,
                "start_time": 0.0,
                "user_id": "recipe_user",
            },
        )
        assert res_apply.status_code == 200
        apply_data = res_apply.json()
        rev1 = apply_data.get("revision")
        assert rev1 == rev0 + 1
        doc1 = apply_data.get("document", {})
        tracks1 = doc1.get("timeline", {}).get("tracks", [])
        assert any(len(t.get("clips", [])) > 0 for t in tracks1)

        # 2. Undo recipe
        res_undo = await client.post(
            f"/api/projects/{proj_id}/recipes/recipe_kinetic_hook_5s/undo",
            json={
                "expected_revision": rev1,
                "user_id": "recipe_user",
            },
        )
        assert res_undo.status_code == 200
        undo_data = res_undo.json()
        rev2 = undo_data.get("revision")
        assert rev2 == rev1 + 1
        doc2 = undo_data.get("document", {})
        meta2 = doc2.get("metadata", {})
        assert len(meta2.get("applied_recipes", [])) == 0


@pytest.mark.asyncio
async def test_spa_api_404_protection_returns_json(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/unknown-route-that-does-not-exist")
        assert res.status_code == 404
        assert res.headers.get("content-type", "").startswith("application/json")
        assert "detail" in res.json()
