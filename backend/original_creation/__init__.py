# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Original Creation package.
Provides grounded original content creation, evidence ledgers, clean teleprompter scripts,
physical FFmpeg video rendering, and canonical ProjectService adapter interfaces.
"""
from backend.original_creation.models import (
    EvidenceLedger,
    EvidenceLedgerEntry,
    FactcheckNote,
    OriginalCompositionSpec,
    OriginalCreationStatus,
    ProductionV1Adapter,
    RenderedVideoResult,
    ShotListEntry,
    TeleprompterScript,
    VideoProbeStats,
    VoiceInputRequirement,
)
from backend.original_creation.renderer import (
    OriginalVideoRenderer,
    generate_procedural_scene_card,
    render_scene_clip,
    synthesize_narration_audio,
)
from backend.original_creation.workflow import (
    OriginalCreatorWorkflow,
    calculate_spoken_read_time,
    clean_teleprompter_text,
)

__all__ = [
    "EvidenceLedger",
    "EvidenceLedgerEntry",
    "FactcheckNote",
    "OriginalCompositionSpec",
    "OriginalCreationStatus",
    "ProductionV1Adapter",
    "RenderedVideoResult",
    "ShotListEntry",
    "TeleprompterScript",
    "VideoProbeStats",
    "VoiceInputRequirement",
    "OriginalCreatorWorkflow",
    "OriginalVideoRenderer",
    "generate_procedural_scene_card",
    "render_scene_clip",
    "synthesize_narration_audio",
    "calculate_spoken_read_time",
    "clean_teleprompter_text",
]
