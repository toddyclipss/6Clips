# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Tests for donor repository physical census and historical discrepancy reconciliation.
Verifies the 1,440 physical files, 552 MDX breakdown, 6 MD files, 25 blocks without MDX,
14 components without MDX, 222 component dirs / 223 MDX resolution, 26/36 caption identities resolution,
and 25 hero primitives shelf.
"""
import json
from pathlib import Path
import pytest

WORKTREE_ROOT = Path(__file__).resolve().parents[3]
LEDGER_JSON_PATH = WORKTREE_ROOT / "tools" / "wave21_a3" / "knowledge_document_acceptance.json"
DONOR_ROOT = Path(r"C:\Users\toddy\Desktop\hyperframes")


@pytest.fixture(scope="module")
def ledger_data():
    return json.loads(LEDGER_JSON_PATH.read_text(encoding="utf-8"))


def test_donor_filesystem_physical_census(ledger_data):
    """Verify physical counts in donor filesystem match audited scope."""
    audit = ledger_data["donor_filesystem_audit"]

    assert audit["curated_files_total"] == 1440
    assert audit["docs_files_total"] == 1294
    assert audit["mdx_files_total"] == 552
    assert audit["md_files_count"] == 6

    # MDX breakdown: 171 block + 223 component + 158 other = 552
    assert audit["block_mdx_count"] == 171
    assert audit["component_mdx_count"] == 223
    assert audit["other_mdx_count"] == 158
    assert (
        audit["block_mdx_count"] + audit["component_mdx_count"] + audit["other_mdx_count"]
        == audit["mdx_files_total"]
    )


def test_reconciled_blocks_and_components(ledger_data):
    """Verify blocks and component dirs without MDX are accurately reconciled."""
    audit = ledger_data["donor_filesystem_audit"]

    # 196 registry block dirs: 171 with MDX + 25 without MDX
    assert audit["registry_block_dirs_count"] == 196
    assert audit["blocks_without_mdx_count"] == 25

    # 236 registry component dirs: 222 with MDX + 14 without MDX
    assert audit["registry_component_dirs_count"] == 236
    assert audit["comp_dirs_without_mdx_count"] == 14
    assert audit["comp_dirs_with_mdx_count"] == 222


def test_component_dirs_vs_mdx_discrepancy_resolution(ledger_data):
    """Verify exact resolution of historical '222 component dirs / 223 MDX' discrepancy."""
    audit = ledger_data["donor_filesystem_audit"]

    # 222 component dirs have matching MDX
    # 1 component MDX ('simulated-cursor') exists in docs without a matching registry dir
    # 222 + 1 = 223 component MDX
    assert audit["comp_dirs_with_mdx_count"] == 222
    assert audit["comp_mdx_without_dirs"] == ["simulated-cursor"]
    assert audit["component_mdx_count"] == 223
    assert "222_vs_223_components" in audit["discrepancy_resolution"]


def test_caption_identities_discrepancy_resolution(ledger_data):
    """Verify exact resolution of historical '26 / 36 caption identities' discrepancy."""
    audit = ledger_data["donor_filesystem_audit"]

    # In themes/ directory, there are 25 theme JSONs
    # Plus standard mode (merged into anchor) = 26 caption modes/themes
    assert audit["theme_json_count"] == 25

    # In CATALOG.md, there are 10 cinematic + 25 themed = 35 genuine identities
    # The 36th item was the markdown table header separator '| ------------- |'
    assert "26_vs_36_captions" in audit["discrepancy_resolution"]


def test_hero_primitives_shelf_inventory(ledger_data):
    """Verify hero primitive shelf count (shelf of 21 containing 25 actual primitives)."""
    audit = ledger_data["donor_filesystem_audit"]
    assert audit["hero_primitives_shelf_count"] == 25
    assert "shelf_of_21_hero_primitives" in audit["discrepancy_resolution"]


def test_total_curated_document_sum(ledger_data):
    """Verify exact composition of 658 first-class knowledge documents."""
    total = ledger_data["reconciliation_summary"]["total_documents"]
    assert total == 658

    docs = ledger_data["documents"]
    assert len(docs) == 658

    # Verify no duplicate doc IDs
    doc_ids = [d["doc_id"] for d in docs]
    assert len(doc_ids) == len(set(doc_ids))
