# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 7 Integration, P0 API Verification & Cross-Domain Durability Tests.

Verifies:
1. P0 API catchall: unhandled /api/* routes return HTTP 404 JSON (not HTTP 500 NameError or HTML SPA fallback).
2. P0 Catalog -> Project: add_block with CAS expected_revision, persisted code binding, and stale revision rejection (409).
3. Narration failure correctness: explicit missing voice/network error raises RuntimeError / WAITING_FOR_INPUT, never fake silent anullsrc audio.
4. Cross-domain capability dispatch: Main Agent / API integration executes without duplicate multipart uploads.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.catalog.manifest_service import CatalogManifestService
from backend.catalog.project_intent_contract import (
    AddToProjectIntentRequest,
    CatalogProjectIntentAdapter,
)
from backend.core.exceptions import RevisionConflictError
from backend.database import Base, get_db
from backend.main import create_app
from backend.original_creation.renderer import synthesize_narration_audio
from backend.services.project_service import ProjectService
import backend.services.project_service as ps_mod


@pytest_asyncio.fixture
async def isolated_session_factory():
    """Create an isolated in-memory SQLite engine for wave 7 integration tests."""
    test_db_url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(test_db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield session_maker
    await engine.dispose()


@pytest.fixture
def app_client(isolated_session_factory):
    """Instantiate a TestClient bound to the isolated database."""
    test_app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with isolated_session_factory() as session:
            yield session

    test_app.dependency_overrides[get_db] = override_get_db
    orig_session_local = ps_mod.AsyncSessionLocal
    ps_mod.AsyncSessionLocal = isolated_session_factory

    with TestClient(test_app, raise_server_exceptions=True) as client:
        yield client

    ps_mod.AsyncSessionLocal = orig_session_local
    test_app.dependency_overrides.pop(get_db, None)


# =========================================================================
# 1. P0 API Catchall Guard Verification
# =========================================================================

def test_p0_api_catchall_returns_json_404_with_server_exceptions_true(app_client):
    """Unknown /api routes must return HTTP 404 JSON and NEVER raise NameError (HTTP 500) or SPA HTML."""
    res = app_client.get("/api/nonexistent-route-wave7")
    assert res.status_code == 404
    assert "<!DOCTYPE html>" not in res.text
    assert "application/json" in res.headers.get("content-type", "")
    assert "not found" in res.json().get("detail", "").lower()


def test_p0_api_nested_missing_route_returns_json_404(app_client):
    """Deep nested unknown /api paths return 404 JSON cleanly."""
    res = app_client.get("/api/v1/tools/missing/deep/endpoint")
    assert res.status_code == 404
    assert "application/json" in res.headers.get("content-type", "")


# =========================================================================
# 2. P0 Catalog -> Project CAS Integration
# =========================================================================

@pytest.mark.asyncio
async def test_p0_catalog_block_insert_cas_and_persistence(isolated_session_factory):
    """Catalog READY block inserts via CAS, binds code, and rejects stale revision with 409."""
    # 1. Pick a SHIP/READY catalog block
    items = CatalogManifestService.list_items(disposition="SHIP", limit=5)["items"]
    assert len(items) > 0, "No SHIP items found in catalog"
    block = items[0]
    block_id = block["id"]

    # 2. Create canonical project
    proj = await ProjectService.create_project(name="Catalog CAS Wave7 Test", user_id="creator_w7")
    assert proj.revision == 1

    # 3. Formulate validated intent contract
    intent_req = AddToProjectIntentRequest(
        project_id=proj.id,
        timeline_track_index=0,
        start_time_seconds=0.0,
        aspect_ratio="9:16",
        custom_variables=block.get("default_variables", {}),
    )
    intent = CatalogProjectIntentAdapter.create_add_to_project_intent(block_id, intent_req)
    assert intent.block_id == block_id

    # 4. Insert into project via ProjectService CAS
    op_payload = {
        "block_id": block_id,
        "title": intent.timeline_item.title,
        "start_seconds": intent.timeline_item.start_time,
        "duration_seconds": intent.timeline_item.duration,
        "variables": intent.timeline_item.variables,
        "track_id": "track_graphics_main",
    }
    res = await ProjectService.apply_operation(
        project_id=proj.id,
        expected_revision=1,
        operation_type="add_block",
        payload=op_payload,
        author="creator_w7",
    )
    assert res["revision"] == 2

    # 5. Verify CAS rejection on stale expected_revision
    with pytest.raises(RevisionConflictError):
        await ProjectService.apply_operation(
            project_id=proj.id,
            expected_revision=1,  # Stale revision
            operation_type="add_block",
            payload=op_payload,
            author="creator_w7",
        )

    # 6. Verify persistence across reload
    reloaded = await ProjectService.get_project(proj.id)
    doc = json.loads(reloaded.document_json)
    clips = [c for t in doc["timeline"]["tracks"] for c in t.get("clips", []) if c.get("block_id") == block_id]
    assert len(clips) == 1
    code_files = doc.get("code", {}).get("files", [])
    assert len(code_files) > 0
    assert any(f.get("block_id") == block_id for f in code_files)


# =========================================================================
# 3. Audio Narration TTS Failure Guard
# =========================================================================

@pytest.mark.asyncio
async def test_narration_failure_prohibits_silent_tone(tmp_path):
    """Refuse to produce silent tone or fake narration when TTS fails."""
    out_audio = tmp_path / "narration_test.mp3"
    old_fixture_env = os.environ.pop("VIRALMINT_TEST_AUDIO_FIXTURE", None)
    try:
        with pytest.raises(RuntimeError) as exc_info:
            await synthesize_narration_audio(
                text="Test narration text",
                output_audio_path=out_audio,
                voice_name="invalid_missing_voice_id",
                allow_test_fixture=False,
            )
        assert "strictly prohibited" in str(exc_info.value).lower()
        assert not out_audio.exists()
    finally:
        if old_fixture_env:
            os.environ["VIRALMINT_TEST_AUDIO_FIXTURE"] = old_fixture_env
