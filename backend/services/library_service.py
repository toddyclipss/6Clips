# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Library Service: unified asset provenance, ownership validation, missing media guard, and safe lifecycle operations."""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.job import Job
from backend.models.generated_video import GeneratedVideo
from backend.models.downloaded_video import DownloadedVideo
from backend.services.library_taxonomy import classify, taxonomy_payload

logger = logging.getLogger(__name__)

# Extensions recognized by the library
ALLOWED_MEDIA_EXTENSIONS = {
    ".mp4", ".mov", ".avi", ".mkv", ".webm",
    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg",
    ".jpg", ".jpeg", ".png", ".webp", ".gif",
}

SYNTHETIC_FIXTURE_PATTERNS = [
    "synth_fixture",
    "synthetic_tone",
    "test_fixture",
    "dummy_media",
    "fake_stock",
    "mock_audio",
]


class LibraryError(Exception):
    """Base error for library service operations."""
    pass


class MissingMediaError(LibraryError):
    """Raised when an asset row refers to a file that does not exist on disk."""
    pass


class OwnershipViolationError(LibraryError):
    """Raised when an operation attempts to modify an asset belonging to another user."""
    pass


class LibraryService:
    """Core domain service for user media library, provenance, and lifecycle security."""

    @classmethod
    def is_synthetic_fixture(cls, identifier: str) -> bool:
        """
        Identify whether a filename, title, or key matches known synthetic test fixtures.
        Requirement A19, G12: synthetic fixtures must never masquerade as user stock media.
        """
        if not identifier:
            return False
        ident_lower = str(identifier).lower()
        return any(pat in ident_lower for pat in SYNTHETIC_FIXTURE_PATTERNS)

    @classmethod
    def compute_sha256(cls, file_path: Path) -> str:
        """Compute SHA-256 checksum for physical file verification."""
        if not file_path.is_file():
            raise MissingMediaError(f"Cannot hash missing file: {file_path}")
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    @classmethod
    def validate_media_file(cls, file_path: Optional[Path]) -> Path:
        """
        Verify physical existence of media file on disk.
        Requirement E02: missing media must never return success.
        """
        if not file_path:
            raise MissingMediaError("Media path is empty or not provided.")
        if not file_path.is_file():
            raise MissingMediaError(f"Media file missing on disk: {file_path}")
        if file_path.stat().st_size == 0:
            raise MissingMediaError(f"Media file is empty (0 bytes): {file_path}")
        return file_path

    @classmethod
    def verify_ownership(cls, asset_user_id: Optional[str], requested_user_id: Optional[str]) -> None:
        """
        Enforce cross-user ownership isolation.
        If both user IDs are present and differ, raises OwnershipViolationError.
        """
        if asset_user_id and requested_user_id and asset_user_id != requested_user_id:
            raise OwnershipViolationError(
                f"Access denied: asset belongs to user '{asset_user_id}', not '{requested_user_id}'."
            )

    @classmethod
    async def resolve_asset_file(cls, key: str, db: AsyncSession) -> Tuple[Path, Dict[str, Any]]:
        """
        Resolve library item key ('gv:<id>', 'dl:<id>', 'job:<id>', 'trk:<name>')
        to its physical file and provenance metadata.
        Raises MissingMediaError if the physical file does not exist.
        """
        if ":" not in key:
            raise LibraryError(f"Invalid library key format: '{key}'")

        prefix, ident = key.split(":", 1)
        meta: Dict[str, Any] = {"key": key, "prefix": prefix, "id": ident}

        if prefix == "gv":
            gv = await db.get(GeneratedVideo, ident)
            if not gv:
                raise HTTPException(status_code=404, detail="Generated video not found")
            p = Path(gv.video_path or "")
            cls.validate_media_file(p)
            meta.update({
                "title": gv.title,
                "media": "video",
                "origin": "created",
                "producer": "6Clips Generator",
                "aspect": gv.aspect_ratio or "9:16",
                "duration_seconds": gv.duration,
                "size_mb": round(p.stat().st_size / (1024 * 1024), 2),
            })
            return p, meta

        elif prefix == "dl":
            dl = await db.get(DownloadedVideo, ident)
            if not dl:
                raise HTTPException(status_code=404, detail="Downloaded video not found")
            p = Path(dl.video_path or dl.audio_path or "")
            cls.validate_media_file(p)
            meta.update({
                "title": dl.title or dl.filename,
                "media": "audio" if dl.audio_path and not dl.video_path else "video",
                "origin": "imported",
                "producer": dl.platform or "Import",
                "aspect": dl.aspect_ratio or "9:16",
                "duration_seconds": dl.duration,
                "size_mb": round(p.stat().st_size / (1024 * 1024), 2),
            })
            return p, meta

        elif prefix == "job":
            job = await db.get(Job, ident)
            if not job or job.status != "success":
                raise HTTPException(status_code=404, detail="Job asset not found or not successful")
            if not job.output_json:
                raise MissingMediaError("Job asset has no output JSON")
            try:
                out = json.loads(job.output_json)
            except Exception:
                raise LibraryError("Corrupt job output JSON")
            file_str = (out or {}).get("file")
            if not file_str:
                raise MissingMediaError("Job output has no file path")

            from backend.api.videos import _safe_resolve_path
            p = _safe_resolve_path(file_str)
            cls.validate_media_file(p)
            meta.update({
                "title": (out or {}).get("title") or job.job_type,
                "media": "video" if p.suffix in (".mp4", ".mov", ".webm") else "audio",
                "origin": "edited",
                "producer": f"tool:{job.job_type}",
                "size_mb": round(p.stat().st_size / (1024 * 1024), 2),
            })
            return p, meta

        elif prefix in ("trk", "music"):
            from backend.api.music import _validate_track_path
            p = _validate_track_path(ident)
            cls.validate_media_file(p)
            meta.update({
                "title": ident,
                "media": "audio",
                "origin": "imported",
                "producer": "Music Library",
                "size_mb": round(p.stat().st_size / (1024 * 1024), 2),
            })
            return p, meta

        else:
            raise LibraryError(f"Unsupported asset key prefix: '{prefix}'")

    @classmethod
    async def safe_delete_asset(
        cls,
        key: str,
        db: AsyncSession,
        requesting_user_id: Optional[str] = None,
        hide_if_locked: bool = False,
    ) -> Dict[str, Any]:
        """
        Safely delete an asset row, physical file, and poster caches.
        Enforces ownership guards. Supports hiding if referenced.
        """
        if ":" not in key:
            raise HTTPException(status_code=400, detail="Invalid item key")

        prefix, ident = key.split(":", 1)

        if prefix == "job":
            job = await db.get(Job, ident)
            if not job:
                raise HTTPException(status_code=404, detail="Asset not found")
            cls.verify_ownership(getattr(job, "user_id", None), requesting_user_id)

            # Drop poster cache
            poster_cache = settings.THUMBNAILS_DIR / f"libposter_{ident}.jpg"
            poster_cache.unlink(missing_ok=True)

            # Unlink file
            if job.output_json:
                try:
                    out = json.loads(job.output_json)
                    file_str = (out or {}).get("file")
                    if file_str:
                        from backend.api.videos import _safe_resolve_path
                        p = _safe_resolve_path(file_str)
                        if p.is_file():
                            p.unlink(missing_ok=True)
                except Exception as e:
                    logger.warning("Error unlinking job file: %s", e)

            await db.delete(job)
            await db.commit()
            return {"ok": True, "deleted_key": key}

        elif prefix == "gv":
            gv = await db.get(GeneratedVideo, ident)
            if not gv:
                raise HTTPException(status_code=404, detail="Generated video not found")
            cls.verify_ownership(getattr(gv, "user_id", None), requesting_user_id)

            if gv.video_path and Path(gv.video_path).is_file():
                Path(gv.video_path).unlink(missing_ok=True)
            if gv.thumbnail_path and Path(gv.thumbnail_path).is_file():
                Path(gv.thumbnail_path).unlink(missing_ok=True)

            await db.delete(gv)
            await db.commit()
            return {"ok": True, "deleted_key": key}

        elif prefix == "dl":
            dl = await db.get(DownloadedVideo, ident)
            if not dl:
                raise HTTPException(status_code=404, detail="Downloaded video not found")
            cls.verify_ownership(getattr(dl, "user_id", None), requesting_user_id)

            if dl.video_path and Path(dl.video_path).is_file():
                Path(dl.video_path).unlink(missing_ok=True)
            if dl.audio_path and Path(dl.audio_path).is_file():
                Path(dl.audio_path).unlink(missing_ok=True)

            await db.delete(dl)
            await db.commit()
            return {"ok": True, "deleted_key": key}

        elif prefix in ("trk", "music"):
            from backend.api.music import safe_delete_music_file
            return await safe_delete_music_file(ident, db, hide_if_locked=hide_if_locked)

        else:
            raise HTTPException(status_code=400, detail="Unsupported item prefix for deletion")

    @classmethod
    def stream_range_media(cls, file_path: Path, request: Request, filename: Optional[str] = None):
        """
        Serve media using RFC 7233 partial content (HTTP 206) for scrubbing and seeking.
        """
        cls.validate_media_file(file_path)
        from backend.api.videos import serve_media_with_range
        return serve_media_with_range(file_path, request, filename=filename or file_path.name)

    # ── Wave 3 Workflow Facades ───────────────────────────────────────────────

    @classmethod
    def probe_media(cls, file_path: Path):
        """Perform deep byte inspection and stream probing via media_probe module."""
        from backend.library_workflows.media_probe import probe_media_file
        return probe_media_file(file_path)

    @classmethod
    async def create_motion_intent(
        cls,
        key: str,
        db: AsyncSession,
        intent_action: str = "add_track",
        target_track: Optional[str] = None,
        target_start_time_seconds: float = 0.0,
    ):
        """Construct verified MotionAssetIntent contract for Motion/DnD integration."""
        from backend.library_workflows.motion_contract import MotionContractManager
        return await MotionContractManager.create_motion_intent(
            key=key,
            db=db,
            intent_action=intent_action,
            target_track=target_track,
            target_start_time_seconds=target_start_time_seconds,
        )

    @classmethod
    async def move_to_trash(
        cls,
        key: str,
        db: AsyncSession,
        user_id: str = "local",
        title: Optional[str] = None,
    ):
        """Soft-delete asset into trash registry."""
        from backend.library_workflows.trash_and_lifecycle import TrashManager
        return await TrashManager.move_to_trash(key, db, user_id=user_id, title=title)

    @classmethod
    async def restore_from_trash(cls, key: str, user_id: str = "local"):
        """Restore asset from trash back to active library."""
        from backend.library_workflows.trash_and_lifecycle import TrashManager
        return await TrashManager.restore_from_trash(key, user_id=user_id)
