# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Exhaustive test suite verifying the Canonical Idempotency Contract.

Mandatory verification targets:
1. Same key and same payload replay correctly.
2. Same key and different payload causes explicit conflict (HTTP 409).
3. Same key and different operation causes explicit conflict (HTTP 409).
4. Stale revision without legitimate replay remains HTTP 409.
5. Concurrent duplicates cannot create duplicate durable effects.
6. No failed request causes partial mutation.
7. Operates cleanly for Motion, document patching, and versioned filetree workflows.
"""
import asyncio
import pytest
from starlette.testclient import TestClient

from backend.main import create_app
from backend.database import init_db
from backend.services.project_service import ProjectService
from backend.core.exceptions import (
    RevisionConflictError,
    IdempotencyConflictError,
    ProjectError,
)


@pytest.fixture(autouse=True)
async def db_setup():
    await init_db()


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


@pytest.mark.asyncio
async def test_same_key_same_payload_replay_and_lineage(client):
    """1. Same key + same payload: legitimate replay, no duplicate side effects, identifies original result."""
    # Create project
    p = await ProjectService.create_project(name="Idem Replay Test", aspect_ratio="9:16")
    pid = p.id
    assert p.revision == 1

    payload = {
        "track_id": "track_video_main",
        "clip": {"id": "clip_alpha", "start_seconds": 0.0, "duration_seconds": 5.0},
    }

    # Request A: Apply operation with key K_1
    res1 = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=1,
        operation_type="add_clip",
        payload=payload,
        idempotency_key="key_alpha_1",
        author="user",
    )
    assert res1["applied"] is True
    assert res1["revision"] == 2
    assert res1.get("idempotent_replay") is not True

    # Replay 1 (Exact retry with expected_revision=1)
    res_replay1 = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=1,
        operation_type="add_clip",
        payload=payload,
        idempotency_key="key_alpha_1",
        author="user",
    )
    assert res_replay1["applied"] is False
    assert res_replay1["idempotent_replay"] is True
    assert res_replay1["revision"] == 2

    # Replay 2 (Client saw current revision=2 and re-sent key_alpha_1)
    res_replay2 = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=2,
        operation_type="add_clip",
        payload=payload,
        idempotency_key="key_alpha_1",
        author="user",
    )
    assert res_replay2["applied"] is False
    assert res_replay2["idempotent_replay"] is True
    assert res_replay2["revision"] == 2

    # Apply an unrelated subsequent mutation (rev 2 -> rev 3)
    res_unrelated = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=2,
        operation_type="set_aspect_ratio",
        payload={"aspect_ratio": "16:9"},
        author="user",
    )
    assert res_unrelated["applied"] is True
    assert res_unrelated["revision"] == 3

    # Replay original key_alpha_1 again: MUST report original revision 2 and original snapshot!
    res_replay_historic = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=1,
        operation_type="add_clip",
        payload=payload,
        idempotency_key="key_alpha_1",
    )
    assert res_replay_historic["applied"] is False
    assert res_replay_historic["idempotent_replay"] is True
    # Crucial: identifies original operation result (2), NOT latest project state (3)!
    assert res_replay_historic["revision"] == 2
    assert res_replay_historic["document"]["aspect_ratio"] == "9:16"

    # API test: Replay through HTTP endpoint returns 200 with idempotent_replay=True
    api_resp = client.post(f"/api/projects/{pid}/operations", json={
        "expected_revision": 1,
        "operation_type": "add_clip",
        "payload": payload,
        "idempotency_key": "key_alpha_1",
    })
    assert api_resp.status_code == 200
    api_data = api_resp.json()
    assert api_data["applied"] is False
    assert api_data["idempotent_replay"] is True
    assert api_data["revision"] == 2


@pytest.mark.asyncio
async def test_same_key_different_payload_causes_explicit_conflict(client):
    """2. Same key + different payload = explicit conflict (HTTP 409). No mutation, no revision bump."""
    p = await ProjectService.create_project(name="Payload Mismatch Test")
    pid = p.id

    payload_A = {
        "track_id": "track_video_main",
        "clip": {"id": "clip_A", "duration_seconds": 10.0},
    }
    payload_B_diff = {
        "track_id": "track_video_main",
        "clip": {"id": "clip_B_different", "duration_seconds": 99.0},
    }

    # Request A with key K
    res_a = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=1,
        operation_type="add_clip",
        payload=payload_A,
        idempotency_key="token_conflict_1",
    )
    assert res_a["applied"] is True
    assert res_a["revision"] == 2

    # Request B reuses key K with different payload -> raises IdempotencyConflictError
    with pytest.raises(IdempotencyConflictError) as exc_info:
        await ProjectService.apply_operation(
            project_id=pid,
            expected_revision=1,
            operation_type="add_clip",
            payload=payload_B_diff,
            idempotency_key="token_conflict_1",
        )
    assert exc_info.value.existing_revision == 2

    # Verify project revision remained strictly 2 and clip_B was NEVER added
    reloaded = await ProjectService.get_project(pid)
    assert reloaded.revision == 2
    clips = [c["id"] for t in (await ProjectService.get_revision_snapshot(pid, 2))["timeline"]["tracks"] for c in t["clips"]]
    assert "clip_A" in clips
    assert "clip_B_different" not in clips

    # API verification: HTTP 409 with structured error
    api_resp = client.post(f"/api/projects/{pid}/operations", json={
        "expected_revision": 1,
        "operation_type": "add_clip",
        "payload": payload_B_diff,
        "idempotency_key": "token_conflict_1",
    })
    assert api_resp.status_code == 409
    err_body = api_resp.json()
    assert err_body["detail"]["error"] == "idempotency_conflict"
    assert "different payload" in err_body["detail"]["message"]


@pytest.mark.asyncio
async def test_same_key_different_operation_causes_explicit_conflict(client):
    """3. Same key + different operation type = explicit conflict (HTTP 409)."""
    p = await ProjectService.create_project(name="Op Mismatch Test")
    pid = p.id

    # Request A: add_clip with key K
    await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=1,
        operation_type="add_clip",
        payload={"track_id": "track_video_main", "clip": {"id": "c1"}},
        idempotency_key="token_op_test",
    )

    # Request B: set_aspect_ratio with SAME key K
    with pytest.raises(IdempotencyConflictError) as exc_info:
        await ProjectService.apply_operation(
            project_id=pid,
            expected_revision=1,
            operation_type="set_aspect_ratio",
            payload={"aspect_ratio": "16:9"},
            idempotency_key="token_op_test",
        )
    assert exc_info.value.existing_revision == 2

    # API verification
    api_resp = client.post(f"/api/projects/{pid}/operations", json={
        "expected_revision": 1,
        "operation_type": "set_aspect_ratio",
        "payload": {"aspect_ratio": "16:9"},
        "idempotency_key": "token_op_test",
    })
    assert api_resp.status_code == 409
    assert api_resp.json()["detail"]["error"] == "idempotency_conflict"


@pytest.mark.asyncio
async def test_stale_revision_without_legitimate_replay_remains_409(client):
    """4. Stale revision without legitimate replay remains HTTP 409 (revision_conflict)."""
    p = await ProjectService.create_project(name="Stale Rev Test")
    pid = p.id

    # Advance to revision 2
    await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=1,
        operation_type="set_aspect_ratio",
        payload={"aspect_ratio": "16:9"},
    )

    # Attempt mutation expecting revision 1 without idempotency key
    api_resp_no_key = client.post(f"/api/projects/{pid}/operations", json={
        "expected_revision": 1,
        "operation_type": "set_aspect_ratio",
        "payload": {"aspect_ratio": "1:1"},
    })
    assert api_resp_no_key.status_code == 409
    assert api_resp_no_key.json()["detail"]["error"] == "revision_conflict"

    # Attempt mutation expecting revision 1 with fresh unused idempotency key
    api_resp_fresh_key = client.post(f"/api/projects/{pid}/operations", json={
        "expected_revision": 1,
        "operation_type": "set_aspect_ratio",
        "payload": {"aspect_ratio": "1:1"},
        "idempotency_key": "new_unused_key",
    })
    assert api_resp_fresh_key.status_code == 409
    assert api_resp_fresh_key.json()["detail"]["error"] == "revision_conflict"


@pytest.mark.asyncio
async def test_concurrent_duplicates_race_safety():
    """5. Concurrent duplicate requests cannot create duplicate durable effects."""
    p = await ProjectService.create_project(name="Concurrency Race Test")
    pid = p.id

    shared_key = "race_token_12345"
    payload = {"track_id": "track_video_main", "clip": {"id": "race_clip", "duration_seconds": 12.0}}

    async def _submit():
        return await ProjectService.apply_operation(
            project_id=pid,
            expected_revision=1,
            operation_type="add_clip",
            payload=payload,
            idempotency_key=shared_key,
        )

    # Launch 10 concurrent requests reusing the exact same idempotency key
    results = await asyncio.gather(*[_submit() for _ in range(10)], return_exceptions=True)

    # All 10 must succeed (either as original application or idempotent replay)
    applied_count = sum(1 for r in results if isinstance(r, dict) and r.get("applied") is True)
    replay_count = sum(1 for r in results if isinstance(r, dict) and r.get("idempotent_replay") is True)

    assert applied_count == 1, f"Expected exactly 1 mutation applied, got {applied_count}"
    assert replay_count == 9, f"Expected 9 idempotent replays, got {replay_count}"

    # Verify project has exactly revision 2
    proj = await ProjectService.get_project(pid)
    assert proj.revision == 2

    # Verify revision log has exactly 2 entries (rev 1 init, rev 2 add_clip)
    revs = await ProjectService.list_revisions(pid)
    assert len(revs) == 2
    assert revs[1]["revision"] == 2
    assert revs[1]["idempotency_key"] == shared_key


@pytest.mark.asyncio
async def test_no_failed_request_causes_partial_mutation():
    """6. No failed request causes partial mutation: revision, document, and revisions table untouched."""
    p = await ProjectService.create_project(name="Atomic Rollback Test")
    pid = p.id

    # Attempt operation on locked element or invalid block variable
    with pytest.raises(ProjectError):
        await ProjectService.apply_operation(
            project_id=pid,
            expected_revision=1,
            operation_type="update_clip",
            payload={"clip_id": "non_existent_clip", "patch": {"duration_seconds": 10.0}},
            idempotency_key="failing_op_token",
        )

    # Verify state is completely intact
    proj = await ProjectService.get_project(pid)
    assert proj.revision == 1
    revs = await ProjectService.list_revisions(pid)
    assert len(revs) == 1
    assert revs[0]["revision"] == 1


@pytest.mark.asyncio
async def test_future_code_and_filetree_idempotency_contract():
    """7. Contract verified for future versioned code/document patching operations."""
    p = await ProjectService.create_project(name="Code Tree Project")
    pid = p.id

    patch_payload = {
        "patch": {
            "filetree": {
                "src/main.ts": {"content": "console.log('viral');", "language": "typescript"},
                "src/styles.css": {"content": "body { margin: 0; }", "language": "css"},
            }
        }
    }

    # Apply document patch with key
    res = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=1,
        operation_type="patch_document",
        payload=patch_payload,
        idempotency_key="code_patch_key_1",
    )
    assert res["applied"] is True
    assert res["revision"] == 2
    assert "filetree" in res["document"]

    # Replay with same key
    replay = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=1,
        operation_type="patch_document",
        payload=patch_payload,
        idempotency_key="code_patch_key_1",
    )
    assert replay["applied"] is False
    assert replay["idempotent_replay"] is True
    assert replay["revision"] == 2
