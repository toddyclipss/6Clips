# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Motion Capabilities module providing typed access to migrated Clip Studio workflows and tools."""

from .adapter import MotionToolRunnerAdapter, execute_motion_capability
from .dispatcher import MotionCapabilityDispatcher
from .models import (
    CapabilityCategory,
    CapabilityExecutionResult,
    MotionCapabilitySpec,
    ParityTier,
)
from .parity_audit import (
    audit_capabilities_registry,
    scan_production_entrypoints_for_mocks,
)
from .registry import ALL_CAPABILITIES_SPEC, MotionCapabilitiesRegistry

__all__ = [
    "ALL_CAPABILITIES_SPEC",
    "CapabilityCategory",
    "CapabilityExecutionResult",
    "MotionCapabilitiesRegistry",
    "MotionCapabilityDispatcher",
    "MotionCapabilitySpec",
    "MotionToolRunnerAdapter",
    "ParityTier",
    "audit_capabilities_registry",
    "execute_motion_capability",
    "scan_production_entrypoints_for_mocks",
]
