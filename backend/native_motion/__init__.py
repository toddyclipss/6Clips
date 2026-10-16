# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""6Clips Native Motion Engine (native_motion_v1).

Knowledge-to-Motion generative system producing original, safe, typed, editable
motion graphics without fixed 196 donor block bundles.
"""

from backend.native_motion.schema import (
    AudioTrackSpec,
    CameraSpec,
    CaptionsConfig,
    Constraints,
    CreativeBrief,
    DataChartConfig,
    DataPoint,
    ElementSpec,
    ElementTransform,
    GradientConfig,
    GradientStop,
    KeyframeSpec,
    KnowledgeRef,
    NativeMotionSpec,
    ParticlesConfig,
    RepairLogEntry,
    SafeZoneSpec,
    SceneSpec,
    ShaderConfig,
    ShapeConfig,
    TextConfig,
    TypographySpec,
    WordTimestampSpec,
)
from backend.native_motion.generator import NativeMotionGenerator
from backend.native_motion.compiler import NativeMotionCompiler
from backend.native_motion.renderer import NativeMotionRenderer, RenderResult
from backend.native_motion.adapter import NativeMotionRevisionAdapter
from backend.native_motion.captions import NativeCaptionEngine, CaptionSpeechUnavailableError
from backend.native_motion.self_repair import NativeSelfRepair, RepairBudgetExhaustedError

__all__ = [
    "AudioTrackSpec",
    "CameraSpec",
    "CaptionsConfig",
    "Constraints",
    "CreativeBrief",
    "DataChartConfig",
    "DataPoint",
    "ElementSpec",
    "ElementTransform",
    "GradientConfig",
    "GradientStop",
    "KeyframeSpec",
    "KnowledgeRef",
    "NativeMotionSpec",
    "ParticlesConfig",
    "RepairLogEntry",
    "SafeZoneSpec",
    "SceneSpec",
    "ShaderConfig",
    "ShapeConfig",
    "TextConfig",
    "TypographySpec",
    "WordTimestampSpec",
    "NativeMotionGenerator",
    "NativeMotionCompiler",
    "NativeMotionRenderer",
    "RenderResult",
    "NativeMotionRevisionAdapter",
    "NativeCaptionEngine",
    "CaptionSpeechUnavailableError",
    "NativeSelfRepair",
    "RepairBudgetExhaustedError",
]
