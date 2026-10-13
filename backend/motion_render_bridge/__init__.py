# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Motion Render Bridge: Deterministic Render Manifest Generator and Worker Parity Contracts.

Connects Motion Studio timeline editing (frame mapping, speed retime, mute/solo mix,
multiline captions, framing presets) to deterministic render manifests for worker consumption.
"""

from .catalog_consumer import CatalogExportConsumer, CatalogExportConsumptionResult
from .manifest import (
    FramingPreset,
    FramingFilterConfig,
    RenderClip,
    RenderTrack,
    RenderAudioMix,
    RenderCaptionSegment,
    RenderManifest,
    WORKER_SUPPORTED_PRESETS,
    build_render_manifest,
)

__all__ = [
    "CatalogExportConsumer",
    "CatalogExportConsumptionResult",
    "FramingPreset",
    "FramingFilterConfig",
    "RenderClip",
    "RenderTrack",
    "RenderAudioMix",
    "RenderCaptionSegment",
    "RenderManifest",
    "WORKER_SUPPORTED_PRESETS",
    "build_render_manifest",
]
