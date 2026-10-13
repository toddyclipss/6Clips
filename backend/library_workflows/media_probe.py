# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Media Probe: physical byte inspection, container/codec validation, and metadata extraction."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class MediaProbeError(Exception):
    """Base error for media probing failures."""
    pass


class MissingMediaError(MediaProbeError):
    """Raised when file does not physically exist on disk."""
    pass


class CorruptedMediaError(MediaProbeError):
    """Raised when media header/streams are corrupted or malformed."""
    pass


class UnrecognizedMediaError(MediaProbeError):
    """Raised when bytes do not match any recognized media container."""
    pass


@dataclass
class MediaStreamInfo:
    stream_type: str  # "video", "audio", "image"
    codec_name: str
    duration_seconds: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    bitrate_kbps: Optional[int] = None


@dataclass
class MediaProbeResult:
    file_path: str
    file_size_bytes: int
    file_size_mb: float
    sha256_hash: str
    container_format: str
    mime_type: str
    media_category: str  # "video", "audio", "image"
    duration_seconds: float
    aspect_ratio: Optional[str]  # e.g. "9:16", "16:9"
    width: Optional[int]
    height: Optional[int]
    streams: List[MediaStreamInfo]
    has_audio: bool
    has_video: bool

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


def detect_magic_container(header_bytes: bytes) -> Tuple[str, str, str]:
    """
    Inspect initial magic bytes to determine genuine container format and MIME type.
    Returns: (container_name, mime_type, media_category)
    Raises UnrecognizedMediaError if format is not supported media.
    """
    if len(header_bytes) < 4:
        raise UnrecognizedMediaError("File is too small to contain valid media headers.")

    # ISO BMFF / MP4 / QuickTime: check offset 4-12 for 'ftyp'
    if len(header_bytes) >= 12 and header_bytes[4:8] == b"ftyp":
        brand = header_bytes[8:12]
        if brand in (b"qt  ", b"moov"):
            return "mov", "video/quicktime", "video"
        return "mp4", "video/mp4", "video"

    # Matroska / WebM EBML header \x1a\x45\xdf\xa3
    if header_bytes.startswith(b"\x1a\x45\xdf\xa3"):
        # If 'webm' string exists in header
        if b"webm" in header_bytes[:64].lower():
            return "webm", "video/webm", "video"
        return "mkv", "video/x-matroska", "video"

    # RIFF containers (WAV, WEBP, AVI)
    if header_bytes.startswith(b"RIFF") and len(header_bytes) >= 12:
        riff_type = header_bytes[8:12]
        if riff_type == b"WAVE":
            return "wav", "audio/wav", "audio"
        elif riff_type == b"WEBP":
            return "webp", "image/webp", "image"
        elif riff_type == b"AVI ":
            return "avi", "video/x-msvideo", "video"

    # MP3: ID3 tag or MPEG sync frames \xff\xfb, \xff\xf3, \xff\xf2
    if header_bytes.startswith(b"ID3") or (
        len(header_bytes) >= 2 and header_bytes[0] == 0xFF and (header_bytes[1] & 0xE0) == 0xE0
    ):
        return "mp3", "audio/mpeg", "audio"

    # FLAC: 'fLaC'
    if header_bytes.startswith(b"fLaC"):
        return "flac", "audio/flac", "audio"

    # Ogg container: 'OggS'
    if header_bytes.startswith(b"OggS"):
        return "ogg", "audio/ogg", "audio"

    # PNG: \x89PNG\r\n\x1a\n
    if header_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", "image/png", "image"

    # JPEG: \xff\xd8\xff
    if header_bytes.startswith(b"\xff\xd8\xff"):
        return "jpeg", "image/jpeg", "image"

    # GIF: GIF87a / GIF89a
    if header_bytes.startswith(b"GIF87a") or header_bytes.startswith(b"GIF89a"):
        return "gif", "image/gif", "image"

    raise UnrecognizedMediaError(
        f"Unrecognized or unsupported media header bytes: {header_bytes[:8].hex()}"
    )


def compute_file_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of entire physical file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def probe_with_ffprobe(file_path: Path) -> Dict[str, Any]:
    """Execute ffprobe synchronously and parse stream metadata JSON."""
    ffprobe_bin = shutil.which("ffprobe")
    if not ffprobe_bin:
        logger.warning("ffprobe not found in system PATH.")
        return {}

    cmd = [
        ffprobe_bin,
        "-v", "error",
        "-show_format",
        "-show_streams",
        "-print_format", "json",
        str(file_path),
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10.0)
        if proc.returncode != 0:
            logger.debug("ffprobe exited with non-zero status: %s", proc.stderr)
            return {}
        return json.loads(proc.stdout)
    except Exception as e:
        logger.debug("ffprobe execution failed for %s: %s", file_path, e)
        return {}


def calculate_aspect_ratio(width: Optional[int], height: Optional[int]) -> Optional[str]:
    """Compute normalized aspect ratio label (e.g. 9:16, 16:9, 1:1)."""
    if not width or not height or width <= 0 or height <= 0:
        return None
    ratio = width / height
    if 0.55 <= ratio <= 0.58:  # 9/16 = 0.5625
        return "9:16"
    elif 1.76 <= ratio <= 1.80:  # 16/9 = 1.777
        return "16:9"
    elif 0.98 <= ratio <= 1.02:
        return "1:1"
    elif 0.78 <= ratio <= 0.82:  # 4/5
        return "4:5"
    return f"{width}:{height}"


def probe_media_file(file_path: Path) -> MediaProbeResult:
    """
    Perform deep physical verification and stream probing on a media file.
    Validates physical existence, container magic bytes, SHA-256 hash, and ffprobe streams.
    """
    if not file_path.exists():
        raise MissingMediaError(f"Media file physically missing on disk: {file_path}")
    if not file_path.is_file():
        raise MissingMediaError(f"Path is not a regular file: {file_path}")

    file_size = file_path.stat().st_size
    if file_size == 0:
        raise CorruptedMediaError("Media file is empty (0 bytes).")

    # Read first 128 bytes to check magic headers
    with open(file_path, "rb") as f:
        header = f.read(128)

    container, mime_type, category = detect_magic_container(header)
    sha256 = compute_file_sha256(file_path)

    # Stream probe
    ff_data = probe_with_ffprobe(file_path)
    streams_raw = ff_data.get("streams", [])
    format_raw = ff_data.get("format", {})

    parsed_streams: List[MediaStreamInfo] = []
    width: Optional[int] = None
    height: Optional[int] = None
    has_audio = False
    has_video = False
    duration = 0.0

    # Read format duration if available
    try:
        duration = float(format_raw.get("duration", 0.0))
    except (ValueError, TypeError):
        duration = 0.0

    for st in streams_raw:
        codec_type = st.get("codec_type")
        codec_name = st.get("codec_name", "unknown")
        st_duration = None
        try:
            if "duration" in st:
                st_duration = float(st["duration"])
                if duration == 0.0 and st_duration > 0.0:
                    duration = st_duration
        except (ValueError, TypeError):
            pass

        if codec_type == "video":
            has_video = True
            st_w = st.get("width")
            st_h = st.get("height")
            if st_w and st_h:
                width = int(st_w)
                height = int(st_h)
            parsed_streams.append(
                MediaStreamInfo(
                    stream_type="video",
                    codec_name=codec_name,
                    duration_seconds=st_duration,
                    width=width,
                    height=height,
                )
            )
        elif codec_type == "audio":
            has_audio = True
            parsed_streams.append(
                MediaStreamInfo(
                    stream_type="audio",
                    codec_name=codec_name,
                    duration_seconds=st_duration,
                    sample_rate=int(st.get("sample_rate", 0)) or None,
                    channels=int(st.get("channels", 0)) or None,
                )
            )

    if not has_video and category == "video":
        has_video = True
    if not has_audio and category == "audio":
        has_audio = True

    aspect = calculate_aspect_ratio(width, height)

    return MediaProbeResult(
        file_path=str(file_path.resolve()),
        file_size_bytes=file_size,
        file_size_mb=round(file_size / (1024 * 1024), 2),
        sha256_hash=sha256,
        container_format=container,
        mime_type=mime_type,
        media_category=category,
        duration_seconds=round(duration, 3),
        aspect_ratio=aspect,
        width=width,
        height=height,
        streams=parsed_streams,
        has_audio=has_audio,
        has_video=has_video,
    )
