# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 3 Role 3: Tests for HyperFrames Catalog inventory reconciliation,
factual status counts, zero-donor runtime independence, and security protection.
"""
from pathlib import Path
import pytest

from backend.catalog.manifest_service import (
    CatalogManifestService,
    CatalogManifestError,
    CORE_INTERNALIZED_BLOCKS,
)
from backend.catalog.preview_engine import CatalogPreviewEngine
from backend.catalog.poster_service import CatalogPosterService, CatalogPosterError


def test_wave3_factual_counts():
    """Verify exact factual counts required by Wave 3 Role 3 acceptance criteria."""
    counts = CatalogManifestService.get_factual_counts()

    assert counts["INVENTORIED"] == 196
    assert counts["INTERNALIZED"] == 6
    assert counts["RENDER_TESTED"] == 6
    assert counts["BROWSER_VERIFIED"] == 6
    assert counts["LICENSE_BLOCKED"] == 165
    assert counts["READY"] == 6
    assert counts["NOT_READY"] == 190
    assert counts["READY"] + counts["NOT_READY"] == counts["INVENTORIED"]


def test_wave3_reconciliation_audit_explanation():
    """Verify that reconciliation summary accurately explains the historical 171 SHIP label."""
    recon = CatalogManifestService.get_reconciliation_summary()
    w3 = recon.get("wave3_reconciliation", {})

    assert w3["inventoried"] == 196
    assert w3["internalized"] == 6
    assert w3["ready"] == 6
    assert w3["not_ready"] == 190
    assert "ready_blocks" in w3
    assert set(w3["ready_blocks"]) == CORE_INTERNALIZED_BLOCKS

    # Audit explanation text must be present and document the blanket registry attribution
    explanation = w3.get("reclassification_explanation", "")
    assert "171" in explanation
    assert "registry.json" in explanation
    assert "UNVERIFIED" in explanation


def test_core_internalized_blocks_exist_locally():
    """Verify that all 6 internalized blocks are bundled in backend/catalog/shipped_blocks."""
    shipped_root = Path(__file__).parent.parent / "backend" / "catalog" / "shipped_blocks"
    assert shipped_root.exists(), "shipped_blocks directory must exist in repo"

    expected_blocks = {
        "aurora",
        "data-chart",
        "instagram-follow",
        "tiktok-follow",
        "weight-wave",
        "yt-lower-third",
    }
    assert expected_blocks == CORE_INTERNALIZED_BLOCKS

    for block_id in expected_blocks:
        b_dir = shipped_root / block_id
        assert b_dir.is_dir(), f"Block {block_id} directory missing in shipped_blocks"
        html_files = list(b_dir.glob("*.html"))
        assert len(html_files) > 0, f"Block {block_id} has no HTML composition"
        assert (b_dir / "registry-item.json").is_file(), f"Block {block_id} has no registry-item.json"


def test_zero_donor_runtime_independence(monkeypatch):
    """
    GT-20 & Requirement 5: Verify preview engine renders all 6 shipped blocks
    WITHOUT the donor checkout being available or mounted at runtime.
    """
    # Point DONOR_BLOCKS_DIR to an inaccessible non-existent directory
    dummy_donor = Path("C:/non_existent_donor_repo_6clips_isolated_test/blocks")
    monkeypatch.setattr("backend.catalog.preview_engine.DONOR_BLOCKS_DIR", dummy_donor)

    for block_id in CORE_INTERNALIZED_BLOCKS:
        html = CatalogPreviewEngine.get_preview_html(block_id, aspect_ratio="9:16")
        assert len(html) > 100, f"Preview failed for {block_id} without donor checkout"
        assert "<html" in html.lower()
        # Ensure it contains the actual composition, not the unverified fallback card
        assert "UNVERIFIED — PENDING INTERNALIZATION" not in html


def test_security_path_traversal_protection():
    """Requirement 7: Verify strict rejection of directory traversal and injection payloads."""
    malicious_ids = [
        "../etc/passwd",
        "..\\..\\windows\\system32",
        "....//....//shadow",
        "block/with/slash",
        "block\\with\\backslash",
        "<script>alert(1)</script>",
        "block\x00nullbyte",
        "%2e%2e%2froot",
        "",
        "   ",
        "../../../secret",
    ]

    for bad_id in malicious_ids:
        with pytest.raises(CatalogManifestError):
            CatalogManifestService.validate_block_id(bad_id)

        with pytest.raises(CatalogManifestError):
            CatalogManifestService.get_item(bad_id)

        with pytest.raises(CatalogManifestError):
            CatalogPreviewEngine.get_preview_html(bad_id)

        with pytest.raises((CatalogManifestError, CatalogPosterError)):
            CatalogPosterService.get_poster_path(bad_id)


def test_readiness_filtering():
    """Verify faceted filtering by Wave 3 readiness states (READY, UNVERIFIED, FIX)."""
    ready_res = CatalogManifestService.list_items(disposition="READY")
    assert ready_res["total"] == 6
    for it in ready_res["items"]:
        assert it["id"] in CORE_INTERNALIZED_BLOCKS
        assert it["internalized"] is True
        assert it["runtime_ready"] is True

    unverified_res = CatalogManifestService.list_items(disposition="UNVERIFIED")
    assert unverified_res["total"] == 168
    for it in unverified_res["items"]:
        assert it["id"] not in CORE_INTERNALIZED_BLOCKS
        assert it["internalized"] is False

    fix_res = CatalogManifestService.list_items(disposition="FIX")
    assert fix_res["total"] == 25
    for it in fix_res["items"]:
        assert it["disposition"] == "FIX"
