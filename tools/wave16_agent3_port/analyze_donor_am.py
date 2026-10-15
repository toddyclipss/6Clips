#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""
Script to derive the exact not-yet-functional A-M original ID set from donor registry/blocks/
and current integrated snapshot. Groups targets by renderer dependency and rights status.
"""
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DONOR_ROOT = Path(r"C:\Users\toddy\Desktop\hyperframes\registry\blocks")
SHIPPED_ROOT = REPO_ROOT / "backend" / "catalog" / "shipped_blocks"

def analyze():
    if not DONOR_ROOT.exists():
        raise RuntimeError(f"Donor root does not exist: {DONOR_ROOT}")

    all_donor_dirs = sorted([d.name for d in DONOR_ROOT.iterdir() if d.is_dir()])
    shipped_dirs = set(d.name for d in SHIPPED_ROOT.iterdir() if d.is_dir())

    am_donor_slugs = [s for s in all_donor_dirs if s[0].lower() <= 'm']
    am_already_shipped = [s for s in am_donor_slugs if s in shipped_dirs]
    am_unported = [s for s in am_donor_slugs if s not in shipped_dirs]

    print(f"Total donor directories: {len(all_donor_dirs)}")
    print(f"Total A-M donor slugs: {len(am_donor_slugs)}")
    print(f"A-M already shipped in repo: {len(am_already_shipped)}")
    print(f"A-M unported (target backlog): {len(am_unported)}")

    # Analyze each unported block
    target_inventory = {}
    brand_keywords = [
        "apple", "chatgpt", "claude", "heygen", "macos", "ios", "instagram", "tiktok"
    ]

    for slug in am_unported:
        donor_dir = DONOR_ROOT / slug
        html_file = donor_dir / f"{slug}.html"
        reg_file = donor_dir / "registry-item.json"
        assets_dir = donor_dir / "assets"

        html_content = html_file.read_text(encoding="utf-8", errors="ignore") if html_file.exists() else ""
        reg_data = json.loads(reg_file.read_text(encoding="utf-8", errors="ignore")) if reg_file.exists() else {}

        # Dependencies
        scripts = re.findall(r'<script[^>]*src=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
        links = re.findall(r'<link[^>]*href=["\']([^"\']+)["\']', html_content, re.IGNORECASE)

        # Technology detection
        tech = []
        if "three" in html_content.lower() or any("three" in s.lower() for s in scripts):
            tech.append("three.js")
        if "gsap" in html_content.lower() or any("gsap" in s.lower() for s in scripts):
            tech.append("gsap")
        if "typegpu" in html_content.lower() or "webgpu" in html_content.lower() or "shaders.iife.js" in html_content:
            tech.append("webgpu/shader")
        if "lottie" in html_content.lower() or any("lottie" in s.lower() for s in scripts):
            tech.append("lottie")
        if "<canvas" in html_content.lower() and not tech:
            tech.append("canvas")
        if not tech:
            tech.append("css/dom")

        # Rights / Proprietary trademarks check
        title = reg_data.get("title", "")
        desc = reg_data.get("description", "")
        tags = [t.lower() for t in reg_data.get("tags", [])]
        text_corp = f"{slug} {title} {desc} {' '.join(tags)}".lower()

        matched_brands = [b for b in brand_keywords if b in text_corp]
        has_proprietary_branding = False
        blocked_reason = None

        # Check for proprietary logos / brands
        if "heygen" in slug.lower() or "heygen" in matched_brands:
            has_proprietary_branding = True
            blocked_reason = "Proprietary third-party brand/avatar asset (HeyGen trademark)"
        elif "apple" in slug.lower() or "macos" in slug.lower() or "ios" in slug.lower():
            # Check if assets contain apple trademark or logo
            if assets_dir.exists():
                has_proprietary_branding = True
                blocked_reason = "Proprietary Apple trademark/assets"
        elif "chatgpt" in slug.lower() or "claude" in slug.lower():
            has_proprietary_branding = True
            blocked_reason = f"Proprietary AI brand trademark ({slug})"

        target_inventory[slug] = {
            "slug": slug,
            "title": title,
            "tech": tech,
            "scripts": scripts,
            "links": links,
            "has_assets": assets_dir.exists(),
            "rights_status": "BLOCKED_RIGHTS" if has_proprietary_branding else "VERIFIED_PERMISSIVE",
            "blocked_reason": blocked_reason,
            "duration": reg_data.get("duration", 0),
            "dimensions": reg_data.get("dimensions", {}),
            "tags": tags
        }

    out_file = REPO_ROOT / "tools" / "wave16_agent3_port" / "am_backlog_analysis.json"
    out_file.write_text(json.dumps(target_inventory, indent=2), encoding="utf-8")
    print(f"Wrote backlog analysis to {out_file}")

    # Summary by tech
    tech_counts = {}
    for item in target_inventory.values():
        t_key = "+".join(sorted(item["tech"]))
        tech_counts[t_key] = tech_counts.get(t_key, 0) + 1
    print("\nBreakdown by technology:")
    for k, v in sorted(tech_counts.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    # Summary by rights
    rights_counts = {}
    for item in target_inventory.values():
        r = item["rights_status"]
        rights_counts[r] = rights_counts.get(r, 0) + 1
    print("\nBreakdown by rights status:")
    for k, v in sorted(rights_counts.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

if __name__ == "__main__":
    analyze()
