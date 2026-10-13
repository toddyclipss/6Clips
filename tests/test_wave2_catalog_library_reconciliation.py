# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 2 Agent 4: Tests for HyperFrames Catalog inventory reconciliation, manifest filtering, and legal provenance."""
import json
import pytest
from pathlib import Path

from backend.catalog.manifest_service import CatalogManifestService, CatalogManifestError


def test_reconciliation_exact_counts():
    """Verify exact historical reconciliation: 196 block dirs, 170 aggregate items, 26 unbundled, 222 components, 8 examples."""
    recon = CatalogManifestService.get_reconciliation_summary()
    r = recon["reconciliation"]

    assert r["historical_block_dirs"] == 196, f"Expected 196 historical block dirs, got {r['historical_block_dirs']}"
    assert r["aggregate_manifest_blocks"] == 170, f"Expected 170 aggregate manifest blocks, got {r['aggregate_manifest_blocks']}"
    assert r["unbundled_block_dirs"] == 26, f"Expected 26 unbundled blocks, got {r['unbundled_block_dirs']}"
    assert r["aggregate_components"] == 222, f"Expected 222 microcomponents, got {r['aggregate_components']}"
    assert r["aggregate_examples"] == 8, f"Expected 8 examples, got {r['aggregate_examples']}"

    # Verify inventory counts
    inv = recon["block_inventory"]
    assert inv["total_blocks"] == 196
    assert inv["ship"] == 171
    assert inv["fix"] == 25
    assert inv["unsupported"] == 0


def test_unbundled_shader_blocks_inventory():
    """Verify the 26 unbundled blocks omitted from the historical aggregate registry bundle."""
    recon = CatalogManifestService.get_reconciliation_summary()
    unbundled = recon["unbundled_blocks"]

    assert len(unbundled) == 26
    # Known unbundled blocks: shaders, turntable, merges
    expected_samples = {"aurora", "blob", "frost", "plasma", "prism", "voronoi", "water", "week-in-merges"}
    assert expected_samples.issubset(set(unbundled)), f"Missing expected unbundled blocks in {unbundled}"


def test_manifest_categories_and_facets():
    """Verify categorical breakdown and faceted query support across canonical categories."""
    facets_res = CatalogManifestService.list_items(limit=10, offset=0)
    assert facets_res["total"] == 196
    assert len(facets_res["items"]) == 10

    cats = facets_res["facets"]["categories"]
    assert "typography" in cats
    assert "backgrounds" in cats
    assert "transitions" in cats
    assert "call-to-action" in cats
    assert "charts" in cats
    assert "lower-thirds" in cats
    assert "mock-ui" in cats


def test_category_filtering():
    """Test filtering by specific category."""
    cta_items = CatalogManifestService.list_items(category="call-to-action")
    assert cta_items["total"] > 0
    for it in cta_items["items"]:
        assert it["category"] == "call-to-action"

    typo_items = CatalogManifestService.list_items(category="typography")
    assert typo_items["total"] > 0
    for it in typo_items["items"]:
        assert it["category"] == "typography"


def test_search_filtering():
    """Test searching by title, id, and tags."""
    search_res = CatalogManifestService.list_items(search="instagram")
    assert search_res["total"] > 0
    found_ids = [it["id"] for it in search_res["items"]]
    assert "instagram-follow" in found_ids

    tag_res = CatalogManifestService.list_items(search="shader")
    assert tag_res["total"] > 0


def test_disposition_filtering():
    """Test filtering by release disposition (SHIP vs FIX)."""
    ship_res = CatalogManifestService.list_items(disposition="SHIP")
    assert ship_res["total"] == 171

    fix_res = CatalogManifestService.list_items(disposition="FIX")
    assert fix_res["total"] == 25
    fix_ids = [it["id"] for it in fix_res["items"]]
    assert "aurora" in fix_ids
    assert "yt-lower-third" in fix_ids


def test_license_inventory_attribution():
    """Verify that license inventory reports SPDX identifiers and attribution."""
    licenses = CatalogManifestService.get_license_inventory()
    assert len(licenses) == 196

    for entry in licenses:
        assert "id" in entry
        assert "license" in entry
        assert "author" in entry
        assert "disposition" in entry
        assert entry["license"].startswith("Apache-2.0") or "MIT" in entry["license"]


def test_zero_donor_independence():
    """Requirement F08 / GT-20: verify catalog service runs cleanly and resolves blocks without donor repo."""
    item = CatalogManifestService.get_item("weight-wave")
    assert item is not None
    assert item["id"] == "weight-wave"
    assert item["title"] == "Weight Wave"
    assert item["disposition"] == "SHIP"

    # Shipped block packaged locally
    shipped_dir = Path(__file__).parent.parent / "backend" / "catalog" / "shipped_blocks" / "weight-wave"
    assert shipped_dir.exists()
    assert (shipped_dir / "weight-wave.html").exists()
    assert (shipped_dir / "registry-item.json").exists()
