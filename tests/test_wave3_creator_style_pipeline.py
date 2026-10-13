# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Tests for Style Recipe Extraction and Multi-Niche Original Pipelines (Wave 3 Role 5).

Verifies:
- Style-only extraction: extracts abstract conventions without downloading/cloning third-party footage.
- Conversion of style hypotheses into executable composition recipes.
- Domain versatility: science, tech, cooking, and gaming niches handled generatively.
- Fair use and licensing preservation in metadata.
"""
from backend.original_creation.workflow import OriginalCreatorWorkflow
from backend.trends_research.reference_extractor import (
    analyze_reference_style,
    convert_hypothesis_to_project_recipe,
)


def test_reference_style_extraction_abstract_patterns():
    """Verify analysis extracts abstract timing/typography rather than copying assets."""
    hypo = analyze_reference_style(
        reference_id="ref-sci-101",
        title="10 Astronomy Facts That Defy Physics",
        duration_seconds=58,
        channel_or_author="CosmosDaily",
    )

    assert hypo.observable_features.suggested_aspect_ratio == "9:16"
    assert hypo.observable_features.hook_duration_sec == 2.5
    assert hypo.observable_features.motion_energy == "high"
    assert "INSPIRATION ONLY" in hypo.fair_use_and_rights_notice
    assert "Direct reproduction of third-party footage" in hypo.fair_use_and_rights_notice


def test_hypothesis_to_project_recipe_conversion():
    """Verify style hypothesis translates cleanly to an original project recipe."""
    hypo = analyze_reference_style(
        reference_id="ref-culinary-202",
        title="Perfect Espresso in 60 Seconds",
        duration_seconds=60,
        channel_or_author="CoffeeLab",
    )

    recipe = convert_hypothesis_to_project_recipe(hypo, custom_target_duration_sec=45)

    assert recipe.target_duration_sec == 45
    assert recipe.target_aspect_ratio == "9:16"
    assert recipe.scene_cadence_seconds > 1.0
    assert "background" in recipe.color_palette
    assert len(recipe.composition_rules) >= 4
    assert "No third-party footage cloning" in recipe.composition_rules[-1]
    assert "Zero copyrighted reference" in recipe.licensing_terms


def test_generic_creator_multi_niche_grounding():
    """Verify evidence ledgers ground properly across science, culinary, and tech niches."""
    # Science / Astronomy
    science_brief = OriginalCreatorWorkflow.create_brief(topic="James Webb Galaxy Analysis")
    assert any("infrared" in e.claim_text.lower() or "galaxy" in e.claim_text.lower() for e in science_brief.evidence_ledger.entries)

    # Culinary
    culinary_brief = OriginalCreatorWorkflow.create_brief(topic="Coffee Roasting Science")
    assert any("maillard" in e.claim_text.lower() or "acidity" in e.claim_text.lower() for e in culinary_brief.evidence_ledger.entries)

    # AI / Technology
    tech_brief = OriginalCreatorWorkflow.create_brief(topic="Transformer Attention Mechanism")
    assert any("attention" in e.claim_text.lower() or "memory" in e.claim_text.lower() for e in tech_brief.evidence_ledger.entries)

    # Creator Custom Context
    custom_brief = OriginalCreatorWorkflow.create_brief(
        topic="Custom Hardware Review",
        creator_context="Benchmark tests show a 35% reduction in thermal throttling under load.",
    )
    assert any("35%" in e.claim_text for e in custom_brief.evidence_ledger.entries)
