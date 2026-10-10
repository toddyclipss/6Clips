# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Comprehensive test suite closing the Canonical Project Asset Contract.

Verifies:
1. Physical existence of assets (database record + file on disk).
2. Authorization boundaries & user/project access scoping.
3. Media type compatibility validation (video, audio, image, block variable types).
4. Deleted or unavailable asset handling.
5. Atomic rejection of invalid references (path traversals, missing IDs, arbitrary files).
"""
import pytest
from pathlib import Path
from starlette.testclient import TestClient

from backend.database import init_db, AsyncSessionLocal
from backend.main import create_app
from backend.models.downloaded_video import DownloadedVideo
from backend.models.generated_video import GeneratedVideo
from backend.services.asset_resolver import (
    resolve_asset_record_and_path,
    validate_asset_identifier_safety,
)
from backend.services.project_service import ProjectService
from backend.core.exceptions import (
    AssetNotFoundError,
    AssetAccessError,
    AssetTypeMismatchError,
    InvalidAssetReferenceError,
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
async def test_asset_physical_existence_contract(tmp_path):
    """1. Assets must exist both in database and on physical filesystem."""
    # Create real dummy media file
    media_file = tmp_path / "valid_clip.mp4"
    media_file.write_bytes(b"\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom" + b"1" * 1024)

    # Insert into database
    async with AsyncSessionLocal() as db:
        dv = DownloadedVideo(
            title="Real Downloaded Video",
            video_path=str(media_file),
            duration_seconds=10,
            user_id="local",
        )
        db.add(dv)
        await db.commit()
        await db.refresh(dv)
        dv_id = dv.id

    # Resolve using canonical key
    key, path, meta = await resolve_asset_record_and_path(f"dl:{dv_id}", must_exist=True)
    assert key == f"dl:{dv_id}"
    assert path == media_file
    assert meta["duration"] == 10
    assert meta["media_type"] == "video"

    # Non-existent asset ID raises AssetNotFoundError
    with pytest.raises(AssetNotFoundError) as exc:
        await resolve_asset_record_and_path("dl:00000000-0000-0000-0000-000000000000", must_exist=True)
    assert "not found in database" in str(exc.value)


@pytest.mark.asyncio
async def test_asset_authorization_and_ownership_scope(tmp_path):
    """2. Enforces user and project authorization boundaries."""
    media_file = tmp_path / "user_bob_clip.mp4"
    media_file.write_bytes(b"dummy_data_12345678")

    async with AsyncSessionLocal() as db:
        dv_bob = DownloadedVideo(
            title="Bob's Private Clip",
            video_path=str(media_file),
            duration_seconds=5,
            user_id="user_bob",
        )
        gv_scoped = GeneratedVideo(
            title="Project A Render",
            video_path=str(media_file),
            duration_seconds=8,
            user_id="local",
            project_id="project_alpha_uuid",
        )
        db.add_all([dv_bob, gv_scoped])
        await db.commit()
        await db.refresh(dv_bob)
        await db.refresh(gv_scoped)
        bob_id = dv_bob.id
        gv_id = gv_scoped.id

    # Caller 'user_alice' attempting to access Bob's asset raises AssetAccessError
    with pytest.raises(AssetAccessError) as exc_user:
        await resolve_asset_record_and_path(
            f"dl:{bob_id}",
            user_id="user_alice",
            must_exist=False,
        )
    assert "unauthorized" in str(exc_user.value)

    # Project B attempting to access Project A's scoped GeneratedVideo raises AssetAccessError
    with pytest.raises(AssetAccessError) as exc_proj:
        await resolve_asset_record_and_path(
            f"gv:{gv_id}",
            project_id="project_beta_uuid",
            must_exist=False,
        )
    assert "scoped to project 'project_alpha_uuid'" in str(exc_proj.value)

    # Authorized project resolves cleanly
    key, _, _ = await resolve_asset_record_and_path(
        f"gv:{gv_id}",
        project_id="project_alpha_uuid",
        must_exist=False,
    )
    assert key == f"gv:{gv_id}"


@pytest.mark.asyncio
async def test_asset_media_type_compatibility(tmp_path):
    """3. Validates media type compatibility for video, audio, and image."""
    vid_file = tmp_path / "vid.mp4"
    vid_file.write_bytes(b"video" * 100)
    img_file = tmp_path / "thumbnail.png"
    img_file.write_bytes(b"image" * 100)

    async with AsyncSessionLocal() as db:
        dv_vid = DownloadedVideo(video_path=str(vid_file), user_id="local")
        gv_img = GeneratedVideo(video_path=str(img_file), user_id="local")
        db.add_all([dv_vid, gv_img])
        await db.commit()
        await db.refresh(dv_vid)
        await db.refresh(gv_img)
        vid_id = dv_vid.id
        img_id = gv_img.id

    # Video asset satisfies 'video' requirement
    _, _, meta_vid = await resolve_asset_record_and_path(
        f"dl:{vid_id}", expected_media_type="video", must_exist=False
    )
    assert meta_vid["media_type"] == "video"

    # Video asset can also satisfy 'audio' requirement (soundtrack extraction)
    _, _, _ = await resolve_asset_record_and_path(
        f"dl:{vid_id}", expected_media_type="audio", must_exist=False
    )

    # Image asset attempting to satisfy 'video' raises AssetTypeMismatchError
    with pytest.raises(AssetTypeMismatchError) as exc_type:
        await resolve_asset_record_and_path(
            f"gv:{img_id}", expected_media_type="video", must_exist=False
        )
    assert "is incompatible with expected type 'video'" in str(exc_type.value)


@pytest.mark.asyncio
async def test_deleted_or_unavailable_asset_handling(tmp_path):
    """4. Cleanly handles assets whose physical files were deleted from disk."""
    media_file = tmp_path / "temporary.mp4"
    media_file.write_bytes(b"clip content")

    async with AsyncSessionLocal() as db:
        dv = DownloadedVideo(video_path=str(media_file), user_id="local")
        db.add(dv)
        await db.commit()
        await db.refresh(dv)
        dv_id = dv.id

    # Delete physical file from disk
    media_file.unlink()

    # Resolution with must_exist=True raises AssetNotFoundError
    with pytest.raises(AssetNotFoundError) as exc:
        await resolve_asset_record_and_path(f"dl:{dv_id}", must_exist=True)
    assert "missing from disk" in str(exc.value)


@pytest.mark.asyncio
async def test_atomic_rejection_of_invalid_asset_references():
    """5. Reject arbitrary filesystem paths and ensure atomic rollback with zero mutation."""
    # Test path injection validation directly
    with pytest.raises(InvalidAssetReferenceError):
        validate_asset_identifier_safety("../../etc/passwd")

    with pytest.raises(InvalidAssetReferenceError):
        validate_asset_identifier_safety("/var/log/syslog")

    with pytest.raises(InvalidAssetReferenceError):
        validate_asset_identifier_safety("C:\\Windows\\System32\\cmd.exe")

    # Now test inside ProjectService.apply_operation with add_asset
    p = await ProjectService.create_project(name="Asset Safety Project")
    pid = p.id
    assert p.revision == 1

    # Attempt to inject arbitrary path as asset
    with pytest.raises(ProjectError):
        await ProjectService.apply_operation(
            project_id=pid,
            expected_revision=1,
            operation_type="add_asset",
            payload={"asset": {"id": "../../secret.env", "name": "Injected File"}},
        )

    # Verify project revision and document are 100% untouched
    reloaded = await ProjectService.get_project(pid)
    assert reloaded.revision == 1
    doc = (await ProjectService.get_revision_snapshot(pid, 1))
    assert doc.get("assets") == []

    # Attempt to add non-existent asset ID with strict validation
    with pytest.raises(ProjectError) as exc_missing:
        await ProjectService.apply_operation(
            project_id=pid,
            expected_revision=1,
            operation_type="add_asset",
            payload={"asset": {"id": "dl:00000000-0000-0000-0000-000000000000"}},
        )
    assert reloaded.revision == 1
    assert "not found in database" in str(exc_missing.value)
