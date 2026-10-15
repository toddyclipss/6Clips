# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Canonical Data Models for Wave 15 Catalog Runtime Core.
Defines immutable proofs, provenance, origin types, and runtime block specifications.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class BlockOrigin(str, Enum):
    """Origin provenance distinguishing true HyperFrames donors from retired 6Clips-authored blocks."""
    DONOR_ORIGINAL = "DONOR_ORIGINAL"
    RETIRED_6CLIPS_AUTHORED = "RETIRED_6CLIPS_AUTHORED"


class SourceCategoryStatus(str, Enum):
    """
    Indicates whether category was explicitly present in upstream source registry metadata.
    Upstream HyperFrames blocks have tags and dimensions but lack explicit top-level 'category'.
    """
    SOURCE_CATEGORY_MISSING = "SOURCE_CATEGORY_MISSING"
    SOURCE_CATEGORY_VERIFIED = "SOURCE_CATEGORY_VERIFIED"
    SOURCE_CATEGORY_UNSPECIFIED = "SOURCE_CATEGORY_UNSPECIFIED"
    SOURCE_CATEGORY_CONFIRMED = "SOURCE_CATEGORY_CONFIRMED"


@dataclass
class ReadinessProofLadder:
    """
    Seven independent verification classes required by Wave 15 Acceptance Contract 3.
    Never derived from a single synthetic boolean.
    """
    source_inventoried: bool = True
    source_ported: bool = False
    runtime_ready: bool = False
    browser_preview_verified: bool = False
    motion_edit_verified: bool = False
    render_artifact_verified: bool = False
    rights_cleared: bool = False

    def to_dict(self) -> Dict[str, bool]:
        return {
            "source_inventoried": self.source_inventoried,
            "source_ported": self.source_ported,
            "runtime_ready": self.runtime_ready,
            "browser_preview_verified": self.browser_preview_verified,
            "motion_edit_verified": self.motion_edit_verified,
            "render_artifact_verified": self.render_artifact_verified,
            "rights_cleared": self.rights_cleared,
        }

    @property
    def fully_proven(self) -> bool:
        """True only if all seven independent classes have affirmative evidence."""
        return (
            self.source_inventoried
            and self.source_ported
            and self.runtime_ready
            and self.browser_preview_verified
            and self.motion_edit_verified
            and self.render_artifact_verified
            and self.rights_cleared
        )


@dataclass
class RuntimeBlockSpec:
    """
    Stable runtime interface consumed by downstream peers (Agents 3, 5, 6).
    Enforces clear property naming without requiring teammates to edit internal files.
    """
    original_id: str
    vendored_root: Optional[Path] = None
    source_category_id: Optional[str] = None
    source_category_status: str = SourceCategoryStatus.SOURCE_CATEGORY_MISSING.value
    proposed_fallback_category: str = "general"
    is_original_category: bool = False
    variables: List[Dict[str, Any]] = field(default_factory=list)
    source_aspect: str = "9:16"
    readiness: Dict[str, bool] = field(default_factory=dict)
    render_adapter: str = "webgpu_canvas2d"
    is_public_catalog_item: bool = False
    requires_migration: bool = False
    blocker_code: Optional[str] = None
    blocker_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        if self.vendored_root:
            res["vendored_root"] = str(self.vendored_root)
        return res


@dataclass
class RuntimeBlock:
    """Full canonical in-memory representation of an inventoried or operable catalog block."""
    id: str
    title: str
    description: str
    origin: BlockOrigin
    source_category: Optional[str]
    source_category_status: SourceCategoryStatus
    proposed_fallback_category: str
    is_original_category: bool
    source_tags: List[str]
    dimensions: Dict[str, int]
    native_aspect: str
    supported_aspects: List[str]
    duration: float
    variables: List[Dict[str, Any]]
    license: str
    license_status: str
    license_evidence: str
    source_sha256: str
    vendored_sha256: Optional[str]
    vendored_path: Optional[str]
    readiness: ReadinessProofLadder
    runtime_operable: bool
    blocker_code: Optional[str] = None
    blocker_reason: Optional[str] = None
    render_adapter: str = "webgpu_canvas2d"
    in_aggregate_manifest: bool = True
    evidence_refs: List[str] = field(default_factory=list)

    def to_catalog_item(self) -> Dict[str, Any]:
        """Convert to consumer-facing REST dictionary."""
        return {
            "id": self.id,
            "name": self.id,
            "title": self.title,
            "description": self.description,
            "origin": self.origin.value,
            "category": self.proposed_fallback_category,
            "source_category": self.source_category,
            "source_category_status": self.source_category_status.value,
            "proposed_fallback_category": self.proposed_fallback_category,
            "is_original_category": self.is_original_category,
            "tags": self.source_tags,
            "dimensions": self.dimensions,
            "native_aspect": self.native_aspect,
            "supported_aspects": self.supported_aspects,
            "aspect_9_16": "NATIVE" if "9:16" in self.supported_aspects else "CONTAINED_ONLY",
            "aspect_16_9": "NATIVE" if "16:9" in self.supported_aspects else "CONTAINED_ONLY",
            "duration": self.duration,
            "variables": self.variables,
            "variables_count": len(self.variables),
            "license": self.license,
            "license_status": self.license_status,
            "license_evidence": self.license_evidence,
            "source_sha256": self.source_sha256,
            "vendored_sha256": self.vendored_sha256,
            "internalized": self.runtime_operable,
            "runtime_ready": self.runtime_operable,
            "runtime_operable": self.runtime_operable,
            "readiness": "READY" if self.runtime_operable else "UNVERIFIED",
            "proof_ladder": self.readiness.to_dict(),
            "blocker_code": self.blocker_code,
            "blocker_reason": self.blocker_reason,
            "render_adapter": self.render_adapter,
            "in_aggregate_manifest": self.in_aggregate_manifest,
            "evidence_refs": self.evidence_refs,
        }
