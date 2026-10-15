# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 16 Agent 2 Test Suite: Frontend Catalog Taxonomy, 196 Original Inventory, and Category Reconciliation."""

import json
import os
import subprocess
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_UTILS = REPO_ROOT / "frontend" / "src" / "utils"
SHIPPED_BLOCKS = REPO_ROOT / "backend" / "catalog" / "shipped_blocks"


def run_node_eval(script: str):
    """Run a small node script in the frontend directory and return parsed JSON."""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=REPO_ROOT / "frontend",
        capture_output=True,
        text=True,
        check=True,
    )
    # Filter out any node warnings before JSON
    stdout = result.stdout.strip()
    if stdout.startswith("Warning:"):
        lines = stdout.splitlines()
        # Find first line starting with { or [
        for idx, line in enumerate(lines):
            if line.strip().startswith("{") or line.strip().startswith("["):
                stdout = "\n".join(lines[idx:])
                break
    return json.loads(stdout)


class TestWave16Agent2CatalogTaxonomy:
    """Verifies the complete 196 authentic donor inventory, category reconciliation, and shipped blocks."""

    def test_original_196_inventory_count_and_uniqueness(self):
        """Verify exactly 196 unique original donor slugs, no duplicates, no retired 6Clips blocks."""
        data = run_node_eval("""
            import('./src/utils/catalogOriginals.js').then(m => {
                const ids = m.ORIGINAL_HYPERFRAMES_IDS;
                const setIds = new Set(ids);
                console.log(JSON.stringify({
                    total: ids.length,
                    unique: setIds.size,
                    hasCreatorHud: ids.includes('creator-hud'),
                    hasGlitchTransition: ids.includes('glitch-transition'),
                    sample: ids.slice(0, 5)
                }));
            });
        """)
        assert data["total"] == 196, f"Expected 196 inventory items, got {data['total']}"
        assert data["unique"] == 196, f"Expected 196 unique items, found duplicate slugs"
        assert not data["hasCreatorHud"], "Retired 6Clips block 'creator-hud' must not be in original donor inventory"
        assert not data["hasGlitchTransition"], "Retired 6Clips block 'glitch-transition' must not be in original donor inventory"

    def test_taxonomy_reconciliation_171_confirmed_vs_25_missing(self):
        """Verify reconciliation of 171 gallery-confirmed categories vs 25 missing categories with proposed fallbacks."""
        data = run_node_eval("""
            import('./src/utils/catalogOriginals.js').then(m => {
                const items = m.buildOriginalCatalogItems();
                const confirmed = items.filter(i => i.category_status === 'SOURCE_CATEGORY_CONFIRMED');
                const missing = items.filter(i => i.category_status === 'SOURCE_CATEGORY_MISSING');
                const missingIds = Array.from(m.SOURCE_CATEGORY_MISSING_IDS);
                
                // Ensure all missing items have an explicit proposed fallback category
                const missingWithoutFallback = missing.filter(i => !i.proposed_fallback_category);

                console.log(JSON.stringify({
                    total: items.length,
                    confirmedCount: confirmed.length,
                    missingCount: missing.length,
                    missingListCount: missingIds.length,
                    missingWithoutFallbackCount: missingWithoutFallback.length,
                    missingIds: missingIds
                }));
            });
        """)
        assert data["total"] == 196
        assert data["confirmedCount"] == 171, f"Expected 171 confirmed category items, got {data['confirmedCount']}"
        assert data["missingCount"] == 25, f"Expected 25 source category missing items, got {data['missingCount']}"
        assert data["missingListCount"] == 25
        assert data["missingWithoutFallbackCount"] == 0, "All 25 missing items must have an explicit proposed fallback category"

    def test_packaged_cards_count_reconciliation_owner_37(self):
        """Verify the owner's observation: exactly 37 authentic donor blocks are packaged in shipped_blocks.
        10 baseline internalized + 17 shaders + 10 lower thirds = 37 packaged cards.
        """
        data = run_node_eval("""
            import('./src/utils/catalogOriginals.js').then(m => {
                console.log(JSON.stringify({
                    packagedIds: Array.from(m.DONOR_PACKAGED_IDS),
                    internalizedIds: Array.from(m.DONOR_INTERNALIZED_IDS),
                    shaderIds: Array.from(m.DONOR_SHADER_IDS),
                    lowerThirdIds: Array.from(m.DONOR_LOWER_THIRD_IDS),
                }));
            });
        """)
        packaged_ids = set(data["packagedIds"])
        internalized_ids = set(data["internalizedIds"])
        shader_ids = set(data["shaderIds"])
        lower_third_ids = set(data["lowerThirdIds"])

        assert len(packaged_ids) == 37, f"Expected 37 packaged donor blocks, got {len(packaged_ids)}"
        assert len(internalized_ids) == 10, f"Expected 10 internalized blocks, got {len(internalized_ids)}"
        assert len(shader_ids) == 17, f"Expected 17 shader blocks, got {len(shader_ids)}"
        assert len(lower_third_ids) == 10, f"Expected 10 lower-third blocks, got {len(lower_third_ids)}"
        assert internalized_ids | shader_ids | lower_third_ids == packaged_ids

        # Check that all 37 exist on disk in backend/catalog/shipped_blocks
        for block_id in packaged_ids:
            block_dir = SHIPPED_BLOCKS / block_id
            assert block_dir.is_dir(), f"Packaged block {block_id} directory missing on disk: {block_dir}"
            registry_json = block_dir / "registry-item.json"
            assert registry_json.is_file(), f"Packaged block {block_id} missing registry-item.json"

        # Check disk count: exactly 37 authentic donor blocks present on disk (plus newly ported in Wave 16)
        disk_dirs = [d.name for d in SHIPPED_BLOCKS.iterdir() if d.is_dir()]
        assert len(disk_dirs) >= 39
        retired_on_disk = {"creator-hud", "glitch-transition"}
        assert packaged_ids.issubset(set(disk_dirs) - retired_on_disk)

    def test_item_normalization_schema(self):
        """Verify each normalized item contains required Wave 16 fields."""
        data = run_node_eval("""
            import('./src/utils/catalogOriginals.js').then(m => {
                const item = m.normalizeDonorBlock({ id: 'aurora' });
                console.log(JSON.stringify(item));
            });
        """)
        assert data["id"] == "aurora"
        assert data["isPackaged"] is True
        assert data["isOperational"] is True
        assert data["category_status"] in ("SOURCE_CATEGORY_CONFIRMED", "SOURCE_CATEGORY_MISSING")
        assert "poster_url" in data
        assert "preview_url" in data
        assert "proposed_fallback_category" in data
        assert "status_label" in data

    def test_multi_page_inventory_traversal(self):
        """Verify that paginateInventory traverses and slices all 196 items deterministically with zero loss."""
        data = run_node_eval("""
            import('./src/utils/catalogOriginals.js').then(m => {
                const allItems = m.buildOriginalCatalogItems();
                const pageSize = 24;
                const totalPages = Math.ceil(allItems.length / pageSize);
                
                const gatheredIds = [];
                for (let page = 1; page <= totalPages; page++) {
                    const slice = m.paginateInventory(allItems, page, pageSize);
                    gatheredIds.push(...slice.map(i => i.id));
                }
                
                console.log(JSON.stringify({
                    totalPages,
                    gatheredCount: gatheredIds.length,
                    uniqueGatheredCount: new Set(gatheredIds).size,
                    matchesExactOriginal: JSON.stringify(gatheredIds) === JSON.stringify(allItems.map(i => i.id))
                }));
            });
        """)
        assert data["totalPages"] == 9  # 196 / 24 = 8.16 -> 9 pages
        assert data["gatheredCount"] == 196
        assert data["uniqueGatheredCount"] == 196
        assert data["matchesExactOriginal"] is True

    def test_catalog_inventory_filter_modes(self):
        """Verify filterCatalogItems behaves according to the 3 distinct census sets:
        AVAILABLE_NOW (37), ALL_ORIGINAL_196 (196), NEEDS_WORK (159).
        """
        data = run_node_eval("""
            Promise.all([
                import('./src/utils/catalogOriginals.js'),
                import('./src/utils/catalogInventory.js')
            ]).then(([orig, inv]) => {
                const items = orig.buildOriginalCatalogItems();
                
                const available = inv.filterCatalogItems(items, { filterMode: 'AVAILABLE_NOW' });
                const all196 = inv.filterCatalogItems(items, { filterMode: 'ALL_ORIGINAL_196' });
                const needsWork = inv.filterCatalogItems(items, { filterMode: 'NEEDS_WORK' });
                const blocked = inv.filterCatalogItems(items, { filterMode: 'BLOCKED' });
                
                console.log(JSON.stringify({
                    availableCount: available.length,
                    all196Count: all196.length,
                    needsWorkCount: needsWork.length,
                    blockedCount: blocked.length
                }));
            });
        """)
        assert data["availableCount"] == 37, f"Expected 37 available now, got {data['availableCount']}"
        assert data["all196Count"] == 196, f"Expected 196 total originals, got {data['all196Count']}"
        assert data["needsWorkCount"] == 159, f"Expected 159 unported needs work, got {data['needsWorkCount']}"
        assert data["blockedCount"] == 159
        assert data["availableCount"] + data["needsWorkCount"] == data["all196Count"]
