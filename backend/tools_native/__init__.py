# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 19 Native Tools Package.
Recovers all 21 original tools from ViralMint-Legado as first-class native Motion
editing commands and agent-callable capabilities.
"""

from .models import (
    NativeToolType,
    ToolActionRequest,
    ToolActionResult,
    ToolDescriptor,
    ToolExecutionMode,
)
from .registry import NativeToolRegistry
from .executor import NativeToolExecutor
from .adapter import ToolsNativeAdapter

__all__ = [
    "NativeToolType",
    "ToolActionRequest",
    "ToolActionResult",
    "ToolDescriptor",
    "ToolExecutionMode",
    "NativeToolRegistry",
    "NativeToolExecutor",
    "ToolsNativeAdapter",
]
