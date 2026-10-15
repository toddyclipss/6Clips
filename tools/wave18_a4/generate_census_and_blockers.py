# SPDX-License-Identifier: AGPL-3.0-only
"""Generate Wave 18 N-Z Census and Blockers Ledger.

Truthful accounting of all 75 N-Z original donor blocks:
- 52 Shipped (13 pre-wave16 + 14 wave16 + 18 wave17 + 7 wave18)
- 23 Blocked (11 trademark/platform, 5 external GIS, 7 unvendored 3D/shader engines)
"""
import json
import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DONOR_BLOCKS = Path(r"C:\Users\toddy\Desktop\hyperframes\registry\blocks")
SHIPPED_ROOT = REPO_ROOT / "backend" / "catalog" / "shipped_blocks"

PRE_WAVE16_NZ = [
    "nebula", "plasma", "prism", "sine-wave", "strands", "stripes", "swirl",
    "tiktok-follow", "voronoi", "water", "waveform", "weight-wave", "yt-lower-third"
]

WAVE16_NZ = [
    "news-ticker", "notification-cascade", "organic-light-leak-overlay", "split-flap-board",
    "thread-message-stack", "week-in-merges", "whip-pan", "ripple-waves", "sdf-iris",
    "ridged-burn", "thermal-distortion", "transitions-push", "transitions-dissolve",
    "transitions-radial"
]

WAVE17_NZ = [
    "transitions-3d", "transitions-blur", "transitions-cover", "transitions-destruction",
    "transitions-distortion", "transitions-grid", "transitions-light", "transitions-mechanical",
    "transitions-other", "transitions-scale", "share-sheet-carousel", "snow",
    "starfield", "rack-focus", "swirl-vortex", "vfx-magnetic", "vfx-text-cursor",
    "ui-3d-reveal"
]

WAVE18_NZ = [
    "orbit-card", "north-korea-locked-down", "notes-reveal", "nyc-paris-flight",
    "us-map-hex", "oscilloscope-trace", "vfx-anamorphic-flare"
]

BLOCKED_NZ = {
    # 11 Platform & Corporate Trademark
    "reddit-post": {
        "family": "TRADEMARK_AND_PLATFORM_ASSETS",
        "rights": "TRADEMARK_PROTECTED",
        "reason": "Contains Reddit proprietary UI layout, upvote/downvote arrows, and brand trade dress without license agreement."
    },
    "slack-notification-ad": {
        "family": "TRADEMARK_AND_PLATFORM_ASSETS",
        "rights": "TRADEMARK_PROTECTED",
        "reason": "Contains Slack corporate notification layout and proprietary branding (slack-mark.svg) requiring trademark clearance."
    },
    "spotify-card": {
        "family": "TRADEMARK_AND_PLATFORM_ASSETS",
        "rights": "TRADEMARK_PROTECTED",
        "reason": "Contains Spotify brand assets, track player layout, and platform styling requiring partner authorization."
    },
    "vfx-iphone-device": {
        "family": "TRADEMARK_AND_PLATFORM_ASSETS",
        "rights": "TRADEMARK_PROTECTED",
        "reason": "Contains Apple iPhone/MacBook hardware bezel trade dress and proprietary screen mask assets (iphone.glb, macbook.glb)."
    },
    "vpn-youtube-spot": {
        "family": "TRADEMARK_AND_PLATFORM_ASSETS",
        "rights": "TRADEMARK_PROTECTED",
        "reason": "Contains YouTube native player interface and sponsored brand placement graphics requiring platform consent."
    },
    "x-post": {
        "family": "TRADEMARK_AND_PLATFORM_ASSETS",
        "rights": "TRADEMARK_PROTECTED",
        "reason": "Contains X (formerly Twitter) social UI, verified checkmarks, and tweet actions requiring developer terms clearance."
    },
    "yt-comment-card": {
        "family": "TRADEMARK_AND_PLATFORM_ASSETS",
        "rights": "TRADEMARK_PROTECTED",
        "reason": "Contains YouTube comment UI, profile layout, and platform badges subject to platform branding guidelines."
    },
    "yt-lcd-background": {
        "family": "TRADEMARK_AND_PLATFORM_ASSETS",
        "rights": "TRADEMARK_PROTECTED",
        "reason": "Contains YouTube brand identity backdrops and platform styling subject to brand protection."
    },
    "yt-logo-intro": {
        "family": "TRADEMARK_AND_PLATFORM_ASSETS",
        "rights": "TRADEMARK_PROTECTED",
        "reason": "Contains YouTube official logo animation and red platform badge requiring YouTube trademark licensing."
    },
    "yt-prism-title": {
        "family": "TRADEMARK_AND_PLATFORM_ASSETS",
        "rights": "TRADEMARK_PROTECTED",
        "reason": "Contains YouTube channel typography styling with platform branding requiring platform clearance."
    },
    "yt-vertical-fill": {
        "family": "TRADEMARK_AND_PLATFORM_ASSETS",
        "rights": "TRADEMARK_PROTECTED",
        "reason": "Contains YouTube Shorts branding and video frame fill subject to platform brand usage guidelines."
    },

    # 5 External GIS Datasets (require remote TopoJSON fetch)
    "spain-map": {
        "family": "EXTERNAL_GIS_DATASETS",
        "rights": "EXTERNAL_NETWORK_DEPENDENT",
        "reason": "Performs runtime fetch() to cdn.jsdelivr.net for unvendored Spain administrative boundary shapefiles, violating offline CSP."
    },
    "us-map": {
        "family": "EXTERNAL_GIS_DATASETS",
        "rights": "EXTERNAL_NETWORK_DEPENDENT",
        "reason": "Performs runtime fetch() to cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json, violating offline zero-egress requirement."
    },
    "us-map-bubble": {
        "family": "EXTERNAL_GIS_DATASETS",
        "rights": "EXTERNAL_NETWORK_DEPENDENT",
        "reason": "Performs runtime network fetch() for US demographic coordinates and county boundaries from unvendored remote CDN."
    },
    "us-map-flow": {
        "family": "EXTERNAL_GIS_DATASETS",
        "rights": "EXTERNAL_NETWORK_DEPENDENT",
        "reason": "Performs runtime network fetch() for US interstate vector flow datasets from unvendored remote CDN."
    },
    "world-map": {
        "family": "EXTERNAL_GIS_DATASETS",
        "rights": "EXTERNAL_NETWORK_DEPENDENT",
        "reason": "Performs runtime fetch() to cdn.jsdelivr.net for Natural Earth 110m global landmass vectors, violating offline CSP."
    },

    # 7 Unvendored 3D Engines & Shaders
    "product-turntable": {
        "family": "UNVENDORED_3D_ENGINES",
        "rights": "UNVENDORED_UPSTREAM_ENGINE",
        "reason": "Imports Three.js 0.184.0 ESM modules from cdn.jsdelivr.net (+esm) at runtime; unvendored in donor folder."
    },
    "spiral-galaxy": {
        "family": "UNVENDORED_3D_ENGINES",
        "rights": "UNVENDORED_UPSTREAM_ENGINE",
        "reason": "Requires unvendored Three.js point-cloud simulation script loaded from cdn.jsdelivr.net."
    },
    "vfx-liquid-background": {
        "family": "UNVENDORED_3D_ENGINES",
        "rights": "UNVENDORED_UPSTREAM_ENGINE",
        "reason": "Requires unvendored Three.js WebGL2 fluid dynamics simulation with ping-pong framebuffers loaded from remote CDN."
    },
    "vfx-liquid-glass": {
        "family": "UNVENDORED_3D_ENGINES",
        "rights": "UNVENDORED_UPSTREAM_ENGINE",
        "reason": "Requires 8 unvendored Three.js postprocessing and shader scripts loaded from cdn.jsdelivr.net."
    },
    "vfx-portal": {
        "family": "UNVENDORED_3D_ENGINES",
        "rights": "UNVENDORED_UPSTREAM_ENGINE",
        "reason": "Requires unvendored Three.js volumetric portal shaders with depth buffer raymarching loaded from remote CDN."
    },
    "vfx-shatter": {
        "family": "UNVENDORED_3D_ENGINES",
        "rights": "UNVENDORED_UPSTREAM_ENGINE",
        "reason": "Requires unvendored Three.js Voronoi 3D mesh fragmentation loaded from cdn.jsdelivr.net."
    },
    "wireframe-portal-title": {
        "family": "UNVENDORED_3D_ENGINES",
        "rights": "UNVENDORED_UPSTREAM_ENGINE",
        "reason": "Requires unvendored Clipper-lib and 10 Three.js postprocessing modules loaded from cdn.jsdelivr.net."
    }
}

def get_category(slug: str) -> str:
    reg_file = DONOR_BLOCKS / slug / "registry-item.json"
    if reg_file.exists():
        try:
            d = json.loads(reg_file.read_text(encoding="utf-8"))
            cats = d.get("categories", [])
            if cats:
                return cats[0]
            tags = d.get("tags", [])
            if "transition" in tags:
                return "transitions"
            if "3d" in tags:
                return "3d-motion"
            if "map" in tags or "chart" in tags or "data" in tags:
                return "data-charts"
            if "vfx" in tags or "surface" in tags:
                return "surfaces"
            if "carousel" in tags:
                return "carousels"
            if "caption" in tags:
                return "text-captions"
        except Exception:
            pass
    return "scenes-demos"

def main():
    blocks = []

    # 1. Shipped pre-wave16
    for slug in sorted(PRE_WAVE16_NZ):
        shipped_p = SHIPPED_ROOT / slug
        evidence_file = shipped_p / "port-evidence.json"
        src_sha = ""
        out_sha = ""
        if evidence_file.exists():
            ev = json.loads(evidence_file.read_text(encoding="utf-8"))
            src_sha = ev.get("source_sha256", "")
            out_sha = ev.get("output_html_sha256", "")
        blocks.append({
            "slug": slug,
            "status": "SHIPPED",
            "wave": "pre-wave16",
            "category": get_category(slug),
            "relative_source_path": f"registry/blocks/{slug}",
            "rights_status": "VERIFIED_PERMISSIVE",
            "blocker_family": None,
            "blocker_reason": None,
            "offline_vendored": True,
            "source_sha256": src_sha,
            "output_html_sha256": out_sha
        })

    # 2. Shipped wave16
    for slug in sorted(WAVE16_NZ):
        shipped_p = SHIPPED_ROOT / slug
        evidence_file = shipped_p / "port-evidence.json"
        src_sha = ""
        out_sha = ""
        if evidence_file.exists():
            ev = json.loads(evidence_file.read_text(encoding="utf-8"))
            src_sha = ev.get("source_sha256", "")
            out_sha = ev.get("output_html_sha256", "")
        blocks.append({
            "slug": slug,
            "status": "SHIPPED",
            "wave": "wave16",
            "category": get_category(slug),
            "relative_source_path": f"registry/blocks/{slug}",
            "rights_status": "VERIFIED_PERMISSIVE",
            "blocker_family": None,
            "blocker_reason": None,
            "offline_vendored": True,
            "source_sha256": src_sha,
            "output_html_sha256": out_sha
        })

    # 3. Shipped wave17
    for slug in sorted(WAVE17_NZ):
        shipped_p = SHIPPED_ROOT / slug
        evidence_file = shipped_p / "port-evidence.json"
        src_sha = ""
        out_sha = ""
        if evidence_file.exists():
            ev = json.loads(evidence_file.read_text(encoding="utf-8"))
            src_sha = ev.get("source_sha256", "")
            out_sha = ev.get("output_html_sha256", "")
        blocks.append({
            "slug": slug,
            "status": "SHIPPED",
            "wave": "wave17",
            "category": get_category(slug),
            "relative_source_path": f"registry/blocks/{slug}",
            "rights_status": "VERIFIED_PERMISSIVE",
            "blocker_family": None,
            "blocker_reason": None,
            "offline_vendored": True,
            "source_sha256": src_sha,
            "output_html_sha256": out_sha
        })

    # 4. Shipped wave18
    for slug in sorted(WAVE18_NZ):
        shipped_p = SHIPPED_ROOT / slug
        evidence_file = shipped_p / "port-evidence.json"
        src_sha = ""
        out_sha = ""
        if evidence_file.exists():
            ev = json.loads(evidence_file.read_text(encoding="utf-8"))
            src_sha = ev.get("source_sha256", "")
            out_sha = ev.get("output_html_sha256", "")
        blocks.append({
            "slug": slug,
            "status": "SHIPPED",
            "wave": "wave18",
            "category": get_category(slug),
            "relative_source_path": f"registry/blocks/{slug}",
            "rights_status": "VERIFIED_PERMISSIVE",
            "blocker_family": None,
            "blocker_reason": None,
            "offline_vendored": True,
            "source_sha256": src_sha,
            "output_html_sha256": out_sha
        })

    # 5. Blocked
    for slug in sorted(BLOCKED_NZ.keys()):
        info = BLOCKED_NZ[slug]
        donor_html = DONOR_BLOCKS / slug / f"{slug}.html"
        src_sha = hashlib.sha256(donor_html.read_bytes()).hexdigest() if donor_html.exists() else ""
        blocks.append({
            "slug": slug,
            "status": "BLOCKED",
            "wave": None,
            "category": get_category(slug),
            "relative_source_path": f"registry/blocks/{slug}",
            "rights_status": info["rights"],
            "blocker_family": info["family"],
            "blocker_reason": info["reason"],
            "offline_vendored": False,
            "source_sha256": src_sha,
            "output_html_sha256": None
        })

    census = {
        "schema_version": 1,
        "wave": 18,
        "agent": "agent-4",
        "summary": {
            "total_nz_blocks": len(blocks),
            "total_shipped": len([b for b in blocks if b["status"] == "SHIPPED"]),
            "shipped_pre_wave16": len(PRE_WAVE16_NZ),
            "shipped_wave16": len(WAVE16_NZ),
            "shipped_wave17": len(WAVE17_NZ),
            "shipped_wave18": len(WAVE18_NZ),
            "total_blocked": len(BLOCKED_NZ),
            "blocked_trademark": len([k for k, v in BLOCKED_NZ.items() if v["family"] == "TRADEMARK_AND_PLATFORM_ASSETS"]),
            "blocked_gis_maps": len([k for k, v in BLOCKED_NZ.items() if v["family"] == "EXTERNAL_GIS_DATASETS"]),
            "blocked_3d_engines": len([k for k, v in BLOCKED_NZ.items() if v["family"] == "UNVENDORED_3D_ENGINES"])
        },
        "blocks": sorted(blocks, key=lambda b: b["slug"])
    }

    out_file = REPO_ROOT / "scripts" / "qa_wave18" / "nz_census_and_blockers.json"
    out_file.write_text(json.dumps(census, indent=2), encoding="utf-8", newline="\n")
    print(f"Generated census with {len(blocks)} blocks: {census['summary']['total_shipped']} shipped, {census['summary']['total_blocked']} blocked.")
    print(f"Saved to: {out_file}")

if __name__ == "__main__":
    main()
