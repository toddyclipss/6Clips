#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
import os
import re
import sys

def main():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    shipped_dir = os.path.join(root, "backend", "catalog", "shipped_blocks")
    catalog_originals = os.path.join(root, "frontend", "src", "utils", "catalogOriginals.js")

    with open(catalog_originals, "r", encoding="utf-8") as f:
        content = f.read()

    keys = re.findall(r'^  "([a-z0-9-]+)":\s*\{', content, re.MULTILINE)
    print(f"Total top-level keys in AUTHENTIC_DONOR_TAXONOMY: {len(keys)}")

    shipped_dirs = sorted([d for d in os.listdir(shipped_dir) if os.path.isdir(os.path.join(shipped_dir, d)) and not d.startswith(".")])
    print(f"Total shipped dirs on disk: {len(shipped_dirs)}")

    retired = {"creator-hud", "glitch-transition"}
    print(f"creator-hud in taxonomy: {'creator-hud' in keys}")
    print(f"glitch-transition in taxonomy: {'glitch-transition' in keys}")

    key_set = set(keys)
    shipped_set = set(shipped_dirs)
    print(f"Shipped NOT in taxonomy: {shipped_set - key_set}")
    print(f"Active shipped in taxonomy: {len(key_set.intersection(shipped_set - retired))}")
    print(f"Unported taxonomy blocks: {len(key_set - shipped_set)}")

if __name__ == "__main__":
    main()
