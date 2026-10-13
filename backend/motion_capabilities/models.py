# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Data models for Motion Studio native capabilities and parity registry."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class ParityTier(str, Enum):
    """Validation readiness tier for a migrated capability."""
    VERIFIED_REAL = "VERIFIED_REAL"
    FUNCTIONAL_WITH_LIMITS = "FUNCTIONAL_WITH_LIMITS"
    BLOCKED = "BLOCKED"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


class CapabilityCategory(str, Enum):
    """Logical grouping of capabilities."""
    VIDEO = "video"
    AUDIO = "audio"
    SUBTITLES = "subtitles"
    AI_EDITORIAL = "ai_editorial"
    CLIP_STUDIO_WORKFLOW = "clip_studio_workflow"


@dataclass
class MotionCapabilitySpec:
    """Specification of a migrated capability in Motion Graphics."""
    id: str
    title: str
    category: CapabilityCategory
    legacy_source: str
    motion_entrypoint: str
    backend_action: str
    parity_tier: ParityTier
    description: str
    parameters_schema: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    limitations: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category.value if isinstance(self.category, Enum) else self.category,
            "legacy_source": self.legacy_source,
            "motion_entrypoint": self.motion_entrypoint,
            "backend_action": self.backend_action,
            "parity_tier": self.parity_tier.value if isinstance(self.parity_tier, Enum) else self.parity_tier,
            "description": self.description,
            "parameters_schema": self.parameters_schema,
            "dependencies": self.dependencies,
            "limitations": self.limitations,
        }


@dataclass
class CapabilityExecutionResult:
    """Strongly typed execution outcome from dispatching a capability."""
    capability_id: str
    status: str  # "SUCCESS", "FAILED", "BLOCKED", "PARTIAL"
    message: str
    output_path: Optional[str] = None
    output_data: Optional[Dict[str, Any]] = None
    execution_time_seconds: float = 0.0
    warnings: List[str] = field(default_factory=list)
    error_detail: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
