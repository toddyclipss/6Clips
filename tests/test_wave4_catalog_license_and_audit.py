# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 4 Role 3: Tests for Factual Audit, Dynamic Reconciliation,
License Clearance, and Explicit Blocker Annotations.
"""
import pytest
from backend.catalog.manifest_service import (
    CatalogManifestService,
    CORE_INTERNALIZED_BLOCKS,
    WAVE4_INTERNALIZED_BLOCKS,
)


def test_wave4_factual_audit_comparison():
    """Verify before (Wave 3) and after (Wave 4) factual counts and deltas."""
    audit = CatalogManifestService.get_factual_audit()
    baseline = audit["baseline_wave3"]
    expanded = audit["expanded_wave4"]
    delta = audit["delta"]

    # Wave 3 baseline counts
    assert baseline["INVENTORIED"] == 196
    assert baseline["INTERNALIZED"] == 6
    assert baseline["READY"] == 6
    assert baseline["NOT_READY"] == 190
    assert baseline["LICENSE_BLOCKED"] == 165

    # Wave 4 expanded counts
    assert expanded["INVENTORIED"] == 196
    assert expanded["INTERNALIZED"] == 10
    assert expanded["DEPENDENCIES_VERIFIED"] == 10
    assert expanded["RENDER_TESTED"] == 10
    assert expanded["BROWSER_VERIFIED"] == 10
    assert expanded["READY"] == 10
    assert expanded["NOT_READY"] == 186
    assert expanded["READY"] + expanded["NOT_READY"] == expanded["INVENTORIED"]

    # Blocker categories sum to NOT_READY
    assert expanded["LICENSE_REVIEW_REQUIRED"] + expanded["STRUCTURAL_FIX_REQUIRED"] == expanded["NOT_READY"]

    # Delta assertions
    assert delta["ready_count_diff"] == 4
    assert delta["not_ready_count_diff"] == -4
    assert set(delta["newly_operational_blocks"]) == {
        "flowing-gradient",
        "plasma",
        "stripes",
        "holographic",
        "creator-hud",
        "glitch-transition",
    }


def test_wave4_explicit_blocker_reasons_on_all_unready_items():
    """Verify that 100% of unready items have non-empty English blocker reasons and codes."""
    items = CatalogManifestService.get_all_items()
    assert len(items) == 196

    ready_items = [it for it in items if it.get("runtime_ready")]
    unready_items = [it for it in items if not it.get("runtime_ready")]

    assert len(ready_items) == 10
    assert len(unready_items) == 186

    for it in unready_items:
        b_code = it.get("blocker_code")
        b_reason = it.get("blocker_reason")

        assert b_code in (
            "LICENSE_REVIEW_REQUIRED_AMBIGUOUS_RIGHTS",
            "STRUCTURAL_FIX_MISSING_ENTRYPOINT",
        ), f"Item {it['id']} has invalid blocker code: {b_code}"

        assert isinstance(b_reason, str) and len(b_reason) > 10, f"Item {it['id']} missing detailed blocker reason"
        assert "coming soon" not in b_reason.lower(), f"Item {it['id']} used vague 'coming soon'"


def test_wave4_category_summary_breakdown():
    """Verify truthful per-category operational status and blocker aggregation."""
    cat_summary = CatalogManifestService.get_category_summary()
    assert cat_summary["total_categories"] >= 7

    by_cat = cat_summary["summary_by_category"]

    # Verify background category has ready items
    assert "backgrounds" in by_cat
    assert by_cat["backgrounds"]["ready_count"] >= 2
    assert "aurora" in by_cat["backgrounds"]["ready_blocks"]
    assert "flowing-gradient" in by_cat["backgrounds"]["ready_blocks"]

    # Verify call-to-action has ready items
    assert "call-to-action" in by_cat
    assert by_cat["call-to-action"]["ready_count"] >= 2
    assert "instagram-follow" in by_cat["call-to-action"]["ready_blocks"]
    assert "tiktok-follow" in by_cat["call-to-action"]["ready_blocks"]

    # Verify typography has ready items
    assert "typography" in by_cat
    assert by_cat["typography"]["ready_count"] >= 2
    assert "weight-wave" in by_cat["typography"]["ready_blocks"]
    assert "plasma" in by_cat["typography"]["ready_blocks"]

    # Verify transitions has ready items
    assert "transitions" in by_cat
    assert by_cat["transitions"]["ready_count"] >= 1
    assert "stripes" in by_cat["transitions"]["ready_blocks"]

    # Verify total sum matches 196
    total_audited = sum(data["total"] for data in by_cat.values())
    assert total_audited == 196


def test_wave4_license_inventory_provenance():
    """Verify license attribution records explicit license grants or authorship."""
    inventory = CatalogManifestService.get_license_inventory()
    assert len(inventory) == 196

    ready_inventory = [it for it in inventory if it.get("runtime_ready")]
    assert len(ready_inventory) == 10

    for it in ready_inventory:
        assert it["license"] in ("Apache-2.0", "Apache-2.0 AND MIT", "OFL-1.1", "MIT")
        assert it["blocker_code"] is None
        assert it["blocker_reason"] is None
