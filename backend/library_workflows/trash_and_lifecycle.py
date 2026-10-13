# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Trash and Lifecycle: soft-delete, restore rollback, and active project reference guards."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.job import Job
from backend.models.generated_video import GeneratedVideo
from backend.models.downloaded_video import DownloadedVideo
from backend.models.project import Project

logger = logging.getLogger(__name__)

TRASH_REGISTRY_FILE = settings.STORAGE_ROOT / "library_trash.json"


class LifecycleError(Exception):
    """Base error for library lifecycle operations."""
    pass


class AssetLockedByProjectError(LifecycleError):
    """Raised when an asset cannot be purged because it is actively referenced in a project revision."""
    pass


class AssetOwnershipError(LifecycleError):
    """Raised when an unauthorized user attempts to modify or purge an asset."""
    pass


class TrashManager:
    """Manages soft-delete (trash), rollback/restore, and project reference integrity."""

    @classmethod
    def _read_trash_records(cls) -> Dict[str, Dict[str, Any]]:
        if not TRASH_REGISTRY_FILE.exists():
            return {}
        try:
            return json.loads(TRASH_REGISTRY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}

    @classmethod
    def _write_trash_records(cls, records: Dict[str, Dict[str, Any]]) -> None:
        TRASH_REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
        TRASH_REGISTRY_FILE.write_text(json.dumps(records, indent=2), encoding="utf-8")

    @classmethod
    def is_trashed(cls, key: str) -> bool:
        """Check if an item is currently in trash."""
        records = cls._read_trash_records()
        return key in records

    @classmethod
    def get_trash_items(cls, user_id: str = "local") -> List[Dict[str, Any]]:
        """Return list of items in the trash for a given user."""
        records = cls._read_trash_records()
        items = []
        for key, rec in records.items():
            if rec.get("user_id", "local") == user_id or user_id == "admin":
                items.append(rec)
        return sorted(items, key=lambda x: x.get("trashed_at", 0), reverse=True)

    @classmethod
    async def check_project_references(cls, key: str, db: AsyncSession) -> List[str]:
        """
        Scan active projects to check if this asset key or ID is referenced in project tracks.
        Returns list of referencing project IDs / titles.
        """
        prefix, ident = key.split(":", 1) if ":" in key else ("", key)
        referencing_projects = []

        try:
            stmt = select(Project)
            res = await db.execute(stmt)
            projects = res.scalars().all()
            for p in projects:
                # Check document_json or legacy data_json
                pdata_str = getattr(p, "document_json", None) or getattr(p, "data_json", None) or "{}"
                if ident in pdata_str or key in pdata_str:
                    referencing_projects.append(f"{p.id} ({p.name})")
        except Exception as e:
            logger.debug("Project reference check non-fatal error: %s", e)

        return referencing_projects

    @classmethod
    async def move_to_trash(
        cls,
        key: str,
        db: AsyncSession,
        user_id: str = "local",
        title: Optional[str] = None,
        reason: str = "user_action",
    ) -> Dict[str, Any]:
        """
        Soft-delete an asset by moving it into the trash registry.
        Does not physically delete the file, enabling rollback/restore.
        """
        records = cls._read_trash_records()
        if key in records:
            return {"ok": True, "already_trashed": True, "key": key}

        # Check ownership and gather basic metadata
        prefix, ident = key.split(":", 1) if ":" in key else ("", key)
        asset_title = title or ident
        asset_user_id = "local"
        file_path_str = None

        if prefix == "dl":
            dv = await db.get(DownloadedVideo, ident)
            if dv:
                asset_user_id = dv.user_id or "local"
                asset_title = dv.title or asset_title
                file_path_str = dv.video_path or dv.audio_path
        elif prefix == "gv":
            gv = await db.get(GeneratedVideo, ident)
            if gv:
                asset_user_id = gv.user_id or "local"
                asset_title = gv.title or asset_title
                file_path_str = gv.video_path
        elif prefix == "job":
            jb = await db.get(Job, ident)
            if jb:
                asset_user_id = getattr(jb, "user_id", "local")
                asset_title = jb.job_type or asset_title

        if asset_user_id != user_id and user_id != "admin":
            raise AssetOwnershipError(f"Access denied: item belongs to user '{asset_user_id}'.")

        record = {
            "key": key,
            "title": asset_title,
            "user_id": user_id,
            "file_path": file_path_str,
            "trashed_at": time.time(),
            "reason": reason,
        }
        records[key] = record
        cls._write_trash_records(records)

        return {"ok": True, "trashed": True, "key": key, "title": asset_title}

    @classmethod
    async def restore_from_trash(cls, key: str, user_id: str = "local") -> Dict[str, Any]:
        """Restore an item from the trash back to the active library."""
        records = cls._read_trash_records()
        if key not in records:
            raise LifecycleError(f"Item '{key}' is not in the trash.")

        rec = records[key]
        if rec.get("user_id") != user_id and user_id != "admin":
            raise AssetOwnershipError("Access denied: cannot restore an asset owned by another user.")

        del records[key]
        cls._write_trash_records(records)
        return {"ok": True, "restored": True, "key": key, "title": rec.get("title")}

    @classmethod
    async def permanently_purge(
        cls,
        key: str,
        db: AsyncSession,
        user_id: str = "local",
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Permanently delete an asset, unlinking files and removing DB rows.
        Guarded against active project references unless force=True.
        """
        # Project reference guard
        refs = await cls.check_project_references(key, db)
        if refs and not force:
            raise AssetLockedByProjectError(
                f"Asset '{key}' is actively used in project revisions: {', '.join(refs)}. "
                f"Remove asset from timeline or pass force=True to purge."
            )

        # Delegate to LibraryService for atomic unlinking and DB delete
        from backend.services.library_service import LibraryService
        res = await LibraryService.safe_delete_asset(
            key=key,
            db=db,
            requesting_user_id=user_id,
            hide_if_locked=False,
        )

        # Remove from trash records if present
        records = cls._read_trash_records()
        if key in records:
            del records[key]
            cls._write_trash_records(records)

        return {"ok": True, "purged": True, "key": key, "detail": res}
