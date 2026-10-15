# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Stable Runtime Interface for Teammates (Agents 3, 5, 6).
Provides typed, read-only inspection methods and contracts for:
- original_id: canonical HyperFrames directory identifier
- vendored_root: local file path to vendored block assets
- source_category_id: upstream category (None when absent)
- source_category_status: SOURCE_CATEGORY_MISSING
- proposed_fallback_category: derived catalog category
- variables: schema variable declarations
- source_aspect: native aspect ratio ("9:16", "16:9")
- readiness: 7-stage proof ladder dictionary
- render_adapter: "webgpu_canvas2d" or "gsap_timeline"
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.catalog_runtime.core.models import (
    BlockOrigin,
    SourceCategoryStatus,
    RuntimeBlockSpec,
)
from backend.catalog_runtime.core.registry_engine import (
    UniversalRuntimeRegistry,
    BlockUnavailableError,
)
from backend.catalog_runtime.core.taxonomy import (
    DonorTaxonomyReconciler,
    RETIRED_6CLIPS_BLOCK_IDS,
)


def get_runtime_block_spec(block_id: str, wave: Optional[int] = None) -> Optional[RuntimeBlockSpec]:
    """
    Retrieve typed RuntimeBlockSpec for any known block.
    Returns None if block_id is unknown.
    """
    b = UniversalRuntimeRegistry.get_block(block_id, wave=wave)
    if not b:
        return None

    is_retired = DonorTaxonomyReconciler.is_retired_6clips_block(b.id)
    v_root = Path(b.vendored_path) if b.vendored_path else None

    return RuntimeBlockSpec(
        original_id=b.id,
        vendored_root=v_root,
        source_category_id=b.source_category,
        source_category_status=b.source_category_status.value,
        proposed_fallback_category=b.proposed_fallback_category,
        is_original_category=b.is_original_category,
        variables=b.variables,
        source_aspect=b.native_aspect,
        readiness=b.readiness.to_dict(),
        render_adapter=b.render_adapter,
        is_public_catalog_item=b.runtime_operable and not is_retired,
        requires_migration=is_retired,
        blocker_code=b.blocker_code,
        blocker_reason=b.blocker_reason,
    )


def list_runtime_block_specs(only_public: bool = True, wave: Optional[int] = None) -> List[RuntimeBlockSpec]:
    """
    List all runtime block specs.
    If only_public is True, returns only verified operable donor blocks.
    If False, returns all 196 donor blocks plus retired blocks.
    """
    blocks = UniversalRuntimeRegistry.discover_all_blocks(wave=wave)
    specs = []
    for b in blocks.values():
        is_retired = DonorTaxonomyReconciler.is_retired_6clips_block(b.id)
        if only_public and (not b.runtime_operable or is_retired):
            continue
        spec = get_runtime_block_spec(b.id, wave=wave)
        if spec:
            specs.append(spec)
    return specs


def validate_runtime_operable(block_id: str, wave: Optional[int] = None, allow_retired: bool = False) -> None:
    """
    Convenience validator for peer modules.
    Raises BlockUnavailableError (HTTP 403 or 409) if block cannot be operated on.
    """
    UniversalRuntimeRegistry.validate_block_operable(block_id, wave=wave, allow_retired=allow_retired)


def get_proof_ladder(block_id: str, wave: Optional[int] = None) -> Dict[str, Any]:
    """
    Returns the independent proof ladder for a specific block ID.
    Raises BlockUnavailableError if block does not exist.
    """
    b = UniversalRuntimeRegistry.get_block(block_id, wave=wave)
    if not b:
        raise BlockUnavailableError(
            block_id=block_id,
            blocker_code="BLOCK_NOT_FOUND",
            detail=f"Block '{block_id}' not found.",
            http_code=404,
        )
    return {
        "block_id": b.id,
        "origin": b.origin.value,
        "runtime_operable": b.runtime_operable,
        "proof_ladder": b.readiness.to_dict(),
        "blocker_code": b.blocker_code,
        "blocker_reason": b.blocker_reason,
    }
