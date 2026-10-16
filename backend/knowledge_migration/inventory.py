# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Donor inventory ledger, shipped bundle catalog crosswalk, and native mapping registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

REPO_ROOT = Path(__file__).resolve().parents[2]
LEDGER_FILE = REPO_ROOT / "backend" / "catalog_inventory" / "196_REAL_RUNNING_UI_PREVIEW_LEDGER.json"
SHIPPED_BLOCKS_DIR = REPO_ROOT / "backend" / "catalog" / "shipped_blocks"

RETIRED_CUSTOM_SLUGS: Set[str] = {"creator-hud", "glitch-transition"}

# Canonical mapping of legacy block slugs to native motion capabilities and operators
LEGACY_TO_NATIVE_MAPPING: Dict[str, Dict[str, Any]] = {
    "lower-third-bild": {
        "capability_family": "typography_kinetic",
        "technique": "lower_third_bar",
        "primary_element": "text",
        "secondary_element": "shape",
        "default_fill": "#FFFFFF",
        "default_accent": "#F59E0B",
        "default_font_size": 36.0,
        "default_duration": 3.0,
    },
    "yt-lower-third": {
        "capability_family": "typography_kinetic",
        "technique": "lower_third_badge",
        "primary_element": "text",
        "secondary_element": "shape",
        "default_fill": "#FFFFFF",
        "default_accent": "#EF4444",
        "default_font_size": 32.0,
        "default_duration": 4.0,
    },
    "weight-wave": {
        "capability_family": "typography_kinetic",
        "technique": "kinetic_weight_wave",
        "primary_element": "text",
        "default_fill": "#FFFFFF",
        "default_accent": "#3B82F6",
        "default_font_size": 48.0,
        "default_duration": 3.0,
    },
    "minimal-title": {
        "capability_family": "typography_kinetic",
        "technique": "kinetic_headline",
        "primary_element": "text",
        "default_fill": "#FFFFFF",
        "default_accent": "#A855F7",
        "default_font_size": 52.0,
        "default_duration": 4.0,
    },
    "bar-chart-race": {
        "capability_family": "data_visualization",
        "technique": "animated_bar_chart",
        "primary_element": "chart",
        "default_fill": "#10B981",
        "default_accent": "#6366F1",
        "default_duration": 4.0,
    },
    "apple-money-count": {
        "capability_family": "data_visualization",
        "technique": "kinetic_number_counter",
        "primary_element": "text",
        "default_fill": "#34D399",
        "default_accent": "#059669",
        "default_font_size": 56.0,
        "default_duration": 3.0,
    },
    "aurora": {
        "capability_family": "background_shader",
        "technique": "aurora_gradient",
        "primary_element": "shape",
        "default_fill": "#0A0A0C",
        "default_accent": "#8B5CF6",
        "default_duration": 5.0,
    },
    "notification-cascade": {
        "capability_family": "ui_simulation",
        "technique": "notification_card",
        "primary_element": "shape",
        "secondary_element": "text",
        "default_fill": "#1F2937",
        "default_accent": "#3B82F6",
        "default_duration": 3.5,
    },
    "spotify-card": {
        "capability_family": "ui_simulation",
        "technique": "audio_player_card",
        "primary_element": "shape",
        "secondary_element": "text",
        "default_fill": "#121212",
        "default_accent": "#1DB954",
        "default_duration": 4.0,
    },
    "tiktok-follow": {
        "capability_family": "ui_simulation",
        "technique": "social_cta_badge",
        "primary_element": "shape",
        "secondary_element": "text",
        "default_fill": "#FE2C55",
        "default_accent": "#25F4EE",
        "default_duration": 3.0,
    },
    "glass-hero": {
        "capability_family": "ui_simulation",
        "technique": "glassmorphic_hero",
        "primary_element": "shape",
        "secondary_element": "text",
        "default_fill": "#1E293B",
        "default_accent": "#38BDF8",
        "default_duration": 3.5,
    },
    "ai-answer-rank": {
        "capability_family": "ui_simulation",
        "technique": "ranked_list",
        "primary_element": "shape",
        "secondary_element": "text",
        "default_fill": "#0F172A",
        "default_accent": "#06B6D4",
        "default_duration": 4.0,
    },
    "carousel-text-circle-1": {
        "capability_family": "typography_kinetic",
        "technique": "circular_text",
        "primary_element": "text",
        "default_fill": "#EDEDEF",
        "default_accent": "#60A5FA",
        "default_font_size": 32.0,
        "default_duration": 3.0,
    },
    "hw-path-text": {
        "capability_family": "typography_kinetic",
        "technique": "path_text",
        "primary_element": "text",
        "default_fill": "#FFFFFF",
        "default_accent": "#EC4899",
        "default_font_size": 36.0,
        "default_duration": 3.0,
    },
    "closure-test-block": {
        "capability_family": "typography_kinetic",
        "technique": "test_headline",
        "primary_element": "text",
        "default_fill": "#F3F4F6",
        "default_accent": "#10B981",
        "default_font_size": 40.0,
        "default_duration": 2.5,
    },
    "creator-hud": {
        "capability_family": "ui_simulation",
        "technique": "creator_hud_overlay",
        "primary_element": "shape",
        "secondary_element": "text",
        "default_fill": "#000000",
        "default_accent": "#EF4444",
        "default_duration": 4.0,
    },
    "glitch-transition": {
        "capability_family": "transition_wipe",
        "technique": "glitch_dissolve",
        "primary_element": "shape",
        "default_fill": "#000000",
        "default_accent": "#00FFCC",
        "default_duration": 1.0,
    },
}


class DonorInventoryLedger:
    """Manages the canonical donor ledger, shipped bundles census, and native mappings."""

    def __init__(self, ledger_file: Optional[Path] = None, shipped_dir: Optional[Path] = None):
        self.ledger_file = ledger_file or LEDGER_FILE
        self.shipped_dir = shipped_dir or SHIPPED_BLOCKS_DIR
        self._donor_blocks: List[str] = []
        self._shipped_dirs: List[str] = []
        self._load()

    def _load(self) -> None:
        if self.ledger_file.exists():
            try:
                with open(self.ledger_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    blocks = data.get("blocks", [])
                    self._donor_blocks = [b.get("slug") for b in blocks if isinstance(b, dict) and b.get("slug")]
            except Exception:
                pass

        if self.shipped_dir.exists():
            self._shipped_dirs = sorted([d.name for d in self.shipped_dir.iterdir() if d.is_dir()])

    @property
    def total_donor_blocks(self) -> int:
        return len(self._donor_blocks) or 196

    @property
    def shipped_donor_slugs(self) -> List[str]:
        return [s for s in self._shipped_dirs if s not in RETIRED_CUSTOM_SLUGS]

    @property
    def shipped_custom_slugs(self) -> List[str]:
        return [s for s in self._shipped_dirs if s in RETIRED_CUSTOM_SLUGS]

    @property
    def total_shipped_bundles(self) -> int:
        return len(self._shipped_dirs)

    def get_native_mapping(self, block_slug: str) -> Dict[str, Any]:
        """Get native motion mapping parameters for a legacy slug."""
        if block_slug in LEGACY_TO_NATIVE_MAPPING:
            return LEGACY_TO_NATIVE_MAPPING[block_slug]

        # Generic safe fallback for unmapped or unknown slugs
        return {
            "capability_family": "typography_kinetic",
            "technique": "kinetic_text_card",
            "primary_element": "text",
            "secondary_element": "shape",
            "default_fill": "#FFFFFF",
            "default_accent": "#6366F1",
            "default_font_size": 36.0,
            "default_duration": 3.0,
        }
