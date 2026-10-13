# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Deterministic tests for Trends Research, Editorial Roles, Source Suitability,
and Reference Style Extraction.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest

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


class TestSourceSuitabilityClassification:
    """Tests deterministic separation between creative references and editable footage."""

    def test_short_form_is_creative_reference(self):
        suit = classify_source_suitability(duration_seconds=58, target_clips=3, clip_duration_sec=60)
        assert suit.status == "unsuitable_too_short"
        assert suit.is_suitable is False
        assert suit.is_editable_source is False
        assert suit.is_reference is True
        assert suit.trend_role == EditorialRole.CREATIVE_REFERENCE
        assert suit.format_category == "short_form"
        assert suit.deficit_seconds == 180 - 58
        assert "valuable research reference" in suit.reason

    def test_marginal_duration_candidate(self):
        suit = classify_source_suitability(duration_seconds=200, target_clips=3, clip_duration_sec=60)
        assert suit.status == "marginal"
        assert suit.is_suitable is True
        assert suit.is_editable_source is True
        assert suit.trend_role == EditorialRole.MARGINAL_SOURCE
        assert suit.format_category == "marginal"

    def test_substantial_longform_is_editable_source(self):
        suit = classify_source_suitability(duration_seconds=600, target_clips=3, clip_duration_sec=60)
        assert suit.status == "suitable_longform"
        assert suit.is_suitable is True
        assert suit.is_editable_source is True
        assert suit.trend_role == EditorialRole.EDITABLE_SOURCE_CANDIDATE
        assert suit.format_category == "long_form"
        assert suit.surplus_seconds == 600 - 240
        assert "Substantial footage" in suit.reason

    def test_unknown_duration_preserved_as_unverified_reference(self):
        suit = classify_source_suitability(duration_seconds=None, target_clips=3, clip_duration_sec=60)
        assert suit.status == "unknown_duration"
        assert suit.is_suitable is False
        assert suit.is_editable_source is False
        assert suit.is_reference is True
        assert suit.trend_role == EditorialRole.CREATIVE_REFERENCE
        assert suit.format_category == "unknown"


class TestTrendScoreTransparency:
    """Verifies that missing metrics are never fraudulently reported as zero."""

    def test_missing_metrics_explicitly_tracked(self):
        data = {
            "views": 50000,
            # likes, comments, shares are missing
            "upload_date": datetime.now(timezone.utc) - timedelta(days=2),
        }
        score = compute_deterministic_trend_score(data, provenance="youtube_public_test")
        assert score.views == 50000
        assert score.likes is None
        assert score.comments is None
        assert score.shares is None
        assert "likes" in score.missing_metrics
        assert "comments" in score.missing_metrics
        assert score.input_provenance == "youtube_public_test"
        assert score.virality_score > 0.0

    def test_zero_metrics_distinguished_from_missing(self):
        data = {
            "views": 100,
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "upload_date": datetime.now(timezone.utc) - timedelta(days=1),
        }
        score = compute_deterministic_trend_score(data, provenance="api_v3_test")
        assert score.likes == 0
        assert score.comments == 0
        assert score.shares == 0
        assert score.missing_metrics == []


class TestHighlightQualityGate:
    """Ensures highlight quality remains strictly NOT_ASSESSED prior to transcript analysis."""

    def test_discovery_item_defaults_to_unassessed_highlight_quality(self):
        item_dict = {
            "id": "vid-123",
            "platform": "youtube",
            "title": "Insane Fortnite Endgame Clutch",
            "duration_seconds": 720,
            "views": 250000,
            "likes": 12000,
        }
        discovery_item = build_discovery_item(item_dict)
        hq = discovery_item.highlight_quality
        assert hq.status == "NOT_ASSESSED"
        assert hq.assessed is False
        assert hq.score is None
        assert "requires media ingestion" in hq.reason


class TestDiscoveryRankingAndSelection:
    """Tests automatic candidate selection based on editorial workflow."""

    def test_clip_repurposing_selects_editable_source_candidate(self):
        items = [
            build_discovery_item({
                "id": "short-1",
                "title": "Viral Short Hook",
                "duration_seconds": 45,
                "views": 2000000,
                "likes": 150000,
            }),
            build_discovery_item({
                "id": "long-1",
                "title": "Full Match Gameplay VOD",
                "duration_seconds": 1200,
                "views": 350000,
                "likes": 20000,
            }),
            build_discovery_item({
                "id": "marginal-1",
                "title": "Quick Match",
                "duration_seconds": 210,
                "views": 500000,
                "likes": 30000,
            }),
        ]
        # For clip repurposing, the 1200s long video MUST be chosen despite lower raw views
        selected = select_best_editorial_candidates(items, goal="clip_repurposing", count=1)
        assert len(selected) == 1
        assert selected[0].id == "long-1"
        assert selected[0].editorial_role == EditorialRole.EDITABLE_SOURCE_CANDIDATE

    def test_creative_reference_selects_viral_short(self):
        items = [
            build_discovery_item({
                "id": "short-1",
                "title": "Viral Short Hook",
                "duration_seconds": 45,
                "views": 2000000,
                "likes": 150000,
            }),
            build_discovery_item({
                "id": "long-1",
                "title": "Full Match Gameplay VOD",
                "duration_seconds": 1200,
                "views": 50000,
                "likes": 2000,
            }),
        ]
        # For creative reference, the viral Short with highest TrendScore is chosen
        selected = select_best_editorial_candidates(items, goal="creative_reference", count=1)
        assert len(selected) == 1
        assert selected[0].id == "short-1"
        assert selected[0].editorial_role == EditorialRole.CREATIVE_REFERENCE


class TestReferenceStyleExtraction:
    """Tests style extraction from reference videos."""

    def test_extract_short_form_style(self):
        hypo = analyze_reference_style("ref-yt-99", "Viral Movement Trick", duration_seconds=42)
        assert hypo.reference_source_id == "ref-yt-99"
        assert hypo.rendering_status == "analysis_complete_rendering_pending"
        assert "INSPIRATION ONLY" in hypo.fair_use_and_rights_notice
        assert hypo.observable_features.suggested_aspect_ratio == "9:16"
        assert hypo.observable_features.hook_duration_sec == 2.5
        assert hypo.observable_features.average_cut_duration_sec < 2.0

    def test_extract_long_form_style(self):
        hypo = analyze_reference_style("ref-yt-long", "Full Game Guide", duration_seconds=600)
        assert hypo.observable_features.suggested_aspect_ratio == "16:9"
        assert hypo.observable_features.hook_duration_sec == 4.0
        assert hypo.observable_features.average_cut_duration_sec > 3.0


class TestBlockedStateHandling:
    """Verifies informative BLOCKED state responses without phantom scoring."""

    def test_blocked_response_structure(self):
        resp = create_blocked_state_response(
            niche="Fortnite",
            reason="Platform API rate limit reached and no cached items available."
        )
        assert resp["status"] == "BLOCKED"
        assert resp["niche"] == "Fortnite"
        assert len(resp["suggested_alternatives"]) >= 2
        assert "authorized source route" in resp["action_required"]
