# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Production Acceptance Package (Wave 8).
"""
from .contracts import (
    MediaProbeMetadata,
    OrchestrationContractStatus,
    OrchestrationResult,
    RightsVerificationStatus,
    SourceMediaAsset,
    V1ExpectedOutputSpec,
    V1ProductionContract,
    V2ExpectedOutputSpec,
    V2ProductionContract,
    V3NarrativeCut,
    V3ProductionContract,
)
from .probe import MediaProbeService
from .orchestration import (
    V1GameplayOrchestrator,
    V2MultiSourceOrchestrator,
    V3LongFormOrchestrator,
)
from .protocol import get_acceptance_protocol_spec
from .registry import ProductionAcceptanceRegistry

__all__ = [
    "MediaProbeMetadata",
    "OrchestrationContractStatus",
    "OrchestrationResult",
    "RightsVerificationStatus",
    "SourceMediaAsset",
    "V1ExpectedOutputSpec",
    "V1ProductionContract",
    "V2ExpectedOutputSpec",
    "V2ProductionContract",
    "V3NarrativeCut",
    "V3ProductionContract",
    "MediaProbeService",
    "V1GameplayOrchestrator",
    "V2MultiSourceOrchestrator",
    "V3LongFormOrchestrator",
    "get_acceptance_protocol_spec",
    "ProductionAcceptanceRegistry",
]
