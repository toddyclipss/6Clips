# SPDX-License-Identifier: AGPL-3.0-only
"""Audit and census for pending N-Z/0-9 original donor blocks.

Read-only inspection of donor blocks and current repository state.
"""
from __future__ import annotations
import json
import os
import re
from pathlib import Path

DONOR_BLOCKS_DIR = Path(r"C:\Users\toddy\Desktop\hyperframes\registry\blocks")
REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_FILE = REPO_ROOT / "backend" / "catalog_inventory" / "hyperframes_196_inventory.json"
SHIPPED_DIR = REPO_ROOT / "backend" / "catalog" / "shipped_blocks"

SCRIPT_SRC_RE = re.compile(r'<script[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
LINK_HREF_RE = re.compile(r'<link[^>]+href=["\']([^"\']+)["\']', re.IGNORECASE)

KNOWN_TRADEMARKS = {
    "reddit-post": "Reddit",
    "spotify-card": "Spotify",
    "slack-notification-ad": "Slack",
    "x-post": "X (formerly Twitter)",
    "yt-comment-card": "YouTube",
    "yt-logo-intro": "YouTube",
    "yt-prism-title": "YouTube",
    "yt-vertical-fill": "YouTube",
    "yt-lcd-background": "YouTube",
    "vpn-youtube-spot": "YouTube",
    "vfx-iphone-device": "Apple iPhone",
}

def audit_nz_blocks():
    with open(INVENTORY_FILE, "r", encoding="utf-8") as f:
        inv = json.load(f)
    blocks = inv.get("blocks", inv) if isinstance(inv, dict) else inv

    nz_all = []
    for b in blocks:
        bid = b.get("id") or b.get("slug")
        ch = bid[0].lower()
        if ("n" <= ch <= "z") or ch.isdigit():
            nz_all.append(b)

    results = []
    shipped_count = 0
    pending_count = 0

    for b in nz_all:
        bid = b.get("id") or b.get("slug")
        is_shipped = (SHIPPED_DIR / bid).exists()
        if is_shipped:
            shipped_count += 1
            results.append({
                "id": bid,
                "status": "ALREADY_SHIPPED",
                "category": b.get("category"),
                "is_shipped": True,
            })
            continue

        pending_count += 1
        donor_dir = DONOR_BLOCKS_DIR / bid
        if not donor_dir.exists():
            results.append({
                "id": bid,
                "status": "DONOR_NOT_FOUND",
                "category": b.get("category"),
                "is_shipped": False,
            })
            continue

        html_file = donor_dir / f"{bid}.html"
        reg_file = donor_dir / "registry-item.json"
        assets_dir = donor_dir / "assets"

        scripts = []
        links = []
        html_content = ""
        if html_file.exists():
            html_content = html_file.read_text(encoding="utf-8", errors="replace")
            scripts = SCRIPT_SRC_RE.findall(html_content)
            links = LINK_HREF_RE.findall(html_content)

        reg_data = {}
        if reg_file.exists():
            try:
                reg_data = json.loads(reg_file.read_text(encoding="utf-8"))
            except Exception as e:
                reg_data = {"parse_error": str(e)}

        assets = [f.name for f in assets_dir.iterdir()] if assets_dir.exists() else []

        # Analyze motion engine / dependencies
        has_gsap = any("gsap" in s.lower() for s in scripts) or "gsap" in html_content.lower()
        has_three = any("three" in s.lower() for s in scripts) or "three" in html_content.lower()
        has_canvas = "<canvas" in html_content.lower()
        has_svg = "<svg" in html_content.lower()
        has_shader = "glsl" in html_content.lower() or "uniform" in html_content.lower() or "fragmentshader" in html_content.lower()

        # Check trademark / rights
        trademark = KNOWN_TRADEMARKS.get(bid)

        results.append({
            "id": bid,
            "status": "PENDING",
            "category": b.get("category") or reg_data.get("category"),
            "is_shipped": False,
            "scripts": scripts,
            "links": links,
            "assets": assets,
            "has_gsap": has_gsap,
            "has_three": has_three,
            "has_canvas": has_canvas,
            "has_svg": has_svg,
            "has_shader": has_shader,
            "trademark": trademark,
            "variables": reg_data.get("variables", []),
            "duration": reg_data.get("duration", 5.0),
            "description": b.get("description") or reg_data.get("description", ""),
        })

    report = {
        "total_nz_09": len(nz_all),
        "already_shipped": shipped_count,
        "pending": pending_count,
        "items": results,
    }

    out_file = REPO_ROOT / "tools" / "wave16_agent4_port" / "nz_census_report.json"
    out_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Census completed: Total={len(nz_all)}, Shipped={shipped_count}, Pending={pending_count}")
    return report

if __name__ == "__main__":
    audit_nz_blocks()
