# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Native Clip Studio Package for Wave 19 Agent 3.
Provides forensic parity for all 34 original Clip Studio capabilities
within Motion Graphics native architecture.
"""

from .adapter import ClipStudioNativeAdapter, clipstudio_native_adapter
from .models import (
    ClipDeliverable,
    ClipRange,
    ClipStudioActionResult,
    ClipStudioActionType,
    ExtractClipsParams,
    MapClipToProjectParams,
    SuggestClipsParams,
)
from .service import ClipStudioNativeService

__all__ = [
    "ClipStudioNativeAdapter",
    "clipstudio_native_adapter",
    "ClipStudioNativeService",
    "ClipStudioActionType",
    "ClipRange",
    "SuggestClipsParams",
    "ExtractClipsParams",
    "MapClipToProjectParams",
    "ClipDeliverable",
    "ClipStudioActionResult",
]
