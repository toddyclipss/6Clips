# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for Wave 3 Library Trash and Asset Lifecycle."""
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from backend.library_workflows.trash_and_lifecycle import (
    TrashManager,
    AssetLockedByProjectError,
    AssetOwnershipError,
    LifecycleError,
)
from backend.models.project import Project


@pytest.mark.asyncio
async def test_trash_soft_delete_and_restore(tmp_path: Path, monkeypatch):
    test_registry = tmp_path / "test_trash.json"
    monkeypatch.setattr("backend.library_workflows.trash_and_lifecycle.TRASH_REGISTRY_FILE", test_registry)

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=None)

    key = "dl:test_video_123"
    assert TrashManager.is_trashed(key) is False

    # Move to trash
    res = await TrashManager.move_to_trash(key, mock_db, user_id="local", title="My Test Video")
    assert res["ok"] is True
    assert res["trashed"] is True
    assert TrashManager.is_trashed(key) is True

    # List trash items
    trash_list = TrashManager.get_trash_items(user_id="local")
    assert len(trash_list) == 1
    assert trash_list[0]["key"] == key
    assert trash_list[0]["title"] == "My Test Video"

    # Restore from trash
    rest_res = await TrashManager.restore_from_trash(key, user_id="local")
    assert rest_res["ok"] is True
    assert rest_res["restored"] is True
    assert TrashManager.is_trashed(key) is False
    assert len(TrashManager.get_trash_items(user_id="local")) == 0


@pytest.mark.asyncio
async def test_trash_ownership_guard(tmp_path: Path, monkeypatch):
    test_registry = tmp_path / "test_trash.json"
    monkeypatch.setattr("backend.library_workflows.trash_and_lifecycle.TRASH_REGISTRY_FILE", test_registry)

    # Item in trash owned by user_a
    records = {
        "dl:asset_user_a": {
            "key": "dl:asset_user_a",
            "title": "Private Clip",
            "user_id": "user_a",
            "trashed_at": 1000,
        }
    }
    test_registry.write_text(json.dumps(records), encoding="utf-8")

    # user_b attempts restore -> rejected
    with pytest.raises(AssetOwnershipError, match="Access denied"):
        await TrashManager.restore_from_trash("dl:asset_user_a", user_id="user_b")

    # admin attempts restore -> permitted
    admin_res = await TrashManager.restore_from_trash("dl:asset_user_a", user_id="admin")
    assert admin_res["ok"] is True


@pytest.mark.asyncio
async def test_project_reference_guard_blocks_purge(tmp_path: Path, monkeypatch):
    test_registry = tmp_path / "test_trash.json"
    monkeypatch.setattr("backend.library_workflows.trash_and_lifecycle.TRASH_REGISTRY_FILE", test_registry)

    key = "gv:video_in_use"
    mock_proj = Project(
        id="proj_xyz",
        name="Active TikTok Edit",
        document_json=json.dumps({"tracks": [{"clips": [{"asset_key": key}]}]}),
    )

    mock_db = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_proj]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_db.execute.return_value = mock_result

    # Purge without force should fail because project references it
    with pytest.raises(AssetLockedByProjectError, match="actively used in project revisions"):
        await TrashManager.permanently_purge(key, mock_db, user_id="local", force=False)


@pytest.mark.asyncio
async def test_project_reference_force_purge_override(tmp_path: Path, monkeypatch):
    test_registry = tmp_path / "test_trash.json"
    monkeypatch.setattr("backend.library_workflows.trash_and_lifecycle.TRASH_REGISTRY_FILE", test_registry)

    key = "gv:video_force_override"
    mock_proj = Project(
        id="proj_xyz",
        name="Active TikTok Edit",
        document_json=json.dumps({"tracks": [{"clips": [{"asset_key": key}]}]}),
    )

    mock_db = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_proj]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_db.execute.return_value = mock_result

    # Mock safe_delete_asset
    with patch_library_delete():
        res = await TrashManager.permanently_purge(key, mock_db, user_id="local", force=True)
        assert res["ok"] is True
        assert res["purged"] is True


def patch_library_delete():
    from unittest.mock import patch
    return patch(
        "backend.services.library_service.LibraryService.safe_delete_asset",
        new_callable=AsyncMock,
        return_value={"deleted": True},
    )
