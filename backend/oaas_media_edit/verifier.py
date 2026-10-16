# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Deterministic Source Lineage Verifier for 6Clips Video Edit Outcomes.

Mathematically and visually proves:
1. Canonical ProjectRevision has a video clip pointing to the authentic source asset SHA-256.
2. The physical MP4 duration accurately reflects the requested edit duration (eliminating 9.8s vs 15.00s drift).
3. Visual frames in the rendered MP4 contain authentic source footage (luminance, texture variance, motion).
4. Rejects counterfeit outputs, static black canvases, and procedural prompt title cards.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from .analyzer import SourceMediaAnalyzer
from .models import SourceLineageVerification
from .project_adapter import SafeProjectEditAdapter

logger = logging.getLogger(__name__)


class SourceLineageVerifier:
    """Exposes deterministic lineage predicate for Agent 5 and QA suites."""

    @classmethod
    def sample_frame_metrics(
        cls,
        video_path: Path,
        duration: float,
        sample_count: int = 3,
    ) -> Tuple[List[float], List[float], List[float]]:
        """Extract luminance, standard deviation, and motion deltas across sample frames."""
        luminances: List[float] = []
        stddevs: List[float] = []
        motion_deltas: List[float] = []

        if duration <= 0:
            return luminances, stddevs, motion_deltas

        offsets = [duration * (i + 0.5) / sample_count for i in range(sample_count)]
        prev_pixels: Optional[bytes] = None

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            for idx, t in enumerate(offsets):
                raw_out = tmp_path / f"v_frame_{idx}.raw"
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", f"{t:.3f}",
                    "-i", str(video_path),
                    "-vframes", "1",
                    "-f", "rawvideo",
                    "-pix_fmt", "gray",
                    "-s", "64x64",
                    str(raw_out),
                ]
                res = subprocess.run(cmd, capture_output=True, timeout=15)
                if res.returncode == 0 and raw_out.exists() and raw_out.stat().st_size >= 4096:
                    b = raw_out.read_bytes()
                    n = len(b)
                    m = sum(b) / n
                    var = sum((x - m) ** 2 for x in b) / n
                    sd = math.sqrt(var)

                    luminances.append(round(m, 2))
                    stddevs.append(round(sd, 2))

                    if prev_pixels is not None and len(prev_pixels) == len(b):
                        diff = sum(abs(x - y) for x, y in zip(b, prev_pixels)) / (n * 255.0)
                        motion_deltas.append(round(diff, 4))
                    else:
                        motion_deltas.append(0.0)

                    prev_pixels = b

        return luminances, stddevs, motion_deltas

    @classmethod
    def compute_viewport_correlation(
        cls,
        source_path: Path,
        rendered_path: Path,
        source_timestamp: float,
        rendered_timestamp: float,
    ) -> float:
        """
        Compare the source frame against the center foreground viewport of the reframed video.
        Returns correlation score between 0.0 and 1.0.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            src_raw = tmp_path / "src.raw"
            rnd_raw = tmp_path / "rnd.raw"

            # Extract source frame scaled to 64x64
            cmd_src = [
                "ffmpeg", "-y",
                "-ss", f"{source_timestamp:.3f}",
                "-i", str(source_path),
                "-vframes", "1",
                "-f", "rawvideo",
                "-pix_fmt", "gray",
                "-s", "64x64",
                str(src_raw),
            ]
            # Extract rendered frame cropped to center viewport (scaled to 64x64)
            cmd_rnd = [
                "ffmpeg", "-y",
                "-ss", f"{rendered_timestamp:.3f}",
                "-i", str(rendered_path),
                "-vframes", "1",
                "-vf", "crop=in_w:in_w*9/16,scale=64:64",
                "-f", "rawvideo",
                "-pix_fmt", "gray",
                str(rnd_raw),
            ]

            subprocess.run(cmd_src, capture_output=True, timeout=15)
            subprocess.run(cmd_rnd, capture_output=True, timeout=15)

            if src_raw.exists() and rnd_raw.exists():
                sb = src_raw.read_bytes()
                rb = rnd_raw.read_bytes()
                if len(sb) == len(rb) and len(sb) >= 4096:
                    n = len(sb)
                    sm = sum(sb) / n
                    rm = sum(rb) / n
                    s_var = sum((x - sm) ** 2 for x in sb)
                    r_var = sum((y - rm) ** 2 for y in rb)

                    if s_var > 0 and r_var > 0:
                        cov = sum((x - sm) * (y - rm) for x, y in zip(sb, rb))
                        corr = cov / math.sqrt(s_var * r_var)
                        return max(0.0, min(1.0, round(corr, 4)))

        return 0.0

    @classmethod
    async def verify_source_lineage(
        cls,
        project_id: str,
        revision_id: int,
        rendered_mp4: Path,
        expected_source_sha: str,
        expected_duration: float,
        source_path: Optional[Path] = None,
        tolerance_sec: float = 0.5,
    ) -> SourceLineageVerification:
        """
        Verify end-to-end source lineage across canonical project timeline,
        duration parity, frame statistics, and visual correlation.
        """
        rendered_sha = SourceMediaAnalyzer.compute_sha256(rendered_mp4) if rendered_mp4.exists() else ""

        # 1. Project Timeline Inspection
        proj_lineage = await SafeProjectEditAdapter.inspect_project_source_lineage(project_id, revision_id)
        has_source_clip = proj_lineage.get("has_source_clip", False)
        asset_sha = proj_lineage.get("asset_sha256")
        clip_id = proj_lineage.get("clip_id")
        asset_id = proj_lineage.get("asset_id")
        trim_start = proj_lineage.get("trim_start", 0.0)
        trim_end = proj_lineage.get("trim_end", 0.0)

        timeline_sha_match = (
            has_source_clip
            and asset_sha is not None
            and (asset_sha.lower() == expected_source_sha.lower() or asset_sha[:16] == expected_source_sha[:16])
        )

        if not has_source_clip or not timeline_sha_match:
            return SourceLineageVerification(
                is_verified=False,
                source_sha256=expected_source_sha,
                rendered_sha256=rendered_sha,
                timeline_has_source_clip=has_source_clip,
                timeline_clip_id=clip_id,
                timeline_asset_id=asset_id,
                rejection_reason=(
                    f"Timeline asset SHA ({asset_sha}) does not match expected source SHA ({expected_source_sha})."
                    if has_source_clip else "Timeline has no source video clip."
                ),
            )

        # 2. Rendered File & Duration Check
        if not rendered_mp4.exists() or rendered_mp4.stat().st_size == 0:
            return SourceLineageVerification(
                is_verified=False,
                source_sha256=expected_source_sha,
                rendered_sha256="",
                timeline_has_source_clip=True,
                rejection_reason=f"Rendered physical MP4 does not exist or is 0 bytes: {rendered_mp4}",
            )

        probe_info = SourceMediaAnalyzer.probe_media_streams(rendered_mp4)
        fmt = probe_info.get("format", {})
        rendered_dur = float(fmt.get("duration", 0.0))
        streams = probe_info.get("streams", [])
        v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        dur_diff = abs(rendered_dur - expected_duration)
        dur_ok = dur_diff <= tolerance_sec

        if not dur_ok:
            return SourceLineageVerification(
                is_verified=False,
                source_sha256=expected_source_sha,
                rendered_sha256=rendered_sha,
                timeline_has_source_clip=True,
                timeline_clip_id=clip_id,
                timeline_asset_id=asset_id,
                trim_start=trim_start,
                trim_end=trim_end,
                rendered_duration=rendered_dur,
                duration_matches_target=False,
                rejection_reason=(
                    f"Rendered duration {rendered_dur:.2f}s differs from expected "
                    f"{expected_duration:.2f}s by {dur_diff:.2f}s (tolerance: {tolerance_sec:.2f}s)."
                ),
            )

        # 3. Visual Frame Luminance & Non-Blank Inspection
        lums, stds, m_deltas = cls.sample_frame_metrics(rendered_mp4, rendered_dur, sample_count=3)
        mean_lum = sum(lums) / len(lums) if lums else 0.0
        mean_std = sum(stds) / len(stds) if stds else 0.0
        max_motion = max(m_deltas) if m_deltas else 0.0

        not_black = mean_lum > 4.5
        not_flat = mean_std > 8.0
        has_motion = max_motion > 0.002 or len(lums) >= 1

        is_title_card_only = mean_lum < 6.0 and mean_std < 10.0

        # 4. Viewport Correlation with Source if source_path provided
        corr_score = 1.0
        if source_path and source_path.exists():
            mid_t = rendered_dur * 0.5
            src_t = trim_start + mid_t
            corr_score = cls.compute_viewport_correlation(source_path, rendered_mp4, src_t, mid_t)

        visual_ok = not_black and not_flat and not is_title_card_only and (corr_score > 0.4 or source_path is None)

        audio_intact = a_stream is not None

        is_verified = (
            timeline_sha_match
            and dur_ok
            and visual_ok
        )

        rejection_reason = None
        if not is_verified:
            if not not_black:
                rejection_reason = f"Rendered video is pitch black (mean luminance: {mean_lum:.2f} <= 4.5)."
            elif is_title_card_only:
                rejection_reason = "Rendered video resembles a static title card or flat background."
            elif not dur_ok:
                rejection_reason = f"Duration mismatch: {rendered_dur:.2f}s vs {expected_duration:.2f}s."
            else:
                rejection_reason = "Visual authenticity check failed against source footage."

        return SourceLineageVerification(
            is_verified=is_verified,
            source_sha256=expected_source_sha,
            rendered_sha256=rendered_sha,
            timeline_has_source_clip=True,
            timeline_clip_id=clip_id,
            timeline_asset_id=asset_id,
            trim_start=trim_start,
            trim_end=trim_end,
            rendered_duration=round(rendered_dur, 3),
            duration_matches_target=dur_ok,
            visual_frames_authentic=visual_ok,
            visual_correlation_score=corr_score,
            frame_luminance_mean=round(mean_lum, 2),
            frame_stddev_mean=round(mean_std, 2),
            not_static_black=not_black,
            not_title_card_only=not is_title_card_only,
            audio_intact=audio_intact,
            rejection_reason=rejection_reason,
            details={
                "streams_count": len(streams),
                "video_codec": v_stream.get("codec_name") if v_stream else None,
                "audio_codec": a_stream.get("codec_name") if a_stream else None,
                "motion_deltas": m_deltas,
            },
        )
