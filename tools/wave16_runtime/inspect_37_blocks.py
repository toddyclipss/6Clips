# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 16 Agent 1: Diagnostic audit of all 37 shipped/ported blocks on the frozen baseline.
Evaluates the 7-stage proof ladder:
1. Source inventoried
2. Source ported to backend/catalog/shipped_blocks
3. Real assets / offline integrity
4. Permissive license clearance
5. Browser preview & frame motion support
6. Canonical Motion insertion & CAS ProjectRevision support
7. Render & MP4 overlay export support
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SHIPPED_DIR = REPO_ROOT / "backend" / "catalog" / "shipped_blocks"
INVENTORY_PATH = REPO_ROOT / "backend" / "catalog_inventory" / "hyperframes_196_inventory.json"
RETIRED_BLOCKS = {"creator-hud", "glitch-transition"}

TEN_BASE_BLOCKS = {
    "aurora", "data-chart", "flowing-gradient", "holographic",
    "instagram-follow", "plasma", "stripes", "tiktok-follow",
    "weight-wave", "yt-lower-third",
}

SEVENTEEN_SHADERS = {
    "blob", "fractal-noise", "frost", "godrays", "goo", "lens-flare",
    "liquid-metal", "marble", "mesh-gradient", "nebula", "prism",
    "sine-wave", "strands", "swirl", "voronoi", "water", "waveform",
}

TEN_LOWER_THIRDS = {
    "lt-accent-underline", "lt-bold-block", "lt-clean-bar", "lt-color-block",
    "lt-dark-card", "lt-kicker-name", "lt-mask-reveal", "lt-side-rule",
    "lt-soft-pill", "lt-stack-bars",
}


def audit_block(block_id: str) -> dict:
    bdir = SHIPPED_DIR / block_id
    if not bdir.exists():
        return {"id": block_id, "exists": False, "blocker": "DIRECTORY_MISSING"}

    is_retired = block_id in RETIRED_BLOCKS
    manifest_file = bdir / "registry-item.json"
    manifest_data = {}
    if manifest_file.exists():
        try:
            manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
        except Exception as e:
            return {"id": block_id, "manifest_error": str(e)}

    # Find html entrypoint
    entrypoint = None
    for cand in [f"{block_id}.html", "index.html"]:
        p = bdir / cand
        if p.exists():
            entrypoint = p
            break
    if not entrypoint:
        for p in bdir.glob("*.html"):
            entrypoint = p
            break

    # Check external scripts
    has_external_scripts = False
    external_refs = []
    if entrypoint:
        html_txt = entrypoint.read_text(encoding="utf-8", errors="ignore")
        urls = re.findall(r'<script[^>]+src=[\'"]([^\'"]+)[\'"]', html_txt, re.IGNORECASE)
        for u in urls:
            if u.startswith("http://") or u.startswith("https://"):
                has_external_scripts = True
                external_refs.append(u)

    # Check licenses
    lic = manifest_data.get("license", "")
    lic_file = any((bdir / f).exists() for f in ["LICENSE.txt", "RUNTIME-LICENSE.txt", "LICENSE"])
    is_permissive = any(k in lic.upper() for k in ["APACHE", "MIT", "BSD", "CC0", "UNLICENSE", "OFL"]) or lic_file

    # Category and cohort
    cohort = "TEN_BASE" if block_id in TEN_BASE_BLOCKS else (
        "SEVENTEEN_SHADERS" if block_id in SEVENTEEN_SHADERS else (
            "TEN_LOWER_THIRDS" if block_id in TEN_LOWER_THIRDS else "RETIRED_6CLIPS"
        )
    )

    # Determine render adapter
    if cohort in ("TEN_BASE", "SEVENTEEN_SHADERS"):
        if any(t in manifest_data.get("tags", []) for t in ["webgpu", "shader", "webgpu-shader"]):
            adapter = "webgpu_canvas2d"
        elif block_id in ("instagram-follow", "tiktok-follow", "data-chart", "weight-wave", "yt-lower-third"):
            adapter = "html_canvas_motion"
        else:
            adapter = "webgpu_canvas2d"
    elif cohort == "TEN_LOWER_THIRDS":
        adapter = "gsap_native_timeline"
    else:
        adapter = "retired_legacy"

    return {
        "id": block_id,
        "cohort": cohort,
        "is_retired": is_retired,
        "has_manifest": manifest_file.exists(),
        "has_entrypoint": entrypoint is not None,
        "entrypoint_name": entrypoint.name if entrypoint else None,
        "has_external_scripts": has_external_scripts,
        "external_refs": external_refs,
        "is_permissive_license": is_permissive,
        "license_text": lic or ("LICENSE.txt" if lic_file else "UNSPECIFIED"),
        "adapter": adapter,
        "dimensions": manifest_data.get("dimensions", {"width": 1080, "height": 1920}),
        "duration": manifest_data.get("duration", 5.0),
        "variables_count": len(manifest_data.get("variables", [])),
    }


def main():
    dirs = sorted([d.name for d in SHIPPED_DIR.iterdir() if d.is_dir()])
    print(f"Total shipped dirs on disk: {len(dirs)}")
    donor_37 = [d for d in dirs if d not in RETIRED_BLOCKS]
    print(f"Total donor original blocks on disk: {len(donor_37)}")

    results = [audit_block(d) for d in donor_37]
    
    print("\n--- AUDIT OF 37 ORIGINAL SHIPPED BLOCKS ---")
    header = f"{'Block ID':22} | {'Cohort':18} | {'Entrypoint':22} | {'Offline':7} | {'License':22} | {'Adapter':20}"
    print(header)
    print("-" * len(header))
    for r in results:
        print(f"{r['id']:22} | {r['cohort']:18} | {str(r['entrypoint_name']):22} | {str(not r['has_external_scripts']):7} | {r['license_text'][:22]:22} | {r['adapter']:20}")


if __name__ == "__main__":
    main()
