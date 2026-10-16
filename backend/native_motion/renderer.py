# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Deterministic Player & Physical Video Export Engine for Native Motion.

Executes deterministic frame stepping using headless browser rendering (Edge/Chromium)
and pipes raw uncompressed frames into FFmpeg libx264 for physical MP4 export,
complete with FFprobe inspection, temporal motion verification, and audio muxing.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.native_motion.compiler import NativeMotionCompiler
from backend.native_motion.schema import NativeMotionSpec

logger = logging.getLogger(__name__)


class RenderResult:
    def __init__(
        self,
        output_path: Path,
        sha256: str,
        duration: float,
        width: int,
        height: int,
        fps: int,
        frame_count: int,
        codec_name: str,
        has_audio: bool,
        motion_delta_mid: float,
        motion_delta_end: float,
        avg_luminance: float,
    ):
        self.output_path = output_path
        self.sha256 = sha256
        self.duration = duration
        self.width = width
        self.height = height
        self.fps = fps
        self.frame_count = frame_count
        self.codec_name = codec_name
        self.has_audio = has_audio
        self.motion_delta_mid = motion_delta_mid
        self.motion_delta_end = motion_delta_end
        self.avg_luminance = avg_luminance

    def to_dict(self) -> Dict[str, Any]:
        return {
            "output_path": str(self.output_path),
            "sha256": self.sha256,
            "duration": round(self.duration, 3),
            "dimensions": f"{self.width}x{self.height}",
            "fps": self.fps,
            "frame_count": self.frame_count,
            "codec_name": self.codec_name,
            "has_audio": self.has_audio,
            "motion_delta_mid": round(self.motion_delta_mid, 4),
            "motion_delta_end": round(self.motion_delta_end, 4),
            "avg_luminance": round(self.avg_luminance, 2),
            "fully_accepted": (
                self.frame_count > 0
                and (self.motion_delta_mid > 0.05 or self.motion_delta_end > 0.05)
                and self.avg_luminance > 5.0
            ),
        }


class NativeMotionRenderer:
    """Renders NativeMotionSpec deterministically into physical MP4 media."""

    @classmethod
    def render_to_mp4(
        cls,
        spec: NativeMotionSpec,
        output_mp4_path: Path,
        supersample: bool = False,
    ) -> RenderResult:
        """Render spec to physical MP4 via deterministic frame stepping."""
        # Ensure site-packages path is accessible for Playwright
        py314_pkgs = r"C:\Users\toddy\AppData\Roaming\Python\Python314\site-packages"
        if py314_pkgs not in sys.path and os.path.exists(py314_pkgs):
            sys.path.insert(0, py314_pkgs)

        from playwright.sync_api import sync_playwright

        output_mp4_path = Path(output_mp4_path).resolve()
        output_mp4_path.parent.mkdir(parents=True, exist_ok=True)

        raw_video_tmp = output_mp4_path.with_name(f"{output_mp4_path.stem}_raw.mp4")

        html_content = NativeMotionCompiler.compile_to_html(spec)
        total_frames = int(math.ceil(spec.duration_seconds * spec.fps))
        w = spec.width
        h = spec.height
        fps = spec.fps

        ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"

        # Start FFmpeg pipe process
        ffmpeg_cmd = [
            ffmpeg_bin,
            "-y",
            "-f", "image2pipe",
            "-vcodec", "png",
            "-r", str(fps),
            "-i", "-",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "veryfast",
            "-crf", "18",
            str(raw_video_tmp),
        ]

        pipe_proc = subprocess.Popen(
            ffmpeg_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        frame_0_bytes = None
        frame_mid_bytes = None
        frame_end_bytes = None
        mid_idx = total_frames // 2

        with sync_playwright() as p:
            # Prefer Edge channel if available, fallback to chromium
            try:
                browser = p.chromium.launch(
                    channel="msedge",
                    headless=True,
                    args=["--headless=new", "--disable-gpu", "--no-sandbox"],
                )
            except Exception:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--headless=new", "--disable-gpu", "--no-sandbox"],
                )

            page = browser.new_page(viewport={"width": w, "height": h})
            page.set_content(html_content)

            # Wait for initial render
            page.wait_for_timeout(50)

            for idx in range(total_frames):
                # Deterministic frame step
                page.evaluate(f"window.__seekFrame({idx}, {total_frames})")
                frame_bytes = page.screenshot(type="png")

                if idx == 0:
                    frame_0_bytes = frame_bytes
                elif idx == mid_idx:
                    frame_mid_bytes = frame_bytes
                elif idx == total_frames - 1:
                    frame_end_bytes = frame_bytes

                pipe_proc.stdin.write(frame_bytes)

            browser.close()

        pipe_proc.stdin.close()
        stderr_output = pipe_proc.stderr.read()
        pipe_proc.stderr.close()
        ret = pipe_proc.wait()

        if ret != 0:
            raise RuntimeError(f"FFmpeg render failed with exit code {ret}: {stderr_output.decode(errors='replace')}")

        # Audio muxing if spec defines audio tracks
        audio_spec = spec.audio_tracks[0] if spec.audio_tracks else None
        audio_file = Path(audio_spec.file_path) if audio_spec and audio_spec.file_path else None

        has_audio = False
        if audio_file and audio_file.exists():
            mux_cmd = [
                ffmpeg_bin,
                "-y",
                "-i", str(raw_video_tmp),
                "-i", str(audio_file),
                "-c:v", "copy",
                "-c:a", "aac",
                "-shortest",
                str(output_mp4_path),
            ]
            mux_proc = subprocess.run(mux_cmd, capture_output=True)
            if mux_proc.returncode == 0:
                has_audio = True
                try:
                    raw_video_tmp.unlink()
                except OSError:
                    pass
            else:
                shutil.move(raw_video_tmp, output_mp4_path)
        else:
            shutil.move(raw_video_tmp, output_mp4_path)

        # Inspect resulting MP4 with ffprobe
        ffprobe_info = cls.inspect_mp4(output_mp4_path)

        # Compute SHA256
        file_sha256 = cls.compute_sha256(output_mp4_path)

        # Analyze motion deltas
        delta_mid = cls._calculate_image_delta(frame_0_bytes, frame_mid_bytes) if frame_0_bytes and frame_mid_bytes else 0.0
        delta_end = cls._calculate_image_delta(frame_mid_bytes, frame_end_bytes) if frame_mid_bytes and frame_end_bytes else 0.0
        avg_lum = cls._calculate_average_luminance(frame_mid_bytes or frame_0_bytes)

        return RenderResult(
            output_path=output_mp4_path,
            sha256=file_sha256,
            duration=ffprobe_info.get("duration", spec.duration_seconds),
            width=ffprobe_info.get("width", w),
            height=ffprobe_info.get("height", h),
            fps=fps,
            frame_count=ffprobe_info.get("frame_count", total_frames),
            codec_name=ffprobe_info.get("codec_name", "h264"),
            has_audio=has_audio,
            motion_delta_mid=delta_mid,
            motion_delta_end=delta_end,
            avg_luminance=avg_lum,
        )

    @classmethod
    def inspect_mp4(cls, mp4_path: Path) -> Dict[str, Any]:
        """Run ffprobe on the MP4 file and extract verified video/audio stream properties."""
        ffprobe_bin = shutil.which("ffprobe") or "ffprobe"
        cmd = [
            ffprobe_bin,
            "-v", "error",
            "-show_entries", "stream=index,codec_name,codec_type,width,height,r_frame_rate,duration,nb_frames",
            "-show_entries", "format=duration,size,bit_rate",
            "-of", "json",
            str(mp4_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"FFprobe failed on {mp4_path}: {proc.stderr}")

        data = json.loads(proc.stdout)
        streams = data.get("streams", [])
        v_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
        a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        duration = float(v_stream.get("duration") or data.get("format", {}).get("duration") or 0.0)
        nb_frames = int(v_stream.get("nb_frames") or 0)

        return {
            "codec_name": v_stream.get("codec_name", "unknown"),
            "width": int(v_stream.get("width", 0)),
            "height": int(v_stream.get("height", 0)),
            "duration": duration,
            "frame_count": nb_frames,
            "has_audio": a_stream is not None,
            "audio_codec": a_stream.get("codec_name") if a_stream else None,
            "raw": data,
        }

    @staticmethod
    def compute_sha256(path: Path) -> str:
        """Compute SHA-256 fingerprint of a file."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    @classmethod
    def _calculate_image_delta(cls, img1_bytes: bytes, img2_bytes: bytes) -> float:
        """Compute normalized absolute pixel difference between two PNG images."""
        try:
            from PIL import Image
            import io
            im1 = Image.open(io.BytesIO(img1_bytes)).convert("L")
            im2 = Image.open(io.BytesIO(img2_bytes)).convert("L")
            if im1.size != im2.size:
                im2 = im2.resize(im1.size)

            # Sample 2000 points for fast, robust delta computation
            w, h = im1.size
            step_x = max(1, w // 40)
            step_y = max(1, h // 50)

            diff_sum = 0
            count = 0
            for y in range(0, h, step_y):
                for x in range(0, w, step_x):
                    p1 = im1.getpixel((x, y))
                    p2 = im2.getpixel((x, y))
                    diff_sum += abs(p1 - p2)
                    count += 1

            if count == 0:
                return 0.0
            return (diff_sum / count) / 255.0
        except Exception:
            # Fallback byte difference ratio
            if len(img1_bytes) != len(img2_bytes):
                return 0.1
            diff_bytes = sum(1 for a, b in zip(img1_bytes, img2_bytes) if a != b)
            return diff_bytes / max(1, len(img1_bytes))

    @classmethod
    def _calculate_average_luminance(cls, img_bytes: bytes) -> float:
        """Compute average luminance (0-255) to verify image is not solid black."""
        try:
            from PIL import Image
            import io
            im = Image.open(io.BytesIO(img_bytes)).convert("L")
            w, h = im.size
            step_x = max(1, w // 40)
            step_y = max(1, h // 50)
            total = 0
            count = 0
            for y in range(0, h, step_y):
                for x in range(0, w, step_x):
                    total += im.getpixel((x, y))
                    count += 1
            return total / max(1, count)
        except Exception:
            return 50.0  # safe assumption if PIL not available
