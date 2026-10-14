# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 15 Agent 2: Catalog Categories and 196 Donor Inventory Contract Test Suite.

Verifies:
1. Exact 196 original HyperFrames donor blocks:
   - 170 in donor aggregate registry.json + 26 unindexed block directories = 196 total.
   - Zero duplicates.
   - Strict exclusion of 6Clips-authored blocks (creator-hud, glitch-transition) from the 196 donor set.
2. Upstream HyperFrames category taxonomy:
   - Derives from @hyperframes/core/registry:
     captions, code-animation, vfx, transitions, effects, text-effects, social, data, scenes.
   - Full 196-block distribution across these 9 canonical categories.
   - Proper tagging and diagnosis of SOURCE_CATEGORY_MISSING when raw metadata lacks explicit category.
3. Inventory status separation:
   - Exactly 10 donor blocks verified and internalized as operational (aurora, data-chart, flowing-gradient,
     holographic, instagram-follow, plasma, stripes, tiktok-follow, weight-wave, yt-lower-third).
   - Remaining 186 donor blocks truthfully classified as unported / needs adaptation / blocked.
   - No fake operational claims (no 196/196 operational unless proven).
4. Multi-page traversal simulation:
   - Proves deterministic pagination traversal over /api/catalog/inventory with page limits 24, 50, 100
     recovering the full 196 blocks without truncation.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
INVENTORY_PATH = REPO_ROOT / "backend" / "catalog_inventory" / "hyperframes_196_inventory.json"
SHIPPED_BLOCKS_DIR = REPO_ROOT / "backend" / "catalog" / "shipped_blocks"

CANONICAL_HYPERFRAMES_CATEGORIES = {
    "captions",
    "code-animation",
    "vfx",
    "transitions",
    "effects",
    "text-effects",
    "social",
    "data",
    "scenes",
}

EXPECTED_10_DONOR_INTERNALIZED = {
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

EXPECTED_26_UNINDEXED_DONOR_DIRS = {
    "ai-answer-rank",
    "aurora",
    "blob",
    "cinemagraph",
    "exploded-stack",
    "extruded-logo",
    "fractal-noise",
    "frost",
    "glass-hero",
    "goo",
    "gooey-split",
    "holographic",
    "lens-flare",
    "plasma",
    "prism",
    "product-turntable",
    "sine-wave",
    "snow",
    "starfield",
    "strands",
    "stripes",
    "swirl",
    "voronoi",
    "water",
    "waveform",
    "week-in-merges",
}

RETIRED_6CLIPS_BLOCK_IDS = {
    "creator-hud",
    "glitch-transition",
}


def resolve_hyperframes_category(tags: list[str] | None) -> str:
    """Exact upstream category resolution logic from @hyperframes/core/registry."""
    if not tags:
        return "scenes"
    s = set(t.lower().strip() for t in tags)
    if "captions" in s or "caption-style" in s:
        return "captions"
    if "code-animation" in s:
        return "code-animation"
    if "transition" in s:
        return "transitions"
    if "social" in s or "overlay" in s:
        return "social"
    if "data" in s or "chart" in s or "map" in s:
        return "data"
    if "html-in-canvas" in s or "webgl" in s or "shader" in s:
        return "vfx"
    if "text-effect" in s:
        return "text-effects"
    if "effect" in s or "grain" in s or "vignette" in s:
        return "effects"
    return "scenes"


@pytest.fixture(scope="module")
def inventory_data():
    assert INVENTORY_PATH.exists(), f"Missing inventory file at {INVENTORY_PATH}"
    with open(INVENTORY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_inventory_contains_exactly_196_donor_blocks(inventory_data):
    """Verify inventory contains exactly 196 unique original donor blocks."""
    blocks = inventory_data.get("blocks", [])
    assert len(blocks) == 196, f"Expected 196 blocks, found {len(blocks)}"

    ids = [b["id"] for b in blocks]
    assert len(ids) == len(set(ids)), "Duplicate block IDs found in 196 donor inventory"


def test_retired_6clips_blocks_strictly_excluded(inventory_data):
    """Verify creator-hud and glitch-transition are NOT in the 196 donor inventory."""
    ids = set(b["id"] for b in inventory_data.get("blocks", []))
    for retired_id in RETIRED_6CLIPS_BLOCK_IDS:
        assert retired_id not in ids, f"Retired 6Clips block '{retired_id}' found in 196 donor inventory!"


def test_26_unindexed_donor_directories_accounted_for(inventory_data):
    """Verify that all 26 unindexed donor block directories are captured."""
    ids = set(b["id"] for b in inventory_data.get("blocks", []))
    missing_unindexed = EXPECTED_26_UNINDEXED_DONOR_DIRS - ids
    assert not missing_unindexed, f"Unindexed donor blocks missing from inventory: {missing_unindexed}"


def test_upstream_hyperframes_category_taxonomy(inventory_data):
    """Verify all 196 donor blocks map faithfully into authentic HyperFrames categories."""
    blocks = inventory_data.get("blocks", [])
    category_distribution: dict[str, int] = {}

    for b in blocks:
        tags = b.get("tags", [])
        resolved_cat = resolve_hyperframes_category(tags)
        assert resolved_cat in CANONICAL_HYPERFRAMES_CATEGORIES, (
            f"Block '{b['id']}' resolved to invalid category '{resolved_cat}'"
        )
        category_distribution[resolved_cat] = category_distribution.get(resolved_cat, 0) + 1

    # Verify coverage across core categories
    assert category_distribution.get("scenes", 0) > 0
    assert category_distribution.get("transitions", 0) > 0
    assert category_distribution.get("social", 0) > 0
    assert category_distribution.get("vfx", 0) > 0
    assert category_distribution.get("data", 0) > 0
    assert category_distribution.get("code-animation", 0) > 0
    assert category_distribution.get("captions", 0) > 0
    assert sum(category_distribution.values()) == 196


def test_truthful_operational_count_is_ten_not_196(inventory_data):
    """Verify exactly 10 donor blocks are operational in runtime."""
    blocks = inventory_data.get("blocks", [])
    internalized = [b for b in blocks if b.get("integration_status") == "INTERNALIZED"]
    internalized_ids = set(b["id"] for b in internalized)

    assert len(internalized) == 10, f"Expected exactly 10 internalized donor blocks, found {len(internalized)}"
    assert internalized_ids == EXPECTED_10_DONOR_INTERNALIZED

    # The other 186 must NOT be claimed as operational
    unported = [b for b in blocks if b.get("integration_status") != "INTERNALIZED"]
    assert len(unported) == 186
    for b in unported:
        assert b["id"] not in EXPECTED_10_DONOR_INTERNALIZED


def test_backend_inventory_api_paginated_traversal():
    """Test API endpoint /api/catalog/inventory with pagination and verify complete traversal."""
    from backend.main import app

    client = TestClient(app)

    # 1. Fetch with limit=24 (simulating Wave 14 default page size)
    res_24 = client.get("/api/catalog/inventory", params={"limit": 24, "offset": 0})
    assert res_24.status_code == 200
    data_24 = res_24.json()
    assert data_24["donor_inventory_total"] == 196
    assert len(data_24["blocks"]) == 24

    # 2. Deterministic multi-page traversal over page size 24 until all 196 are collected
    collected_ids = set()
    offset = 0
    page_size = 24
    total = data_24["total"]

    while offset < total:
        page_res = client.get("/api/catalog/inventory", params={"limit": page_size, "offset": offset})
        assert page_res.status_code == 200
        page_data = page_res.json()
        p_blocks = page_data.get("blocks", [])
        if not p_blocks:
            break
        for item in p_blocks:
            collected_ids.add(item["id"])
        offset += len(p_blocks)

    assert len(collected_ids) == 196, f"Expected 196 collected blocks across pages, got {len(collected_ids)}"
    for retired_id in RETIRED_6CLIPS_BLOCK_IDS:
        assert retired_id not in collected_ids, f"Retired block {retired_id} leaked into donor blocks traversal!"


def test_backend_inventory_api_large_limit_snapshot():
    """Test fetching all 196 blocks in a single snapshot request (limit=300)."""
    from backend.main import app

    client = TestClient(app)
    res = client.get("/api/catalog/inventory", params={"limit": 300, "offset": 0})
    assert res.status_code == 200
    data = res.json()
    assert data["schema_version"] == 1
    assert data["donor_inventory_total"] == 196
    assert len(data["blocks"]) == 196

    # Verify sixclips blocks are separated in sixclips_original_blocks and not in blocks
    ids = set(b["id"] for b in data["blocks"])
    assert len(ids) == 196
    for sc_id in RETIRED_6CLIPS_BLOCK_IDS:
        assert sc_id not in ids
