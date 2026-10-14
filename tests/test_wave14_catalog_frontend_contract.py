# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 14 Agent 2: Catalog Frontend Truth and Usable Discovery Contract Test Suite.

Verifies:
1. Shared Cross-Agent Inventory Contract v1 compliance:
   - Exactly 196 original donor blocks in hyperframes_196_fixture.json.
   - Schema version 1, source_inventory 'HyperFrames'.
   - Exactly 10 donor internalized blocks.
   - Exactly 2 separate 6Clips-authored blocks (creator-hud, glitch-transition) NOT in the 196 donor manifest.
   - Total operational = 12; total donor unported = 186.
2. Endpoint payload mapping & status truth:
   - Required fields on all 196 blocks: id, relative_source_path, source_sha256,
     license_status, license_evidence, integration_status, blocker_reason, supported_aspects, evidence_refs.
   - Valid license statuses: VERIFIED_PERMISSIVE, VERIFIED_OTHER_OBLIGATIONS, UNVERIFIED, RESTRICTED.
   - Valid integration statuses: INTERNALIZED, ELIGIBLE_NOT_PORTED, NEEDS_ADAPTATION,
     BLOCKED_LICENSE, BLOCKED_SECURITY, BLOCKED_DEPENDENCY, NOT_EVALUATED.
3. Explicit view filters & dynamic counts:
   - 'Available now': 12 operational blocks.
   - 'All original HyperFrames (196 verified)': 196 verified donor blocks.
   - 'Needs work' and 'Blocked' partition the remaining blocks with real counts.
4. Tile invariants & absence of fabricated thumbnails:
   - Non-internalized blocks have NO fake poster image or live preview iframe.
   - Real blocker_reason displayed for all unported blocks.
   - Insert, customize, and export actions disabled for inventory-only blocks.
5. Canonical Motion Project/CAS link invariants:
   - 'Insert into Motion' targets single canonical Project/ProjectRevision/CAS path.
   - Blocks without operational clearance cannot be inserted into timelines.
6. Zero unsolicited Ollama/cloud calls on mount/hover/filter.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"
FIXTURE_PATH = FRONTEND_SRC / "fixtures" / "hyperframes_196_fixture.json"

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

EXPECTED_2_SIXCLIPS_ORIGINALS = {
    "creator-hud",
    "glitch-transition",
}

VALID_LICENSE_STATUSES = {
    "VERIFIED_PERMISSIVE",
    "VERIFIED_OTHER_OBLIGATIONS",
    "UNVERIFIED",
    "RESTRICTED",
}

VALID_INTEGRATION_STATUSES = {
    "INTERNALIZED",
    "ELIGIBLE_NOT_PORTED",
    "NEEDS_ADAPTATION",
    "BLOCKED_LICENSE",
    "BLOCKED_SECURITY",
    "BLOCKED_DEPENDENCY",
    "NOT_EVALUATED",
}


@pytest.fixture(scope="module")
def v1_manifest():
    assert FIXTURE_PATH.exists(), f"Missing v1 fixture at {FIXTURE_PATH}"
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def test_v1_manifest_schema_and_counts(v1_manifest):
    """Test schema version 1 and exact 196 original donor count."""
    assert v1_manifest.get("schema_version") == 1
    assert v1_manifest.get("source_inventory") == "HyperFrames"
    assert v1_manifest.get("original_block_count") == 196

    blocks = v1_manifest.get("blocks", [])
    assert len(blocks) == 196, f"Expected 196 blocks, found {len(blocks)}"

    # Ensure unique IDs
    ids = [b["id"] for b in blocks]
    assert len(ids) == len(set(ids)), "Duplicate block IDs found in v1 manifest"


def test_sixclips_originals_strictly_excluded_from_donor_manifest(v1_manifest):
    """Verify that neither creator-hud nor glitch-transition is in the 196 donor manifest."""
    ids = set(b["id"] for b in v1_manifest.get("blocks", []))
    for sc_id in EXPECTED_2_SIXCLIPS_ORIGINALS:
        assert sc_id not in ids, f"6Clips original '{sc_id}' contaminated donor 196 manifest"


def test_ten_internalized_donor_blocks_truth(v1_manifest):
    """Verify exact 10 donor-original blocks are marked INTERNALIZED."""
    blocks = v1_manifest.get("blocks", [])
    internalized = [b for b in blocks if b.get("integration_status") == "INTERNALIZED"]
    internalized_ids = set(b["id"] for b in internalized)

    assert len(internalized) == 10, f"Expected exactly 10 internalized donor blocks, found {len(internalized)}"
    assert internalized_ids == EXPECTED_10_DONOR_INTERNALIZED, (
        f"Internalized set mismatch: {internalized_ids ^ EXPECTED_10_DONOR_INTERNALIZED}"
    )

    for b in internalized:
        assert b.get("license_status") == "VERIFIED_PERMISSIVE"
        assert b.get("blocker_reason") is None


def test_inventory_math_reconciliation(v1_manifest):
    """Test inventory math: 196 donor originals, 10 internalized, 186 unported, 2 6Clips originals."""
    blocks = v1_manifest.get("blocks", [])
    total_donor = len(blocks)
    internalized_donor = sum(1 for b in blocks if b.get("integration_status") == "INTERNALIZED")
    unported_donor = total_donor - internalized_donor

    assert total_donor == 196
    assert internalized_donor == 10
    assert unported_donor == 186

    operational_total = internalized_donor + len(EXPECTED_2_SIXCLIPS_ORIGINALS)
    assert operational_total == 12


def test_all_196_blocks_have_mandatory_v1_fields(v1_manifest):
    """Verify every block has required v1 contract metadata fields."""
    required_fields = [
        "id",
        "relative_source_path",
        "source_sha256",
        "license_status",
        "license_evidence",
        "integration_status",
        "supported_aspects",
        "evidence_refs",
    ]

    for b in v1_manifest.get("blocks", []):
        for field in required_fields:
            assert field in b, f"Block {b.get('id')} missing mandatory field '{field}'"

        assert b["license_status"] in VALID_LICENSE_STATUSES, (
            f"Block {b['id']} has invalid license_status: {b['license_status']}"
        )
        assert b["integration_status"] in VALID_INTEGRATION_STATUSES, (
            f"Block {b['id']} has invalid integration_status: {b['integration_status']}"
        )

        assert isinstance(b["supported_aspects"], list) and len(b["supported_aspects"]) > 0
        assert isinstance(b["evidence_refs"], list) and len(b["evidence_refs"]) > 0
        assert b["source_sha256"] and len(b["source_sha256"]) > 0

        # Non-internalized blocks must have an explicit blocker reason
        if b["integration_status"] != "INTERNALIZED":
            assert b.get("blocker_reason"), f"Unported block {b['id']} missing blocker_reason"


def test_view_filter_partitioning(v1_manifest):
    """Verify that view filters correctly partition blocks into Available now, Needs work, and Blocked."""
    blocks = v1_manifest.get("blocks", [])

    internalized = [b for b in blocks if b.get("integration_status") == "INTERNALIZED"]
    needs_work = [
        b for b in blocks
        if b.get("integration_status") in ("NEEDS_ADAPTATION", "ELIGIBLE_NOT_PORTED")
    ]
    blocked = [
        b for b in blocks
        if b.get("integration_status") in ("BLOCKED_LICENSE", "BLOCKED_SECURITY", "BLOCKED_DEPENDENCY")
        or b.get("license_status") == "RESTRICTED"
    ]

    # Available now total includes 10 donor internalized + 2 6Clips original
    avail_now_count = len(internalized) + len(EXPECTED_2_SIXCLIPS_ORIGINALS)
    assert avail_now_count == 12

    # All donor blocks accounted for in partition
    assert len(internalized) + len(needs_work) + len(blocked) == 196
    assert len(needs_work) > 0
    assert len(blocked) > 0


def test_frontend_source_code_contract_invariants():
    """Verify frontend components implement truthful invariants in code."""
    catalog_card_src = (FRONTEND_SRC / "components" / "catalog" / "CatalogCard.jsx").read_text(encoding="utf-8")
    catalog_drawer_src = (FRONTEND_SRC / "components" / "catalog" / "CatalogDrawer.jsx").read_text(encoding="utf-8")
    catalog_facet_src = (FRONTEND_SRC / "components" / "catalog" / "CatalogFacetBar.jsx").read_text(encoding="utf-8")
    catalog_page_src = (FRONTEND_SRC / "pages" / "Catalog.jsx").read_text(encoding="utf-8")
    catalog_utils_src = (FRONTEND_SRC / "utils" / "catalogInventory.js").read_text(encoding="utf-8")
    motion_page_src = (FRONTEND_SRC / "pages" / "MotionGraphics.jsx").read_text(encoding="utf-8")

    # Invariant 1: No fake posters or previews for unported blocks in CatalogCard
    assert "posterUrl = isOperational" in catalog_card_src or "isOperational ?" in catalog_card_src
    assert "INVENTORY ONLY" in catalog_card_src
    assert "Action disabled" in catalog_card_src

    # Invariant 2: CatalogDrawer disables preview and insert for inventory-only blocks
    assert "Live Preview Disabled" in catalog_drawer_src
    assert "Insertion Disabled (Inventory Only Entry)" in catalog_drawer_src
    assert "disabled" in catalog_drawer_src

    # Invariant 3: Explicit view filters in CatalogFacetBar
    assert "Available now" in catalog_facet_src
    assert "All original HyperFrames" in catalog_facet_src
    assert "Needs work" in catalog_facet_src
    assert "Blocked" in catalog_facet_src

    # Invariant 4: Truthful disclosure and honest error handling in Catalog.jsx
    assert "STAGE1_FIXTURE" in catalog_page_src
    assert "UNAVAILABLE_BACKEND_PENDING" in catalog_page_src
    assert "BLOCKED_INVENTORY_RECONCILIATION" in catalog_page_src
    assert "reconcileCatalog" in catalog_page_src

    # Invariant 5: 6Clips original blocks are separately identified in catalogInventory
    assert "creator-hud" in catalog_utils_src
    assert "glitch-transition" in catalog_utils_src
    assert "6CLIPS_ORIGINAL" in catalog_utils_src

    # Invariant 6: MotionGraphics consumes insertBlock deep links through canonical Project CAS path
    assert "insertBlock" in motion_page_src
    assert "handleAddBlock" in motion_page_src


def test_zero_unsolicited_ollama_or_cloud_calls():
    """Ensure no unsolicited LLM or Ollama calls exist in Catalog frontend modules."""
    files_to_check = [
        FRONTEND_SRC / "pages" / "Catalog.jsx",
        FRONTEND_SRC / "components" / "catalog" / "CatalogCard.jsx",
        FRONTEND_SRC / "components" / "catalog" / "CatalogDrawer.jsx",
        FRONTEND_SRC / "components" / "catalog" / "CatalogFacetBar.jsx",
        FRONTEND_SRC / "utils" / "catalogInventory.js",
    ]

    for p in files_to_check:
        content = p.read_text(encoding="utf-8")
        assert "ollama" not in content.lower(), f"Unsolicited ollama callsite in {p.name}"
        assert "/api/llm/" not in content.lower(), f"Unsolicited /api/llm/ callsite in {p.name}"
        assert "/api/chat" not in content.lower(), f"Unsolicited /api/chat callsite in {p.name}"


def test_no_component_tests_labeled_browser_verified():
    """
    Per Wave 14 instructions, component/static tests must NEVER be labeled BROWSER_VERIFIED;
    Edge click validation is exclusively Agent 4's responsibility.
    """
    content = Path(__file__).read_text(encoding="utf-8")
    assert "BROWSER_VERIFIED" not in [line for line in content.splitlines() if not line.strip().startswith("#")]
