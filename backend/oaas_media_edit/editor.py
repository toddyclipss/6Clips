# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Native Media Editor for 6Clips Source-Backed Outcome Video Rendering.

Transforms genuine acquired source video footage into physically verifiable MP4 deliverables:
- 9:16 vertical reframe with background blur and crisp foreground action
- 16:9 widescreen and 1:1 square aspect ratio transformations
- Accurate temporal trimming matching user-specified duration
- Preservation of synchronized source audio tracks
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
import subprocess
from typing import Any, Dict, Optional, Tuple

from backend.config import settings
from .models import EditExistingMediaContract

logger = logging.getLogger(__name__)


class NativeMediaEditor:
    """Executes deterministic physical video rendering from authentic source footage."""

    @classmethod
    def compute_sha256(cls, file_path: Path) -> str:
        """Compute SHA-256 hash of a local file."""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    @classmethod
    def render_source_edit(
        cls,
        contract: EditExistingMediaContract,
        output_file: Optional[Path] = None,
    ) -> Tuple[Path, str, float, Tuple[int, int]]:
        """
        Execute FFmpeg transform on authentic source video.
        Returns: (rendered_path, sha256_hash, probe_duration_sec, (width, height)).
        """
        source_path = Path(contract.file_path)
        if not source_path.exists():
            raise FileNotFoundError(f"Source video not found: {source_path}")

        if output_file is None:
            out_dir = settings.STORAGE_ROOT / "rendered_edits"
            out_dir.mkdir(parents=True, exist_ok=True)
            output_file = out_dir / f"edit_{contract.asset_id}_{contract.target_aspect_ratio.replace(':', '_')}.mp4"

        output_file.parent.mkdir(parents=True, exist_ok=True)

        trim_start, trim_end = contract.source_intervals[0] if contract.source_intervals else (0.0, contract.target_duration)
        target_dur = round(trim_end - trim_start, 3)
        if target_dur <= 0:
            target_dur = contract.target_duration

        aspect = contract.target_aspect_ratio

        # Configure filtergraph for reframing
        if aspect == "9:16":
            w, h = 1080, 1920
            vf = (
                "[0:v]split=2[bg][fg];"
                f"[bg]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=20:5[bgblur];"
                f"[fg]scale={w}:{h}:force_original_aspect_ratio=decrease[fgscaled];"
                "[bgblur][fgscaled]overlay=(W-w)/2:(H-h)/2[v]"
            )
            cmd = [
                "ffmpeg", "-y",
                "-ss", f"{trim_start:.3f}",
                "-i", str(source_path),
                "-t", f"{target_dur:.3f}",
                "-filter_complex", vf,
                "-map", "[v]",
                "-map", "0:a?",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                str(output_file),
            ]
        elif aspect == "1:1":
            w, h = 1080, 1080
            vf = (
                "[0:v]split=2[bg][fg];"
                f"[bg]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=15:4[bgblur];"
                f"[fg]scale={w}:{h}:force_original_aspect_ratio=decrease[fgscaled];"
                "[bgblur][fgscaled]overlay=(W-w)/2:(H-h)/2[v]"
            )
            cmd = [
                "ffmpeg", "-y",
                "-ss", f"{trim_start:.3f}",
                "-i", str(source_path),
                "-t", f"{target_dur:.3f}",
                "-filter_complex", vf,
                "-map", "[v]",
                "-map", "0:a?",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                str(output_file),
            ]
        else:  # 16:9 widescreen or default
            w, h = 1920, 1080
            cmd = [
                "ffmpeg", "-y",
                "-ss", f"{trim_start:.3f}",
                "-i", str(source_path),
                "-t", f"{target_dur:.3f}",
                "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2",
                "-map", "0:v:0",
                "-map", "0:a?",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                str(output_file),
            ]

        logger.info("Executing FFmpeg source edit: %s (in: %.2f, out: %.2f)", output_file.name, trim_start, trim_end)
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode != 0 or not output_file.exists() or output_file.stat().st_size == 0:
            err = proc.stderr or proc.stdout
            raise RuntimeError(f"FFmpeg source edit failed: {err[:250]}")

        # Probe final rendered deliverable
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_format", "-show_streams",
            "-print_format", "json",
            str(output_file),
        ]
        probe_res = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=15)
        probe_dur = target_dur
        actual_dims = (w, h)

        if probe_res.returncode == 0:
            p_data = json.loads(probe_res.stdout)
            fmt = p_data.get("format", {})
            if "duration" in fmt:
                probe_dur = float(fmt["duration"])
            v_st = next((s for s in p_data.get("streams", []) if s.get("codec_type") == "video"), None)
            if v_st:
                actual_dims = (int(v_st.get("width", w)), int(v_st.get("height", h)))

        rendered_sha = cls.compute_sha256(output_file)
        return output_file, rendered_sha, round(probe_dur, 3), actual_dims
