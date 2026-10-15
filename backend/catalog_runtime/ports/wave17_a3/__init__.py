# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 17 Agent 3 HyperFrames A-M Real Runtime Ports and Activation."""
from backend.catalog_runtime.ports.wave17_a3.adapter import (
    get_ports,
    get_preview_html,
    get_blocked_backlog,
    insert_into_project,
    edit_project_block,
    AM_ACTIVATED_104_BLOCKS,
    AM_BLOCKED_RIGHTS_9_BLOCKS,
    AM_BLOCKED_DEPENDENCY_8_BLOCKS,
    ALL_AM_121_BLOCKS,
)

__all__ = [
    "get_ports",
    "get_preview_html",
    "get_blocked_backlog",
    "insert_into_project",
    "edit_project_block",
    "AM_ACTIVATED_104_BLOCKS",
    "AM_BLOCKED_RIGHTS_9_BLOCKS",
    "AM_BLOCKED_DEPENDENCY_8_BLOCKS",
    "ALL_AM_121_BLOCKS",
]
