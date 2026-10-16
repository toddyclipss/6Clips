# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Knowledge Base Adapter Boundary for Agent 1.
Consumes the Agent 3 KnowledgeBase.search() interface contract.
Provides strict validation, rejection of old HyperFrames block slugs,
and an explicitly labeled test-only fallback during pre-merge development.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .models import KnowledgeCitation

logger = logging.getLogger(__name__)

# Disallowed old block slugs - must NEVER be treated as valid knowledge citations
RETIRED_BLOCK_SLUGS = {
    "aurora", "flowing-gradient", "data-chart", "kinetic-type", "hud-elements",
    "minimal-quotes", "retro-terminal", "liquid-metal", "3d-card-reveal",
    "particle-vortex", "neon-flicker", "glassmorphism-card", "cinematic-title",
}


class TestOnlyKnowledgeAdapter:
    """
    Explicitly labeled TEST-ONLY knowledge corpus adapter used during isolated development
    prior to Agent 3's real corpus integration.
    Contains curated technique entries strictly conforming to Agent 3's schema.
    """

    _TEST_CORPUS = [
        {
            "knowledge_doc_id": "hf-doc-kinetic-text-01",
            "source_path": "docs/catalog/components/typography/kinetic-word-stagger.mdx",
            "source_hash": "c63ebdcbe00c06b7d93143056be2bb37d7edc77c5076c1dd3b1c9931f36ddb8a",
            "techniques": "kinetic_word_stagger, spring_easing, staggered_opacity",
            "donor_group": "typography",
            "capability_family": "kinetic_typography",
            "rights": "PERMITTED_INERT_TECHNIQUE",
            "runtime_constraints": "canvas_or_motion_player",
            "retrieval_explanation": "Extracted word-by-word spring entrance technique for high-impact title sequences.",
        },
        {
            "knowledge_doc_id": "hf-doc-chart-morph-02",
            "source_path": "docs/catalog/components/data/bar-chart-fill.mdx",
            "source_hash": "d2a233633ab0a7e6b04312e03f0b2f5b5f25bf0954b4a9a08e1e47d4e5d6148a",
            "techniques": "procedural_bar_growth, count_up_numeric, ease_out_cubic",
            "donor_group": "data_visualization",
            "capability_family": "data_presentation",
            "rights": "PERMITTED_INERT_TECHNIQUE",
            "runtime_constraints": "responsive_aspect_aware",
            "retrieval_explanation": "Dynamic numeric count-up and cubic ease-out bar rendering technique.",
        },
        {
            "knowledge_doc_id": "hf-doc-captions-pop-03",
            "source_path": "skills/embedded-captions/word-highlight-pop.mdx",
            "source_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "techniques": "word_level_highlight, scale_pop_1_15, high_contrast_pill",
            "donor_group": "embedded_captions",
            "capability_family": "accessible_captions",
            "rights": "PERMITTED_INERT_TECHNIQUE",
            "runtime_constraints": "requires_speech_timestamps",
            "retrieval_explanation": "High-contrast active word highlighting with scale pop on speech beats.",
        },
        {
            "knowledge_doc_id": "hf-doc-gradient-wave-04",
            "source_path": "docs/catalog/components/backgrounds/parametric-mesh-gradient.mdx",
            "source_hash": "f4c285619316e6d105a6501d815719f107371dd3ce577b9a85702f00a0495f52",
            "techniques": "parametric_sine_color_wave, procedural_perlin_blend",
            "donor_group": "backgrounds",
            "capability_family": "procedural_visuals",
            "rights": "PERMITTED_INERT_TECHNIQUE",
            "runtime_constraints": "hardware_accelerated",
            "retrieval_explanation": "Procedural mathematical wave color mesh for non-distracting background depth.",
        },
        {
            "knowledge_doc_id": "hf-doc-cinematic-lowerthird-05",
            "source_path": "docs/catalog/components/overlays/cinematic-accent-line.mdx",
            "source_hash": "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e",
            "techniques": "accent_line_wipe, subtitle_opacity_fade, safe_area_clipping",
            "donor_group": "overlays",
            "capability_family": "editorial_lowerthird",
            "rights": "PERMITTED_INERT_TECHNIQUE",
            "runtime_constraints": "safe_title_area_margins",
            "retrieval_explanation": "Geometric horizontal line wipe revealing secondary metadata.",
        },
    ]

    @classmethod
    def search(
        cls,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search test-only knowledge corpus using keyword matching."""
        query_words = set(query.lower().split())
        scored: List[Tuple[int, Dict[str, Any]]] = []

        for item in cls._TEST_CORPUS:
            score = 0
            text_corpus = (
                f"{item['techniques']} {item['capability_family']} "
                f"{item['donor_group']} {item['retrieval_explanation']}"
            ).lower()
            for w in query_words:
                if w in text_corpus:
                    score += 1
            scored.append((score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [item for _, item in scored[:limit]]
        return results


class KnowledgeBaseAdapter:
    """
    Adapter bridging Agent 1's orchestrator with the authentic Agent 3 KnowledgeBase.
    Automatically detects whether Agent 3's backend/knowledge_base module is loaded.
    """

    @classmethod
    def search_knowledge(
        cls,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 3,
    ) -> Tuple[List[KnowledgeCitation], bool]:
        """
        Execute knowledge search and return validated KnowledgeCitation objects.
        Returns (citations_list, is_production_corpus).
        """
        raw_hits = []
        is_production = False

        # Attempt to import Agent 3 KnowledgeBase if merged
        try:
            from backend.knowledge_base import KnowledgeBase
            raw_hits = KnowledgeBase.search(query=query, filters=filters, limit=limit)
            is_production = True
            logger.info("Retrieved %d citations from production KnowledgeBase", len(raw_hits))
        except (ImportError, AttributeError):
            logger.info("Production KnowledgeBase not yet merged. Using TestOnlyKnowledgeAdapter.")
            raw_hits = TestOnlyKnowledgeAdapter.search(query=query, filters=filters, limit=limit)
            is_production = False

        citations: List[KnowledgeCitation] = []
        for hit in raw_hits:
            doc_id = hit.get("knowledge_doc_id", "unknown-doc")
            if doc_id in RETIRED_BLOCK_SLUGS:
                logger.warning("Rejected retired block slug '%s' from knowledge results", doc_id)
                continue

            tech = hit.get("techniques") or hit.get("technique") or "procedural_motion"
            citation = KnowledgeCitation(
                knowledge_doc_id=doc_id,
                source_path=hit.get("source_path") or hit.get("source_ref") or "docs/unknown",
                source_hash=hit.get("source_hash", "0" * 64),
                technique=tech,
                donor_group=hit.get("donor_group"),
                capability_family=hit.get("capability_family"),
                rights=hit.get("rights", "PERMITTED"),
                runtime_constraints=hit.get("runtime_constraints"),
                retrieval_explanation=hit.get("retrieval_explanation"),
            )
            citations.append(citation)

        return citations, is_production
