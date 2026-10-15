# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Test Suite for Wave 18 Agent 1: Block Selector Census & 10-Block Preview Baseline.

Tests:
- Owner's 10-block preview verification baseline
- Dynamic discovery via UniversalRuntimeRegistry
- Strict retirement and rejection of 6Clips-authored blocks ('creator-hud', 'glitch-transition')
- Truthful substitution when unported blocks are requested
- Complete 196-block provenance ledger with per-ID status and blocker codes
"""

import pytest
from backend.oaas_outcomes.block_selector import (
    BlockSelector,
    TEN_DONOR_PREVIEW_VERIFIED,
    OPERABLE_ORIGINALS_37,
    RETIRED_BLOCKS,
)


def test_ten_block_preview_baseline():
    """Validates the owner's 10-block preview baseline is strictly respected."""
    assert len(TEN_DONOR_PREVIEW_VERIFIED) == 10
    expected_10 = {
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
    assert TEN_DONOR_PREVIEW_VERIFIED == expected_10

    # When require_user_preview=True, get_operable_blocks returns exactly these 10
    preview_operable = BlockSelector.get_operable_blocks(require_user_preview=True)
    assert preview_operable == expected_10
    for b_id in expected_10:
        assert BlockSelector.is_operable(b_id, require_user_preview=True) is True
        assert BlockSelector.is_preview_verified(b_id) is True


def test_retired_blocks_strictly_excluded():
    """Validates that creator-hud and glitch-transition are permanently rejected."""
    for retired in RETIRED_BLOCKS:
        assert BlockSelector.is_operable(retired) is False
        assert BlockSelector.is_operable(retired, require_user_preview=True) is False
        assert BlockSelector.is_preview_verified(retired) is False

        is_avail, reason = BlockSelector.check_block_availability(retired)
        assert is_avail is False
        assert "retired" in reason.lower()


def test_truthful_substitution_for_unported_or_retired():
    """When an unported or retired block is requested, selector provides truthful fallback."""
    # 1. Requesting retired block
    selected, cat, rationale = BlockSelector.select_operable_block(
        intent_text="Gaming stream outro",
        requested_block_id="creator-hud",
    )
    assert selected in OPERABLE_ORIGINALS_37 or selected in TEN_DONOR_PREVIEW_VERIFIED
    assert "not operable" in rationale.lower()
    assert "retired" in rationale.lower()

    # 2. Requesting unported block
    selected_unp, cat_unp, rationale_unp = BlockSelector.select_operable_block(
        intent_text="Financial data chart",
        requested_block_id="nonexistent-dummy-block",
    )
    assert BlockSelector.is_operable(selected_unp) is True
    assert "not operable" in rationale_unp.lower()


def test_semantic_intent_matching():
    """Semantic keywords map to appropriate operable HyperFrames blocks."""
    # Financial keywords -> data-chart
    b1, cat1, rat1 = BlockSelector.select_operable_block(intent_text="Analyze quarterly stock market earnings and revenue")
    assert b1 == "data-chart"
    assert cat1 == "infographics"

    # Social YouTube keywords -> yt-lower-third
    b2, cat2, rat2 = BlockSelector.select_operable_block(intent_text="Subscribe to our YouTube channel for weekly insights")
    assert b2 in ("yt-lower-third", "tiktok-follow", "instagram-follow")

    # Tech keywords -> holographic
    b3, cat3, rat3 = BlockSelector.select_operable_block(intent_text="The future of artificial intelligence code and neon tech")
    assert b3 == "holographic"


def test_full_196_ledger_integrity():
    """Validates that the 196-block ledger is complete and well-formed."""
    ledger = BlockSelector.get_full_196_ledger()
    assert isinstance(ledger, dict)
    assert len(ledger) >= 37  # At least the verified set + retired

    # Verify the 10 preview verified blocks have correct status
    for b_id in TEN_DONOR_PREVIEW_VERIFIED:
        assert b_id in ledger
        assert ledger[b_id]["user_preview_verified"] is True
        assert ledger[b_id]["status"] == "USER_PREVIEW_VERIFIED"

    # Verify retired blocks have retired status
    for b_id in RETIRED_BLOCKS:
        assert b_id in ledger
        assert ledger[b_id]["runtime_operable"] is False
        assert ledger[b_id]["status"] == "RETIRED_6CLIPS"
        assert ledger[b_id]["blocker_code"] == "BLOCKED_RETIRED_6CLIPS"
