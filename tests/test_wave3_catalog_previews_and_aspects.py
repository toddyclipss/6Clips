# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 3 Role 3: Tests for 9:16 and 16:9 preview rendering, responsive viewports,
WebGPU fallback shim injection, contrast fixes, safe areas, and poster cache invalidation.
"""
from pathlib import Path
import pytest

from backend.catalog.manifest_service import CORE_INTERNALIZED_BLOCKS
from backend.catalog.preview_engine import CatalogPreviewEngine
from backend.catalog.poster_service import CatalogPosterService


def test_preview_aspect_parity_for_all_shipped_blocks():
    """Verify both 9:16 vertical and 16:9 horizontal preview HTML render for all 6 shipped blocks."""
    for block_id in CORE_INTERNALIZED_BLOCKS:
        # 9:16 Vertical
        html_9_16 = CatalogPreviewEngine.get_preview_html(block_id, aspect_ratio="9:16")
        assert "1080px" in html_9_16 or "1080 / 1920" in html_9_16, f"9:16 framing missing for {block_id}"
        assert "viralmint-stage-viewport" in html_9_16

        # 16:9 Landscape
        html_16_9 = CatalogPreviewEngine.get_preview_html(block_id, aspect_ratio="16:9")
        assert "1920px" in html_16_9 or "1920 / 1080" in html_16_9, f"16:9 framing missing for {block_id}"
        assert "viralmint-stage-viewport" in html_16_9


def test_responsive_viewport_renders():
    """Requirement 6: Inspect authentic block renders at 1366x768, 1440x900, 1920x1080."""
    viewports = [
        (1366, 768),
        (1440, 900),
        (1920, 1080),
        (1080, 1920),
    ]
    for w, h in viewports:
        for block_id in CORE_INTERNALIZED_BLOCKS:
            html = CatalogPreviewEngine.get_preview_html(
                block_id,
                viewport_width=w,
                viewport_height=h,
            )
            assert f"{w}px" in html, f"Viewport width {w}px not injected for {block_id}"
            assert f"{h}px" in html, f"Viewport height {h}px not injected for {block_id}"


def test_webgpu_shader_fallback_injection():
    """Requirement 4: Verify WebGPU shim and fallback flag injection in preview HTML."""
    for block_id in CORE_INTERNALIZED_BLOCKS:
        html = CatalogPreviewEngine.get_preview_html(block_id)
        assert "__HYPERFRAMES_FALLBACK_SHADER__" in html, f"WebGPU shim missing in {block_id}"
        assert "navigator.gpu" in html


def test_contrast_fixes_applied_to_target_blocks():
    """Requirement 4: Verify high-contrast styles applied to yt-lower-third and data-chart."""
    # yt-lower-third contrast fix
    yt_html = CatalogPreviewEngine.get_preview_html("yt-lower-third")
    assert "border-left: 6px solid #ff0000" in yt_html
    assert "lower-third-container" in yt_html

    # data-chart contrast fix
    chart_html = CatalogPreviewEngine.get_preview_html("data-chart")
    assert "chart-bar" in chart_html
    assert "drop-shadow" in chart_html


def test_truthful_unverified_fallback_card():
    """Requirement 3: Verify unbundled/unverified blocks render honest fallback cards."""
    # camcorder-hud is unverified (depends on unpinned cdn.jsdelivr.net GSAP)
    html = CatalogPreviewEngine.get_preview_html("camcorder-hud")
    assert "UNVERIFIED — PENDING INTERNALIZATION" in html
    assert "offline dependency vendoring" in html
    assert "Camcorder HUD" in html


def test_poster_cache_generation_and_invalidation():
    """Requirement 3: Verify poster cache creation, variable fingerprinting, and invalidation."""
    block_id = "weight-wave"

    # Generate initial poster
    poster_path = CatalogPosterService.get_poster_path(block_id, aspect_ratio="9:16")
    assert poster_path.is_file()
    assert poster_path.stat().st_size > 0

    # Variable fingerprint poster
    vars_sample = {"text": "Viral Mint", "weight": 700}
    vfp = CatalogPosterService.compute_variable_fingerprint(vars_sample)
    assert len(vfp) == 8

    vfp_poster = CatalogPosterService.get_poster_path(
        block_id,
        aspect_ratio="9:16",
        variable_fingerprint=vfp,
    )
    assert vfp_poster.is_file()
    assert vfp in vfp_poster.name

    # Invalidate cache
    deleted = CatalogPosterService.invalidate_block_poster(block_id)
    assert deleted >= 1
    assert not poster_path.exists()
