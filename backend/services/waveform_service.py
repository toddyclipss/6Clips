# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Audio waveform extraction and peak caching service.

Extracts authentic amplitude peaks from media files using ffmpeg downsampled PCM,
cached by (filepath, mtime, points) to deliver instantaneous, real waveform geometry.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import struct
import subprocess
from pathlib import Path
from typing import Sequence

from backend.config import settings

logger = logging.getLogger(__name__)

# In-memory cache for fast repeat access: (file_path_str, mtime, points) -> list[float]
_PEAK_CACHE: dict[tuple[str, float, int], list[float]] = {}

WAVEFORM_CACHE_DIR = settings.STORAGE_ROOT / "cache" / "waveforms"


def _cache_file_for(path: Path, mtime: float, points: int) -> Path:
    WAVEFORM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = f"{path.resolve()}:{mtime}:{points}".encode("utf-8")
    digest = hashlib.sha256(key).hexdigest()
    return WAVEFORM_CACHE_DIR / f"{digest}.json"


def extract_audio_peaks(path: Path, points: int = 46) -> list[float]:
    """Extract normalized amplitude peak envelope (0.05..1.0) from an audio file.

    Parameters:
        path: Path to the audio file on disk.
        points: Number of discrete peak bars to return (default 46).

    Returns:
        A list of floating point values between 0.05 and 1.0 representing authentic
        peak amplitude across equal-duration windows of the audio stream.
    """
    if not path.is_file():
        return [0.0] * points

    try:
        st = path.stat()
        mtime = st.st_mtime
    except OSError:
        return [0.0] * points

    mem_key = (str(path.resolve()), mtime, points)
    if mem_key in _PEAK_CACHE:
        return _PEAK_CACHE[mem_key]

    disk_cache = _cache_file_for(path, mtime, points)
    if disk_cache.is_file():
        try:
            data = json.loads(disk_cache.read_text(encoding="utf-8"))
            if isinstance(data, list) and len(data) == points:
                _PEAK_CACHE[mem_key] = data
                return data
        except Exception:
            pass

    # Extract downsampled mono 16-bit PCM at 4000 Hz via ffmpeg
    cmd = [
        "ffmpeg",
        "-nostdin",
        "-y",
        "-i",
        str(path.resolve()),
        "-ac",
        "1",
        "-ar",
        "4000",
        "-f",
        "s16le",
        "-",
    ]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=15.0,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("ffmpeg audio peak extraction failed for %s: %s", path, exc)
        fallback = [0.0] * points
        _PEAK_CACHE[mem_key] = fallback
        return fallback

    raw_pcm = proc.stdout
    num_samples = len(raw_pcm) // 2

    if num_samples == 0:
        fallback = [0.0] * points
        _PEAK_CACHE[mem_key] = fallback
        return fallback

    # Unpack 16-bit signed integers
    samples = struct.unpack(f"<{num_samples}h", raw_pcm)

    chunk_size = max(1, math.floor(num_samples / points))
    peaks: list[float] = []

    for i in range(points):
        start_idx = i * chunk_size
        end_idx = min(num_samples, (i + 1) * chunk_size) if i < points - 1 else num_samples
        if start_idx >= num_samples:
            peaks.append(0.0)
            continue

        window = samples[start_idx:end_idx]
        if not window:
            peaks.append(0.0)
            continue

        # Peak amplitude in window (0..32768)
        max_val = max(abs(s) for s in window)
        norm = max_val / 32768.0
        peaks.append(round(min(1.0, max(0.0, norm)), 4))

    # Normalize/scale only if there is audible signal (global_max >= 0.01)
    global_max = max(peaks) if peaks else 0.0
    if 0.01 <= global_max < 0.5:
        scale = 0.8 / global_max
        peaks = [round(min(1.0, max(0.0, p * scale)), 4) for p in peaks]

    # Save to disk cache
    try:
        disk_cache.write_text(json.dumps(peaks), encoding="utf-8")
    except OSError:
        pass

    _PEAK_CACHE[mem_key] = peaks
    return peaks
