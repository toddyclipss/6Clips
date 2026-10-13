# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Original Creation package.
Provides grounded original content creation, evidence ledgers, clean teleprompter scripts,
and canonical ProjectService adapter interfaces.
"""
from backend.original_creation.models import (
    EvidenceLedger,
    EvidenceLedgerEntry,
    FactcheckNote,
    OriginalCompositionSpec,
    OriginalCreationStatus,
    ProductionV1Adapter,
    ShotListEntry,
    TeleprompterScript,
    VoiceInputRequirement,
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
    "ShotListEntry",
    "TeleprompterScript",
    "VoiceInputRequirement",
    "OriginalCreatorWorkflow",
    "calculate_spoken_read_time",
    "clean_teleprompter_text",
]
