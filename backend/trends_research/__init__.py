# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Trends Research package.
Provides verified trend discovery, editorial role separation, deterministic ranking,
and reference style extraction.
"""
from backend.trends_research.models import (
    AnalysisState,
    DiscoveryItem,
    EditorialRole,
    HighlightQuality,
    PermittedUse,
    PhysicalBytesAvailability,
    SourceSuitability,
    TrendScore,
)
from backend.trends_research.ranking import (
    build_discovery_item,
    classify_source_suitability,
    compute_deterministic_trend_score,
    create_blocked_state_response,
    select_best_editorial_candidates,
)
from backend.trends_research.reference_extractor import (
    ObservableVisualFeatures,
    StyleHypothesis,
    analyze_reference_style,
)

__all__ = [
    "AnalysisState",
    "DiscoveryItem",
    "EditorialRole",
    "HighlightQuality",
    "PermittedUse",
    "PhysicalBytesAvailability",
    "SourceSuitability",
    "TrendScore",
    "build_discovery_item",
    "classify_source_suitability",
    "compute_deterministic_trend_score",
    "create_blocked_state_response",
    "select_best_editorial_candidates",
    "ObservableVisualFeatures",
    "StyleHypothesis",
    "analyze_reference_style",
]
