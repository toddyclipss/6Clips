# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Music tracks API — streaming, listing, and safe deletion.

    GET    /api/music/{filename}   stream background-music file from storage/music/
    DELETE /api/music/{filename}   safely remove user-owned track
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.project import Project
from backend.services.library_index import MUSIC_EXTS
from backend.services.music_service import MUSIC_DIR

router = APIRouter(prefix="/music", tags=["music"])
logger = logging.getLogger(__name__)

BUNDLED_TRACKS = {
    "ambient_calm.mp3",
    "bundled_ambient.mp3",
    "cinematic_dramatic.mp3",
    "corporate_motivational.mp3",
    "lofi_chill.mp3",
    "upbeat_electronic.mp3",
}


def _validate_track_path(filename: str) -> Path:
    """Ensure filename stays within storage/music/ and is an allowed audio file."""
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Bad track name")
    try:
        candidate = (MUSIC_DIR / filename).resolve()
    except (OSError, ValueError):
        raise HTTPException(status_code=400, detail="Bad track name")
    if not candidate.is_relative_to(MUSIC_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Bad track name")
    if not candidate.is_file() or candidate.suffix.lower() not in MUSIC_EXTS:
        raise HTTPException(status_code=404, detail="Track not found")
    return candidate


async def check_track_project_references(db: AsyncSession, filename: str) -> tuple[str, int] | None:
    """Check if any Project document references this audio track.

    Returns (project_name, revision) if referenced, else None.
    Protects durable projects and revision logs from breaking changes.
    """
    stem = Path(filename).stem
    candidates = {filename.lower(), f"trk:{filename}".lower(), stem.lower(), f"trk:{stem}".lower()}

    projects = (await db.execute(select(Project))).scalars().all()
    for proj in projects:
        if not proj.document_json:
            continue
        try:
            doc = json.loads(proj.document_json)
        except Exception:
            continue

        # Check assets manifest
        for asset in doc.get("assets", []):
            aid = str(asset.get("id") or asset.get("canonical_key") or "").lower()
            afile = str(asset.get("file") or asset.get("filename") or "").lower()
            if aid in candidates or afile in candidates or filename.lower() in (aid, afile):
                return (proj.name or "Untitled Project", proj.revision or 1)

        # Check timeline tracks & clips
        timeline = doc.get("timeline", {})
        tracks = timeline.get("tracks", [])
        for trk in tracks:
            for clip in trk.get("clips", []):
                clip_asset = str(clip.get("asset_id") or "").lower()
                clip_file = str(clip.get("file") or clip.get("asset_file") or "").lower()
                clip_src = str(clip.get("source_id") or "").lower()
                if any(c in (clip_asset, clip_file, clip_src) for c in candidates):
                    return (proj.name or "Untitled Project", proj.revision or 1)
                if filename.lower() in clip_asset or filename.lower() in clip_file:
                    return (proj.name or "Untitled Project", proj.revision or 1)

    return None


async def safe_delete_music_file(
    filename: str,
    db: AsyncSession,
    hide_if_blocked: bool = False,
) -> dict:
    """Execute safe deletion semantics for a music track."""
    candidate = _validate_track_path(filename)
    from backend.services.library_index import hide_track

    # 1. Bundled / shared system track guard
    if filename.lower() in BUNDLED_TRACKS:
        if hide_if_blocked:
            hide_track(filename)
            return {"ok": True, "hidden": filename, "reason": "bundled"}
        raise HTTPException(
            status_code=403,
            detail=f"Cannot delete bundled track '{filename}'. Bundled tracks are shared system resources.",
        )

    # 2. Project reference guard
    ref = await check_track_project_references(db, filename)
    if ref:
        if hide_if_blocked:
            hide_track(filename)
            return {"ok": True, "hidden": filename, "reason": "referenced"}
        proj_name, rev = ref
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete '{filename}': it is referenced by project '{proj_name}' (revision {rev}). Remove the clip from the project timeline before deleting.",
        )

    # 3. Unlink physical file
    try:
        candidate.unlink(missing_ok=True)
    except OSError as exc:
        logger.error(f"Failed to unlink track '{filename}': {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to delete track file: {exc}")

    # 4. Invalidate duration cache
    from backend.services.library_index import evict_track_duration
    evict_track_duration(candidate)

    return {"ok": True, "deleted": filename}


@router.get("/{filename}")
async def stream_music(filename: str, request: Request):
    """Stream a background-music file from storage/music/."""
    candidate = _validate_track_path(filename)
    from backend.api.videos import serve_media_with_range
    return serve_media_with_range(candidate, request, filename=candidate.name)


@router.get("/{filename}/waveform")
async def get_music_waveform(filename: str, count: int = 46):
    """Return authentic cached waveform peak envelope (0.05..1.0) for a music track."""
    candidate = _validate_track_path(filename)
    from backend.services.waveform_service import extract_audio_peaks
    peaks = extract_audio_peaks(candidate, points=max(10, min(200, count)))
    return {"filename": filename, "peaks": peaks, "count": len(peaks)}


@router.post("/{filename}/hide")
async def hide_music_track(filename: str):
    """Hide a music track so it no longer appears in the browsable Library."""
    _validate_track_path(filename)
    from backend.services.library_index import hide_track
    hide_track(filename)
    return {"ok": True, "hidden": filename}


@router.post("/{filename}/unhide")
async def unhide_music_track(filename: str):
    """Unhide a music track so it reappears in the browsable Library."""
    _validate_track_path(filename)
    from backend.services.library_index import unhide_track
    unhide_track(filename)
    return {"ok": True, "unhidden": filename}


@router.delete("/{filename}")
async def delete_music(
    filename: str,
    hide_if_blocked: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Safely delete a user-owned music track, or hide it if blocked."""
    return await safe_delete_music_file(filename, db, hide_if_blocked=hide_if_blocked)

