# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
OAAS Editor Native Package.
Dissolves Clip Studio and Tools into a single unified Motion Graphics editor
operating over atomic CAS ProjectRevisions with a single transport, single timeline, and single player.
"""

from backend.oaas_editor_native.models import (
    NativeCommandType,
    ParityStatus,
    CapabilityDescriptor,
    NativeCommandRequest,
    NativeCommandResult,
)
from backend.oaas_editor_native.registry import NativeCapabilityRegistry
from backend.oaas_editor_native.executor import (
    NativeCommandExecutor,
    CASConcurrencyError,
    CommandExecutionError,
)
from backend.oaas_editor_native.migrator import LegacyProjectMigrator

__all__ = [
    "NativeCommandType",
    "ParityStatus",
    "CapabilityDescriptor",
    "NativeCommandRequest",
    "NativeCommandResult",
    "NativeCapabilityRegistry",
    "NativeCommandExecutor",
    "CASConcurrencyError",
    "CommandExecutionError",
    "LegacyProjectMigrator",
]
