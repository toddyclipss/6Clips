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
    if s.startswith("trk:"):
        return "trk", s[4:]
    if s.startswith("track:"):
        return "trk", s[6:]
    if s.startswith("music:"):
        return "trk", s[6:]
    if s.startswith("sfx:"):
        return "sfx", s[4:]
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
        
        from backend.config import settings
        music_dir = settings.STORAGE_ROOT / "music"
        sfx_dir = settings.STORAGE_ROOT / "sfx"

        if prefix in ("trk", "sfx"):
            base_dir = music_dir if prefix == "trk" else sfx_dir
            target_path = (base_dir / clean_id).resolve()
            if not target_path.exists():
                for ext in (".mp3", ".wav", ".aac", ".m4a", ".ogg", ".flac"):
                    alt = (base_dir / f"{clean_id}{ext}").resolve()
                    if alt.exists():
                        target_path = alt
                        break

            if target_path.exists() and target_path.is_file() and target_path.is_relative_to(base_dir.resolve()):
                clean_title = target_path.stem.replace("_", " ").title()
                from backend.services.video_utils import probe_duration
                probed_dur = probe_duration(target_path, default=30.0 if prefix == "trk" else 1.0)
                meta = {
                    "id": clean_id,
                    "canonical_key": f"{prefix}:{clean_id}",
                    "type": "audio",
                    "media_type": "audio",
                    "title": clean_title,
                    "duration": probed_dur,
                    "user_id": user_id or "local",
                }
                return f"{prefix}:{clean_id}", target_path, meta
            if must_exist:
                raise AssetNotFoundError(f"Audio asset '{clean_id}' not found in {prefix} directory: {target_path}")

        if prefix == "dl":
            dv = (await session.execute(select(DownloadedVideo).where(DownloadedVideo.id == clean_id))).scalar_one_or_none()
        elif prefix == "gv":
            gv = (await session.execute(select(GeneratedVideo).where(GeneratedVideo.id == clean_id))).scalar_one_or_none()
        elif prefix == "job":
            from backend.models.job import Job
            job = (await session.execute(select(Job).where(Job.id == clean_id))).scalar_one_or_none()
            if job and job.output_json:
                try:
                    out = json.loads(job.output_json)
                    file_str = (out or {}).get("file")
                    if file_str:
                        from backend.api.videos import _safe_resolve_path
                        p = _safe_resolve_path(file_str)
                        if p and (not must_exist or p.is_file()):
                            m_type = determine_path_media_type(p) or "video"
                            meta = {
                                "id": job.id,
                                "canonical_key": f"job:{job.id}",
                                "type": "job",
                                "media_type": m_type,
                                "title": job.title or "Job Output",
                                "duration": 0.0,
                                "user_id": job.user_id,
                            }
                            return f"job:{job.id}", p, meta
                except Exception:
                    pass
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

        # Fallback for un-prefixed audio names (e.g. corporate_motivational.mp3)
        m_path = (music_dir / clean_id).resolve()
        if not m_path.exists() and not clean_id.endswith(".mp3"):
            m_path = (music_dir / f"{clean_id}.mp3").resolve()
        if m_path.exists() and m_path.is_file() and m_path.is_relative_to(music_dir.resolve()):
            clean_title = m_path.stem.replace("_", " ").title()
            meta = {
                "id": clean_id,
                "canonical_key": f"trk:{clean_id}",
                "type": "audio",
                "media_type": "audio",
                "title": clean_title,
                "duration": 30.0,
                "user_id": user_id or "local",
            }
            return f"trk:{clean_id}", m_path, meta

        s_path = (sfx_dir / clean_id).resolve()
        if not s_path.exists() and not clean_id.endswith(".mp3"):
            s_path = (sfx_dir / f"{clean_id}.mp3").resolve()
        if s_path.exists() and s_path.is_file() and s_path.is_relative_to(sfx_dir.resolve()):
            clean_title = s_path.stem.replace("_", " ").title()
            meta = {
                "id": clean_id,
                "canonical_key": f"sfx:{clean_id}",
                "type": "audio",
                "media_type": "audio",
                "title": clean_title,
                "duration": 1.0,
                "user_id": user_id or "local",
            }
            return f"sfx:{clean_id}", s_path, meta

        # Fallback for storage-relative paths (e.g. videos/foo.mp4)
        storage_bases = [settings.STORAGE_ROOT]
        if hasattr(settings, "DATA_DIR") and settings.DATA_DIR:
            storage_bases.append(settings.DATA_DIR / "storage")
        for base in storage_bases:
            direct_p = (base / clean_id).resolve()
            if direct_p.exists() and direct_p.is_file() and direct_p.is_relative_to(base.resolve()):
                clean_title = direct_p.stem.replace("_", " ").title()
                m_type = determine_path_media_type(direct_p) or "video"
                from backend.services.video_utils import probe_duration
                probed = probe_duration(direct_p, default=0.0)
                meta = {
                    "id": clean_id,
                    "canonical_key": f"file:{clean_id}",
                    "type": m_type,
                    "media_type": m_type,
                    "title": clean_title,
                    "duration": probed,
                    "user_id": user_id or "local",
                }
                return f"file:{clean_id}", direct_p, meta
            
        raise AssetNotFoundError(f"Media asset '{asset_id}' not found in database or library audio.")

    if db is not None:
        return await _lookup(db)
    else:
        async with AsyncSessionLocal() as session:
            return await _lookup(session)
