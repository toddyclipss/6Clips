#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 15 Agent 4: Independent 196-Original Donor Truth Ledger Scanner.

Performs a forensic, read-only census of C:\\Users\\toddy\\Desktop\\hyperframes.
Generates an independent ground-truth ledger covering:
- 196 donor block directories under registry/blocks
- 170 indexed blocks in registry.json
- 26 unindexed block directories on disk
- 222 microcomponents (quarantined)
- 8 examples (quarantined)
- Upstream tags and category taxonomy extraction
- Strict exclusion of 6Clips-authored blocks (creator-hud, glitch-transition)
- File hashes and asset inventories
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

DEFAULT_DONOR_PATH = Path(os.environ.get("HYPERFRAMES_DONOR_PATH", r"C:\Users\toddy\Desktop\hyperframes"))
DEFAULT_OUTPUT_DIR = Path(tempfile.gettempdir()) / "6clips_wave15_acceptance"
DEFAULT_LEDGER_PATH = DEFAULT_OUTPUT_DIR / "donor_truth_ledger_196.json"

NON_DONOR_BLOCKS = {"creator-hud", "glitch-transition"}


def compute_file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_directory_sha256(dir_path: Path) -> str:
    """Compute deterministic SHA-256 over all files in directory sorted by relative path."""
    h = hashlib.sha256()
    for root, _, files in os.walk(dir_path):
        for f in sorted(files):
            fp = Path(root) / f
            rel = fp.relative_to(dir_path).as_posix()
            h.update(rel.encode("utf-8"))
            try:
                with open(fp, "rb") as fh:
                    while chunk := fh.read(65536):
                        h.update(chunk)
            except OSError:
                pass
    return h.hexdigest()


def derive_source_category(tags: List[str], block_id: str) -> Dict[str, str]:
    """Derive source category and subcategory from upstream tags without inventing taxonomy."""
    tags_lower = [t.lower().strip() for t in tags]

    # Category heuristic based on upstream HyperFrames tag clusters
    if any(t in tags_lower for t in ["transition", "wipe", "slide", "dissolve", "split"]):
        return {"category": "transitions", "subcategory": "wipes" if "wipe" in tags_lower else "general"}
    if any(t in tags_lower for t in ["typography", "title-card", "lower-third", "title", "heading"]):
        return {"category": "typography", "subcategory": "lower-third" if "lower-third" in tags_lower else "titles"}
    if any(t in tags_lower for t in ["data", "chart", "ranking", "data-chart"]):
        return {"category": "data", "subcategory": "charts" if "chart" in tags_lower else "metrics"}
    if any(t in tags_lower for t in ["social", "follow", "profile", "avatar"]):
        return {"category": "social", "subcategory": "badges" if "follow" in tags_lower else "profiles"}
    if any(t in tags_lower for t in ["webgpu", "webgpu-shader", "shader", "webgl"]):
        return {"category": "shaders", "subcategory": "procedural" if "procedural" in tags_lower else "abstract"}
    if any(t in tags_lower for t in ["background", "mesh-gradient", "noise"]):
        return {"category": "backgrounds", "subcategory": "gradients" if "gradient" in tags_lower else "textures"}
    if any(t in tags_lower for t in ["3d", "3d-object", "three-js", "3d-motion"]):
        return {"category": "3d", "subcategory": "objects" if "3d-object" in tags_lower else "scenes"}
    if any(t in tags_lower for t in ["showcase", "carousel", "gallery", "mock-ui", "product", "ad-template"]):
        return {"category": "showcase", "subcategory": "carousel" if "carousel" in tags_lower else "product"}
    if any(t in tags_lower for t in ["code", "developer", "code-animation"]):
        return {"category": "code", "subcategory": "syntax" if "syntax" in tags_lower else "terminal"}

    return {"category": "SOURCE_CATEGORY_MISSING", "subcategory": "unclassified"}


def scan_donor_repository(donor_path: Path) -> Dict[str, Any]:
    """Perform read-only forensic inspection of donor repository."""
    blocks_dir = donor_path / "registry" / "blocks"
    components_dir = donor_path / "registry" / "components"
    examples_dir = donor_path / "registry" / "examples"
    registry_json_path = donor_path / "registry" / "registry.json"

    if not blocks_dir.exists() or not blocks_dir.is_dir():
        raise FileNotFoundError(f"Donor registry/blocks directory not found at {blocks_dir}")

    # Read registry.json
    reg_data = {}
    if registry_json_path.exists():
        with open(registry_json_path, "r", encoding="utf-8") as f:
            reg_data = json.load(f)

    indexed_blocks = {
        it["name"]: it for it in reg_data.get("items", []) if it.get("type") == "hyperframes:block"
    }
    indexed_components = {
        it["name"]: it for it in reg_data.get("items", []) if it.get("type") == "hyperframes:component"
    }
    indexed_examples = {
        it["name"]: it for it in reg_data.get("items", []) if it.get("type") == "hyperframes:example"
    }

    # Enumerate all directories under registry/blocks
    disk_block_dirs = sorted([d.name for d in blocks_dir.iterdir() if d.is_dir()])
    unindexed_dirs = sorted(list(set(disk_block_dirs) - set(indexed_blocks.keys())))

    ledger_blocks: List[Dict[str, Any]] = []
    category_counts = Counter()

    for block_name in disk_block_dirs:
        b_dir = blocks_dir / block_name
        item_json_path = b_dir / "registry-item.json"

        item_meta = {}
        if item_json_path.exists():
            with open(item_json_path, "r", encoding="utf-8") as f:
                item_meta = json.load(f)

        tags = item_meta.get("tags", [])
        tax = derive_source_category(tags, block_name)
        category_counts[tax["category"]] += 1

        is_indexed = block_name in indexed_blocks
        dir_sha = compute_directory_sha256(b_dir)

        # Assets inspection
        assets_dir = b_dir / "assets"
        assets_list = [p.name for p in assets_dir.iterdir()] if assets_dir.exists() and assets_dir.is_dir() else []

        entry = {
            "id": block_name,
            "title": item_meta.get("title") or block_name.replace("-", " ").title(),
            "description": item_meta.get("description", ""),
            "origin": "DONOR_ORIGINAL",
            "is_indexed_in_registry_json": is_indexed,
            "relative_source_path": f"registry/blocks/{block_name}",
            "directory_sha256": dir_sha,
            "tags": tags,
            "source_category": tax["category"],
            "source_subcategory": tax["subcategory"],
            "dimensions": item_meta.get("dimensions", {"width": 1920, "height": 1080}),
            "duration": float(item_meta.get("duration", 5.0) or 5.0),
            "variables": item_meta.get("variables", []),
            "has_preview": "preview" in item_meta,
            "has_assets": len(assets_list) > 0,
            "assets_count": len(assets_list),
            "assets": assets_list,
            "files": item_meta.get("files", []),
            "license": item_meta.get("license", "UNVERIFIED"),
        }
        ledger_blocks.append(entry)

    # Verification of non-donor blocks exclusion
    for sc in NON_DONOR_BLOCKS:
        assert sc not in disk_block_dirs, f"Critical: 6Clips original {sc} found in donor checkout!"

    census = {
        "donor_path": str(donor_path),
        "total_donor_blocks_on_disk": len(disk_block_dirs),
        "indexed_in_registry_json": len(indexed_blocks),
        "unindexed_block_dirs": len(unindexed_dirs),
        "unindexed_ids": unindexed_dirs,
        "indexed_microcomponents": len(indexed_components),
        "indexed_examples": len(indexed_examples),
        "category_breakdown": dict(category_counts),
        "non_donor_excluded": list(NON_DONOR_BLOCKS),
    }

    return {
        "schema_version": "wave15_truth_ledger_v1",
        "census": census,
        "blocks": ledger_blocks,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate HyperFrames 196 Donor Truth Ledger")
    parser.add_argument("--donor-path", type=Path, default=DEFAULT_DONOR_PATH, help="Path to donor checkout")
    parser.add_argument("--output", type=Path, default=DEFAULT_LEDGER_PATH, help="Destination JSON path")
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    print(f"Scanning donor repository at: {args.donor_path}...")
    ledger = scan_donor_repository(args.donor_path)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2)

    c = ledger["census"]
    print("=" * 70)
    print("HYPERFRAMES 196 DONOR TRUTH LEDGER GENERATED")
    print("=" * 70)
    print(f"Total Block Dirs on Disk : {c['total_donor_blocks_on_disk']}")
    print(f"Indexed in registry.json : {c['indexed_in_registry_json']}")
    print(f"Unindexed on Disk        : {c['unindexed_block_dirs']}")
    print(f"Microcomponents          : {c['indexed_microcomponents']}")
    print(f"Examples                 : {c['indexed_examples']}")
    print(f"Categories Count         : {len(c['category_breakdown'])}")
    print(f"Category Breakdown       : {c['category_breakdown']}")
    print(f"Ledger Output File       : {args.output}")
    print("=" * 70)


if __name__ == "__main__":
    main()
