# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Upload Handler: safe file persistence, chunked upload sessions, path sanitization, and probe integration."""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import AsyncSessionLocal
from backend.models.downloaded_video import DownloadedVideo
from backend.models.trends_result import TrendsResult as ScoutResult
from backend.library_workflows.media_probe import (
    CorruptedMediaError,
    MediaProbeError,
    MediaProbeResult,
    UnrecognizedMediaError,
    probe_media_file,
)
from backend.library_workflows.quota_service import (
    DiskSpaceExceededError,
    QuotaService,
    StorageQuotaExceededError,
)

logger = logging.getLogger(__name__)

# Upload limits
MAX_SINGLE_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB
CHUNKED_UPLOAD_STAGING_DIR = settings.STORAGE_ROOT / "upload_sessions"
CHUNKED_UPLOAD_STAGING_DIR.mkdir(parents=True, exist_ok=True)

# Session TTL (24 hours)
SESSION_TTL_SECONDS = 24 * 3600


class UploadError(Exception):
    """Base error for upload workflow failures."""
    pass


class InvalidFilenameError(UploadError):
    """Raised when filename is unsafe or malicious."""
    pass


def sanitize_filename(raw_name: str) -> str:
    """
    Sanitize user-provided filename against path traversal, control chars, and illegal symbols.
    Preserves clean alphanumeric characters, dashes, underscores, and normalized extension.
    """
    if not raw_name or not isinstance(raw_name, str):
        return "uploaded_media.mp4"

    # Remove null bytes
    cleaned = raw_name.replace("\x00", "")

    # Strip directory components (both Unix / and Windows \)
    cleaned = cleaned.replace("\\", "/").split("/")[-1].strip()

    # Disallow traversal tokens if still present
    cleaned = cleaned.replace("..", "").strip()

    if not cleaned:
        return "uploaded_media.mp4"

    p = Path(cleaned)
    stem = p.stem
    ext = p.suffix.lower()

    # Clean stem: keep alphanumeric, dashes, underscores, spaces, dots
    clean_stem = re.sub(r"[^\w\-_ .]", "", stem).strip()

    if not clean_stem:
        return "uploaded_media.mp4"

    # Limit stem length
    clean_stem = clean_stem[:100]

    return f"{clean_stem}{ext or '.mp4'}"


class UploadHandler:
    """Manages single and chunked upload workflows with strict verification and cleanup."""

    @classmethod
    async def process_single_upload(
        cls,
        upload_file: UploadFile,
        user_id: str = "local",
        title: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        Stream, verify, probe, and register a single uploaded media file.
        Cleans up partial files on any disconnect or failure.
        """
        raw_filename = upload_file.filename or "upload.mp4"
        safe_name = sanitize_filename(raw_filename)
        file_id = str(uuid4())[:12]
        ext = Path(safe_name).suffix.lower()

        # Temporary destination during streaming
        temp_dest = settings.STORAGE_ROOT / f".part_{file_id}{ext}"
        temp_dest.parent.mkdir(parents=True, exist_ok=True)

        file_size = 0
        try:
            with open(temp_dest, "wb") as f:
                while chunk := await upload_file.read(1024 * 1024):  # 1MB chunks
                    file_size += len(chunk)
                    if file_size > MAX_SINGLE_UPLOAD_BYTES:
                        raise HTTPException(413, "File exceeds maximum upload size (2GB).")
                    f.write(chunk)
        except BaseException as e:
            temp_dest.unlink(missing_ok=True)
            if isinstance(e, HTTPException):
                raise
            logger.error("Upload stream interrupted: %s", e)
            raise HTTPException(499, "Client interrupted upload stream.") from e

        if file_size == 0:
            temp_dest.unlink(missing_ok=True)
            raise HTTPException(400, "Uploaded file is empty (0 bytes).")

        # Quota check
        try:
            QuotaService.check_capacity(file_size, target_dir=settings.VIDEOS_DIR, user_id=user_id)
        except (DiskSpaceExceededError, StorageQuotaExceededError) as qe:
            temp_dest.unlink(missing_ok=True)
            raise HTTPException(413, str(qe)) from qe

        # Probe media bytes
        try:
            probe = probe_media_file(temp_dest)
        except UnrecognizedMediaError as ue:
            temp_dest.unlink(missing_ok=True)
            raise HTTPException(415, f"Unsupported media type: {ue}") from ue
        except CorruptedMediaError as ce:
            temp_dest.unlink(missing_ok=True)
            raise HTTPException(422, f"Corrupted media file: {ce}") from ce
        except MediaProbeError as me:
            temp_dest.unlink(missing_ok=True)
            raise HTTPException(400, f"Media inspection failed: {me}") from me

        # Destination directory based on verified category
        is_audio = probe.media_category == "audio"
        dest_dir = settings.AUDIO_DIR if is_audio else settings.VIDEOS_DIR
        dest_dir.mkdir(parents=True, exist_ok=True)
        final_dest = dest_dir / f"{file_id}{ext}"

        # Atomic rename from temp to final
        temp_dest.rename(final_dest)

        display_title = title or Path(safe_name).stem

        # Register in database
        async def _persist(sess: AsyncSession):
            sr = ScoutResult(
                user_id=user_id,
                platform="import",
                video_id=file_id,
                video_url="",
                title=display_title,
                is_downloaded=True,
                virality_score=0,
            )
            sess.add(sr)
            await sess.flush()

            dv = DownloadedVideo(
                user_id=user_id,
                scout_result_id=sr.id,
                title=display_title,
                platform="import",
                video_path=str(final_dest) if not is_audio else None,
                audio_path=str(final_dest) if is_audio else None,
                file_size_mb=probe.file_size_mb,
                duration=int(probe.duration_seconds),
                aspect_ratio=probe.aspect_ratio or ("9:16" if not is_audio else None),
            )
            sess.add(dv)
            await sess.commit()
            await sess.refresh(dv)
            return dv

        if db:
            dv_row = await _persist(db)
        else:
            async with AsyncSessionLocal() as sess:
                dv_row = await _persist(sess)

        return {
            "ok": True,
            "id": dv_row.id,
            "key": f"dl:{dv_row.id}",
            "title": display_title,
            "file_size_mb": probe.file_size_mb,
            "duration": probe.duration_seconds,
            "aspect_ratio": probe.aspect_ratio,
            "sha256": probe.sha256_hash,
            "media_category": probe.media_category,
            "mime_type": probe.mime_type,
            "streams": [s.codec_name for s in probe.streams],
        }

    # ── Chunked / Resumable Upload Session Handlers ────────────────────────────

    @classmethod
    def init_chunked_session(
        cls,
        filename: str,
        total_bytes: int,
        total_chunks: int,
        user_id: str = "local",
    ) -> Dict[str, Any]:
        """Initialize staging directory for a chunked upload."""
        safe_name = sanitize_filename(filename)
        if total_bytes <= 0 or total_bytes > MAX_SINGLE_UPLOAD_BYTES:
            raise HTTPException(400, "Invalid total bytes for chunked upload.")
        if total_chunks <= 0 or total_chunks > 2000:
            raise HTTPException(400, "Invalid chunk count (1-2000 allowed).")

        # Quota check upfront
        QuotaService.check_capacity(total_bytes, user_id=user_id)

        session_id = str(uuid4())
        session_dir = CHUNKED_UPLOAD_STAGING_DIR / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        meta = {
            "session_id": session_id,
            "filename": safe_name,
            "total_bytes": total_bytes,
            "total_chunks": total_chunks,
            "received_chunks": [],
            "user_id": user_id,
            "created_at": time.time(),
        }
        (session_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

        return {
            "session_id": session_id,
            "safe_filename": safe_name,
            "total_chunks": total_chunks,
        }

    @classmethod
    def write_chunk(cls, session_id: str, chunk_index: int, chunk_bytes: bytes) -> Dict[str, Any]:
        """Write single chunk file into session directory."""
        session_dir = CHUNKED_UPLOAD_STAGING_DIR / session_id
        meta_file = session_dir / "meta.json"
        if not meta_file.exists():
            raise HTTPException(404, "Upload session not found or expired.")

        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        if chunk_index < 0 or chunk_index >= meta["total_chunks"]:
            raise HTTPException(400, f"Invalid chunk index {chunk_index}.")

        chunk_path = session_dir / f"chunk_{chunk_index:05d}.part"
        chunk_path.write_bytes(chunk_bytes)

        if chunk_index not in meta["received_chunks"]:
            meta["received_chunks"].append(chunk_index)
            meta_file.write_text(json.dumps(meta), encoding="utf-8")

        return {
            "session_id": session_id,
            "chunk_index": chunk_index,
            "received_chunks": len(meta["received_chunks"]),
            "received_count": len(meta["received_chunks"]),
            "total_chunks": meta["total_chunks"],
            "is_complete": len(meta["received_chunks"]) >= meta["total_chunks"],
        }

    @classmethod
    async def complete_chunked_session(
        cls,
        session_id: str,
        user_id: str = "local",
        title: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """Assemble all chunks, verify integrity, probe media, and commit asset."""
        session_dir = CHUNKED_UPLOAD_STAGING_DIR / session_id
        meta_file = session_dir / "meta.json"
        if not meta_file.exists():
            raise HTTPException(404, "Upload session not found or expired.")

        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        if meta.get("user_id") != user_id:
            raise HTTPException(403, "Access denied: session belongs to another user.")

        total_chunks = meta["total_chunks"]
        if len(meta["received_chunks"]) < total_chunks:
            raise HTTPException(
                400,
                f"Cannot complete: missing chunks ({len(meta['received_chunks'])}/{total_chunks} received).",
            )

        # Assemble chunks into combined temp file
        ext = Path(meta["filename"]).suffix.lower()
        assembled_path = session_dir / f"assembled{ext}"

        with open(assembled_path, "wb") as outfile:
            for idx in range(total_chunks):
                cpath = session_dir / f"chunk_{idx:05d}.part"
                if not cpath.exists():
                    assembled_path.unlink(missing_ok=True)
                    raise HTTPException(400, f"Missing chunk {idx} on disk.")
                with open(cpath, "rb") as infile:
                    while block := infile.read(65536):
                        outfile.write(block)

        # Probe assembled media
        try:
            probe = probe_media_file(assembled_path)
        except MediaProbeError as me:
            import shutil
            shutil.rmtree(session_dir, ignore_errors=True)
            raise HTTPException(422, f"Assembled media is invalid: {me}") from me

        # Move to final storage
        file_id = str(uuid4())[:12]
        is_audio = probe.media_category == "audio"
        dest_dir = settings.AUDIO_DIR if is_audio else settings.VIDEOS_DIR
        dest_dir.mkdir(parents=True, exist_ok=True)
        final_dest = dest_dir / f"{file_id}{ext}"

        assembled_path.rename(final_dest)

        # Cleanup staging session
        import shutil
        shutil.rmtree(session_dir, ignore_errors=True)

        display_title = title or Path(meta["filename"]).stem

        # Persist DB row
        async def _persist(sess: AsyncSession):
            sr = ScoutResult(
                user_id=user_id,
                platform="import",
                video_id=file_id,
                video_url="",
                title=display_title,
                is_downloaded=True,
                virality_score=0,
            )
            sess.add(sr)
            await sess.flush()

            dv = DownloadedVideo(
                user_id=user_id,
                scout_result_id=sr.id,
                title=display_title,
                platform="import",
                video_path=str(final_dest) if not is_audio else None,
                audio_path=str(final_dest) if is_audio else None,
                file_size_mb=probe.file_size_mb,
                duration=int(probe.duration_seconds),
                aspect_ratio=probe.aspect_ratio or ("9:16" if not is_audio else None),
            )
            sess.add(dv)
            await sess.commit()
            await sess.refresh(dv)
            return dv

        if db:
            dv_row = await _persist(db)
        else:
            async with AsyncSessionLocal() as sess:
                dv_row = await _persist(sess)

        return {
            "ok": True,
            "id": dv_row.id,
            "key": f"dl:{dv_row.id}",
            "title": display_title,
            "file_size_mb": probe.file_size_mb,
            "duration": probe.duration_seconds,
            "sha256": probe.sha256_hash,
            "aspect_ratio": probe.aspect_ratio,
        }
