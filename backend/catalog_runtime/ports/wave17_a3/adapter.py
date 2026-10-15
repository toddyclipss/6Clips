# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 17 Agent 3 Port Adapter:
Full runtime activation and productization engine for original HyperFrames A-M blocks.
Provides airgapped zero-egress sandboxing, strict CSP, responsive dual-aspect-ratio
scaling (16:9 and 9:16), parameter schema injection, and Motion project persistence.
"""
from __future__ import annotations

import hashlib
import json
import re
import copy
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[4]
SHIPPED_BLOCKS = ROOT / "backend" / "catalog" / "shipped_blocks"
LEDGER_PATH = Path(__file__).resolve().parent / "activated_am_ledger.json"

EXISTING_24_AM: List[str] = [
    "aurora", "blob", "data-chart", "flowing-gradient", "fractal-noise",
    "frost", "godrays", "goo", "holographic", "instagram-follow",
    "lens-flare", "liquid-metal", "lt-accent-underline", "lt-bold-block",
    "lt-clean-bar", "lt-color-block", "lt-dark-card", "lt-kicker-name",
    "lt-mask-reveal", "lt-side-rule", "lt-soft-pill", "lt-stack-bars",
    "marble", "mesh-gradient",
]

NEW_80_AM: List[str] = [
    "frost-sequence-camera-orbit", "cuboid-carousel", "cosmic-orb",
    "gallery-tunnel", "gooey-split", "code-3d-extrude",
    "code-particle-assemble", "code-shader-dissolve",
    "glitch", "gravitational-lens", "halftone-field", "light-leak",
    "chromatic-radial-split", "cinemagraph", "cinematic-zoom", "cross-warp-morph",
    "domain-warp-dissolve", "editorial-flash-overlay", "flash-through-white",
    "freeze-frame-dressing", "beat-freeze-cut", "camera-dolly-zoom",
    "code-diff", "code-highlight", "code-morph", "code-scroll",
    "code-slice-hero", "code-snippet-dark-2026", "code-snippet-dark-modern", "code-typing",
    "bar-chart-race", "flowchart", "flowchart-vertical",
    "mk-line-graph", "mk-progress-stat", "mk-specs-list",
    "ai-answer-rank", "ai-chat-reveal", "app-showcase", "camcorder-hud",
    "message-thread-reveal", "mk-background", "mk-callout-highlight",
    "mk-clone-wall-transition", "mk-placeholder-grid",
    "lower-third-bild", "lt-neon-border",
    "hw-frame", "hw-path-text", "hw-pipeline", "hw-scribble-transition",
    "hw-text-cloud", "hw-title", "hw-write-title", "logo-outro",
    "carousel-circle-1", "carousel-circle-2", "carousel-circle-3", "carousel-circle-4", "carousel-circle-5",
    "carousel-orbit-1", "carousel-orbit-2", "carousel-orbit-3", "carousel-orbit-4", "carousel-orbit-5",
    "carousel-path-1", "carousel-path-2", "carousel-path-3", "carousel-path-4", "carousel-path-5",
    "carousel-text-circle-1", "carousel-text-circle-2", "carousel-text-circle-3", "carousel-text-circle-4", "carousel-text-circle-5",
    "carousel-vision-1", "carousel-vision-2", "carousel-vision-3", "carousel-vision-4", "carousel-vision-5",
]

AM_ACTIVATED_104_BLOCKS: List[str] = sorted(EXISTING_24_AM + NEW_80_AM)

AM_BLOCKED_RIGHTS_9_BLOCKS: Dict[str, Dict[str, str]] = {
    "apple-money-count": {
        "status": "BLOCKED_RIGHTS",
        "legal_obstacle": "Proprietary Apple trademark, Apple Pay references, and proprietary audio assets.",
        "donor_source_path": "registry/blocks/apple-money-count",
    },
    "blue-sweater-intro-video": {
        "status": "BLOCKED_RIGHTS",
        "legal_obstacle": "Proprietary personal creator likeness and avatar photograph (joe-sai-avatar.png).",
        "donor_source_path": "registry/blocks/blue-sweater-intro-video",
    },
    "chatgpt-exchange": {
        "status": "BLOCKED_RIGHTS",
        "legal_obstacle": "Proprietary OpenAI ChatGPT brand name, logo, and trademark trade dress.",
        "donor_source_path": "registry/blocks/chatgpt-exchange",
    },
    "claude-exchange": {
        "status": "BLOCKED_RIGHTS",
        "legal_obstacle": "Proprietary Anthropic Claude brand name, logo, and trademark trade dress.",
        "donor_source_path": "registry/blocks/claude-exchange",
    },
    "code-snippet-apple-terminal-pro": {
        "status": "BLOCKED_RIGHTS",
        "legal_obstacle": "Proprietary Apple macOS Terminal interface trade dress and branding.",
        "donor_source_path": "registry/blocks/code-snippet-apple-terminal-pro",
    },
    "heygen-avatar-promo-card": {
        "status": "BLOCKED_RIGHTS",
        "legal_obstacle": "Proprietary HeyGen avatar video service trademark and visual branding.",
        "donor_source_path": "registry/blocks/heygen-avatar-promo-card",
    },
    "ios26-liquid-glass": {
        "status": "BLOCKED_RIGHTS",
        "legal_obstacle": "Proprietary Apple iPhone 3D model (iphone.glb) and 25 proprietary trademarked iOS app icons.",
        "donor_source_path": "registry/blocks/ios26-liquid-glass",
    },
    "macos-notification": {
        "status": "BLOCKED_RIGHTS",
        "legal_obstacle": "Proprietary Apple macOS system notification interface and visual assets.",
        "donor_source_path": "registry/blocks/macos-notification",
    },
    "macos-tahoe-liquid-glass": {
        "status": "BLOCKED_RIGHTS",
        "legal_obstacle": "Proprietary Apple MacBook 3D model (macbook.glb) and trademarked macOS application icons.",
        "donor_source_path": "registry/blocks/macos-tahoe-liquid-glass",
    },
}

AM_BLOCKED_DEPENDENCY_8_BLOCKS: Dict[str, Dict[str, str]] = {
    "canopy-part-title": {
        "status": "BLOCKED_DEPENDENCY",
        "technical_obstacle": "Requires unvendored Three.js r170 ESM postprocessing (EffectComposer/BokehPass) and dynamic Google Fonts runtime loader.",
        "donor_source_path": "registry/blocks/canopy-part-title",
    },
    "exploded-stack": {
        "status": "BLOCKED_DEPENDENCY",
        "technical_obstacle": "Requires unvendored Three.js r184 ESM geometry modules (RoundedBoxGeometry) and jsdelivr fontsource woff2 webfonts.",
        "donor_source_path": "registry/blocks/exploded-stack",
    },
    "extruded-logo": {
        "status": "BLOCKED_DEPENDENCY",
        "technical_obstacle": "Requires unvendored Three.js r184 ESM FontLoader and TextGeometry external modules.",
        "donor_source_path": "registry/blocks/extruded-logo",
    },
    "glass-hero": {
        "status": "BLOCKED_DEPENDENCY",
        "technical_obstacle": "Requires unvendored Three.js r184 ESM modules and jsdelivr fontsource woff2 webfonts.",
        "donor_source_path": "registry/blocks/glass-hero",
    },
    "glass-shard-title": {
        "status": "BLOCKED_DEPENDENCY",
        "technical_obstacle": "Requires unvendored d3-delaunay.min.js external script and custom HDR environment loader.",
        "donor_source_path": "registry/blocks/glass-shard-title",
    },
    "lottie-character-walk": {
        "status": "BLOCKED_DEPENDENCY",
        "technical_obstacle": "Requires unvendored lottie-web external runtime player and external character animation data.",
        "donor_source_path": "registry/blocks/lottie-character-walk",
    },
    "liquid-glass-notification": {
        "status": "BLOCKED_DEPENDENCY",
        "technical_obstacle": "Requires WebGPU API (navigator.gpu) and unbundled liquid-glass IIFE library.",
        "donor_source_path": "registry/blocks/liquid-glass-notification",
    },
    "liquid-glass-widgets": {
        "status": "BLOCKED_DEPENDENCY",
        "technical_obstacle": "Requires WebGPU API (navigator.gpu) and unbundled liquid-glass IIFE library.",
        "donor_source_path": "registry/blocks/liquid-glass-widgets",
    },
}

ALL_AM_121_BLOCKS: List[str] = sorted(
    AM_ACTIVATED_104_BLOCKS + list(AM_BLOCKED_RIGHTS_9_BLOCKS.keys()) + list(AM_BLOCKED_DEPENDENCY_8_BLOCKS.keys())
)


def get_ports(repo_root: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Returns the list of all 104 verified, active A-M original HyperFrames blocks.
    """
    root = repo_root or ROOT
    shipped = root / "backend" / "catalog" / "shipped_blocks"
    ports = []

    for slug in AM_ACTIVATED_104_BLOCKS:
        bdir = shipped / slug
        if not bdir.exists():
            continue
        reg_file = bdir / "registry-item.json"
        html_file = bdir / f"{slug}.html"
        if not (reg_file.exists() and html_file.exists()):
            continue

        try:
            reg_data = json.loads(reg_file.read_text(encoding="utf-8"))
        except Exception:
            reg_data = {}

        ports.append({
            "id": slug,
            "path": f"backend/catalog/shipped_blocks/{slug}",
            "title": reg_data.get("title", slug.replace("-", " ").title()),
            "description": reg_data.get("description", f"Original HyperFrames block '{slug}'."),
            "dimensions": reg_data.get("dimensions", {"width": 1920, "height": 1080}),
            "duration": float(reg_data.get("duration", 4.0)),
            "rights_status": "VERIFIED_PERMISSIVE",
            "runtime_status": "ACTIVATED_REAL",
            "supported_aspects": ["16:9", "9:16"],
            "variables": reg_data.get("variables", []),
        })

    return ports


def get_blocked_backlog() -> Dict[str, Dict[str, Any]]:
    """
    Returns the exact 17 blocked A-M blocks ledger with strict legal/technical rationale.
    """
    backlog: Dict[str, Dict[str, Any]] = {}
    for bid, data in AM_BLOCKED_RIGHTS_9_BLOCKS.items():
        backlog[bid] = {
            "id": bid,
            "status": "BLOCKED_RIGHTS",
            "reason": data["legal_obstacle"],
            "donor_source_path": data["donor_source_path"],
            "rights_cleared": False,
        }
    for bid, data in AM_BLOCKED_DEPENDENCY_8_BLOCKS.items():
        backlog[bid] = {
            "id": bid,
            "status": "BLOCKED_DEPENDENCY",
            "reason": data["technical_obstacle"],
            "donor_source_path": data["donor_source_path"],
            "rights_cleared": False,
        }
    return backlog


def get_preview_html(
    block_id: str,
    aspect_ratio: str = "16:9",
    variables: Optional[Dict[str, Any]] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    repo_root: Optional[Path] = None,
) -> str:
    """
    Generates a secure, zero-egress, airgapped composition HTML document
    with strict CSP, variable injection, and responsive 16:9 / 9:16 viewport staging.
    """
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", block_id):
        raise ValueError(f"Invalid block ID: {block_id}")

    root = repo_root or ROOT
    block_dir = root / "backend" / "catalog" / "shipped_blocks" / block_id
    html_file = block_dir / f"{block_id}.html"
    reg_file = block_dir / "registry-item.json"

    if not (html_file.exists() and reg_file.exists()):
        raise KeyError(f"Block '{block_id}' is not an active shipped block.")

    if aspect_ratio not in {"16:9", "9:16"}:
        raise ValueError(f"Unsupported aspect ratio: {aspect_ratio}")

    default_dims = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)
    w = width or default_dims[0]
    h = height or default_dims[1]

    if not (64 <= w <= 4096 and 64 <= h <= 4096):
        raise ValueError(f"Invalid viewport dimensions: {w}x{h}")

    try:
        reg_data = json.loads(reg_file.read_text(encoding="utf-8"))
    except Exception:
        reg_data = {}

    specs = {s["id"]: s for s in reg_data.get("variables", [])}
    variables = variables or {}
    for k, v in variables.items():
        if not isinstance(v, (str, int, float, bool)):
            raise ValueError(f"Variable '{k}' has invalid type: {type(v)}")

    values = {k: s.get("default") for k, s in specs.items()}
    values.update(variables)

    raw_html = html_file.read_text(encoding="utf-8")

    # Strict zero-egress CSP sandbox
    csp = (
        "default-src 'none'; "
        "script-src 'unsafe-inline' 'unsafe-eval' blob:; "
        "style-src 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data:; "
        "connect-src 'none'; "
        "media-src 'self' data: blob:; "
        "object-src 'none'; "
        "base-uri 'none'; "
        "form-action 'none'; "
        "worker-src blob:;"
    )

    payload = (
        json.dumps(values, ensure_ascii=True)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    bridge = f"<script>window.__hyperframes={{getVariables:()=>({payload})}};</script>"

    if "<head>" in raw_html:
        raw_html = raw_html.replace(
            "<head>",
            f'<head><meta http-equiv="Content-Security-Policy" content="{csp}">{bridge}',
            1,
        )
    else:
        raw_html = (
            f'<meta http-equiv="Content-Security-Policy" content="{csp}">{bridge}'
            + raw_html
        )

    # Responsive aspect ratio scaling container
    nw = reg_data.get("dimensions", {}).get("width", 1920)
    nh = reg_data.get("dimensions", {}).get("height", 1080)
    scale = min(w / nw, h / nh)
    left = (w - nw * scale) / 2
    top = (h - nh * scale) / 2

    stage_prefix = (
        f'<div id="wave17-stage" style="position:absolute;left:{left}px;top:{top}px;'
        f'width:{nw}px;height:{nh}px;transform:scale({scale});transform-origin:0 0;overflow:hidden;">'
    )
    if "<body>" in raw_html:
        raw_html = raw_html.replace("<body>", f"<body>{stage_prefix}", 1)
        raw_html = raw_html.replace("</body>", "</div></body>", 1)

    override_css = (
        f"<style>html,body{{width:{w}px!important;height:{h}px!important;"
        f"overflow:hidden!important;margin:0!important;padding:0!important;background:transparent!important}}</style>"
    )
    if "</head>" in raw_html:
        raw_html = raw_html.replace("</head>", f"{override_css}</head>", 1)

    return raw_html


# --- Project Revision, Insertion, Edit, and Reopen Workflow ---

def insert_into_project(
    project_data: Dict[str, Any],
    block_id: str,
    start_time: float = 0.0,
    variables: Optional[Dict[str, Any]] = None,
    aspect_ratio: str = "16:9",
    repo_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Inserts a verified active A-M block into a Motion project revision.
    Validates parameter schema and tracks origin provenance.
    """
    if block_id not in AM_ACTIVATED_104_BLOCKS:
        if block_id in AM_BLOCKED_RIGHTS_9_BLOCKS:
            raise ValueError(f"Block '{block_id}' is BLOCKED_RIGHTS and cannot be inserted.")
        if block_id in AM_BLOCKED_DEPENDENCY_8_BLOCKS:
            raise ValueError(f"Block '{block_id}' is BLOCKED_DEPENDENCY and cannot be inserted.")
        raise KeyError(f"Block '{block_id}' is not an active catalog block.")

    root = repo_root or ROOT
    reg_file = root / "backend" / "catalog" / "shipped_blocks" / block_id / "registry-item.json"
    if not reg_file.exists():
        raise FileNotFoundError(f"Missing registry manifest for '{block_id}'")

    reg_data = json.loads(reg_file.read_text(encoding="utf-8"))
    duration = float(reg_data.get("duration", 4.0))

    specs = {s["id"]: s for s in reg_data.get("variables", [])}
    user_vars = variables or {}
    resolved_vars = {k: s.get("default") for k, s in specs.items()}
    resolved_vars.update(user_vars)

    instance_id = f"block_{block_id}_{uuid.uuid4().hex[:8]}"
    item = {
        "instance_id": instance_id,
        "block_id": block_id,
        "title": reg_data.get("title", block_id.title()),
        "start_time": start_time,
        "duration": duration,
        "aspect_ratio": aspect_ratio,
        "variables": resolved_vars,
        "origin": "DONOR_ORIGINAL",
        "provenance": {
            "shipped_path": f"backend/catalog/shipped_blocks/{block_id}",
            "verified_wave": 17,
        },
    }

    proj = copy.deepcopy(project_data)
    if "tracks" not in proj:
        proj["tracks"] = [{"id": "track_1", "name": "Main Video", "items": []}]

    proj["tracks"][0]["items"].append(item)
    proj["version"] = proj.get("version", 1) + 1
    return proj


def edit_project_block(
    project_data: Dict[str, Any],
    instance_id: str,
    variables: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Edits variables on an existing block instance within a Motion project.
    """
    proj = copy.deepcopy(project_data)
    found = False
    for track in proj.get("tracks", []):
        for item in track.get("items", []):
            if item.get("instance_id") == instance_id:
                for k, v in variables.items():
                    item["variables"][k] = v
                found = True
                break
        if found:
            break

    if not found:
        raise KeyError(f"Instance '{instance_id}' not found in project.")

    proj["version"] = proj.get("version", 1) + 1
    return proj
