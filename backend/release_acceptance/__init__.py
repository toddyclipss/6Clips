# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Release Acceptance Package (Wave 6).
Provides bounded, evidence-based acceptance validators for V2 (GT-06) and V3 (GT-07).
"""
from backend.release_acceptance.validator import (
    AcceptanceGateStatus,
    ReleaseAcceptanceAuditor,
    V2AcceptanceResult,
    V2MultiOutputValidator,
    V3AcceptanceResult,
    V3LongFormNarrativeValidator,
)

__all__ = [
    "AcceptanceGateStatus",
    "ReleaseAcceptanceAuditor",
    "V2AcceptanceResult",
    "V2MultiOutputValidator",
    "V3AcceptanceResult",
    "V3LongFormNarrativeValidator",
]
