# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
OAAS Motion Actions: Native Editor Command Layer.

Provides typed, atomic, CAS-validated editing actions directly manipulating
canonical ProjectService documents and ProjectRevisions.
"""

from .models import (
    ActionExecutionStatus,
    AudioAdjustActionParams,
    CaptionItem,
    CaptionsEditActionParams,
    CropActionParams,
    DeleteClipActionParams,
    ExportActionParams,
    GraphicInsertActionParams,
    MotionActionEnvelope,
    MotionActionResult,
    MotionActionType,
    RangeSelectActionParams,
    ReframeActionParams,
    RippleDeleteActionParams,
    SceneDetectActionParams,
    SpeechTranscribeActionParams,
    SpeedActionParams,
    SplitActionParams,
    TrimActionParams,
)
from .capability_catalog import CapabilityDiscovery, HISTORICAL_CAPABILITIES_CROSSWALK
from .executor import NativeMotionActionExecutor
from .adapter import OAASMotionActionAdapter

__all__ = [
    "ActionExecutionStatus",
    "AudioAdjustActionParams",
    "CaptionItem",
    "CaptionsEditActionParams",
    "CropActionParams",
    "DeleteClipActionParams",
    "ExportActionParams",
    "GraphicInsertActionParams",
    "MotionActionEnvelope",
    "MotionActionResult",
    "MotionActionType",
    "RangeSelectActionParams",
    "ReframeActionParams",
    "RippleDeleteActionParams",
    "SceneDetectActionParams",
    "SpeechTranscribeActionParams",
    "SpeedActionParams",
    "SplitActionParams",
    "TrimActionParams",
    "CapabilityDiscovery",
    "HISTORICAL_CAPABILITIES_CROSSWALK",
    "NativeMotionActionExecutor",
    "OAASMotionActionAdapter",
]
