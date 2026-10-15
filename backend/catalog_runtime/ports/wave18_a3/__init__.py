# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 18 Agent 3 Runtime Port Package."""
from backend.catalog_runtime.ports.wave18_a3.adapter import (
    AM_VERIFIED_100_BLOCKS,
    AM_BLOCKED_DEPENDENCY_12_BLOCKS,
    AM_BLOCKED_RIGHTS_9_BLOCKS,
    AM_RETIRED_2_BLOCKS,
    ALL_AM_121_DONOR_BLOCKS,
    Agent3PortAdapter,
    agent3_port_adapter,
)

__all__ = [
    "AM_VERIFIED_100_BLOCKS",
    "AM_BLOCKED_DEPENDENCY_12_BLOCKS",
    "AM_BLOCKED_RIGHTS_9_BLOCKS",
    "AM_RETIRED_2_BLOCKS",
    "ALL_AM_121_DONOR_BLOCKS",
    "Agent3PortAdapter",
    "agent3_port_adapter",
]
