# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Autonomous HyperFrames Block Selector.
Autonomously selects verified operable HyperFrames donor originals (37 verified)
and strictly avoids advertising unported (159) or retired blocks (creator-hud, glitch-transition)
as renderable in production workflows.
"""

import re
from typing import Dict, List, Optional, Set, Tuple

# Pinned 37 verified operable donor originals from the 196 donor catalog
OPERABLE_ORIGINALS_37: Set[str] = {
    "aurora",
    "blob",
    "data-chart",
    "flowing-gradient",
    "fractal-noise",
    "frost",
    "godrays",
    "goo",
    "holographic",
    "instagram-follow",
    "lens-flare",
    "liquid-metal",
    "lt-accent-underline",
    "lt-bold-block",
    "lt-clean-bar",
    "lt-color-block",
    "lt-dark-card",
    "lt-kicker-name",
    "lt-mask-reveal",
    "lt-side-rule",
    "lt-soft-pill",
    "lt-stack-bars",
    "marble",
    "mesh-gradient",
    "nebula",
    "plasma",
    "prism",
    "sine-wave",
    "strands",
    "stripes",
    "swirl",
    "tiktok-follow",
    "voronoi",
    "water",
    "waveform",
    "weight-wave",
    "yt-lower-third",
}

# Retired 6Clips blocks that must never be presented as operable originals
RETIRED_BLOCKS: Set[str] = {
    "creator-hud",
    "glitch-transition",
}

# Categorized operable originals for semantic matching
OPERABLE_CATEGORIES: Dict[str, List[str]] = {
    "infographics": ["data-chart", "weight-wave"],
    "lower_thirds": [
        "lt-clean-bar",
        "lt-bold-block",
        "lt-accent-underline",
        "lt-color-block",
        "lt-dark-card",
        "lt-kicker-name",
        "lt-mask-reveal",
        "lt-side-rule",
        "lt-soft-pill",
        "lt-stack-bars",
        "yt-lower-third",
    ],
    "social": ["instagram-follow", "tiktok-follow", "yt-lower-third"],
    "motion_backgrounds": [
        "flowing-gradient",
        "mesh-gradient",
        "aurora",
        "nebula",
        "plasma",
        "holographic",
        "liquid-metal",
        "prism",
        "voronoi",
        "waveform",
        "sine-wave",
        "blob",
        "godrays",
        "goo",
        "lens-flare",
        "marble",
        "strands",
        "stripes",
        "swirl",
        "water",
        "frost",
        "fractal-noise",
    ],
}


class BlockSelector:
    """Selects operable HyperFrames originals based on user intent and channel constraints."""

    @classmethod
    def is_operable(cls, block_id: str) -> bool:
        """True if block_id belongs to the 37 verified operable donor originals."""
        return block_id in OPERABLE_ORIGINALS_37

    @classmethod
    def check_block_availability(cls, block_id: str) -> Tuple[bool, str]:
        """
        Check if a requested block is available, unported, or retired.
        Returns (is_available, status_detail).
        """
        if block_id in RETIRED_BLOCKS:
            return False, f"Block '{block_id}' is retired and removed from active catalog."
        if block_id in OPERABLE_ORIGINALS_37:
            return True, "Verified operable HyperFrames donor original."
        return False, f"Block '{block_id}' is unported or awaiting stage-two acceptance."

    @classmethod
    def select_operable_block(
        cls,
        intent_text: str,
        preferred_category: Optional[str] = None,
        requested_block_id: Optional[str] = None,
    ) -> Tuple[str, str, str]:
        """
        Autonomously pick an operable HyperFrames original matching intent.
        Returns: (block_id, category, rationale).
        """
        # If user explicitly specified a block ID:
        if requested_block_id:
            if cls.is_operable(requested_block_id):
                category = cls._resolve_category_for_block(requested_block_id)
                return requested_block_id, category, f"Directly requested verified operable original '{requested_block_id}'."
            # Unported or retired block requested: provide truthful substitution
            is_avail, reason = cls.check_block_availability(requested_block_id)
            fallback = cls._semantic_match(intent_text, preferred_category)
            return (
                fallback[0],
                fallback[1],
                f"Requested block '{requested_block_id}' is not operable ({reason}). "
                f"Autonomously selected verified operable original '{fallback[0]}'.",
            )

        # Semantic matching from intent keywords
        return cls._semantic_match(intent_text, preferred_category)

    @classmethod
    def _semantic_match(
        cls,
        intent_text: str,
        preferred_category: Optional[str] = None,
    ) -> Tuple[str, str, str]:
        lower = intent_text.lower()

        # Infographics / Data / Metrics
        if any(w in lower for w in ("data", "chart", "finance", "metric", "stat", "economy", "growth", "numbers", "graph")):
            return "data-chart", "infographics", "Selected 'data-chart' for quantitative and financial topic alignment."

        # Social / YouTube / Follow CTA
        if any(w in lower for w in ("youtube", "subscribe", "subscribers", "follow", "creator", "channel")):
            if "tiktok" in lower:
                return "tiktok-follow", "social", "Selected 'tiktok-follow' for TikTok creator engagement CTA."
            if "instagram" in lower or "insta" in lower:
                return "instagram-follow", "social", "Selected 'instagram-follow' for Instagram creator engagement CTA."
            return "yt-lower-third", "lower_thirds", "Selected 'yt-lower-third' for YouTube branding and speaker title."

        # Lower thirds / News / Interview / Speaker
        if any(w in lower for w in ("news", "interview", "speaker", "headline", "quote", "podcast", "title")):
            return "lt-clean-bar", "lower_thirds", "Selected 'lt-clean-bar' for clean, readable editorial lower thirds."

        # High energy / Tech / Gaming
        if any(w in lower for w in ("tech", "gaming", "future", "ai", "crypto", "neon", "code")):
            return "holographic", "motion_backgrounds", "Selected 'holographic' for futuristic/tech visual backdrop."

        # Default clean motion background
        if preferred_category and preferred_category in OPERABLE_CATEGORIES:
            block = OPERABLE_CATEGORIES[preferred_category][0]
            return block, preferred_category, f"Selected '{block}' for requested '{preferred_category}' category."

        return "flowing-gradient", "motion_backgrounds", "Selected 'flowing-gradient' as clean, versatile motion backdrop."

    @classmethod
    def _resolve_category_for_block(cls, block_id: str) -> str:
        for cat, blocks in OPERABLE_CATEGORIES.items():
            if block_id in blocks:
                return cat
        return "general"
