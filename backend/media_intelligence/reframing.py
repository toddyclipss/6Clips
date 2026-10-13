# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""9:16 reframing engine with safe-region presets and objective filtergraphs."""

from enum import Enum
from typing import Optional, Tuple


class ReframePreset(str, Enum):
    CENTER_CROP = "center_crop"
    GAMEPLAY_RETICLE = "gameplay_reticle"
    SPLIT_FACECAM_GAMEPLAY = "split_facecam_gameplay"
    HUD_AWARE_BLUR = "hud_aware_blur"


def build_reframe_filter(
    in_width: int,
    in_height: int,
    target_w: int = 1080,
    target_h: int = 1920,
    preset: str = ReframePreset.GAMEPLAY_RETICLE.value,
    custom_params: Optional[dict] = None,
) -> Tuple[str, str]:
    """Build FFmpeg video filter for reframing to target aspect ratio (9:16).
    
    Returns:
        (filtergraph, disclosure_warning)
    """
    aspect_in = in_width / in_height if in_height > 0 else (16 / 9)
    aspect_target = target_w / target_h

    # If already close to 9:16, just scale directly
    if abs(aspect_in - aspect_target) < 0.05:
        return (
            f"scale={target_w}:{target_h}",
            "Source is already 9:16 aspect ratio; scaled directly without cropping.",
        )

    # Normalize preset string
    preset_lower = (preset or ReframePreset.CENTER_CROP.value).lower()

    if preset_lower == ReframePreset.HUD_AWARE_BLUR.value:
        # Full 16:9 frame preserved with blurred background fill
        fg_height = int(round(target_w / aspect_in))
        if fg_height % 2 != 0:
            fg_height += 1
        vf = (
            f"[0:v]split=2[bg_raw][fg_raw];"
            f"[bg_raw]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h},boxblur=20:5[bg];"
            f"[fg_raw]scale={target_w}:{fg_height}:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2"
        )
        disclosure = (
            "HUD-aware blur preset applied: full 16:9 gameplay preserved with blurred vertical fill; "
            "minimap and HUD elements intact."
        )
        return vf, disclosure

    elif preset_lower == ReframePreset.SPLIT_FACECAM_GAMEPLAY.value:
        # Streamer layout: top 30% facecam, bottom 70% gameplay
        cam_h = int(target_h * 0.30)
        game_h = target_h - cam_h
        vf = (
            f"[0:v]split=2[cam_raw][game_raw];"
            f"[cam_raw]crop=iw*0.35:ih*0.35:0:0,scale={target_w}:{cam_h}:force_original_aspect_ratio=increase,crop={target_w}:{cam_h}[cam];"
            f"[game_raw]scale={target_w}:{game_h}:force_original_aspect_ratio=increase,crop={target_w}:{game_h}[game];"
            f"[cam][game]vstack=inputs=2"
        )
        disclosure = (
            "Split facecam/gameplay heuristic preset applied: top-left camera crop stacked above centered gameplay. "
            "Verify facecam coordinates in Motion Review."
        )
        return vf, disclosure

    elif preset_lower == ReframePreset.GAMEPLAY_RETICLE.value:
        # Crosshair/reticle prioritized: horizontal center with vertical upper-third bias
        # Keeps gameplay action prominent and bottom third open for subtitles/captions
        vf = (
            f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
            f"crop={target_w}:{target_h}:(in_w-out_w)/2:max(0\\,min(in_h-out_h\\,(in_h-out_h)/3))"
        )
        disclosure = (
            "Gameplay reticle safe-region preset applied: centered on tactical reticle with upper-third bias; "
            "bottom safe region reserved for subtitles. Verify HUD visibility."
        )
        return vf, disclosure

    else:
        # Default CENTER_CROP
        vf = (
            f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
            f"crop={target_w}:{target_h}"
        )
        disclosure = (
            "Standard center crop 9:16 applied: edge HUD elements (minimap, killfeed) may be cropped. "
            "Verify composition in Motion Review."
        )
        return vf, disclosure
