#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
import os
import sys
import re

def test_all_previews():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, root)
    from backend.services.catalog_preview_service import CatalogPreviewService

    catalog_originals = os.path.join(root, "frontend", "src", "utils", "catalogOriginals.js")
    with open(catalog_originals, "r", encoding="utf-8") as f:
        content = f.read()

    keys = re.findall(r'^  "([a-z0-9-]+)":\s*\{', content, re.MULTILINE)
    shipped_dirs = set(os.listdir(os.path.join(root, "backend", "catalog", "shipped_blocks")))
    retired = {"creator-hud", "glitch-transition"}

    successes = []
    failures = []
    unported = []

    for slug in keys:
        if slug in shipped_dirs and slug not in retired:
            try:
                html = CatalogPreviewService.get_preview_html(slug, aspect_ratio="9:16")
                if html and len(html) > 50 and "<html" in html.lower():
                    successes.append(slug)
                else:
                    failures.append((slug, "HTML too short or invalid"))
            except Exception as e:
                failures.append((slug, str(e)))
        else:
            unported.append(slug)

    print(f"Total taxonomy slugs tested: {len(keys)}")
    print(f"PASS (valid preview HTML generated): {len(successes)}/149")
    print(f"FAIL: {len(failures)}")
    print(f"UNPORTED: {len(unported)}/47")
    if failures:
        print("Failures detail:", failures[:5])

if __name__ == "__main__":
    test_all_previews()
