# SPDX-License-Identifier: AGPL-3.0-only
"""Generate N-Z Census and Blocker Ledger for Wave 17."""
from __future__ import annotations
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SHIPPED_ROOT = REPO_ROOT / "backend" / "catalog" / "shipped_blocks"
INV_FILE = REPO_ROOT / "backend" / "catalog_inventory" / "hyperframes_196_inventory.json"
OUTPUT_FILE = REPO_ROOT / "scripts" / "qa_wave17" / "nz_census_and_blockers.json"

PRE_WAVE16_SHIPPED = [
    "nebula", "plasma", "prism", "sine-wave", "strands", "stripes", "swirl",
    "tiktok-follow", "voronoi", "water", "waveform", "weight-wave", "yt-lower-third"
]

WAVE16_SHIPPED = [
    "news-ticker", "notification-cascade", "organic-light-leak-overlay", "ridged-burn",
    "ripple-waves", "sdf-iris", "split-flap-board", "thermal-distortion",
    "thread-message-stack", "transitions-dissolve", "transitions-push", "transitions-radial",
    "week-in-merges", "whip-pan"
]

WAVE17_SHIPPED = [
    "transitions-3d", "transitions-blur", "transitions-cover", "transitions-destruction",
    "transitions-distortion", "transitions-grid", "transitions-light", "transitions-mechanical",
    "transitions-other", "transitions-scale", "share-sheet-carousel", "snow", "starfield",
    "rack-focus", "swirl-vortex", "vfx-magnetic", "vfx-text-cursor", "ui-3d-reveal"
]

TRADEMARK_BLOCKED = {
    "reddit-post": "Contains Reddit proprietary UI layout, upvote/downvote arrows, and brand dress.",
    "slack-notification-ad": "Contains Slack corporate notification UI and proprietary branding.",
    "spotify-card": "Contains Spotify brand assets, track player layout, and platform styling.",
    "vfx-iphone-device": "Contains Apple iPhone hardware bezel trade dress and proprietary screen mask.",
    "vpn-youtube-spot": "Contains YouTube native player interface and sponsored brand placement graphics.",
    "x-post": "Contains X (formerly Twitter) social UI, verified checkmarks, and tweet actions.",
    "yt-comment-card": "Contains YouTube comment UI, profile layout, and platform badges.",
    "yt-lcd-background": "Contains YouTube brand identity backdrops.",
    "yt-logo-intro": "Contains YouTube official logo animation and red platform badge.",
    "yt-prism-title": "Contains YouTube channel typography styling with platform branding.",
    "yt-vertical-fill": "Contains YouTube Shorts branding and video frame fill."
}

MAP_BLOCKED = {
    "north-korea-locked-down": "Requires external GIS geo-boundary datasets and flight vector coordinates.",
    "nyc-paris-flight": "Requires external transatlantic flight route GeoJSON/TopoJSON coordinates.",
    "spain-map": "Requires external Spain regional administrative boundary shapefiles.",
    "us-map": "Requires external US states TopoJSON atlas boundaries.",
    "us-map-bubble": "Requires external US demographic coordinates and county boundaries.",
    "us-map-flow": "Requires external US interstate vector flow datasets.",
    "us-map-hex": "Requires external US hex-grid cartogram datasets.",
    "world-map": "Requires external Natural Earth 110m global landmass vectors."
}

ENGINE_3D_BLOCKED = {
    "notes-reveal": "Requires unvendored Three.js canvas setup with custom lighting models.",
    "orbit-card": "Requires headless Three.js WebGL orbit controls with complex shader pipeline.",
    "oscilloscope-trace": "Requires high-frequency audio visualizer Three.js mesh geometry.",
    "product-turntable": "Requires GLTF 3D model loader and Three.js PBR renderer.",
    "spiral-galaxy": "Requires Three.js particle system with float texture point-cloud simulation.",
    "vfx-anamorphic-flare": "Requires Three.js post-processing pipeline with anamorphic bloom pass.",
    "vfx-liquid-background": "Requires Three.js WebGL2 fluid dynamics simulation with ping-pong framebuffers.",
    "vfx-liquid-glass": "Requires Three.js refraction shaders with custom normal mapping.",
    "vfx-portal": "Requires Three.js volumetric portal shaders with depth buffer raymarching.",
    "vfx-shatter": "Requires Three.js Voronoi 3D mesh fragmentation and physics simulation.",
    "wireframe-portal-title": "Requires Clipper-lib and Three.js polygon triangulation engines."
}

def main():
    with open(INV_FILE, "r", encoding="utf-8") as f:
        inv_data = json.load(f)

    inv_blocks = {b["id"]: b for b in inv_data.get("blocks", [])}
    
    nz_slugs = []
    for bid, b in inv_blocks.items():
        first = bid[0].lower()
        if ("n" <= first <= "z") or first.isdigit():
            nz_slugs.append(bid)
    nz_slugs = sorted(nz_slugs)

    items = []
    shipped_count = 0
    blocked_count = 0

    for slug in nz_slugs:
        inv_item = inv_blocks.get(slug, {})
        cat = inv_item.get("taxonomy", {}).get("category_id")

        if slug in WAVE17_SHIPPED:
            shipped_count += 1
            ev_file = SHIPPED_ROOT / slug / "port-evidence.json"
            ev = json.loads(ev_file.read_text(encoding="utf-8")) if ev_file.exists() else {}
            items.append({
                "slug": slug,
                "status": "SHIPPED",
                "wave": 17,
                "category": cat,
                "relative_source_path": f"registry/blocks/{slug}",
                "output_html_sha256": ev.get("output_html_sha256"),
                "source_sha256": ev.get("source_sha256"),
                "rights_status": "VERIFIED_PERMISSIVE",
                "offline_vendored": True,
                "blocker_reason": None
            })
        elif slug in WAVE16_SHIPPED:
            shipped_count += 1
            ev_file = SHIPPED_ROOT / slug / "port-evidence.json"
            ev = json.loads(ev_file.read_text(encoding="utf-8")) if ev_file.exists() else {}
            items.append({
                "slug": slug,
                "status": "SHIPPED",
                "wave": 16,
                "category": cat,
                "relative_source_path": f"registry/blocks/{slug}",
                "output_html_sha256": ev.get("output_html_sha256"),
                "source_sha256": ev.get("source_sha256"),
                "rights_status": "VERIFIED_PERMISSIVE",
                "offline_vendored": True,
                "blocker_reason": None
            })
        elif slug in PRE_WAVE16_SHIPPED:
            shipped_count += 1
            items.append({
                "slug": slug,
                "status": "SHIPPED",
                "wave": "pre-wave16",
                "category": cat,
                "relative_source_path": f"registry/blocks/{slug}",
                "rights_status": "VERIFIED_PERMISSIVE",
                "offline_vendored": True,
                "blocker_reason": None
            })
        elif slug in TRADEMARK_BLOCKED:
            blocked_count += 1
            items.append({
                "slug": slug,
                "status": "BLOCKED",
                "blocker_family": "TRADEMARK_AND_PLATFORM_ASSETS",
                "category": cat,
                "relative_source_path": f"registry/blocks/{slug}",
                "rights_status": "RESTRICTED_TRADEMARK",
                "blocker_reason": TRADEMARK_BLOCKED[slug]
            })
        elif slug in MAP_BLOCKED:
            blocked_count += 1
            items.append({
                "slug": slug,
                "status": "BLOCKED",
                "blocker_family": "EXTERNAL_GIS_DATASETS",
                "category": cat,
                "relative_source_path": f"registry/blocks/{slug}",
                "rights_status": "DATASET_DEPENDENT",
                "blocker_reason": MAP_BLOCKED[slug]
            })
        elif slug in ENGINE_3D_BLOCKED:
            blocked_count += 1
            items.append({
                "slug": slug,
                "status": "BLOCKED",
                "blocker_family": "UNVENDORED_3D_ENGINES",
                "category": cat,
                "relative_source_path": f"registry/blocks/{slug}",
                "rights_status": "ENGINE_DEPENDENT",
                "blocker_reason": ENGINE_3D_BLOCKED[slug]
            })
        else:
            blocked_count += 1
            items.append({
                "slug": slug,
                "status": "BLOCKED",
                "blocker_family": "AWAITING_PORT",
                "category": cat,
                "relative_source_path": f"registry/blocks/{slug}",
                "rights_status": "PENDING_AUDIT",
                "blocker_reason": "Scheduled for subsequent porting waves."
            })

    report = {
        "schema_version": 1,
        "wave": 17,
        "agent": "Agent 4 (N-Z Backlog Porting & Independent Anti-Fake QA)",
        "summary": {
            "total_nz_blocks": len(nz_slugs),
            "total_shipped": shipped_count,
            "shipped_pre_wave16": len(PRE_WAVE16_SHIPPED),
            "shipped_wave16": len(WAVE16_SHIPPED),
            "shipped_wave17": len(WAVE17_SHIPPED),
            "total_blocked": blocked_count,
            "blocked_trademark": len(TRADEMARK_BLOCKED),
            "blocked_gis_maps": len(MAP_BLOCKED),
            "blocked_3d_engines": len(ENGINE_3D_BLOCKED)
        },
        "blocks": items
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8", newline="\n")
    print(f"Generated {OUTPUT_FILE}: {shipped_count} shipped, {blocked_count} blocked (Total {len(nz_slugs)}).")

if __name__ == "__main__":
    main()
