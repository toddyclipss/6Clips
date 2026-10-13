# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Deterministic render manifest builder and worker compatibility layer.

Maps Motion Graphics timeline documents to strongly-typed deterministic render manifests.
Features:
- Exact frame calculations (timeline & source in/out frames)
- Time scale & speed multiplier retime calculations
- Track mute/solo isolation matrix
- Multiline caption structure preservation
- Advanced framing presets with worker readiness flags
- Deterministic canonical SHA-256 manifest hash
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class FramingPreset(str, Enum):
    """Supported framing choices in Motion Studio."""
    CENTER_CROP = "center_crop"
    GAMEPLAY_RETICLE = "gameplay_reticle"
    HUD_AWARE_BLUR = "hud_aware_blur"
    SPLIT_FACECAM_GAMEPLAY = "split_facecam_gameplay"
    FIT_LETTERBOX = "fit_letterbox"


# Presets currently natively handled by backend/media_pipeline/clip_renderer.py
WORKER_SUPPORTED_PRESETS: Set[str] = {FramingPreset.CENTER_CROP.value}


@dataclass
class FramingFilterConfig:
    """Filter description and worker readiness for an aspect framing preset."""
    preset: str
    target_width: int = 1080
    target_height: int = 1920
    worker_supported: bool = False
    ffmpeg_filter: str = ""
    unsupported_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RenderClip:
    """Single audiovisual or graphic clip placed on the render timeline."""
    id: str
    track_id: str
    type: str  # "video", "audio", "image", "captions", "block"
    asset_id: Optional[str] = None
    asset_file: Optional[str] = None
    stream_url: Optional[str] = None
    title: str = "Clip"
    timeline_start_seconds: float = 0.0
    timeline_duration_seconds: float = 0.0
    timeline_end_seconds: float = 0.0
    source_trim_start: float = 0.0
    source_trim_end: float = 0.0
    speed_multiplier: float = 1.0
    source_in_frame: int = 0
    source_out_frame: int = 0
    timeline_in_frame: int = 0
    timeline_out_frame: int = 0
    volume: float = 1.0
    muted: bool = False
    caption_text: Optional[str] = None
    caption_lines: List[str] = field(default_factory=list)
    manual_transcript_override: bool = False
    framing: Optional[FramingFilterConfig] = None
    z_index: int = 0

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        if self.framing:
            res["framing"] = self.framing.to_dict()
        return res


@dataclass
class RenderAudioMix:
    """Channel gain, mute, and solo configuration for a single track."""
    track_id: str
    track_name: str
    gain: float = 1.0
    is_muted: bool = False
    is_solo: bool = False
    effective_active: bool = True
    effective_gain: float = 1.0
    clips_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RenderCaptionSegment:
    """Subtitle / caption block with line-break preservation and frame timing."""
    clip_id: str
    text: str
    lines: List[str]
    start_seconds: float
    end_seconds: float
    start_frame: int
    end_frame: int
    manual_override: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RenderTrack:
    """Timeline track containing ordered clips."""
    id: str
    type: str  # "video", "audio", "captions", "graphics", "components"
    name: str
    muted: bool = False
    solo: bool = False
    volume: float = 1.0
    layer_order: int = 0
    clips: List[RenderClip] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "muted": self.muted,
            "solo": self.solo,
            "volume": self.volume,
            "layer_order": self.layer_order,
            "clips": [c.to_dict() for c in self.clips],
        }


@dataclass
class RenderManifest:
    """Deterministic typed render manifest consumed by media pipeline workers."""
    manifest_version: str = "1.0.0"
    project_id: str = "proj_default"
    revision: int = 1
    fps: float = 30.0
    width: int = 1080
    height: int = 1920
    aspect_ratio: str = "9:16"
    total_duration_seconds: float = 0.0
    total_frames: int = 0
    tracks: List[RenderTrack] = field(default_factory=list)
    audio_mix: List[RenderAudioMix] = field(default_factory=list)
    caption_segments: List[RenderCaptionSegment] = field(default_factory=list)
    worker_compatibility: Dict[str, Any] = field(default_factory=dict)
    manifest_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manifest_version": self.manifest_version,
            "project_id": self.project_id,
            "revision": self.revision,
            "fps": self.fps,
            "width": self.width,
            "height": self.height,
            "aspect_ratio": self.aspect_ratio,
            "total_duration_seconds": self.total_duration_seconds,
            "total_frames": self.total_frames,
            "tracks": [t.to_dict() for t in self.tracks],
            "audio_mix": [am.to_dict() for am in self.audio_mix],
            "caption_segments": [cs.to_dict() for cs in self.caption_segments],
            "worker_compatibility": self.worker_compatibility,
            "manifest_hash": self.manifest_hash,
        }

    def compute_hash(self) -> str:
        """Compute deterministic SHA-256 hash of canonical manifest representation."""
        data = self.to_dict()
        data.pop("manifest_hash", None)
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _resolve_aspect_dimensions(aspect_ratio: str) -> Tuple[int, int]:
    """Resolve standard canvas dimensions for an aspect ratio string."""
    normalized = (aspect_ratio or "9:16").strip()
    if normalized == "16:9":
        return 1920, 1080
    elif normalized == "1:1":
        return 1080, 1080
    elif normalized == "4:5":
        return 1080, 1350
    # Default vertical short-form
    return 1080, 1920


def _build_framing_filter_config(
    preset_name: Optional[str],
    target_w: int = 1080,
    target_h: int = 1920,
) -> FramingFilterConfig:
    """Build framing filter configuration with explicit worker readiness."""
    preset = (preset_name or FramingPreset.CENTER_CROP.value).lower().strip()

    if preset == FramingPreset.CENTER_CROP.value:
        return FramingFilterConfig(
            preset=preset,
            target_width=target_w,
            target_height=target_h,
            worker_supported=True,
            ffmpeg_filter=f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h}",
            unsupported_reason=None,
        )
    elif preset == FramingPreset.GAMEPLAY_RETICLE.value:
        return FramingFilterConfig(
            preset=preset,
            target_width=target_w,
            target_height=target_h,
            worker_supported=False,
            ffmpeg_filter=(
                f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h},"
                f"drawbox=x=(iw-200)/2:y=(ih-200)/2:w=200:h=200:color=cyan@0.4:t=2"
            ),
            unsupported_reason=(
                "Worker backend/media_pipeline/clip_renderer.py lacks implementation for 'gameplay_reticle'. "
                "Requires INTEGRATION_REQUEST for reticle coordinate detection and overlay."
            ),
        )
    elif preset == FramingPreset.HUD_AWARE_BLUR.value:
        return FramingFilterConfig(
            preset=preset,
            target_width=target_w,
            target_height=target_h,
            worker_supported=False,
            ffmpeg_filter=(
                f"split[bg][fg];[bg]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
                f"crop={target_w}:{target_h},boxblur=20:5[blurred];[fg]scale={target_w}:-1[sharp];"
                f"[blurred][sharp]overlay=(W-w)/2:(H-h)/2"
            ),
            unsupported_reason=(
                "Worker backend/media_pipeline/clip_renderer.py lacks implementation for 'hud_aware_blur'. "
                "Requires INTEGRATION_REQUEST for split background blur filter graph."
            ),
        )
    elif preset == FramingPreset.SPLIT_FACECAM_GAMEPLAY.value:
        cam_h = int(target_h * 0.33)
        game_h = target_h - cam_h
        return FramingFilterConfig(
            preset=preset,
            target_width=target_w,
            target_height=target_h,
            worker_supported=False,
            ffmpeg_filter=(
                f"split[cam][game];[cam]crop=iw:ih*0.33:0:0,scale={target_w}:{cam_h}[top];"
                f"[game]crop=iw:ih*0.67:0:ih*0.33,scale={target_w}:{game_h}[bot];"
                f"[top][bot]vstack"
            ),
            unsupported_reason=(
                "Worker backend/media_pipeline/clip_renderer.py lacks implementation for 'split_facecam_gameplay'. "
                "Requires INTEGRATION_REQUEST for dual-ROI crop and vstack filter graph."
            ),
        )
    elif preset == FramingPreset.FIT_LETTERBOX.value:
        return FramingFilterConfig(
            preset=preset,
            target_width=target_w,
            target_height=target_h,
            worker_supported=True,
            ffmpeg_filter=f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2",
            unsupported_reason=None,
        )
    else:
        # Unknown preset, fallback to center crop with warning
        return FramingFilterConfig(
            preset=preset,
            target_width=target_w,
            target_height=target_h,
            worker_supported=False,
            ffmpeg_filter=f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h}",
            unsupported_reason=f"Unknown framing preset '{preset}'. Defaulting to center crop fallback.",
        )


def build_render_manifest(
    document: Dict[str, Any],
    project_id: str = "proj_default",
    revision: int = 1,
    options: Optional[Dict[str, Any]] = None,
) -> RenderManifest:
    """Build a deterministic, strongly-typed render manifest from a timeline document.

    Args:
        document: Canonical project document containing timeline, tracks, and clips.
        project_id: Unique project identifier.
        revision: Document revision number.
        options: Optional overrides (fps, aspect_ratio, framing_preset).

    Returns:
        RenderManifest with exact frame numbers, audio mix matrix, multiline captions,
        framing presets, and deterministic hash.
    """
    options = options or {}
    timeline = document.get("timeline") or {}
    raw_tracks = timeline.get("tracks") or []

    # 1. Canvas & Framerate Resolution
    aspect_ratio = options.get("aspect_ratio") or document.get("aspect_ratio") or "9:16"
    width, height = _resolve_aspect_dimensions(aspect_ratio)
    fps = float(options.get("fps") or document.get("fps") or 30.0)

    # 2. Track Solo / Mute Evaluation
    has_solo = any(bool(t.get("solo")) for t in raw_tracks if (t.get("type") or "video") == "audio")

    # 3. Process Tracks, Clips, and Audio Mix
    manifest_tracks: List[RenderTrack] = []
    audio_mix: List[RenderAudioMix] = []
    caption_segments: List[RenderCaptionSegment] = []
    unsupported_features: List[str] = []

    max_end_seconds = 0.0

    for t_idx, raw_t in enumerate(raw_tracks):
        t_id = raw_t.get("id") or f"track_{t_idx}"
        t_type = (raw_t.get("type") or "video").lower()
        t_name = raw_t.get("name") or f"{t_type.capitalize()} {t_idx + 1}"
        t_muted = bool(raw_t.get("muted", False))
        t_solo = bool(raw_t.get("solo", False))
        t_vol = float(raw_t.get("volume", 1.0))
        t_order = int(raw_t.get("layer_order", raw_t.get("order", t_idx)))

        # Audio mix active resolution
        if t_type == "audio":
            if has_solo:
                effective_active = t_solo and not t_muted
            else:
                effective_active = not t_muted
            effective_gain = t_vol if effective_active else 0.0

            audio_mix.append(
                RenderAudioMix(
                    track_id=t_id,
                    track_name=t_name,
                    gain=t_vol,
                    is_muted=t_muted,
                    is_solo=t_solo,
                    effective_active=effective_active,
                    effective_gain=effective_gain,
                    clips_count=len(raw_t.get("clips") or []),
                )
            )

        render_clips: List[RenderClip] = []

        for c_idx, raw_c in enumerate(raw_t.get("clips") or []):
            c_id = raw_c.get("id") or f"clip_{t_id}_{c_idx}"
            c_type = (raw_c.get("type") or t_type).lower()
            start_s = max(0.0, float(raw_c.get("timeline_start_seconds", raw_c.get("start_seconds", 0.0))))
            dur_s = max(0.05, float(raw_c.get("timeline_duration_seconds", raw_c.get("duration_seconds", raw_c.get("duration", 3.0)))))
            end_s = start_s + dur_s
            if end_s > max_end_seconds:
                max_end_seconds = end_s

            trim_start = max(0.0, float(raw_c.get("source_trim_start", raw_c.get("trim_start", 0.0))))
            speed = float(raw_c.get("speed_multiplier", raw_c.get("speed", 1.0)))
            if speed <= 0:
                speed = 1.0

            # Source duration read is duration_seconds scaled by speed multiplier
            source_dur_needed = dur_s * speed
            trim_end = float(raw_c.get("trim_end", trim_start + source_dur_needed))

            # Exact frame calculations at document FPS
            t_in_frame = int(round(start_s * fps))
            t_out_frame = int(round(end_s * fps))
            s_in_frame = int(round(trim_start * fps))
            s_out_frame = int(round((trim_start + source_dur_needed) * fps))

            # Framing Preset resolution
            clip_framing_preset = (
                raw_c.get("framing_preset")
                or options.get("framing_preset")
                or document.get("framing_preset")
                or FramingPreset.CENTER_CROP.value
            )
            framing_cfg = None
            if c_type in ("video", "image"):
                framing_cfg = _build_framing_filter_config(clip_framing_preset, width, height)
                if not framing_cfg.worker_supported:
                    unsupported_features.append(f"clip:{c_id}:framing:{framing_cfg.preset}")

            # Captions / Multiline handling
            caption_raw = raw_c.get("caption_text")
            caption_lines: List[str] = []
            if caption_raw is not None:
                # Preserve multiline structure without stripping line breaks
                caption_lines = str(caption_raw).split("\n")

            is_manual_override = bool(raw_c.get("manual_transcript_override", False))

            if c_type in ("captions", "caption") or caption_raw is not None:
                caption_segments.append(
                    RenderCaptionSegment(
                        clip_id=c_id,
                        text=caption_raw or "",
                        lines=caption_lines,
                        start_seconds=start_s,
                        end_seconds=end_s,
                        start_frame=t_in_frame,
                        end_frame=t_out_frame,
                        manual_override=is_manual_override,
                    )
                )

            r_clip = RenderClip(
                id=c_id,
                track_id=t_id,
                type=c_type,
                asset_id=raw_c.get("asset_id"),
                asset_file=raw_c.get("asset_file") or raw_c.get("source_path") or raw_c.get("source"),
                stream_url=raw_c.get("stream_url"),
                title=raw_c.get("title") or f"Clip {c_id}",
                timeline_start_seconds=round(start_s, 4),
                timeline_duration_seconds=round(dur_s, 4),
                timeline_end_seconds=round(end_s, 4),
                source_trim_start=round(trim_start, 4),
                source_trim_end=round(trim_end, 4),
                speed_multiplier=round(speed, 4),
                source_in_frame=s_in_frame,
                source_out_frame=s_out_frame,
                timeline_in_frame=t_in_frame,
                timeline_out_frame=t_out_frame,
                volume=float(raw_c.get("volume", 1.0)),
                muted=bool(raw_c.get("muted", False)),
                caption_text=caption_raw,
                caption_lines=caption_lines,
                manual_transcript_override=is_manual_override,
                framing=framing_cfg,
                z_index=t_order,
            )
            render_clips.append(r_clip)

        manifest_tracks.append(
            RenderTrack(
                id=t_id,
                type=t_type,
                name=t_name,
                muted=t_muted,
                solo=t_solo,
                volume=t_vol,
                layer_order=t_order,
                clips=render_clips,
            )
        )

    total_duration = round(max_end_seconds, 4)
    total_frames = int(round(total_duration * fps))

    # Worker compatibility report
    worker_ready = len(unsupported_features) == 0
    worker_compat = {
        "all_features_worker_ready": worker_ready,
        "supported_presets": sorted(list(WORKER_SUPPORTED_PRESETS)),
        "unsupported_features_detected": unsupported_features,
        "worker_engine": "backend/media_pipeline/clip_renderer.py",
        "requires_integration_request": not worker_ready,
    }

    manifest = RenderManifest(
        manifest_version="1.0.0",
        project_id=project_id,
        revision=revision,
        fps=fps,
        width=width,
        height=height,
        aspect_ratio=aspect_ratio,
        total_duration_seconds=total_duration,
        total_frames=total_frames,
        tracks=manifest_tracks,
        audio_mix=audio_mix,
        caption_segments=caption_segments,
        worker_compatibility=worker_compat,
    )

    manifest.manifest_hash = manifest.compute_hash()
    return manifest
