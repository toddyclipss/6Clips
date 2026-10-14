# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Catalog Preview Engine: renders standalone HTML previews supporting 9:16 and 16:9 aspect ratios with shader and contrast fallbacks."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional

from backend.catalog.manifest_service import CatalogManifestService, CatalogManifestError

logger = logging.getLogger(__name__)

SHIPPED_BLOCKS_DIR = Path(__file__).parent / "shipped_blocks"
DONOR_BLOCKS_DIR = Path("C:/hyperframes_donor_placeholder")


class CatalogPreviewEngine:
    """Produces standalone HTML previews with aspect parity, WebGPU fallbacks, and contrast fixes."""

    @classmethod
    def get_preview_html(
        cls,
        block_id: str,
        version_hash: Optional[str] = None,
        aspect_ratio: str = "9:16",
        variables: Optional[Dict[str, str]] = None,
        viewport_width: Optional[int] = None,
        viewport_height: Optional[int] = None,
    ) -> str:
        """
        Generate standalone preview HTML for the requested catalog block.
        Aspect ratio: "9:16" (vertical short-form) or "16:9" (horizontal long-form).
        Supports custom viewport inspection (e.g. 1366x768, 1440x900, 1920x1080).
        """
        CatalogManifestService.validate_block_id(block_id)
        item = CatalogManifestService.get_item(block_id)
        if not item:
            raise CatalogManifestError(f"Block '{block_id}' not found in catalog.")

        aspect_norm = "9:16" if aspect_ratio in ("9:16", "9x16", "vertical") else "16:9"
        if viewport_width and viewport_height:
            target_w, target_h = int(viewport_width), int(viewport_height)
        else:
            target_w, target_h = (1080, 1920) if aspect_norm == "9:16" else (1920, 1080)

        # 1. Resolve source HTML strictly from vendored shipped_blocks
        source_html = cls._find_block_html(block_id)

        # 2. If source HTML not found, generate an authentic rendered preview card
        if not source_html:
            return cls._generate_fallback_preview_html(item, target_w, target_h, aspect_norm)

        # 3. Apply aspect framing, WebGPU shim, and contrast fixes
        transformed_html = cls._wrap_and_adapt_html(source_html, item, target_w, target_h, aspect_norm, variables)
        return transformed_html

    @classmethod
    def _find_block_html(cls, block_id: str) -> Optional[str]:
        """
        Locates the block HTML exclusively from locally vendored SHIPPED_BLOCKS_DIR.
        Strictly zero runtime dependency on the donor directory (GT-20, AC-5).
        """
        shipped = SHIPPED_BLOCKS_DIR / block_id
        if shipped.exists():
            for cand in [f"{block_id}.html", "index.html"]:
                p = shipped / cand
                if p.is_file():
                    try:
                        return p.read_text(encoding="utf-8")
                    except Exception as e:
                        logger.warning("Failed reading block html for %s: %s", block_id, e)
            # Any html file in shipped directory
            for p in shipped.glob("*.html"):
                try:
                    return p.read_text(encoding="utf-8")
                except Exception:
                    pass

        return None

    @classmethod
    def _wrap_and_adapt_html(
        cls,
        raw_html: str,
        item: dict,
        target_w: int,
        target_h: int,
        aspect_ratio: str,
        variables: Optional[Dict[str, str]] = None,
    ) -> str:
        native_aspect = item.get("native_aspect", "16:9")
        block_id = item.get("id", "")

        # WebGPU resilient fallback script injection
        webgpu_shim = """
        <script>
        // WebGPU / Shader fallback shim for headless / non-accelerated environments
        if (!navigator.gpu) {
            console.warn('[6Clips Catalog] WebGPU not available, enabling animated canvas/CSS fallback');
            window.__HYPERFRAMES_FALLBACK_SHADER__ = true;
        }
        </script>
        """

        # Contrast & overlay fix for yt-lower-third and data-chart (F15)
        contrast_fix = ""
        if block_id == "yt-lower-third":
            contrast_fix = """
            <style>
            .lower-third-container, [data-component="yt-lower-third"] {
                background: rgba(15, 23, 42, 0.92) !important;
                border-left: 6px solid #ff0000 !important;
                color: #ffffff !important;
                text-shadow: 0 2px 4px rgba(0,0,0,0.8) !important;
                padding: 12px 24px !important;
                border-radius: 8px !important;
            }
            .lower-third-title { font-weight: 800 !important; font-size: 28px !important; }
            .lower-third-subtitle { color: #e2e8f0 !important; font-size: 20px !important; }
            </style>
            """
        elif block_id == "data-chart":
            contrast_fix = """
            <style>
            .chart-bar, [data-chart-bar] {
                filter: drop-shadow(0 4px 6px rgba(0,0,0,0.5)) !important;
            }
            .chart-label, text.label {
                fill: #ffffff !important;
                font-weight: 700 !important;
                text-shadow: 0 1px 3px rgba(0,0,0,0.9) !important;
            }
            </style>
            """

        # CSS Aspect Ratio Wrapper
        # If block is 16:9 and target is 9:16: center and fit width cleanly
        # If block is 9:16 and target is 16:9: center and pillarbox cleanly
        is_transparent_overlay = block_id in ("yt-lower-third", "creator-hud", "glitch-transition", "instagram-follow", "tiktok-follow") or "overlay" in block_id
        stage_bg = "transparent" if is_transparent_overlay else "#000000"
        body_bg = "transparent" if is_transparent_overlay else "#090d16"

        wrapper_css = f"""
        <style>
        * {{ box-sizing: border-box; }}
        html, body {{
            margin: 0;
            padding: 0;
            width: 100%;
            height: 100%;
            overflow: hidden;
            background: {body_bg};
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }}
        #viralmint-stage-viewport {{
            position: relative;
            width: 100%;
            height: 100%;
            max-width: {target_w}px;
            max-height: {target_h}px;
            aspect-ratio: {target_w} / {target_h};
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
            background: {stage_bg};
        }}
        #viralmint-block-container {{
            position: absolute;
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        </style>
        """

        import json
        vars_script = ""
        page = raw_html

        if variables:
            # Replace {{key}} mustache placeholders
            for vk, vv in variables.items():
                page = page.replace(f"{{{{{vk}}}}}", str(vv))

            # Inject window.__VIRALMINT_VARIABLES__ script and dynamic variable DOM binder
            safe_json = json.dumps(variables)
            vars_script = f"""
            <script id="viralmint-runtime-variables">
            window.__VIRALMINT_VARIABLES__ = {safe_json};
            (function() {{
                function applyVars() {{
                    var v = window.__VIRALMINT_VARIABLES__;
                    if (!v) return;
                    if (v.channel_name || v.title) {{
                        var el = document.querySelector(".title, .lower-third-title, [data-variable='channel_name'], [data-variable='title']");
                        if (el) el.textContent = v.channel_name || v.title;
                    }}
                    if (v.subscribe_prompt || v.subtitle) {{
                        var sub = document.querySelector(".subtitle, .lower-third-subtitle, [data-variable='subscribe_prompt'], [data-variable='subtitle']");
                        if (sub) sub.textContent = v.subscribe_prompt || v.subtitle;
                    }}
                    if (v.creator_handle) {{
                        var h = document.querySelector(".creator-handle, [data-variable='creator_handle']");
                        if (h) h.textContent = v.creator_handle;
                    }}
                    if (v.metric_value) {{
                        var m = document.querySelector(".metric-value, [data-variable='metric_value']");
                        if (m) m.textContent = v.metric_value;
                    }}
                }}
                if (document.readyState === 'loading') {{
                    document.addEventListener('DOMContentLoaded', applyVars);
                }} else {{
                    applyVars();
                }}
            }})();
            </script>
            """

        base_tag = f'<base href="/api/catalog/blocks/{block_id}/">'
        if "</head>" in page:
            head_addon = f"{base_tag}{webgpu_shim}{contrast_fix}{wrapper_css}{vars_script}</head>"
            page = page.replace("</head>", head_addon)
        else:
            page = f"<head>{base_tag}{webgpu_shim}{contrast_fix}{wrapper_css}{vars_script}</head>{page}"

        return page

    @classmethod
    def _generate_fallback_preview_html(
        cls,
        item: dict,
        target_w: int,
        target_h: int,
        aspect_ratio: str,
    ) -> str:
        """Render a clean, animated standalone fallback card when local HTML is unbundled."""
        title = item.get("title", item.get("id"))
        cat = item.get("category", "motion")
        author = item.get("author", "HyperFrames")
        license_id = item.get("license", "Apache-2.0")
        dur = item.get("duration", 5.0)
        disp = item.get("disposition", "UNVERIFIED")
        status_label = "UNVERIFIED — PENDING INTERNALIZATION" if disp != "FIX" else "FIX REQUIRED"

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — Standalone Preview</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    background: #0a0e17;
    color: #f8fafc;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100vh;
    overflow: hidden;
}}
.stage {{
    width: 100vw;
    height: 100vh;
    max-width: {target_w}px;
    max-height: {target_h}px;
    aspect-ratio: {target_w} / {target_h};
    position: relative;
    background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 32px;
    text-align: center;
    overflow: hidden;
}}
.ambient-glow {{
    position: absolute;
    width: 400px;
    height: 400px;
    background: radial-gradient(circle, rgba(245,158,11,0.18) 0%, transparent 70%);
    border-radius: 50%;
    animation: pulse 4s ease-in-out infinite alternate;
}}
@keyframes pulse {{
    0% {{ transform: scale(0.8) translate(-20px, -20px); }}
    100% {{ transform: scale(1.2) translate(20px, 20px); }}
}}
.badge {{
    background: rgba(245, 158, 11, 0.15);
    border: 1px solid rgba(245, 158, 11, 0.5);
    color: #fcd34d;
    padding: 6px 14px;
    border-radius: 9999px;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 20px;
    z-index: 2;
}}
.title {{
    font-size: 32px;
    font-weight: 800;
    letter-spacing: -0.02em;
    margin-bottom: 12px;
    z-index: 2;
    background: linear-gradient(180deg, #ffffff 0%, #cbd5e1 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}}
.desc {{
    font-size: 13px;
    color: #94a3b8;
    max-width: 460px;
    line-height: 1.5;
    z-index: 2;
    margin-bottom: 16px;
}}
.meta {{
    font-size: 13px;
    color: #64748b;
    z-index: 2;
    margin-top: 4px;
}}
.aspect-tag {{
    margin-top: 20px;
    font-size: 12px;
    color: #64748b;
    border: 1px solid #334155;
    padding: 4px 10px;
    border-radius: 4px;
    z-index: 2;
}}
</style>
</head>
<body>
<div class="stage">
    <div class="ambient-glow"></div>
    <div class="badge">{status_label} · {cat}</div>
    <h1 class="title">{title}</h1>
    <p class="desc">This block requires offline dependency vendoring (GSAP/Three) and license clearance before runtime bundling. Only internalized blocks ship in production.</p>
    <p class="meta">{author} · {license_id} · {dur}s</p>
    <div class="aspect-tag">Aspect: {aspect_ratio} ({target_w}×{target_h})</div>
</div>
</body>
</html>
"""
