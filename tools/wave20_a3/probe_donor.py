# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Forensic probe of C:\\Users\\toddy\\Desktop\\hyperframes.
Collects precise counts, groups, and structures across the donor repository.
"""
import json
import re
from pathlib import Path

ROOT = Path(r"C:\Users\toddy\Desktop\hyperframes")


def probe():
    print("=== HYPERFRAMES FORENSIC PROBE ===")
    
    # 1. Docs inventory
    docs_dir = ROOT / "docs"
    docs_files = [p for p in docs_dir.rglob("*") if p.is_file()]
    print(f"Docs total files: {len(docs_files)}")
    
    mdx_files = [p for p in docs_files if p.suffix.lower() == ".mdx"]
    md_files = [p for p in docs_files if p.suffix.lower() == ".md"]
    json_files = [p for p in docs_files if p.suffix.lower() == ".json"]
    print(f"Docs MDX files: {len(mdx_files)}")
    print(f"Docs MD files: {len(md_files)}")
    print(f"Docs JSON files: {len(json_files)}")

    # Break down MDX
    blocks_mdx = [p for p in mdx_files if "catalog" in p.parts and "blocks" in p.parts]
    components_mdx = [p for p in mdx_files if "catalog" in p.parts and "components" in p.parts]
    prompting_mdx = [p for p in mdx_files if "prompting" in p.parts]
    snippets_mdx = [p for p in mdx_files if "snippets" in p.parts]
    other_mdx = [p for p in mdx_files if p not in blocks_mdx and p not in components_mdx]
    
    print(f"  - Block MDX: {len(blocks_mdx)}")
    print(f"  - Component MDX: {len(components_mdx)}")
    print(f"  - Prompting MDX: {len(prompting_mdx)}")
    print(f"  - Snippets MDX: {len(snippets_mdx)}")
    print(f"  - Other MDX: {len(other_mdx)}")
    print(f"  Total MDX sum: {len(blocks_mdx) + len(components_mdx) + len(other_mdx)}")

    # 2. Registry blocks and components
    reg_blocks_dir = ROOT / "registry" / "blocks"
    reg_blocks = [p for p in reg_blocks_dir.iterdir() if p.is_dir()]
    print(f"Registry block dirs: {len(reg_blocks)}")

    reg_comp_dir = ROOT / "registry" / "components"
    reg_comps = [p for p in reg_comp_dir.iterdir() if p.is_dir()]
    print(f"Registry component dirs: {len(reg_comps)}")

    # Discrepancy analysis
    block_dir_names = set(p.name for p in reg_blocks)
    block_mdx_names = set(p.stem for p in blocks_mdx)
    missing_block_mdx = sorted(list(block_dir_names - block_mdx_names))
    print(f"Blocks without MDX ({len(missing_block_mdx)}): {missing_block_mdx}")

    comp_dir_names = set(p.name for p in reg_comps)
    comp_mdx_names = set(p.stem for p in components_mdx)
    comp_dirs_without_mdx = sorted(list(comp_dir_names - comp_mdx_names))
    comp_mdx_without_dirs = sorted(list(comp_mdx_names - comp_dir_names))
    print(f"Component dirs without MDX ({len(comp_dirs_without_mdx)}): {comp_dirs_without_mdx}")
    print(f"Component MDX without dirs ({len(comp_mdx_without_dirs)}): {comp_mdx_without_dirs}")

    # 3. Gallery groups in catalog-gallery-data.mdx
    snip = ROOT / "docs" / "snippets" / "catalog-gallery-data.mdx"
    if snip.exists():
        text = snip.read_text(encoding="utf-8")
        raw_groups = re.findall(r'group:\s*["\']([^"\']+)["\']', text)
        unique_groups = sorted(list(set(raw_groups)))
        print(f"Gallery groups ({len(unique_groups)}): {unique_groups}")

    # 4. Registry JSON
    reg_json_file = ROOT / "registry" / "registry.json"
    if reg_json_file.exists():
        reg_json = json.loads(reg_json_file.read_text(encoding="utf-8"))
        items = reg_json.get("items", [])
        print(f"Registry.json items: {len(items)}")
        categories = sorted(list(set(it.get("type", it.get("category", "unknown")) for it in items)))
        print(f"Registry.json types/categories: {categories}")

    # 5. Captions Catalog
    cap_cat = ROOT / "skills" / "embedded-captions" / "CATALOG.md"
    if cap_cat.exists():
        cap_text = cap_cat.read_text(encoding="utf-8")
        rows = [line.strip() for line in cap_text.splitlines() if line.strip().startswith("|") and not line.strip().startswith("|---") and "Identity" not in line]
        print(f"Embedded captions table rows: {len(rows)}")

    # 6. Hero primitive shelf in registry/components/CATALOG.md
    hero_cat = ROOT / "registry" / "components" / "CATALOG.md"
    if hero_cat.exists():
        hero_text = hero_cat.read_text(encoding="utf-8")
        shelf_headers = [line.strip() for line in hero_text.splitlines() if line.strip().startswith("## ")]
        print(f"Hero primitive shelf entries: {len(shelf_headers)}")


if __name__ == "__main__":
    probe()
