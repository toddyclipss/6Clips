# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
6Clips OAAS Media Edit & Source Lineage Package.

Provides authentic video acquisition, forensic media analysis,
native timeline editing, and cryptographic/visual source lineage verification.
"""

from .models import (
    EditExecutionResult,
    EditExistingMediaContract,
    EditIntentType,
    SourceLineageVerification,
    SourceMediaAnalysis,
    SourceStreamInfo,
)
from .analyzer import SourceMediaAnalyzer
from .editor import NativeMediaEditor
from .project_adapter import SafeProjectEditAdapter
from .verifier import SourceLineageVerifier
from .adapter import EditExistingMediaAdapter

__all__ = [
    "EditExecutionResult",
    "EditExistingMediaContract",
    "EditIntentType",
    "SourceLineageVerification",
    "SourceMediaAnalysis",
    "SourceStreamInfo",
    "SourceMediaAnalyzer",
    "NativeMediaEditor",
    "SafeProjectEditAdapter",
    "SourceLineageVerifier",
    "EditExistingMediaAdapter",
]
