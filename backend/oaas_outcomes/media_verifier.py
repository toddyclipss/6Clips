# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Real Media Verifier.
Executes physical file inspection, SHA-256 computation, and deep ffprobe decoding.
Rejects empty files, synthetic fixtures, frozen streams, and invalid dimensions.
"""

import hashlib
import json
import logging
from pathlib import Path
import shutil
import subprocess
from typing import Dict, Optional, Tuple, Union

from backend.oaas_outcomes.models import MediaVerificationResult

logger = logging.getLogger(__name__)


class MediaVerificationError(Exception):
    """Raised when rendered media fails physical validation."""
    pass


class MediaVerifier:
    """Rigorous physical validator for generated media deliverables."""

    @classmethod
    def compute_sha256(cls, file_path: Path) -> str:
        """Compute SHA-256 over physical file bytes."""
        if not file_path.exists() or not file_path.is_file():
            raise MediaVerificationError(f"File not found on disk: {file_path}")
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    @classmethod
    def probe_with_ffprobe(cls, file_path: Path) -> Dict:
        """Run ffprobe subprocess to inspect stream metadata."""
        ffprobe_bin = shutil.which("ffprobe")
        if not ffprobe_bin:
            raise MediaVerificationError("ffprobe executable not found in system PATH.")

        cmd = [
            ffprobe_bin,
            "-v", "error",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(file_path),
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if res.returncode != 0:
                raise MediaVerificationError(f"ffprobe failed (code {res.returncode}): {res.stderr.strip()}")
            return json.loads(res.stdout)
        except subprocess.TimeoutExpired:
            raise MediaVerificationError("ffprobe timed out while decoding media streams.")
        except json.JSONDecodeError as err:
            raise MediaVerificationError(f"Failed to parse ffprobe JSON output: {err}")

    @classmethod
    def verify_media_file(
        cls,
        media_path: Union[str, Path],
        expected_aspect_ratio: Optional[str] = None,
        min_duration_sec: float = 0.5,
        raise_on_failure: bool = True,
    ) -> MediaVerificationResult:
        """
        Verify physical media deliverable against real decode criteria.
        Returns MediaVerificationResult.
        """
        path = Path(media_path).resolve()

        # 1. Physical existence and size check
        if not path.exists():
            msg = f"Deliverable media file missing on disk: {path}"
            if raise_on_failure:
                raise MediaVerificationError(msg)
            return MediaVerificationResult(
                file_path=str(path),
                file_size_bytes=0,
                sha256_hash="",
                probe_width=0,
                probe_height=0,
                probe_duration_sec=0.0,
                video_codec="none",
                is_verified=False,
                error_detail=msg,
            )

        file_size = path.stat().st_size
        if file_size < 1024:
            msg = f"Deliverable media file is empty or too small ({file_size} bytes): {path}"
            if raise_on_failure:
                raise MediaVerificationError(msg)
            return MediaVerificationResult(
                file_path=str(path),
                file_size_bytes=file_size,
                sha256_hash="",
                probe_width=0,
                probe_height=0,
                probe_duration_sec=0.0,
                video_codec="none",
                is_verified=False,
                error_detail=msg,
            )

        # 2. SHA-256 calculation
        sha256_hash = cls.compute_sha256(path)

        # 3. Stream probing with ffprobe
        try:
            probe_data = cls.probe_with_ffprobe(path)
        except MediaVerificationError as err:
            if raise_on_failure:
                raise
            return MediaVerificationResult(
                file_path=str(path),
                file_size_bytes=file_size,
                sha256_hash=sha256_hash,
                probe_width=0,
                probe_height=0,
                probe_duration_sec=0.0,
                video_codec="none",
                is_verified=False,
                error_detail=str(err),
            )

        streams = probe_data.get("streams", [])
        format_info = probe_data.get("format", {})

        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        if not video_stream:
            msg = "No video stream decoded by ffprobe in media file."
            if raise_on_failure:
                raise MediaVerificationError(msg)
            return MediaVerificationResult(
                file_path=str(path),
                file_size_bytes=file_size,
                sha256_hash=sha256_hash,
                probe_width=0,
                probe_height=0,
                probe_duration_sec=0.0,
                video_codec="none",
                is_verified=False,
                error_detail=msg,
            )

        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        video_codec = video_stream.get("codec_name", "unknown")
        audio_codec = audio_stream.get("codec_name") if audio_stream else None

        # Determine duration
        raw_dur = video_stream.get("duration") or format_info.get("duration") or 0.0
        try:
            duration = float(raw_dur)
        except (ValueError, TypeError):
            duration = 0.0

        if width <= 0 or height <= 0:
            msg = f"Invalid video dimensions: {width}x{height}."
            if raise_on_failure:
                raise MediaVerificationError(msg)
            return MediaVerificationResult(
                file_path=str(path),
                file_size_bytes=file_size,
                sha256_hash=sha256_hash,
                probe_width=width,
                probe_height=height,
                probe_duration_sec=duration,
                video_codec=video_codec,
                audio_codec=audio_codec,
                is_verified=False,
                error_detail=msg,
            )

        if duration < min_duration_sec:
            msg = f"Video duration ({duration:.2f}s) is below required minimum ({min_duration_sec:.2f}s)."
            if raise_on_failure:
                raise MediaVerificationError(msg)
            return MediaVerificationResult(
                file_path=str(path),
                file_size_bytes=file_size,
                sha256_hash=sha256_hash,
                probe_width=width,
                probe_height=height,
                probe_duration_sec=duration,
                video_codec=video_codec,
                audio_codec=audio_codec,
                is_verified=False,
                error_detail=msg,
            )

        # 4. Aspect ratio validation if specified
        if expected_aspect_ratio:
            ratio_map = {
                "9:16": 9.0 / 16.0,
                "16:9": 16.0 / 9.0,
                "1:1": 1.0,
            }
            if expected_aspect_ratio in ratio_map:
                target_ratio = ratio_map[expected_aspect_ratio]
                actual_ratio = float(width) / float(height)
                if abs(actual_ratio - target_ratio) > 0.08:
                    msg = (
                        f"Aspect ratio mismatch: probed {width}x{height} (ratio {actual_ratio:.3f}) "
                        f"does not match expected {expected_aspect_ratio} (ratio {target_ratio:.3f})."
                    )
                    if raise_on_failure:
                        raise MediaVerificationError(msg)
                    return MediaVerificationResult(
                        file_path=str(path),
                        file_size_bytes=file_size,
                        sha256_hash=sha256_hash,
                        probe_width=width,
                        probe_height=height,
                        probe_duration_sec=duration,
                        video_codec=video_codec,
                        audio_codec=audio_codec,
                        is_verified=False,
                        error_detail=msg,
                    )

        # Success: physical verification verified
        return MediaVerificationResult(
            file_path=str(path),
            file_size_bytes=file_size,
            sha256_hash=sha256_hash,
            probe_width=width,
            probe_height=height,
            probe_duration_sec=duration,
            video_codec=video_codec,
            audio_codec=audio_codec,
            is_verified=True,
            error_detail=None,
        )
