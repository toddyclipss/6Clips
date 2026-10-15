# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Catalog Runtime Core: Canonical models, taxonomy reconciliation, stable interfaces, and verification."""
from backend.catalog_runtime.core.models import (
    BlockOrigin,
    SourceCategoryStatus,
    ReadinessProofLadder,
    RuntimeBlock,
    RuntimeBlockSpec,
)
from backend.catalog_runtime.core.taxonomy import DonorTaxonomyReconciler
from backend.catalog_runtime.core.interface import (
    get_runtime_block_spec,
    list_runtime_block_specs,
    validate_runtime_operable,
    get_proof_ladder,
)
from backend.catalog_runtime.core.registry_engine import UniversalRuntimeRegistry
from backend.catalog_runtime.core.migration import LegacyBlockMigrationManager
from backend.catalog_runtime.core.render_verifier import DynamicFrameMotionVerifier
from backend.catalog_runtime.core.onboarding import (
    DeterministicDonorOnboardingPipeline,
    OnboardingValidationResult,
)

__all__ = [
    "BlockOrigin",
    "SourceCategoryStatus",
    "ReadinessProofLadder",
    "RuntimeBlock",
    "RuntimeBlockSpec",
    "DonorTaxonomyReconciler",
    "get_runtime_block_spec",
    "list_runtime_block_specs",
    "validate_runtime_operable",
    "get_proof_ladder",
    "UniversalRuntimeRegistry",
    "LegacyBlockMigrationManager",
    "DynamicFrameMotionVerifier",
    "DeterministicDonorOnboardingPipeline",
    "OnboardingValidationResult",
]

