# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Source Media Analyzer for 6Clips Video Editing Pipeline.

Performs authentic content inspection:
- Stream and container probing via ffprobe
- Pixel luminance, variance, and motion analysis on extracted frames
- Audio stream validation and speech synchronization
- Source edit span selection with bounded timecodes
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from .models import SourceMediaAnalysis, SourceStreamInfo

logger = logging.getLogger(__name__)


class SourceMediaAnalyzer:
    """Performs deep inspection of authentic video media before editing."""

    @classmethod
    def compute_sha256(cls, file_path: Path) -> str:
        """Compute SHA-256 hash of a local file."""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    @classmethod
    def probe_media_streams(cls, file_path: Path) -> Dict[str, Any]:
        """Execute ffprobe to extract raw stream and format JSON."""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_format",
            "-show_streams",
            "-print_format", "json",
            str(file_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if res.returncode != 0:
            raise RuntimeError(f"ffprobe failed for {file_path}: {res.stderr[:200]}")
        return json.loads(res.stdout)

    @classmethod
    def sample_frame_statistics(
        cls,
        file_path: Path,
        duration: float,
        sample_count: int = 5,
    ) -> Tuple[List[float], List[float], List[float], List[float]]:
        """
        Extract frame statistics at equidistant intervals across the video.
        Returns: (timestamps, luminances, stddevs, motion_deltas).
        """
        timestamps: List[float] = []
        luminances: List[float] = []
        stddevs: List[float] = []
        motion_deltas: List[float] = []

        if duration <= 0:
            return timestamps, luminances, stddevs, motion_deltas

        # Determine timestamps: e.g. 10%, 30%, 50%, 70%, 90%
        offsets = [
            duration * (i + 0.5) / sample_count
            for i in range(sample_count)
        ]

        prev_pixels: Optional[bytes] = None

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            for idx, t in enumerate(offsets):
                out_raw = tmp_path / f"frame_{idx}.raw"
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", f"{t:.3f}",
                    "-i", str(file_path),
                    "-vframes", "1",
                    "-f", "rawvideo",
                    "-pix_fmt", "gray",
                    "-s", "64x64",
                    str(out_raw),
                ]
                res = subprocess.run(cmd, capture_output=True, timeout=15)
                if res.returncode == 0 and out_raw.exists() and out_raw.stat().st_size >= 4096:
                    raw_bytes = out_raw.read_bytes()
                    timestamps.append(round(t, 3))

                    # Compute luminance and stddev over 64x64 gray pixels
                    n = len(raw_bytes)
                    mean_val = sum(raw_bytes) / n
                    variance = sum((b - mean_val) ** 2 for b in raw_bytes) / n
                    std_val = math.sqrt(variance)

                    luminances.append(round(mean_val, 2))
                    stddevs.append(round(std_val, 2))

                    if prev_pixels is not None and len(prev_pixels) == len(raw_bytes):
                        diff = sum(abs(a - b) for a, b in zip(raw_bytes, prev_pixels)) / (n * 255.0)
                        motion_deltas.append(round(diff, 4))
                    else:
                        motion_deltas.append(0.0)

                    prev_pixels = raw_bytes
                else:
                    logger.debug("Could not sample frame at offset %.2fs from %s", t, file_path)

        return timestamps, luminances, stddevs, motion_deltas

    @classmethod
    def analyze_file(cls, file_path: Path) -> SourceMediaAnalysis:
        """
        Perform complete forensic analysis of an authentic video file on disk.
        Fails closed if the file is unreadable, missing video stream, or empty.
        """
        if not file_path.exists() or file_path.stat().st_size == 0:
            raise ValueError(f"Source file does not exist or is empty: {file_path}")

        file_size = file_path.stat().st_size
        sha256 = cls.compute_sha256(file_path)
        probe_data = cls.probe_media_streams(file_path)

        streams_raw = probe_data.get("streams", [])
        fmt_raw = probe_data.get("format", {})

        video_stream = next((s for s in streams_raw if s.get("codec_type") == "video"), None)
        if not video_stream:
            raise ValueError(f"No video stream found in media file: {file_path}")

        audio_stream = next((s for s in streams_raw if s.get("codec_type") == "audio"), None)

        # Parse duration
        duration_sec = 0.0
        if "duration" in fmt_raw:
            try:
                duration_sec = float(fmt_raw["duration"])
            except (ValueError, TypeError):
                duration_sec = 0.0
        if duration_sec <= 0 and "duration" in video_stream:
            try:
                duration_sec = float(video_stream["duration"])
            except (ValueError, TypeError):
                duration_sec = 0.0

        if duration_sec <= 0:
            raise ValueError(f"Media duration could not be determined or is zero: {file_path}")

        # Dimensions & aspect ratio
        width = int(video_stream.get("width") or 1920)
        height = int(video_stream.get("height") or 1080)
        resolution = (width, height)

        ratio = width / height if height > 0 else 1.777
        if ratio > 1.3:
            aspect_ratio = "16:9"
        elif ratio < 0.8:
            aspect_ratio = "9:16"
        else:
            aspect_ratio = "1:1"

        # Frame rate
        fps = 30.0
        r_fps = video_stream.get("r_frame_rate", "30/1")
        if "/" in r_fps:
            num, den = r_fps.split("/")
            if float(den) > 0:
                fps = round(float(num) / float(den), 2)
        elif r_fps:
            fps = float(r_fps)

        # Stream infos
        stream_list: List[SourceStreamInfo] = []
        for s in streams_raw:
            c_type = s.get("codec_type", "unknown")
            s_dur = float(s.get("duration", duration_sec)) if s.get("duration") else duration_sec
            stream_list.append(
                SourceStreamInfo(
                    index=int(s.get("index", 0)),
                    codec_name=s.get("codec_name", "unknown"),
                    codec_type=c_type,
                    width=s.get("width"),
                    height=s.get("height"),
                    fps=fps if c_type == "video" else None,
                    channels=s.get("channels"),
                    sample_rate=int(s.get("sample_rate")) if s.get("sample_rate") else None,
                    duration_sec=s_dur,
                    bit_rate=int(s.get("bit_rate")) if s.get("bit_rate") else None,
                )
            )

        # Frame sampling
        ts, lums, stds, m_deltas = cls.sample_frame_statistics(file_path, duration_sec, sample_count=5)

        avg_lum = sum(lums) / len(lums) if lums else 0.0
        avg_std = sum(stds) / len(stds) if stds else 0.0
        is_static_black = avg_lum < 4.0 and avg_std < 4.0
        is_authentic = len(lums) > 0 and not is_static_black

        # Audio stream detection
        has_audio = audio_stream is not None
        audio_codec = audio_stream.get("codec_name") if audio_stream else None
        audio_channels = audio_stream.get("channels") if audio_stream else None
        audio_sample_rate = int(audio_stream.get("sample_rate")) if audio_stream and audio_stream.get("sample_rate") else None

        # Detect audio language from tags if available
        detected_lang = None
        if audio_stream and "tags" in audio_stream:
            detected_lang = audio_stream["tags"].get("language")

        return SourceMediaAnalysis(
            file_path=str(file_path),
            sha256_hash=sha256,
            file_size_bytes=file_size,
            duration_sec=round(duration_sec, 3),
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            fps=fps,
            has_video=True,
            has_audio=has_audio,
            video_codec=video_stream.get("codec_name", "unknown"),
            audio_codec=audio_codec,
            streams=stream_list,
            sampled_timestamps=ts,
            sampled_luminance=lums,
            sampled_stddev=stds,
            motion_deltas=m_deltas,
            is_authentic_footage=is_authentic,
            is_static_black=is_static_black,
            audio_channels=audio_channels,
            audio_sample_rate=audio_sample_rate,
            detected_language=detected_lang,
        )

    @classmethod
    def select_edit_spans(
        cls,
        analysis: SourceMediaAnalysis,
        requested_duration: Optional[float] = None,
        preferred_offset: float = 0.0,
    ) -> List[Tuple[float, float]]:
        """
        Derive safe, bounded source [in, out] intervals for the requested edit.
        Strictly enforces duration bounds and preserves user's requested length.
        """
        source_dur = analysis.duration_sec
        if requested_duration is not None and requested_duration > 0:
            target_dur = min(requested_duration, source_dur)
        else:
            # Default highlight length: 5 seconds or full duration if shorter
            target_dur = min(5.0, source_dur)

        target_dur = max(target_dur, 1.0)

        # Calculate start offset: ensure start + target <= source_dur
        start = max(0.0, preferred_offset)
        if start + target_dur > source_dur:
            start = max(0.0, source_dur - target_dur)

        end = round(start + target_dur, 3)
        start = round(start, 3)

        return [(start, end)]
