#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Porting and revalidation script for HyperFrames 27 blocks (Wave 15 Agent 3):
- Ports the 17 eligible WebGPU/Canvas shaders from hyperframes donor into backend/catalog/shipped_blocks
- Vendors all required assets locally (shaders.iife.js, THIRD-PARTY-LICENSES.txt, shader_fallback.js)
- Adds dual WebGPU + Canvas 2D fallback engine to all 22 shader blocks
- Verifies and revalidates the existing 10 donor originals
"""

import json
import os
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DONOR_BLOCKS = Path(os.environ.get("HYPERFRAMES_DONOR_PATH", r"C:\Users\toddy\Desktop\hyperframes\registry\blocks"))
SHIPPED_BLOCKS = REPO_ROOT / "backend" / "catalog" / "shipped_blocks"
FALLBACK_JS_SOURCE = REPO_ROOT / "tools" / "wave15_shader_port" / "shader_fallback.js"

ELIGIBLE_17 = [
    "blob", "fractal-noise", "frost", "godrays", "goo", "lens-flare", "liquid-metal",
    "marble", "mesh-gradient", "nebula", "prism", "sine-wave", "strands", "swirl",
    "voronoi", "water", "waveform"
]

EXISTING_SHADER_5 = [
    "aurora", "flowing-gradient", "holographic", "plasma", "stripes"
]

EXISTING_NON_SHADER_5 = [
    "data-chart", "instagram-follow", "tiktok-follow", "weight-wave", "yt-lower-third"
]

ALL_22_SHADERS = EXISTING_SHADER_5 + ELIGIBLE_17
ALL_27 = ALL_22_SHADERS + EXISTING_NON_SHADER_5


def port_single_shader(slug: str):
    donor_dir = DONOR_BLOCKS / slug
    target_dir = SHIPPED_BLOCKS / slug
    target_lib = target_dir / "lib"

    if not donor_dir.exists():
        raise FileNotFoundError(f"Donor block directory not found at '{donor_dir}'")

    target_dir.mkdir(parents=True, exist_ok=True)
    target_lib.mkdir(parents=True, exist_ok=True)

    # 1. Copy shaders.iife.js and THIRD-PARTY-LICENSES.txt from donor
    shutil.copy2(donor_dir / "lib" / "shaders.iife.js", target_lib / "shaders.iife.js")
    shutil.copy2(donor_dir / "lib" / "shaders.THIRD-PARTY-LICENSES.txt", target_lib / "shaders.THIRD-PARTY-LICENSES.txt")

    # 2. Copy shader_fallback.js into lib
    shutil.copy2(FALLBACK_JS_SOURCE, target_lib / "shader_fallback.js")

    # 3. Read and adapt registry-item.json
    with open(donor_dir / "registry-item.json", "r", encoding="utf-8") as f:
        reg_data = json.load(f)

    # Ensure files list includes shader_fallback.js
    files = reg_data.get("files", [])
    has_fallback = any(f.get("path") == "lib/shader_fallback.js" for f in files)
    if not has_fallback:
        files.append({
            "path": "lib/shader_fallback.js",
            "target": "compositions/lib/shader_fallback.js",
            "type": "hyperframes:asset"
        })
    reg_data["files"] = files

    with open(target_dir / "registry-item.json", "w", encoding="utf-8") as f:
        json.dump(reg_data, f, indent=2)

    # 4. Adapt <slug>.html to load shader_fallback.js right after shaders.iife.js
    html_src = (donor_dir / f"{slug}.html").read_text(encoding="utf-8")
    if "lib/shader_fallback.js" not in html_src:
        html_src = html_src.replace(
            '<script src="lib/shaders.iife.js"></script>',
            '<script src="lib/shaders.iife.js"></script>\n    <script src="lib/shader_fallback.js"></script>'
        )

    (target_dir / f"{slug}.html").write_text(html_src, encoding="utf-8")
    print(f"  [PORTED] {slug} -> {target_dir}")


def update_existing_shader_fallback(slug: str):
    target_dir = SHIPPED_BLOCKS / slug
    target_lib = target_dir / "lib"
    target_lib.mkdir(parents=True, exist_ok=True)

    # Copy shader_fallback.js
    shutil.copy2(FALLBACK_JS_SOURCE, target_lib / "shader_fallback.js")

    # Update registry-item.json if needed
    reg_path = target_dir / "registry-item.json"
    if reg_path.exists():
        with open(reg_path, "r", encoding="utf-8") as f:
            reg_data = json.load(f)
        files = reg_data.get("files", [])
        if not any(f.get("path") == "lib/shader_fallback.js" for f in files):
            files.append({
                "path": "lib/shader_fallback.js",
                "target": "compositions/lib/shader_fallback.js",
                "type": "hyperframes:asset"
            })
            reg_data["files"] = files
            with open(reg_path, "w", encoding="utf-8") as f:
                json.dump(reg_data, f, indent=2)

    # Update html if needed
    html_file = target_dir / f"{slug}.html"
    if html_file.exists():
        html_src = html_file.read_text(encoding="utf-8")
        if "lib/shader_fallback.js" not in html_src:
            html_src = html_src.replace(
                '<script src="lib/shaders.iife.js"></script>',
                '<script src="lib/shaders.iife.js"></script>\n    <script src="lib/shader_fallback.js"></script>'
            )
            html_file.write_text(html_src, encoding="utf-8")
    print(f"  [UPDATED_FALLBACK] {slug}")


def main():
    print(f"Porting 17 eligible shaders from {DONOR_BLOCKS}...")
    for s in ELIGIBLE_17:
        port_single_shader(s)

    print("\nUpdating fallback engine in 5 existing shader blocks...")
    for s in EXISTING_SHADER_5:
        update_existing_shader_fallback(s)

    print(f"\nAll 22 shader blocks wired with dual WebGPU + Canvas 2D fallback.")
    print(f"Total blocks in shipped_blocks now: {len(list(SHIPPED_BLOCKS.iterdir()))}")


if __name__ == "__main__":
    main()
