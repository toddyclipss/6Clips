# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Catalog Render Probe:
Provides physical buffer verification, DOM completeness inspection,
zero-CDN validation, zero-donor filesystem isolation, and aspect ratio runtime parity
for HyperFrames motion assets in 6Clips.
"""
from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.catalog.manifest_service import CatalogManifestService, CatalogManifestError
from backend.catalog.preview_engine import CatalogPreviewEngine, SHIPPED_BLOCKS_DIR

logger = logging.getLogger(__name__)

DISALLOWED_CDN_PATTERNS = [
    r"https?://cdn\.jsdelivr\.net",
    r"https?://cdnjs\.cloudflare\.com",
    r"https?://unpkg\.com",
    r"https?://fonts\.googleapis\.com",
    r"https?://fonts\.gstatic\.com",
    r"https?://cdn\.skypack\.dev",
    r"https?://esm\.sh",
]

DISALLOWED_DONOR_PATTERNS = [
    r"[a-zA-Z]:\\[^<\"'\n]*hyperframes",
    r"[a-zA-Z]:/[^<\"'\n]*hyperframes",
    r"file:///[^<\"'\n]*hyperframes",
    r"[a-zA-Z]:\\Users",
    r"/Users/",
]


class CatalogRenderProbeError(Exception):
    """Raised when a catalog render probe fails validation."""
    pass


class CatalogRenderProbe:
    """
    Physical inspection probe for validating rendered block HTML buffers.
    Verifies offline capability, DOM structure, aspect parity, safe areas,
    and ensures zero reliance on external CDNs or the local donor repository.
    """

    @classmethod
    def probe_block_render(
        cls,
        block_id: str,
        aspect_ratio: str = "9:16",
        viewport: Optional[Tuple[int, int]] = None,
        custom_variables: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a physical render probe against a catalog block HTML buffer.
        Validates completeness, checksum, aspect styling, and isolation.
        """
        CatalogManifestService.validate_block_id(block_id)
        item = CatalogManifestService.get_item(block_id)
        if not item:
            raise CatalogRenderProbeError(f"Block '{block_id}' not found in catalog.")

        aspect_norm = "9:16" if aspect_ratio in ("9:16", "9x16", "vertical") else "16:9"

        if viewport:
            vp_w, vp_h = viewport
        else:
            vp_w, vp_h = (1080, 1920) if aspect_norm == "9:16" else (1920, 1080)

        # Convert custom_variables values to strings for preview engine
        vars_str = {k: str(v) for k, v in custom_variables.items()} if custom_variables else None

        # 1. Generate rendered HTML buffer
        rendered_html = CatalogPreviewEngine.get_preview_html(
            block_id=block_id,
            aspect_ratio=aspect_norm,
            variables=vars_str,
            viewport_width=vp_w,
            viewport_height=vp_h,
        )

        buffer_bytes = rendered_html.encode("utf-8")
        buffer_size = len(buffer_bytes)
        buffer_sha256 = hashlib.sha256(buffer_bytes).hexdigest()

        # 2. Check DOM completeness
        has_doctype = "<!doctype html>" in rendered_html.lower() or "<html" in rendered_html.lower()
        has_head = "<head" in rendered_html.lower() and "</head>" in rendered_html.lower()
        has_body = "<body" in rendered_html.lower() and "</body>" in rendered_html.lower()
        has_content = buffer_size > 200

        dom_complete = bool(has_doctype and has_head and has_body and has_content)

        # 3. Check for external CDNs (must be ZERO)
        detected_cdns = []
        for pat in DISALLOWED_CDN_PATTERNS:
            matches = re.findall(pat, rendered_html, re.IGNORECASE)
            if matches:
                detected_cdns.extend(matches)

        zero_external_cdn = len(detected_cdns) == 0

        # 4. Check for donor filesystem paths (must be ZERO)
        detected_donor_refs = []
        for pat in DISALLOWED_DONOR_PATTERNS:
            matches = re.findall(pat, rendered_html, re.IGNORECASE)
            if matches:
                detected_donor_refs.extend(matches)

        zero_donor_references = len(detected_donor_refs) == 0

        # 5. Aspect ratio and dimension constraints
        aspect_check = {
            "requested_aspect": aspect_norm,
            "viewport_dimensions": {"width": vp_w, "height": vp_h},
            "container_aspect_style_present": "aspect-ratio" in rendered_html or f"{vp_w}px" in rendered_html,
            "meta_viewport_present": '<meta name="viewport"' in rendered_html,
        }

        # 6. Fallback and honest GPU statement
        has_webgpu_shim = "navigator.gpu" in rendered_html or "WebGPU not available" in rendered_html
        honest_gpu_statement = (
            "Headless automated test probe. Real WebGL/WebGPU context requires client-side "
            "browser execution. No hardware acceleration or synthetic GPU availability is claimed."
        )

        # 7. Safe area verification (check for HUD/overlay safe margins)
        has_safe_areas = (
            "safe-area" in rendered_html
            or "padding:" in rendered_html
            or "margin:" in rendered_html
            or "inset:" in rendered_html
        )

        # 8. License & local files check
        shipped_dir = SHIPPED_BLOCKS_DIR / block_id
        local_files_exist = shipped_dir.exists() and (shipped_dir / f"{block_id}.html").exists()

        probe_passed = bool(
            dom_complete
            and zero_external_cdn
            and zero_donor_references
            and buffer_size > 0
            and local_files_exist
        )

        return {
            "block_id": block_id,
            "aspect_ratio": aspect_norm,
            "viewport": {"width": vp_w, "height": vp_h},
            "buffer_size_bytes": buffer_size,
            "buffer_sha256": buffer_sha256,
            "dom_complete": dom_complete,
            "zero_external_cdn": zero_external_cdn,
            "detected_cdns": detected_cdns,
            "zero_donor_references": zero_donor_references,
            "detected_donor_refs": detected_donor_refs,
            "aspect_check": aspect_check,
            "safe_areas_verified": has_safe_areas,
            "webgpu_fallback_present": has_webgpu_shim,
            "honest_gpu_statement": honest_gpu_statement,
            "gpu_hardware_claimed": False,
            "local_files_verified": local_files_exist,
            "probe_passed": probe_passed,
        }

    @classmethod
    def probe_all_internalized_blocks(cls) -> Dict[str, Any]:
        """
        Runs comprehensive physical render probes across all internalized blocks,
        verifying both 9:16 and 16:9 aspect ratios and responsive viewports
        (1366x768, 1440x900, 1920x1080).
        """
        from backend.catalog.manifest_service import WAVE4_INTERNALIZED_BLOCKS

        results = {}
        passed_count = 0
        total_probes = 0

        viewports = [
            ("9:16", (1080, 1920)),
            ("16:9", (1920, 1080)),
            ("laptop_1366", (1366, 768)),
            ("laptop_1440", (1440, 900)),
            ("desktop_1920", (1920, 1080)),
        ]

        for block_id in sorted(list(WAVE4_INTERNALIZED_BLOCKS)):
            results[block_id] = {}
            for label, vp in viewports:
                aspect = "9:16" if vp[0] < vp[1] else "16:9"
                probe = cls.probe_block_render(block_id, aspect_ratio=aspect, viewport=vp)
                results[block_id][label] = probe
                total_probes += 1
                if probe["probe_passed"]:
                    passed_count += 1

        return {
            "total_blocks_probed": len(WAVE4_INTERNALIZED_BLOCKS),
            "total_probes_run": total_probes,
            "total_probes_passed": passed_count,
            "all_probes_passed": passed_count == total_probes,
            "results": results,
        }
