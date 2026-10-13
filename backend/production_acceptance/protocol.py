# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Human-Executable Production Acceptance Protocol (Wave 7).

Specifies instructions, CLI entry points, and directory layout for real-media
human verification of Gates GT-05, GT-06 (V3), and GT-07 (V2).
"""
from __future__ import annotations

from typing import Dict, Any


def get_acceptance_protocol_spec() -> Dict[str, Any]:
    """Returns human-executable protocol specification for real-media verification."""
    return {
        "title": "ViralMint Production Acceptance Protocol for Real Media",
        "wave": 7,
        "gates": {
            "GT-05": {
                "name": "Gameplay V1 Vertical Shorts",
                "mode": "V1",
                "input_requirements": {
                    "count": 1,
                    "type": "Authorized gameplay capture (16:9 or native)",
                    "directory": "data/acceptance/gt05_inputs/",
                    "min_duration_sec": 180,
                },
                "expected_outputs": {
                    "count": 3,
                    "aspect_ratio": "9:16",
                    "target_duration_sec": "~60s each",
                    "directory": "data/acceptance/gt05_outputs/",
                },
                "cli_verification_command": "python -m backend.production_acceptance.cli verify-gt05 --input data/acceptance/gt05_inputs/gameplay.mp4 --output-dir data/acceptance/gt05_outputs/",
            },
            "GT-06": {
                "name": "Long-Form Condensation into Narrative (V3)",
                "mode": "V3",
                "input_requirements": {
                    "count": 1,
                    "type": "Authentic long-form recording (~60 minutes, 3000-4200s, 16:9, dual-channel audio)",
                    "directory": "data/acceptance/gt06_inputs/",
                    "rights": ["AUTHORIZED_USER_MEDIA", "COMMERCIAL_CREATOR_LICENSE"],
                },
                "expected_outputs": {
                    "count": 1,
                    "aspect_ratio": "16:9",
                    "target_duration_sec": "480-600s (8 to 10 minutes narrative cut)",
                    "directory": "data/acceptance/gt06_outputs/",
                    "motion_review_url": "/motion?output_id=v3_narrative_{project_id}&project_id={project_id}",
                },
                "cli_verification_command": "python -m backend.production_acceptance.cli verify-gt06 --input data/acceptance/gt06_inputs/longform_60m.mp4 --output-dir data/acceptance/gt06_outputs/",
            },
            "GT-07": {
                "name": "Multi-Source to 10 Distinct Clips (V2)",
                "mode": "V2",
                "input_requirements": {
                    "count": 5,
                    "type": "5 distinct authorized creator video assets with non-identical SHA256 hashes",
                    "directory": "data/acceptance/gt07_inputs/",
                    "rights": ["AUTHORIZED_USER_MEDIA", "COMMERCIAL_CREATOR_LICENSE"],
                },
                "expected_outputs": {
                    "count": 10,
                    "aspect_ratio": "9:16",
                    "target_duration_sec": "45-65s per clip",
                    "directory": "data/acceptance/gt07_outputs/",
                    "deduplication": "10 unique SHA-256 hashes; no synthetic filler (anullsrc prohibited)",
                    "motion_review_urls": "/motion?output_id=v2_out_{project_id}_{01..10}&project_id={project_id}",
                },
                "cli_verification_command": "python -m backend.production_acceptance.cli verify-gt07 --inputs-dir data/acceptance/gt07_inputs/ --output-dir data/acceptance/gt07_outputs/",
            },
        },
        "operator_instructions": [
            "1. Place verified, licensed source media in the respective data/acceptance/ directories.",
            "2. Ensure audio channels are active and magic bytes conform to MP4/WebM containers.",
            "3. Execute the corresponding CLI verification command.",
            "4. Verify that each generated clip is reviewable in the Motion Editor (/motion?output_id=...).",
            "5. The system strictly guards truth: synthetic or missing media will yield NOT_TESTED.",
        ],
    }
