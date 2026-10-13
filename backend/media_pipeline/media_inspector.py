# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Physical media inspection, stream verification, and provenance/rights checking."""

import asyncio
import hashlib
import json
import logging
import math
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from backend.media_pipeline.models import (
    BlockerV1,
    MediaProbeV1,
    SourceAssetV1,
)

logger = logging.getLogger(__name__)

AUTHORIZED_ACQUISITION_ROUTES = frozenset({
    "local_upload",
    "authorized_fixture",
    "library_asset",
    "authorized_partner_api",
})

REQUIRED_PERMITTED_USES = frozenset({
    "clip_extraction",
})


class MediaInspectionError(Exception):
    def __init__(self, blocker: BlockerV1):
        super().__init__(blocker.precise_reason)
        self.blocker = blocker


def compute_file_sha256(filepath: Path) -> str:
    """Compute uppercase SHA-256 hex digest of file bytes."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().upper()


def inspect_source_provenance_and_rights(asset: SourceAssetV1) -> Optional[BlockerV1]:
    """Verify that source asset provenance and usage rights are genuinely permitted."""
    if asset.acquisition_route not in AUTHORIZED_ACQUISITION_ROUTES:
        return BlockerV1(
            code="UNPERMITTED_ACQUISITION_ROUTE",
            precise_reason=(
                f"Acquisition route '{asset.acquisition_route}' for asset '{asset.asset_id}' is not authorized. "
                "Autonomous downloading of unverified third-party content without confirmed ingest route is prohibited."
            ),
            next_action="Provide a local file upload or use an authorized fixture/library asset.",
        )

    uses = set(asset.permitted_uses or [])
    missing = REQUIRED_PERMITTED_USES - uses
    if missing:
        return BlockerV1(
            code="INSUFFICIENT_PERMITTED_USES",
            precise_reason=(
                f"Asset '{asset.asset_id}' lacks mandatory permitted uses: {sorted(missing)}. "
                f"Configured uses: {sorted(uses)}."
            ),
            next_action="Authorize 'clip_extraction' in asset permitted_uses before initiating production.",
        )

    return None


async def probe_physical_media(file_path: Path) -> Tuple[MediaProbeV1, Optional[BlockerV1]]:
    """Inspect physical media bytes via ffprobe and volume detection.
    
    Guarantees that audio/video streams exist and contain non-trivial data.
    """
    if not file_path.exists() or not file_path.is_file():
        blocker = BlockerV1(
            code="PHYSICAL_BYTES_MISSING",
            precise_reason=f"Media file does not exist at path: '{file_path}'.",
            next_action="Ensure the physical media file is ingested and stored in an accessible location.",
        )
        return None, blocker

    file_size = file_path.stat().st_size
    if file_size < 1024:
        blocker = BlockerV1(
            code="CORRUPT_OR_EMPTY_MEDIA",
            precise_reason=f"Media file at '{file_path}' is trivially small ({file_size} bytes).",
            next_action="Re-ingest valid, non-empty media file.",
        )
        return None, blocker

    def _sync_probe():
        # 1. ffprobe format & streams
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_format",
            "-show_streams",
            "-of", "json",
            str(file_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if res.returncode != 0:
            raise MediaInspectionError(BlockerV1(
                code="FFPROBE_PARSE_FAILED",
                precise_reason=f"ffprobe failed to inspect '{file_path.name}': {res.stderr.strip()[:200]}",
                next_action="Verify media file format and codec support.",
            ))

        data = json.loads(res.stdout)
        streams = data.get("streams", [])
        fmt = data.get("format", {})

        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        if not video_stream:
            raise MediaInspectionError(BlockerV1(
                code="MISSING_VIDEO_STREAM",
                precise_reason=f"Media file '{file_path.name}' contains no video stream.",
                next_action="Provide a video file containing a valid video stream.",
            ))

        width = int(video_stream.get("width") or 0)
        height = int(video_stream.get("height") or 0)
        if width <= 0 or height <= 0:
            raise MediaInspectionError(BlockerV1(
                code="INVALID_DIMENSIONS",
                precise_reason=f"Media file '{file_path.name}' has invalid dimensions {width}x{height}.",
                next_action="Ensure media has valid positive dimensions.",
            ))

        # Parse FPS
        r_fps = video_stream.get("r_frame_rate", "30/1")
        try:
            num, den = r_fps.split("/")
            fps = round(float(num) / float(den), 2)
        except Exception:
            fps = 30.0

        # Duration
        dur_str = fmt.get("duration") or video_stream.get("duration")
        duration = float(dur_str) if dur_str and dur_str != "N/A" else 0.0

        video_codec = video_stream.get("codec_name", "unknown")
        audio_codec = audio_stream.get("codec_name", "none") if audio_stream else "none"
        audio_channels = int(audio_stream.get("channels") or 0) if audio_stream else 0
        sample_rate = int(audio_stream.get("sample_rate") or 0) if audio_stream else 0

        # Volume detection if audio stream exists
        mean_vol = None
        is_silent = False
        if audio_stream:
            vol_cmd = [
                "ffmpeg",
                "-i", str(file_path),
                "-af", "volumedetect",
                "-vn", "-sn", "-dn",
                "-f", "null",
                "NUL" if subprocess.os.name == "nt" else "/dev/null",
            ]
            vol_res = subprocess.run(vol_cmd, capture_output=True, text=True, timeout=60)
            for line in vol_res.stderr.splitlines():
                if "mean_volume:" in line:
                    try:
                        mean_vol = float(line.split("mean_volume:")[1].split("dB")[0].strip())
                        if mean_vol <= -70.0:
                            is_silent = True
                    except Exception:
                        pass

        content_hash = compute_file_sha256(file_path)

        return MediaProbeV1(
            width=width,
            height=height,
            duration_seconds=duration,
            video_codec=video_codec,
            audio_codec=audio_codec,
            fps=fps,
            audio_channels=audio_channels,
            sample_rate=sample_rate,
            content_hash=content_hash,
            mean_volume_db=mean_vol,
            is_silent=is_silent,
            is_black=False,
        )

    try:
        probe = await asyncio.to_thread(_sync_probe)
        return probe, None
    except MediaInspectionError as mie:
        return None, mie.blocker
    except Exception as e:
        logger.exception("Unexpected error probing media: %s", e)
        return None, BlockerV1(
            code="INSPECTION_EXCEPTION",
            precise_reason=str(e),
            next_action="Check server logs and ensure media tools are healthy.",
        )
