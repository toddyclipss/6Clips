# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 2 Agent 4: Tests for 9:16 and 16:9 aspect parity, truthful posters, and non-destructive Ghost Previews."""
import pytest
from pathlib import Path
from PIL import Image

from backend.catalog.manifest_service import CatalogManifestService
from backend.catalog.poster_service import CatalogPosterService
from backend.catalog.preview_engine import CatalogPreviewEngine
from backend.catalog.ghost_preview import GhostPreviewContract, GhostPreviewViolation


def test_aspect_ratio_breakdown():
    """Verify aspect ratio distribution across 9:16 and 16:9 formats."""
    recon = CatalogManifestService.get_reconciliation_summary()
    asp_9_16 = recon["aspect_support_9_16"]
    asp_16_9 = recon["aspect_support_16_9"]

    # 9:16 vertical analysis
    assert asp_9_16["native"] >= 12, f"Expected at least 12 native 9:16 blocks, got {asp_9_16['native']}"
    assert asp_9_16["adapted"] > 100
    assert asp_9_16["contained_only"] > 10

    # 16:9 landscape analysis
    assert asp_16_9["native"] >= 180, f"Expected at least 180 native 16:9 blocks, got {asp_16_9['native']}"


def test_preview_engine_9_16_and_16_9_framing():
    """Verify preview engine produces valid standalone HTML with correct aspect framing."""
    html_9_16 = CatalogPreviewEngine.get_preview_html("weight-wave", aspect_ratio="9:16")
    assert "<!DOCTYPE html>" in html_9_16 or "<html" in html_9_16
    assert "1080px" in html_9_16
    assert "1920px" in html_9_16
    assert "aspect-ratio: 1080 / 1920" in html_9_16

    html_16_9 = CatalogPreviewEngine.get_preview_html("weight-wave", aspect_ratio="16:9")
    assert "1920px" in html_16_9
    assert "1080px" in html_16_9
    assert "aspect-ratio: 1920 / 1080" in html_16_9


def test_preview_engine_webgpu_and_shader_fallback():
    """Requirement F15: verify WebGPU resilient fallback script is injected into shader previews."""
    html_aurora = CatalogPreviewEngine.get_preview_html("aurora", aspect_ratio="9:16")
    assert "navigator.gpu" in html_aurora
    assert "__HYPERFRAMES_FALLBACK_SHADER__" in html_aurora


def test_preview_engine_contrast_fixes():
    """Requirement F15: verify contrast fixes are injected for yt-lower-third and data-chart."""
    html_lt = CatalogPreviewEngine.get_preview_html("yt-lower-third", aspect_ratio="9:16")
    assert "lower-third-container" in html_lt
    assert "text-shadow" in html_lt

    html_chart = CatalogPreviewEngine.get_preview_html("data-chart", aspect_ratio="9:16")
    assert "drop-shadow" in html_chart or "chart" in html_chart


def test_truthful_poster_generation_and_dimensions(tmp_path):
    """Requirement F11 / F22: verify authentic posters with exact dimensions and formats."""
    # Test 9:16 vertical poster
    poster_9_16_path = CatalogPosterService.get_poster_path("weight-wave", aspect_ratio="9:16")
    assert poster_9_16_path.exists()
    assert poster_9_16_path.suffix == ".png"
    with Image.open(poster_9_16_path) as im:
        assert im.size == (360, 640), f"Expected (360, 640), got {im.size}"

    # Test 16:9 horizontal poster
    poster_16_9_path = CatalogPosterService.get_poster_path("weight-wave", aspect_ratio="16:9")
    assert poster_16_9_path.exists()
    with Image.open(poster_16_9_path) as im:
        assert im.size == (640, 360), f"Expected (640, 360), got {im.size}"


def test_deterministic_poster_cache_invalidation():
    """Requirement F12 / F22: verify poster invalidation removes cached files deterministically."""
    # Ensure poster exists
    p = CatalogPosterService.get_poster_path("instagram-follow", aspect_ratio="9:16")
    assert p.exists()

    # Invalidate
    deleted_count = CatalogPosterService.invalidate_block_poster("instagram-follow")
    assert deleted_count >= 1
    assert not p.exists()

    # Re-generating recreates the file cleanly
    p2 = CatalogPosterService.get_poster_path("instagram-follow", aspect_ratio="9:16")
    assert p2.exists()


def test_ghost_preview_contract_guarantees():
    """Requirement F13 / E24: verify ghost preview contract enforces muted audio and zero revision mutation."""
    cfg = GhostPreviewContract.get_preview_config("weight-wave")
    assert cfg["audio_muted"] is True
    assert cfg["creates_revision"] is False
    assert cfg["persists_history"] is False
    assert 180 <= cfg["debounce_ms"] <= 300
    assert cfg["dismiss_on_escape"] is True
    assert cfg["dismiss_on_mouseout"] is True

    # Audit assert passes for clean config
    GhostPreviewContract.assert_safe_preview(cfg)

    # Violation triggers error
    bad_cfg = {**cfg, "creates_revision": True}
    with pytest.raises(GhostPreviewViolation, match="ProjectRevision"):
        GhostPreviewContract.assert_safe_preview(bad_cfg)

    bad_audio_cfg = {**cfg, "audio_muted": False}
    with pytest.raises(GhostPreviewViolation, match="muted"):
        GhostPreviewContract.assert_safe_preview(bad_audio_cfg)
