# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Universal asset identity resolver for ViralMint media items.

Normalizes and resolves asset identities across the entire system:
- `dl:<uuid>` / `downloaded:<uuid>` -> DownloadedVideo
- `gv:<uuid>` / `generated:<uuid>` -> GeneratedVideo
- raw `<uuid>` -> attempts DownloadedVideo, then GeneratedVideo

Enforces physical existence checks on disk, media type compatibility,
and authorization/ownership scope verification.
"""
import re
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import AsyncSessionLocal
from backend.models.downloaded_video import DownloadedVideo
from backend.models.generated_video import GeneratedVideo
from backend.core.exceptions import (
    AssetError,
    AssetNotFoundError,
    AssetAccessError,
    AssetTypeMismatchError,
    InvalidAssetReferenceError,
)

logger = logging.getLogger(__name__)

# Canonical media extension sets
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".wma"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".bmp"}


def validate_asset_identifier_safety(raw_id: str) -> None:
    """Ensure asset identity is clean and contains no filesystem paths, traversals, or injections.
    
    Raises InvalidAssetReferenceError if invalid.
    """
    s = str(raw_id).strip()
    if not s:
        raise InvalidAssetReferenceError("Asset identifier cannot be empty.")

    # Reject directory traversals and path separators
    if ".." in s or s.startswith(("/", "\\")) or "\\" in s or "/" in s:
        raise InvalidAssetReferenceError(f"Arbitrary filesystem paths or traversals rejected: {raw_id!r}")

    # Reject Windows drive letters (e.g. C:, D:)
    if re.match(r"^[a-zA-Z]:", s):
        raise InvalidAssetReferenceError(f"Drive letter filesystem paths rejected: {raw_id!r}")


def normalize_asset_id(raw_id: str) -> Tuple[Optional[str], str]:
    """Parse prefix and clean UUID from an asset identity string.
    
    Returns (prefix, clean_id), where prefix is 'dl', 'gv', or None.
    """
    validate_asset_identifier_safety(raw_id)
    s = str(raw_id).strip()
    if s.startswith("dl:"):
        return "dl", s[3:]
    if s.startswith("downloaded:"):
        return "dl", s[11:]
    if s.startswith("gv:"):
        return "gv", s[3:]
    if s.startswith("generated:"):
        return "gv", s[10:]
    return None, s


def determine_path_media_type(p: Path) -> Optional[str]:
    """Return primary media type ('video', 'audio', 'image') based on file extension."""
    if not p:
        return None
    ext = p.suffix.lower()
    if ext in VIDEO_EXTENSIONS:
        return "video"
    if ext in AUDIO_EXTENSIONS:
        return "audio"
    if ext in IMAGE_EXTENSIONS:
        return "image"
    return None


async def resolve_asset_record_and_path(
    asset_id: str,
    db: Optional[AsyncSession] = None,
    must_exist: bool = True,
    user_id: Optional[str] = None,
    project_id: Optional[str] = None,
    expected_media_type: Optional[str] = None,
) -> Tuple[str, Path, Dict[str, Any]]:
    """Resolve an asset ID to its (canonical_key, Path, metadata_dict).
    
    canonical_key: 'dl:<uuid>' or 'gv:<uuid>'
    
    Guarantees:
    - Rejects path traversals and arbitrary filesystem locations.
    - Enforces ownership/user authorization boundary.
    - Validates compatible media type if requested ('video', 'audio', 'image').
    - Verifies physical file existence on disk when must_exist=True.
    
    Raises:
        InvalidAssetReferenceError: on path injection or illegal characters.
        AssetAccessError: on authorization/scope violations.
        AssetTypeMismatchError: on incompatible media type.
        AssetNotFoundError: if record or physical file is missing.
    """
    prefix, clean_id = normalize_asset_id(asset_id)
    
    async def _lookup(session: AsyncSession):
        dv = None
        gv = None
        
        if prefix == "dl":
            dv = (await session.execute(select(DownloadedVideo).where(DownloadedVideo.id == clean_id))).scalar_one_or_none()
        elif prefix == "gv":
            gv = (await session.execute(select(GeneratedVideo).where(GeneratedVideo.id == clean_id))).scalar_one_or_none()
        else:
            # No prefix: check DownloadedVideo first, then GeneratedVideo
            dv = (await session.execute(select(DownloadedVideo).where(DownloadedVideo.id == clean_id))).scalar_one_or_none()
            if not dv:
                gv = (await session.execute(select(GeneratedVideo).where(GeneratedVideo.id == clean_id))).scalar_one_or_none()
                
        if dv:
            # Authorization / user scope check
            if user_id and dv.user_id and dv.user_id != user_id and user_id != "local" and dv.user_id != "local":
                raise AssetAccessError(
                    f"Asset '{asset_id}' belongs to user '{dv.user_id}', unauthorized for caller '{user_id}'."
                )

            path_str = dv.video_path
            p = Path(path_str) if path_str else None
            
            # Select target path based on expected media type
            if expected_media_type == "audio" and dv.audio_path:
                audio_p = Path(dv.audio_path)
                if audio_p.is_file():
                    p = audio_p

            if must_exist and (not p or not p.is_file()):
                raise AssetNotFoundError(f"Downloaded video file missing from disk for asset '{asset_id}': {p}")

            # Media type compatibility validation
            if expected_media_type:
                actual_type = determine_path_media_type(p)
                # Video files can provide both video and audio streams
                if expected_media_type == "audio" and actual_type == "video":
                    pass  # Video with audio stream is compatible
                elif actual_type != expected_media_type:
                    raise AssetTypeMismatchError(
                        f"Asset '{asset_id}' media type '{actual_type}' is incompatible with expected type '{expected_media_type}'."
                    )

            meta = {
                "id": dv.id,
                "canonical_key": f"dl:{dv.id}",
                "type": "downloaded",
                "media_type": determine_path_media_type(p) or "video",
                "title": dv.title or "Video",
                "duration": dv.duration_seconds or 0.0,
                "user_id": dv.user_id,
            }
            return f"dl:{dv.id}", p, meta
            
        if gv:
            # Authorization / user scope check
            if user_id and gv.user_id and gv.user_id != user_id and user_id != "local" and gv.user_id != "local":
                raise AssetAccessError(
                    f"Asset '{asset_id}' belongs to user '{gv.user_id}', unauthorized for caller '{user_id}'."
                )

            # Project scope check (if explicitly bound to a project)
            if project_id and gv.project_id and gv.project_id != project_id:
                raise AssetAccessError(
                    f"Asset '{asset_id}' is scoped to project '{gv.project_id}', unauthorized for project '{project_id}'."
                )

            path_str = gv.video_path
            p = Path(path_str) if path_str else None

            if expected_media_type == "audio" and gv.audio_path:
                audio_p = Path(gv.audio_path)
                if audio_p.is_file():
                    p = audio_p

            if must_exist and (not p or not p.is_file()):
                raise AssetNotFoundError(f"Generated video file missing from disk for asset '{asset_id}': {p}")

            # Media type compatibility validation
            if expected_media_type:
                actual_type = determine_path_media_type(p)
                if expected_media_type == "audio" and actual_type == "video":
                    pass
                elif actual_type != expected_media_type:
                    raise AssetTypeMismatchError(
                        f"Asset '{asset_id}' media type '{actual_type}' is incompatible with expected type '{expected_media_type}'."
                    )

            meta = {
                "id": gv.id,
                "canonical_key": f"gv:{gv.id}",
                "type": "generated",
                "media_type": determine_path_media_type(p) or "video",
                "title": gv.title or "Video",
                "duration": gv.duration_seconds or 0.0,
                "aspect_ratio": gv.aspect_ratio,
                "user_id": gv.user_id,
                "project_id": gv.project_id,
            }
            return f"gv:{gv.id}", p, meta
            
        raise AssetNotFoundError(f"Media asset '{asset_id}' not found in database.")

    if db is not None:
        return await _lookup(db)
    else:
        async with AsyncSessionLocal() as session:
            return await _lookup(session)
