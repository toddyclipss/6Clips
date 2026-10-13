# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Scene transition, frozen video, and black frame detection engine."""

import asyncio
import logging
import re
import subprocess
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)


def detect_scene_changes_sync(
    media_path: Path,
    threshold: float = 0.3,
    max_duration_seconds: float = 600.0,
) -> List[float]:
    """Detect scene cut timestamps using FFmpeg scene score filter."""
    if not media_path.exists():
        return []

    # Use select filter to find frames where scene change score exceeds threshold
    cmd = [
        "ffmpeg",
        "-v", "info",
        "-i", str(media_path),
        "-vf", f"select='gt(scene,{threshold})',metadata=print",
        "-vsync", "vfr",
        "-t", str(max_duration_seconds),
        "-f", "null",
        "NUL" if subprocess.os.name == "nt" else "/dev/null",
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    except Exception as e:
        logger.warning("Scene change detection failed on %s: %s", media_path.name, e)
        return []

    timestamps: List[float] = []
    # Pattern for pts_time in ffmpeg metadata print output
    pts_pattern = re.compile(r"pts_time:([0-9]+(?:\.[0-9]+)?)")
    for line in res.stderr.splitlines():
        match = pts_pattern.search(line)
        if match:
            try:
                t = round(float(match.group(1)), 2)
                if not timestamps or (t - timestamps[-1]) >= 1.0:  # de-bounce within 1s
                    timestamps.append(t)
            except Exception:
                pass

    return timestamps


def detect_frozen_frames_sync(
    media_path: Path,
    noise: float = 0.003,
    min_duration: float = 2.0,
) -> List[Tuple[float, float]]:
    """Detect intervals where video frames are frozen / static."""
    if not media_path.exists():
        return []

    cmd = [
        "ffmpeg",
        "-v", "info",
        "-i", str(media_path),
        "-vf", f"freezedetect=n={noise}:d={min_duration}",
        "-an",
        "-f", "null",
        "NUL" if subprocess.os.name == "nt" else "/dev/null",
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except Exception as e:
        logger.warning("Frozen frame detection error on %s: %s", media_path.name, e)
        return []

    frozen: List[Tuple[float, float]] = []
    start_pattern = re.compile(r"freeze_start:\s*([0-9]+(?:\.[0-9]+)?)")
    end_pattern = re.compile(r"freeze_end:\s*([0-9]+(?:\.[0-9]+)?)")

    current_start = None
    final_time = 0.0
    time_pattern = re.compile(r"time=([0-9]{2}):([0-9]{2}):([0-9]+(?:\.[0-9]+)?)")

    for line in res.stderr.splitlines():
        t_match = time_pattern.search(line)
        if t_match:
            try:
                final_time = (
                    float(t_match.group(1)) * 3600
                    + float(t_match.group(2)) * 60
                    + float(t_match.group(3))
                )
            except Exception:
                pass

        start_match = start_pattern.search(line)
        if start_match:
            try:
                current_start = float(start_match.group(1))
            except Exception:
                pass
            continue

        end_match = end_pattern.search(line)
        if end_match and current_start is not None:
            try:
                end_val = float(end_match.group(1))
                frozen.append((round(current_start, 2), round(end_val, 2)))
                current_start = None
            except Exception:
                pass

    if current_start is not None:
        freeze_end = final_time if final_time > current_start else (current_start + min_duration)
        frozen.append((round(current_start, 2), round(freeze_end, 2)))

    return frozen


def detect_black_frames_sync(
    media_path: Path,
    min_duration: float = 1.0,
    pic_th: float = 0.98,
    pix_th: float = 0.10,
) -> List[Tuple[float, float]]:
    """Detect intervals of black frames."""
    if not media_path.exists():
        return []

    cmd = [
        "ffmpeg",
        "-v", "info",
        "-i", str(media_path),
        "-vf", f"blackdetect=d={min_duration}:pic_th={pic_th}:pix_th={pix_th}",
        "-an",
        "-f", "null",
        "NUL" if subprocess.os.name == "nt" else "/dev/null",
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except Exception as e:
        logger.warning("Black frame detection error on %s: %s", media_path.name, e)
        return []

    blacks: List[Tuple[float, float]] = []
    start_pattern = re.compile(r"black_start:([0-9]+(?:\.[0-9]+)?)")
    end_pattern = re.compile(r"black_end:([0-9]+(?:\.[0-9]+)?)")

    for line in res.stderr.splitlines():
        start_match = start_pattern.search(line)
        end_match = end_pattern.search(line)
        if start_match and end_match:
            try:
                s = float(start_match.group(1))
                e = float(end_match.group(1))
                blacks.append((round(s, 2), round(e, 2)))
            except Exception:
                pass

    return blacks


async def detect_scene_changes(
    media_path: Path,
    threshold: float = 0.3,
    max_duration_seconds: float = 600.0,
) -> List[float]:
    return await asyncio.to_thread(
        detect_scene_changes_sync,
        media_path,
        threshold,
        max_duration_seconds,
    )


async def detect_frozen_frames(
    media_path: Path,
    noise: float = 0.003,
    min_duration: float = 2.0,
) -> List[Tuple[float, float]]:
    return await asyncio.to_thread(
        detect_frozen_frames_sync,
        media_path,
        noise,
        min_duration,
    )


async def detect_black_frames(
    media_path: Path,
    min_duration: float = 1.0,
    pic_th: float = 0.98,
    pix_th: float = 0.10,
) -> List[Tuple[float, float]]:
    return await asyncio.to_thread(
        detect_black_frames_sync,
        media_path,
        min_duration,
        pic_th,
        pix_th,
    )
