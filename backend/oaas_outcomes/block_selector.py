# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Autonomous HyperFrames Block Selector (Wave 18 OAAS Runtime Integration).

Provides authoritative, runtime-discovered HyperFrames donor block selection
based on actual runtime capabilities, preview verification, and export proof.
Enforces:
1. Owner's baseline truth: exactly 10 blocks are verified as user-visible in preview.
2. Dynamic discovery from UniversalRuntimeRegistry (no synthetic claims of 149/196 operable).
3. Strict retirement of 6Clips-authored blocks ('creator-hud', 'glitch-transition').
4. Full transparent per-ID rejection explanations for all 196 donor identities.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# The 10 donor-origin blocks verified with affirmative in-browser preview and render evidence
# (Owner's running-app preview baseline)
TEN_DONOR_PREVIEW_VERIFIED: Set[str] = {
    "aurora",
    "data-chart",
    "flowing-gradient",
    "holographic",
    "instagram-follow",
    "plasma",
    "stripes",
    "tiktok-follow",
    "weight-wave",
    "yt-lower-third",
}

# Legacy 37-block verified set (retained for backward compatibility and test stability)
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

# Retired 6Clips-authored blocks that must never be presented as operable donor originals
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
    """
    Authoritative selector for HyperFrames donor blocks in OAAS outcome workflows.
    Queries the runtime registry dynamically while strictly respecting the owner's
    10-block preview verification baseline and fail-closed readiness gates.
    """

    @classmethod
    def get_runtime_registry(cls) -> Optional[Any]:
        """Dynamically load the UniversalRuntimeRegistry if available."""
        try:
            from backend.catalog_runtime.core.registry_engine import UniversalRuntimeRegistry
            return UniversalRuntimeRegistry
        except Exception as e:
            logger.debug("UniversalRuntimeRegistry unavailable: %s", e)
            return None

    @classmethod
    def get_operable_blocks(cls, require_user_preview: bool = False) -> Set[str]:
        """
        Return the set of operable block IDs.
        If require_user_preview is True: strictly restricts to TEN_DONOR_PREVIEW_VERIFIED.
        Otherwise queries UniversalRuntimeRegistry for operable blocks or falls back to OPERABLE_ORIGINALS_37.
        """
        if require_user_preview:
            return set(TEN_DONOR_PREVIEW_VERIFIED)

        registry = cls.get_runtime_registry()
        if registry:
            try:
                blocks = registry.discover_all_blocks()
                operable = {
                    b_id for b_id, b in blocks.items()
                    if getattr(b, "runtime_operable", False) and b_id not in RETIRED_BLOCKS
                }
                if operable:
                    return operable
            except Exception as e:
                logger.warning("Failed querying UniversalRuntimeRegistry for operable blocks: %s", e)

        return set(OPERABLE_ORIGINALS_37)

    @classmethod
    def is_operable(cls, block_id: str, require_user_preview: bool = False) -> bool:
        """True if block_id is verified operable without blocker codes."""
        if block_id in RETIRED_BLOCKS:
            return False
        if require_user_preview:
            return block_id in TEN_DONOR_PREVIEW_VERIFIED
        return block_id in cls.get_operable_blocks(require_user_preview=False)

    @classmethod
    def is_preview_verified(cls, block_id: str) -> bool:
        """True if block is in the owner-observed 10-block preview baseline."""
        return block_id in TEN_DONOR_PREVIEW_VERIFIED

    @classmethod
    def check_block_availability(cls, block_id: str) -> Tuple[bool, str]:
        """
        Check if a requested block is available, unported, or retired.
        Returns (is_available, status_detail).
        """
        if block_id in RETIRED_BLOCKS:
            return False, f"Block '{block_id}' is retired (6Clips-authored) and removed from active catalog."

        if block_id in TEN_DONOR_PREVIEW_VERIFIED:
            return True, "Verified operable HyperFrames donor original with user preview verification."

        registry = cls.get_runtime_registry()
        if registry:
            try:
                block = registry.get_block(block_id)
                if block:
                    if getattr(block, "runtime_operable", False):
                        return True, "Verified operable HyperFrames donor original."
                    code = getattr(block, "blocker_code", None) or "BLOCKED_UNPORTED"
                    reason = getattr(block, "blocker_reason", None) or "Awaiting runtime porting and acceptance."
                    return False, f"Block '{block_id}' is not operable ({code}: {reason})."
            except Exception:
                pass

        if block_id in OPERABLE_ORIGINALS_37:
            return True, "Verified operable HyperFrames donor original."

        return False, f"Block '{block_id}' is unported or awaiting stage-two acceptance."

    @classmethod
    def select_operable_block(
        cls,
        intent_text: str,
        preferred_category: Optional[str] = None,
        requested_block_id: Optional[str] = None,
        require_user_preview: bool = False,
    ) -> Tuple[str, str, str]:
        """
        Autonomously pick an operable HyperFrames original matching intent.
        Returns: (block_id, category, rationale).
        """
        # If user explicitly specified a block ID:
        if requested_block_id:
            if cls.is_operable(requested_block_id, require_user_preview=require_user_preview):
                category = cls._resolve_category_for_block(requested_block_id)
                pv_note = " (preview verified)" if requested_block_id in TEN_DONOR_PREVIEW_VERIFIED else ""
                return requested_block_id, category, f"Directly requested verified operable original '{requested_block_id}'{pv_note}."

            # Unported or retired block requested: provide truthful substitution
            is_avail, reason = cls.check_block_availability(requested_block_id)
            fallback = cls._semantic_match(intent_text, preferred_category, require_user_preview=require_user_preview)
            return (
                fallback[0],
                fallback[1],
                f"Requested block '{requested_block_id}' is not operable ({reason}). "
                f"Autonomously selected verified operable original '{fallback[0]}'.",
            )

        # Semantic matching from intent keywords
        return cls._semantic_match(intent_text, preferred_category, require_user_preview=require_user_preview)

    @classmethod
    def _semantic_match(
        cls,
        intent_text: str,
        preferred_category: Optional[str] = None,
        require_user_preview: bool = False,
    ) -> Tuple[str, str, str]:
        lower = intent_text.lower()

        # Infographics / Data / Metrics / Financials
        if any(w in lower for w in ("data", "chart", "finance", "metric", "stat", "economy", "growth", "numbers", "graph", "stock", "market", "earnings", "revenue", "profit")):
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
            if require_user_preview:
                return "yt-lower-third", "lower_thirds", "Selected 'yt-lower-third' (preview verified) for speaker title."
            return "lt-clean-bar", "lower_thirds", "Selected 'lt-clean-bar' for clean, readable editorial lower thirds."

        # High energy / Tech / Gaming
        if any(w in lower for w in ("tech", "gaming", "future", "ai", "crypto", "neon", "code")):
            return "holographic", "motion_backgrounds", "Selected 'holographic' for futuristic/tech visual backdrop."

        # Default clean motion background
        if preferred_category and preferred_category in OPERABLE_CATEGORIES:
            candidates = [
                b for b in OPERABLE_CATEGORIES[preferred_category]
                if not require_user_preview or b in TEN_DONOR_PREVIEW_VERIFIED
            ]
            if candidates:
                block = candidates[0]
                return block, preferred_category, f"Selected '{block}' for requested '{preferred_category}' category."

        return "flowing-gradient", "motion_backgrounds", "Selected 'flowing-gradient' as clean, versatile motion backdrop."

    @classmethod
    def _resolve_category_for_block(cls, block_id: str) -> str:
        for cat, blocks in OPERABLE_CATEGORIES.items():
            if block_id in blocks:
                return cat
        return "general"

    @classmethod
    def get_full_196_ledger(cls) -> Dict[str, Dict[str, Any]]:
        """
        Generate comprehensive, truthful 196-block ledger detailing provenance,
        readiness ladder, preview status, and exact blocker reasons.
        """
        registry = cls.get_runtime_registry()
        ledger: Dict[str, Dict[str, Any]] = {}

        if registry:
            try:
                blocks = registry.discover_all_blocks()
                for b_id, b in sorted(blocks.items()):
                    is_preview = b_id in TEN_DONOR_PREVIEW_VERIFIED
                    is_op = getattr(b, "runtime_operable", False) and b_id not in RETIRED_BLOCKS
                    status = "USER_PREVIEW_VERIFIED" if is_preview else ("RUNTIME_OPERABLE" if is_op else "BLOCKED")
                    blocker = getattr(b, "blocker_code", None)
                    if b_id in RETIRED_BLOCKS:
                        status = "RETIRED_6CLIPS"
                        blocker = "BLOCKED_RETIRED_6CLIPS"

                    ledger[b_id] = {
                        "id": b_id,
                        "status": status,
                        "runtime_operable": is_op,
                        "user_preview_verified": is_preview,
                        "blocker_code": blocker,
                        "blocker_reason": getattr(b, "blocker_reason", None) or ("Retired 6Clips authoring" if b_id in RETIRED_BLOCKS else None),
                        "source_category": getattr(b, "source_category", None) or "general",
                    }
                return ledger
            except Exception as ex:
                logger.warning("Error generating 196 ledger from registry: %s", ex)

        # Scaffolding fallback if registry not fully loaded
        for b_id in sorted(OPERABLE_ORIGINALS_37):
            is_preview = b_id in TEN_DONOR_PREVIEW_VERIFIED
            ledger[b_id] = {
                "id": b_id,
                "status": "USER_PREVIEW_VERIFIED" if is_preview else "RUNTIME_OPERABLE",
                "runtime_operable": True,
                "user_preview_verified": is_preview,
                "blocker_code": None,
                "blocker_reason": None,
                "source_category": cls._resolve_category_for_block(b_id),
            }
        for b_id in RETIRED_BLOCKS:
            ledger[b_id] = {
                "id": b_id,
                "status": "RETIRED_6CLIPS",
                "runtime_operable": False,
                "user_preview_verified": False,
                "blocker_code": "BLOCKED_RETIRED_6CLIPS",
                "blocker_reason": "Retired 6Clips-authored block, not a HyperFrames original.",
                "source_category": "retired",
            }
        return ledger
