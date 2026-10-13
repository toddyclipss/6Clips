# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Production Acceptance Registry (Wave 7).

Central registry tracking production path readiness and truth states for GT-05, GT-06, GT-07.
"""
from __future__ import annotations

from typing import Dict, Any
from .contracts import OrchestrationResult
from .protocol import get_acceptance_protocol_spec


class ProductionAcceptanceRegistry:
    """Manages acceptance verification states across all release gates."""

    @classmethod
    def get_all_gate_statuses(cls) -> Dict[str, Any]:
        """
        Returns grounded status matrix for all gates.
        In absence of human-provided live media, real paths remain strictly NOT_TESTED.
        """
        protocol = get_acceptance_protocol_spec()
        return {
            "GT-05": {
                "name": "Gameplay V1 Vertical Shorts",
                "status": "NOT_TESTED",
                "is_real_user_media": False,
                "reason": "Authentic full gameplay recording not provided in testing environment",
            },
            "GT-06": {
                "name": "Long-Form Condensation into Narrative (V3)",
                "status": "NOT_TESTED",
                "is_real_user_media": False,
                "reason": "Authentic ~60-minute recording not provided (bounded CPU test safety)",
            },
            "GT-07": {
                "name": "Multi-Source to 10 Distinct Clips (V2)",
                "status": "NOT_TESTED",
                "is_real_user_media": False,
                "reason": "Authentic licensed 5-source media assets not provided in testing environment",
            },
            "protocol": protocol,
        }
