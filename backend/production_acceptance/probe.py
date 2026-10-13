# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Physical Media Probe Service (Wave 7).

Provides non-transcoding inspection of media assets:
- Validates file headers and container magic bytes (MP4, WebM, WAV, QuickTime).
- Extracts streams, resolution, aspect ratio, duration, audio channels.
- Calculates SHA-256 for cryptographic deduplication.
- Detects synthetic filler (anullsrc, sine_filler, zero-byte runs, missing audio).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

from .contracts import MediaProbeMetadata

logger = logging.getLogger(__name__)


class MediaProbeService:
    """Probes physical media files safely without full decode or re-encoding."""

    @staticmethod
    def calculate_sha256(path: Path | str, chunk_size: int = 65536) -> str:
        """Calculates full SHA-256 hash of a file."""
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def check_magic_bytes(cls, path: Path | str) -> tuple[bool, str]:
        """Checks magic bytes for standard video/audio containers."""
        try:
            with open(path, "rb") as f:
                header = f.read(64)
        except Exception:
            return False, "unknown"

        if len(header) < 8:
            return False, "corrupt_truncated"

        # MP4 / MOV: offset 4 contains 'ftyp'
        if len(header) >= 8 and header[4:8] == b"ftyp":
            brand = header[8:12].decode("latin1", errors="ignore")
            return True, f"mp4/{brand}"

        # Matroska / WebM: starts with \x1a\x45\xdf\xa3
        if header.startswith(b"\x1a\x45\xdf\xa3"):
            return True, "webm"

        # RIFF / WAV: starts with RIFF and has WAVE at offset 8
        if header.startswith(b"RIFF") and len(header) >= 12 and header[8:12] == b"WAVE":
            return True, "wav"

        # QuickTime MOV alternative (moov or mdat at start)
        if len(header) >= 8 and header[4:8] in (b"moov", b"mdat"):
            return True, "mov"

        return False, "unknown"

    @classmethod
    def detect_synthetic_filler(
        cls,
        path: Path | str,
        probe: MediaProbeMetadata,
    ) -> tuple[bool, Optional[str]]:
        """
        Detects synthetic filler indicators:
        - Audio stream missing or silent null audio
        - 'anullsrc' or 'sine_filler' indicators in metadata or path
        - Large runs of all-zero bytes (>85% zeros in sample)
        """
        p_str = str(path).lower()
        if "anullsrc" in p_str or "sine_filler" in p_str or "dummy_audio" in p_str:
            return True, "Explicit synthetic filler indicator in asset identifier"

        if not probe.has_audio_stream or probe.audio_channels == 0:
            return True, "Asset lacks valid audio stream or has 0 audio channels"

        # Check for all-zero binary payloads
        try:
            file_size = os.path.getsize(path)
            if file_size > 0:
                with open(path, "rb") as f:
                    # sample up to 16KB
                    sample = f.read(min(16384, file_size))
                    zero_count = sample.count(b"\x00")
                    if len(sample) > 0 and (zero_count / len(sample)) > 0.85:
                        return True, "High null-byte density (>85%) indicative of uncompressed zero filler"
        except Exception:
            pass

        return False, None

    @classmethod
    def probe_file(cls, file_path: str | Path) -> MediaProbeMetadata:
        """
        Runs container validation and ffprobe inspection on the given media file.
        Falls back to binary inspection if ffprobe is unavailable or fails.
        """
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Media file not found: {file_path}")

        file_size = path.stat().st_size
        if file_size == 0:
            return MediaProbeMetadata(
                file_path=str(path),
                file_size_bytes=0,
                magic_bytes_valid=False,
                has_audio_stream=False,
                synthetic_filler_detected=True,
                synthetic_filler_reason="Zero-byte empty file",
            )

        sha256_hash = cls.calculate_sha256(path)
        magic_valid, detected_fmt = cls.check_magic_bytes(path)

        metadata = MediaProbeMetadata(
            file_path=str(path),
            file_size_bytes=file_size,
            sha256_hash=sha256_hash,
            magic_bytes_valid=magic_valid,
            container_format=detected_fmt,
        )

        # Run ffprobe if available
        ffprobe_data = cls._run_ffprobe(path)
        if ffprobe_data:
            cls._populate_from_ffprobe(metadata, ffprobe_data)
        else:
            # Fallback deduction based on container
            if detected_fmt.startswith("mp4") or detected_fmt == "webm" or detected_fmt == "mov":
                metadata.video_codec = "unknown"
                metadata.audio_codec = "unknown"
            elif detected_fmt == "wav":
                metadata.video_codec = None
                metadata.audio_codec = "pcm_s16le"
                metadata.has_audio_stream = True

        # Check synthetic filler
        filler_detected, filler_reason = cls.detect_synthetic_filler(path, metadata)
        metadata.synthetic_filler_detected = filler_detected
        metadata.synthetic_filler_reason = filler_reason

        return metadata

    @classmethod
    def _run_ffprobe(cls, path: Path) -> Optional[dict]:
        """Runs ffprobe on the target file returning parsed JSON, or None."""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration,size,bit_rate,format_name:stream=codec_type,codec_name,width,height,channels,sample_rate,display_aspect_ratio",
            "-of", "json",
            str(path),
        ]
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                return json.loads(res.stdout)
        except Exception as e:
            logger.debug("ffprobe failed or unavailable for %s: %s", path, e)
        return None

    @classmethod
    def _populate_from_ffprobe(cls, meta: MediaProbeMetadata, data: dict) -> None:
        """Populates metadata fields from parsed ffprobe dictionary."""
        fmt = data.get("format", {})
        try:
            meta.duration_seconds = float(fmt.get("duration", 0.0))
        except (ValueError, TypeError):
            meta.duration_seconds = 0.0

        try:
            meta.bit_rate = int(fmt.get("bit_rate", 0))
        except (ValueError, TypeError):
            meta.bit_rate = 0

        streams = data.get("streams", [])
        has_video = False
        has_audio = False

        for st in streams:
            ctype = st.get("codec_type")
            if ctype == "video" and not has_video:
                has_video = True
                meta.video_codec = st.get("codec_name")
                meta.width = int(st.get("width") or 0)
                meta.height = int(st.get("height") or 0)
                if meta.width > 0 and meta.height > 0:
                    if meta.height > meta.width:
                        meta.aspect_ratio = "9:16"
                    elif meta.width == meta.height:
                        meta.aspect_ratio = "1:1"
                    else:
                        meta.aspect_ratio = "16:9"
            elif ctype == "audio" and not has_audio:
                has_audio = True
                meta.audio_codec = st.get("codec_name")
                meta.audio_channels = int(st.get("channels") or 0)
                meta.sample_rate = int(st.get("sample_rate") or 0)

        meta.has_audio_stream = has_audio
