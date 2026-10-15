#!/usr/bin/env python3
"""
Wave 16 Stage 1 Provenance & Taxonomy Analysis.
Reconciles the 196 original donor directory identities with:
1. Upstream gallery MDX (docs/snippets/catalog-gallery-data.mdx)
2. Upstream registry.json (registry/registry.json)
3. Individual block registry-item.json
4. Explains 171/25 vs 178/18 discrepancy in Wave 15.
"""
import os
import json
import re
from pathlib import Path

DONOR_PATH = Path(r"C:\Users\toddy\Desktop\hyperframes")

def main():
    gallery_mdx = DONOR_PATH / "docs" / "snippets" / "catalog-gallery-data.mdx"
    text = gallery_mdx.read_text(encoding="utf-8")
    m = re.search(r"export const catalogGalleryData\s*=\s*(\{.*\})", text, re.DOTALL)
    gallery_data = json.loads(m.group(1))

    gallery_items_map = {it["id"]: it for it in gallery_data.get("items", [])}
    gallery_blocks = {it["id"]: it for it in gallery_data.get("items", []) if it.get("kind") == "block"}
    gallery_non_blocks = {it["id"]: it for it in gallery_data.get("items", []) if it.get("kind") != "block"}

    with open(DONOR_PATH / "registry" / "registry.json", "r", encoding="utf-8") as f:
        reg = json.load(f)
    reg_blocks = {it["name"]: it for it in reg.get("items", []) if it.get("type") == "hyperframes:block"}
    reg_non_blocks = {it["name"]: it for it in reg.get("items", []) if it.get("type") != "hyperframes:block"}

    blocks_dir = DONOR_PATH / "registry" / "blocks"
    disk_blocks = sorted(os.listdir(blocks_dir))

    print(f"Total disk block dirs: {len(disk_blocks)}")
    print(f"Blocks indexed in registry.json as hyperframes:block: {len(reg_blocks)}")
    print(f"Items in catalog-gallery-data.mdx with kind=='block': {len(gallery_blocks)}")

    in_gallery = [b for b in disk_blocks if b in gallery_blocks]
    missing_from_gallery = [b for b in disk_blocks if b not in gallery_blocks]
    print(f"Disk blocks with gallery kind=='block': {len(in_gallery)}")
    print(f"Disk blocks missing from gallery kind=='block': {len(missing_from_gallery)} (expected 25)")

    # Check if any missing from gallery are in gallery under another kind
    in_gallery_other_kind = [b for b in missing_from_gallery if b in gallery_items_map]
    print(f"Disk blocks in gallery under non-block kind: {len(in_gallery_other_kind)}")
    for b in in_gallery_other_kind:
        it = gallery_items_map[b]
        print(f"   {b}: kind={it.get('kind')} group={it.get('group')} section={it.get('section')}")

    # Check the 25 blocks missing from gallery
    print("\n--- The 25 missing gallery blocks ---")
    for b in sorted(missing_from_gallery):
        in_r = b in reg_blocks
        # Read tags from registry-item.json
        rf = blocks_dir / b / "registry-item.json"
        tags = []
        if rf.exists():
            try:
                tags = json.load(open(rf, encoding="utf-8")).get("tags", [])
            except:
                pass
        print(f"   {b:30s} | in_reg_json={str(in_r):5s} | tags={tags}")

    # Why did Agent 4 report 178 / 18 in Wave 15?
    # Let's inspect tag-based derivation:
    # 25 - 7 = 18. Did 7 blocks have tags that matched a category name?
    # Let's check which missing blocks have tags matching gallery group IDs!
    gallery_group_ids = {g["id"] for g in gallery_data.get("groups", [])}
    print(f"\nGallery group IDs: {sorted(gallery_group_ids)}")
    tag_matches = []
    for b in missing_from_gallery:
        rf = blocks_dir / b / "registry-item.json"
        if rf.exists():
            tags = json.load(open(rf, encoding="utf-8")).get("tags", [])
            overlap = set(tags).intersection(gallery_group_ids)
            if overlap:
                tag_matches.append((b, overlap, tags))
    print(f"Missing blocks with tags matching a gallery group ID: {len(tag_matches)}")
    for b, overlap, tags in tag_matches:
        print(f"   {b:30s} -> tag match: {overlap} (all tags: {tags})")

if __name__ == "__main__":
    main()
