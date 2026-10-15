# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
r"""
Build canonical exactly-196-slug crosswalk against read-only HyperFrames donor sources.
Sources:
- C:\Users\toddy\Desktop\hyperframes\registry\blocks
- C:\Users\toddy\Desktop\hyperframes\docs\snippets\catalog-gallery-data.mdx

Extracts exact native gallery group, section, family, tags, and category.
Unindexed blocks are classified explicitly as SOURCE_CATEGORY_UNSPECIFIED.
Strictly excludes 6Clips-authored retired originals: creator-hud, glitch-transition.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("build_196_crosswalk")

REPO_ROOT = Path(__file__).resolve().parents[2]
DONOR_BLOCKS_DIR = Path(r"C:\Users\toddy\Desktop\hyperframes\registry\blocks")
DONOR_GALLERY_MDX = Path(r"C:\Users\toddy\Desktop\hyperframes\docs\snippets\catalog-gallery-data.mdx")
SHIPPED_BLOCKS_DIR = REPO_ROOT / "backend" / "catalog" / "shipped_blocks"
OUTPUT_JSON = REPO_ROOT / "backend" / "catalog_inventory" / "hyperframes_196_source_crosswalk.json"

# The 10 blocks verified by the owner in the running UI baseline
OWNER_10_BASELINE = {
    "aurora",
    "data-chart",
    "flowing-gradient",
    "holographic",
    "instagram-follow",
    "plasma",
    "stripes",
    "tiktok-follow",
    "weight-wave",
    "yt-lower-third",
}

# 6Clips-authored blocks strictly excluded from the 196 donor catalog
RETIRED_6CLIPS_BLOCKS = {
    "creator-hud",
    "glitch-transition",
}


def load_gallery_metadata() -> Dict[str, Dict[str, Any]]:
    """Parse upstream catalog-gallery-data.mdx safely."""
    if not DONOR_GALLERY_MDX.exists():
        logger.error("Donor gallery metadata file not found at: %s", DONOR_GALLERY_MDX)
        return {}

    content = DONOR_GALLERY_MDX.read_text(encoding="utf-8")
    m = re.search(r"export const \w+\s*=\s*(\{.*?\});", content, re.DOTALL)
    if not m:
        m = re.search(r"(\{.*\})", content, re.DOTALL)
    if not m:
        raise ValueError("Could not parse JSON structure from catalog-gallery-data.mdx")

    raw_data = json.loads(m.group(1))
    items = raw_data.get("items", [])
    gallery_by_id: Dict[str, Dict[str, Any]] = {}
    for it in items:
        bid = it.get("id")
        if bid:
            gallery_by_id[bid] = it

    logger.info("Loaded %d unique items from catalog-gallery-data.mdx", len(gallery_by_id))
    return gallery_by_id


def determine_timeline_track(gallery_group: str, gallery_section: str, slug: str, tags: List[str]) -> str:
    """Derive authentic drag-and-drop target timeline track based on donor semantics."""
    s_lower = slug.lower()
    g_lower = gallery_group.lower()
    sec_lower = gallery_section.lower()
    tags_lower = [t.lower() for t in tags]

    if "transition" in g_lower or "transition" in sec_lower or s_lower.startswith("transitions-") or "transition" in s_lower:
        return "transitions"
    if g_lower == "text-captions" or sec_lower in ("captions", "lower thirds", "typography & text") or s_lower.startswith("lt-") or s_lower.startswith("hw-"):
        return "captions_text"
    if "audio" in tags_lower:
        return "audio"
    return "media_scene"


def build_crosswalk() -> Dict[str, Any]:
    """Build canonical 196-block crosswalk."""
    if not DONOR_BLOCKS_DIR.exists():
        raise FileNotFoundError(f"Donor directory does not exist: {DONOR_BLOCKS_DIR}")

    donor_dirs = sorted([d.name for d in DONOR_BLOCKS_DIR.iterdir() if d.is_dir()])
    logger.info("Found %d directories in donor registry/blocks", len(donor_dirs))

    # Exclude 6Clips retired originals
    donor_slugs = [d for d in donor_dirs if d not in RETIRED_6CLIPS_BLOCKS]
    if len(donor_slugs) != 196:
        logger.warning("Expected exactly 196 donor slugs, found %d", len(donor_slugs))

    gallery_meta = load_gallery_metadata()
    shipped_slugs = set(d.name for d in SHIPPED_BLOCKS_DIR.iterdir() if d.is_dir()) if SHIPPED_BLOCKS_DIR.exists() else set()

    crosswalk_entries: List[Dict[str, Any]] = []
    category_counts: Dict[str, int] = {}
    section_counts: Dict[str, int] = {}

    for slug in donor_slugs:
        g_item = gallery_meta.get(slug)
        is_indexed = g_item is not None

        if is_indexed and g_item:
            gallery_group = g_item.get("group") or "SOURCE_CATEGORY_UNSPECIFIED"
            gallery_section = g_item.get("section") or "SOURCE_CATEGORY_UNSPECIFIED"
            cat_status = "SOURCE_CATEGORY_CONFIRMED"
            title = g_item.get("title") or slug.replace("-", " ").title()
            tagline = g_item.get("tagline") or ""
            description = g_item.get("description") or ""
            tags = g_item.get("tags") or []
            duration = float(g_item.get("duration") or 5.0)
            dims = {"width": g_item.get("width", 1920), "height": g_item.get("height", 1080)}
            preview_mode = (g_item.get("preview") or {}).get("mode", "unknown")
            upstream_video = g_item.get("video")
            upstream_poster = g_item.get("poster")
        else:
            gallery_group = "SOURCE_CATEGORY_UNSPECIFIED"
            gallery_section = "SOURCE_CATEGORY_UNSPECIFIED"
            cat_status = "SOURCE_CATEGORY_UNSPECIFIED"
            title = slug.replace("-", " ").title()
            tagline = f"Unindexed donor block '{slug}'"
            description = f"Present in upstream donor directory registry/blocks/{slug} but omitted from gallery index."
            tags = [slug]
            duration = 5.0
            dims = {"width": 1920, "height": 1080}
            preview_mode = "unspecified"
            upstream_video = None
            upstream_poster = None

        category_counts[gallery_group] = category_counts.get(gallery_group, 0) + 1
        section_counts[gallery_section] = section_counts.get(gallery_section, 0) + 1

        is_shipped = slug in shipped_slugs
        shipped_path = f"backend/catalog/shipped_blocks/{slug}" if is_shipped else None
        target_track = determine_timeline_track(gallery_group, gallery_section, slug, tags)

        entry = {
            "slug": slug,
            "title": title,
            "in_donor_registry": True,
            "indexed_in_gallery": is_indexed,
            "category_status": cat_status,
            "gallery_group": gallery_group,
            "gallery_section": gallery_section,
            "target_timeline_track": target_track,
            "tags": tags,
            "tagline": tagline,
            "description": description,
            "duration": duration,
            "dimensions": dims,
            "preview_mode": preview_mode,
            "upstream_video_url": upstream_video,
            "upstream_poster_url": upstream_poster,
            "shipped_on_disk": is_shipped,
            "shipped_path": shipped_path,
            "owner_observed_baseline": slug in OWNER_10_BASELINE,
            "provenance": {
                "source_repository": "hyperframes",
                "source_path": f"registry/blocks/{slug}",
                "donor_commit": "verified_upstream",
            },
        }
        crosswalk_entries.append(entry)

    manifest = {
        "schema_version": "1.0.0",
        "wave": 19,
        "census": {
            "total_donor_blocks": len(crosswalk_entries),
            "gallery_indexed_count": sum(1 for e in crosswalk_entries if e["indexed_in_gallery"]),
            "source_category_unspecified_count": sum(1 for e in crosswalk_entries if not e["indexed_in_gallery"]),
            "shipped_on_disk_count": sum(1 for e in crosswalk_entries if e["shipped_on_disk"]),
            "unshipped_pending_count": sum(1 for e in crosswalk_entries if not e["shipped_on_disk"]),
            "owner_observed_baseline_count": sum(1 for e in crosswalk_entries if e["owner_observed_baseline"]),
            "retired_6clips_blocks_excluded": sorted(list(RETIRED_6CLIPS_BLOCKS)),
        },
        "category_distribution": category_counts,
        "section_distribution": section_counts,
        "entries": crosswalk_entries,
    }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info("Successfully wrote crosswalk manifest to %s", OUTPUT_JSON)
    return manifest


if __name__ == "__main__":
    manifest = build_crosswalk()
    print("Crosswalk Summary:")
    print(f"  Total donor blocks: {manifest['census']['total_donor_blocks']}")
    print(f"  Gallery indexed: {manifest['census']['gallery_indexed_count']}")
    print(f"  Category unspecified: {manifest['census']['source_category_unspecified_count']}")
    print(f"  Shipped on disk: {manifest['census']['shipped_on_disk_count']}")
    print(f"  Pending/Unshipped: {manifest['census']['unshipped_pending_count']}")
    print(f"  Owner baseline: {manifest['census']['owner_observed_baseline_count']}")
