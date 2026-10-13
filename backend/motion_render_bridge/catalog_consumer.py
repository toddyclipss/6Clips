# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Typed consumer of HyperFrames Catalog export contracts for Motion Graphics render engine.

Consumes CatalogExportContract manifests (from Wave 6 Catalog) and transforms them into
deterministic FFmpeg overlay filter graphs with alpha channel preservation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class CatalogExportConsumerError(Exception):
    """Raised when catalog export manifest is malformed or invalid."""
    pass


@dataclass
class CatalogExportConsumptionResult:
    """Result of parsing and preparing a Catalog block manifest for FFmpeg compositing."""
    block_id: str
    instance_id: str
    aspect_ratio: str
    viewport_width: int
    viewport_height: int
    duration_seconds: float
    fps: int
    alpha_channel_required: bool
    target_pixel_format: str
    recommended_codec: str
    overlay_filter_expression: str
    mp4_parity_status: str  # "RENDERED" | "NOT_TESTED"
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "block_id": self.block_id,
            "instance_id": self.instance_id,
            "aspect_ratio": self.aspect_ratio,
            "viewport_width": self.viewport_width,
            "viewport_height": self.viewport_height,
            "duration_seconds": self.duration_seconds,
            "fps": self.fps,
            "alpha_channel_required": self.alpha_channel_required,
            "target_pixel_format": self.target_pixel_format,
            "recommended_codec": self.recommended_codec,
            "overlay_filter_expression": self.overlay_filter_expression,
            "mp4_parity_status": self.mp4_parity_status,
            "warnings": self.warnings,
        }


class CatalogExportConsumer:
    """Validates and translates CatalogExportContract manifests into FFmpeg overlay filter graphs."""

    @classmethod
    def validate_manifest(cls, manifest: Dict[str, Any]) -> bool:
        """Validate structure and essential keys of a CatalogExportContract manifest."""
        if not isinstance(manifest, dict):
            raise CatalogExportConsumerError("Manifest must be a dictionary.")
        if manifest.get("contract_type") != "MOTION_BLOCK_EXPORT_MANIFEST":
            raise CatalogExportConsumerError(
                f"Unexpected contract_type: {manifest.get('contract_type')}. Expected 'MOTION_BLOCK_EXPORT_MANIFEST'."
            )
        if not manifest.get("block_id"):
            raise CatalogExportConsumerError("Manifest missing required 'block_id'.")
        if "viewport" not in manifest or "width" not in manifest["viewport"] or "height" not in manifest["viewport"]:
            raise CatalogExportConsumerError("Manifest missing valid 'viewport' dimensions.")
        if "rendering_channel" not in manifest:
            raise CatalogExportConsumerError("Manifest missing 'rendering_channel' section.")
        return True

    @classmethod
    def consume(
        cls,
        manifest: Dict[str, Any],
        background_pad: str = "[0:v]",
        overlay_pad: str = "[1:v]",
        start_seconds: float = 0.0,
        end_seconds: Optional[float] = None,
        canvas_width: int = 1080,
        canvas_height: int = 1920,
    ) -> CatalogExportConsumptionResult:
        """Parse Catalog export manifest and construct deterministic FFmpeg overlay filter graph."""
        cls.validate_manifest(manifest)

        block_id = manifest["block_id"]
        instance_id = manifest.get("instance_id", f"block_{block_id}")
        aspect_ratio = manifest.get("aspect_ratio", "9:16")
        viewport = manifest.get("viewport", {})
        vp_w = int(viewport.get("width", canvas_width))
        vp_h = int(viewport.get("height", canvas_height))

        timeline_params = manifest.get("timeline_parameters", {})
        duration = float(timeline_params.get("duration_seconds", 5.0))
        fps = int(timeline_params.get("fps", 30))

        render_channel = manifest.get("rendering_channel", {})
        alpha_req = bool(render_channel.get("alpha_channel_required", False))
        pixel_fmt = str(render_channel.get("pixel_format_target", "yuva420p" if alpha_req else "yuv420p"))
        rec_codec = str(render_channel.get("recommended_codec", "png" if alpha_req else "libx264"))

        warnings: List[str] = []

        # Calculate time-enable window
        t_end = end_seconds if end_seconds is not None else (start_seconds + duration)
        enable_expr = f"enable='between(t,{start_seconds:.3f},{t_end:.3f})'"

        # Construct filter graph for alpha overlay
        # If dimensions differ from canvas, scale overlay to match canvas viewport
        if vp_w != canvas_width or vp_h != canvas_height:
            scale_filter = f"{overlay_pad}scale={canvas_width}:{canvas_height}:force_original_aspect_ratio=decrease[scaled_ov];"
            ov_in = "[scaled_ov]"
            warnings.append(f"Scaled catalog overlay from {vp_w}x{vp_h} to canvas {canvas_width}x{canvas_height}.")
        else:
            scale_filter = ""
            ov_in = overlay_pad

        if alpha_req:
            # Alpha-aware compositing: format=auto with transparent overlay
            overlay_expr = f"{scale_filter}{background_pad}{ov_in}overlay=x=0:y=0:format=auto:{enable_expr}[out_v]"
        else:
            # Opaque overlay
            overlay_expr = f"{scale_filter}{background_pad}{ov_in}overlay=x=0:y=0:{enable_expr}[out_v]"

        # Default MP4 parity status: unless rendered through physical browser frame-grabber,
        # truthfulness mandate 4 requires reporting CATALOG_MP4_PARITY: NOT_TESTED.
        mp4_status = "NOT_TESTED"

        return CatalogExportConsumptionResult(
            block_id=block_id,
            instance_id=instance_id,
            aspect_ratio=aspect_ratio,
            viewport_width=vp_w,
            viewport_height=vp_h,
            duration_seconds=duration,
            fps=fps,
            alpha_channel_required=alpha_req,
            target_pixel_format=pixel_fmt,
            recommended_codec=rec_codec,
            overlay_filter_expression=overlay_expr,
            mp4_parity_status=mp4_status,
            warnings=warnings,
        )
