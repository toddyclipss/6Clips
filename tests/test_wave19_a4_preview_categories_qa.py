# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
r"""
Wave 19 Agent 4 Comprehensive Test Suite:
HyperFrames True Preview, Source Categories & Anti-Fake QA.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CROSSWALK_PATH = REPO_ROOT / "backend" / "catalog_inventory" / "hyperframes_196_source_crosswalk.json"
SHIPPED_BLOCKS = REPO_ROOT / "backend" / "catalog" / "shipped_blocks"
LEDGER_PATH = REPO_ROOT / "tools" / "wave19_a4" / "196_REAL_RUNNING_UI_PREVIEW_LEDGER.json"

OWNER_10_BASELINE = {
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

RETIRED_6CLIPS_BLOCKS = {"creator-hud", "glitch-transition"}

UPSTREAM_GALLERY_GROUPS = {
    "3d-motion",
    "carousels",
    "text-captions",
    "code",
    "transitions",
    "data-charts",
    "scenes-demos",
    "motion-effects",
    "surfaces",
    "blocks",
    "SOURCE_CATEGORY_UNSPECIFIED",
}


@pytest.fixture(scope="session")
def crosswalk_data():
    assert CROSSWALK_PATH.exists(), f"Crosswalk manifest missing at {CROSSWALK_PATH}"
    return json.loads(CROSSWALK_PATH.read_text(encoding="utf-8"))


def test_canonical_196_donor_census(crosswalk_data):
    """Assert exactly 196 donor block identities, strictly excluding 6Clips originals."""
    census = crosswalk_data.get("census", {})
    assert census.get("total_donor_blocks") == 196
    entries = crosswalk_data.get("entries", [])
    assert len(entries) == 196

    slugs = set(e["slug"] for e in entries)
    assert len(slugs) == 196
    # Strictly zero 6Clips-authored retired blocks in donor census
    for retired in RETIRED_6CLIPS_BLOCKS:
        assert retired not in slugs, f"Retired 6Clips block '{retired}' must be excluded from donor catalog"


def test_gallery_source_categories_distribution(crosswalk_data):
    """Verify exact 171 gallery-confirmed + 25 unspecified category distribution."""
    entries = crosswalk_data.get("entries", [])
    indexed = [e for e in entries if e["indexed_in_gallery"]]
    unindexed = [e for e in entries if not e["indexed_in_gallery"]]

    assert len(indexed) == 171
    assert len(unindexed) == 25

    # All indexed must have confirmed category status and valid group
    for it in indexed:
        assert it["category_status"] == "SOURCE_CATEGORY_CONFIRMED"
        assert it["gallery_group"] in UPSTREAM_GALLERY_GROUPS
        assert it["gallery_group"] != "SOURCE_CATEGORY_UNSPECIFIED"

    # All unindexed must be classified explicitly as SOURCE_CATEGORY_UNSPECIFIED
    for it in unindexed:
        assert it["category_status"] == "SOURCE_CATEGORY_UNSPECIFIED"
        assert it["gallery_group"] == "SOURCE_CATEGORY_UNSPECIFIED"
        assert it["gallery_section"] == "SOURCE_CATEGORY_UNSPECIFIED"


def test_owner_10_observed_baseline(crosswalk_data):
    """Confirm faithful tracking of the owner's 10-block baseline."""
    entries = crosswalk_data.get("entries", [])
    baseline_entries = [e["slug"] for e in entries if e.get("owner_observed_baseline")]
    assert len(baseline_entries) == 10
    assert set(baseline_entries) == OWNER_10_BASELINE


def test_zero_external_cdn_egress_in_shipped_blocks():
    """Assert strict airgapped zero-CDN compliance across all shipped blocks."""
    assert SHIPPED_BLOCKS.exists()
    donor_dirs = [d for d in SHIPPED_BLOCKS.iterdir() if d.is_dir() and d.name not in RETIRED_6CLIPS_BLOCKS]

    prohibited_domains = [
        "cdn.jsdelivr.net",
        "unpkg.com",
        "cdnjs.cloudflare.com",
        "fonts.googleapis.com",
        "fonts.gstatic.com",
    ]

    for bdir in donor_dirs:
        for html_file in bdir.glob("*.html"):
            text = html_file.read_text(encoding="utf-8", errors="ignore")
            for dom in prohibited_domains:
                assert dom not in text, f"Block '{bdir.name}' ({html_file.name}) violates airgap with CDN domain '{dom}'"


def test_shipped_vs_blocked_accounting(crosswalk_data):
    """Verify file census: exactly 156 donor blocks shipped on disk, 40 pending/blocked."""
    entries = crosswalk_data.get("entries", [])
    shipped = [e for e in entries if e["shipped_on_disk"]]
    unshipped = [e for e in entries if not e["shipped_on_disk"]]

    assert len(shipped) == 156
    assert len(unshipped) == 40
    assert len(shipped) + len(unshipped) == 196


def test_taxonomy_reconciler_wave19():
    """Verify DonorTaxonomyReconciler supports Wave 19 census summary."""
    from backend.catalog_runtime.core.taxonomy import (
        DonorTaxonomyReconciler,
        UNINDEXED_DONOR_BLOCK_IDS_25,
        OWNER_OBSERVED_10_BASELINE,
    )

    assert len(UNINDEXED_DONOR_BLOCK_IDS_25) == 25
    assert len(OWNER_OBSERVED_10_BASELINE) == 10

    census = DonorTaxonomyReconciler.get_census_summary(wave=19)
    assert census["total_donor_blocks"] == 196
    assert census["indexed_in_gallery_mdx"] == 171
    assert census["unindexed_block_directories"] == 25
    assert census["retired_6clips_count"] == 2
    assert census["owner_observed_baseline_count"] == 10
    assert census["donor_operable_count"] == 156
    assert census["unshipped_pending_or_blocked_count"] == 40


def test_adversarial_negative_controls():
    """Verify that the adversarial QA evaluator rejects false claims."""
    from scripts.qa_wave19.adversarial_qa_harness_w19 import AdversarialQAEvaluator

    p1, _ = AdversarialQAEvaluator.test_negative_control_reject_zero_motion()
    assert p1 is True

    p2, _ = AdversarialQAEvaluator.test_negative_control_reject_solid_black()
    assert p2 is True

    p3, _ = AdversarialQAEvaluator.test_negative_control_reject_cdn_egress()
    assert p3 is True

    p4, _ = AdversarialQAEvaluator.test_negative_control_reject_fake_category()
    assert p4 is True

    p5, _ = AdversarialQAEvaluator.test_negative_control_reject_premature_196()
    assert p5 is True


def test_legacy_and_oaas_sidebar_lock():
    """Assert preservation of 30 legacy workflows and exact 5 OAAS destinations."""
    from scripts.qa_wave19.adversarial_qa_harness_w19 import (
        AdversarialQAEvaluator,
        LEGACY_TOOLS_21,
        LEGACY_CLIP_STUDIO_9,
        OAAS_FIVE_DESTINATIONS,
    )

    assert len(LEGACY_TOOLS_21) == 21
    assert len(LEGACY_CLIP_STUDIO_9) == 9
    assert len(LEGACY_TOOLS_21) + len(LEGACY_CLIP_STUDIO_9) == 30

    expected_destinations = ["Motion Graphics", "Trends", "My Channel", "Library", "Messages"]
    assert OAAS_FIVE_DESTINATIONS == expected_destinations
    assert OAAS_FIVE_DESTINATIONS[0] == "Motion Graphics"

    p_leg, _ = AdversarialQAEvaluator.audit_legacy_30_workflows()
    assert p_leg is True

    p_oaas, _ = AdversarialQAEvaluator.audit_oaas_five_destinations()
    assert p_oaas is True
