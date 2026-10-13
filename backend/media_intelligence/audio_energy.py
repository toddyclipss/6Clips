# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Audio energy, loudness dynamics, and silence detection engine."""

import asyncio
import logging
import math
import struct
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class AudioWindow:
    start_seconds: float
    end_seconds: float
    rms_db: float
    is_silent: bool
    is_high_energy: bool


@dataclass
class AudioEnergyProfile:
    duration_seconds: float
    mean_rms_db: float
    peak_rms_db: float
    dynamic_range_db: float
    is_silent: bool
    windows: List[AudioWindow] = field(default_factory=list)
    silence_intervals: List[Tuple[float, float]] = field(default_factory=list)
    high_energy_intervals: List[Tuple[float, float]] = field(default_factory=list)

    def energy_in_range(self, start_s: float, end_s: float) -> float:
        """Compute average RMS dB across windows overlapping [start_s, end_s]."""
        matching = [
            w.rms_db for w in self.windows
            if w.end_seconds > start_s and w.start_seconds < end_s
        ]
        if not matching:
            return self.mean_rms_db
        return sum(matching) / len(matching)

    def silence_ratio_in_range(self, start_s: float, end_s: float) -> float:
        """Compute fraction of range duration spent in silence."""
        dur = max(0.001, end_s - start_s)
        silent_dur = 0.0
        for s_start, s_end in self.silence_intervals:
            overlap_start = max(start_s, s_start)
            overlap_end = min(end_s, s_end)
            if overlap_end > overlap_start:
                silent_dur += (overlap_end - overlap_start)
        return min(1.0, silent_dur / dur)


def _compute_rms_from_pcm(raw_bytes: bytes) -> float:
    """Compute normalized RMS (0.0 to 1.0) from 16-bit signed little-endian PCM."""
    if not raw_bytes:
        return 0.0
    num_samples = len(raw_bytes) // 2
    if num_samples == 0:
        return 0.0
    # Unpack 16-bit signed shorts
    samples = struct.unpack(f"<{num_samples}h", raw_bytes[:num_samples * 2])
    sum_sq = sum(s * s for s in samples)
    rms_int = math.sqrt(sum_sq / num_samples)
    return rms_int / 32768.0


def _rms_to_db(rms: float) -> float:
    """Convert normalized RMS (0.0 - 1.0) to dBFS (-100.0 to 0.0)."""
    if rms <= 1e-5:
        return -100.0
    return round(20.0 * math.log10(rms), 2)


def analyze_audio_energy_sync(
    media_path: Path,
    sample_rate: int = 8000,
    window_sec: float = 1.0,
    silence_threshold_db: float = -45.0,
) -> AudioEnergyProfile:
    """Synchronously extract audio energy profile by decoding downsampled PCM via FFmpeg."""
    if not media_path.exists():
        return AudioEnergyProfile(
            duration_seconds=0.0,
            mean_rms_db=-100.0,
            peak_rms_db=-100.0,
            dynamic_range_db=0.0,
            is_silent=True,
        )

    bytes_per_sample = 2  # 16-bit
    channels = 1          # mono
    bytes_per_sec = sample_rate * channels * bytes_per_sample
    window_bytes = int(window_sec * bytes_per_sec)

    cmd = [
        "ffmpeg",
        "-v", "error",
        "-i", str(media_path),
        "-vn", "-sn", "-dn",
        "-ac", str(channels),
        "-ar", str(sample_rate),
        "-f", "s16le",
        "pipe:1",
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        raw_audio, stderr_bytes = proc.communicate(timeout=60)
    except Exception as e:
        logger.warning("Audio energy extraction process error for %s: %s", media_path.name, e)
        return AudioEnergyProfile(
            duration_seconds=0.0,
            mean_rms_db=-100.0,
            peak_rms_db=-100.0,
            dynamic_range_db=0.0,
            is_silent=True,
        )

    total_len = len(raw_audio)
    if total_len == 0:
        return AudioEnergyProfile(
            duration_seconds=0.0,
            mean_rms_db=-100.0,
            peak_rms_db=-100.0,
            dynamic_range_db=0.0,
            is_silent=True,
        )

    total_duration = total_len / bytes_per_sec
    windows: List[AudioWindow] = []
    offset = 0
    curr_time = 0.0

    while offset < total_len:
        chunk = raw_audio[offset:offset + window_bytes]
        chunk_dur = len(chunk) / bytes_per_sec
        rms = _compute_rms_from_pcm(chunk)
        rms_db = _rms_to_db(rms)
        is_sil = rms_db <= silence_threshold_db

        windows.append(AudioWindow(
            start_seconds=round(curr_time, 2),
            end_seconds=round(curr_time + chunk_dur, 2),
            rms_db=rms_db,
            is_silent=is_sil,
            is_high_energy=False,
        ))

        offset += window_bytes
        curr_time += chunk_dur

    if not windows:
        return AudioEnergyProfile(
            duration_seconds=total_duration,
            mean_rms_db=-100.0,
            peak_rms_db=-100.0,
            dynamic_range_db=0.0,
            is_silent=True,
        )

    all_dbs = [w.rms_db for w in windows]
    mean_db = round(sum(all_dbs) / len(all_dbs), 2)
    peak_db = round(max(all_dbs), 2)
    dynamic_range = round(peak_db - mean_db, 2)
    is_overall_silent = mean_db <= -65.0 or all(w.is_silent for w in windows)

    # Flag high energy (e.g. at least 3 dB above mean and above silence floor)
    high_threshold = max(mean_db + 2.5, silence_threshold_db + 10.0)
    high_energy_intervals: List[Tuple[float, float]] = []
    silence_intervals: List[Tuple[float, float]] = []

    current_high_start: Optional[float] = None
    current_sil_start: Optional[float] = None

    for w in windows:
        if w.rms_db >= high_threshold:
            w.is_high_energy = True
            if current_high_start is None:
                current_high_start = w.start_seconds
        else:
            if current_high_start is not None:
                high_energy_intervals.append((current_high_start, w.start_seconds))
                current_high_start = None

        if w.is_silent:
            if current_sil_start is None:
                current_sil_start = w.start_seconds
        else:
            if current_sil_start is not None:
                silence_intervals.append((current_sil_start, w.start_seconds))
                current_sil_start = None

    if current_high_start is not None:
        high_energy_intervals.append((current_high_start, total_duration))
    if current_sil_start is not None:
        silence_intervals.append((current_sil_start, total_duration))

    return AudioEnergyProfile(
        duration_seconds=round(total_duration, 2),
        mean_rms_db=mean_db,
        peak_rms_db=peak_db,
        dynamic_range_db=dynamic_range,
        is_silent=is_overall_silent,
        windows=windows,
        silence_intervals=silence_intervals,
        high_energy_intervals=high_energy_intervals,
    )


async def analyze_audio_energy(
    media_path: Path,
    sample_rate: int = 8000,
    window_sec: float = 1.0,
    silence_threshold_db: float = -45.0,
) -> AudioEnergyProfile:
    """Asynchronously extract audio energy profile."""
    return await asyncio.to_thread(
        analyze_audio_energy_sync,
        media_path,
        sample_rate,
        window_sec,
        silence_threshold_db,
    )
