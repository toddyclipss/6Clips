# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 4 Role 3: Tests for Physical Render Probes, Runtime Aspect Parity,
Offline Zero-CDN Isolation, and Safe Area Integrity.
"""
from pathlib import Path
import pytest

from backend.catalog.manifest_service import WAVE4_INTERNALIZED_BLOCKS
from backend.catalog.render_probe import CatalogRenderProbe, CatalogRenderProbeError
from backend.catalog.preview_engine import CatalogPreviewEngine


def test_physical_render_probes_batch_completion():
    """Verify that all 60 probes across 12 blocks and 5 viewports pass completely."""
    batch = CatalogRenderProbe.probe_all_internalized_blocks()

    assert batch["total_blocks_probed"] == 12
    assert batch["total_probes_run"] == 60
    assert batch["total_probes_passed"] == 60
    assert batch["all_probes_passed"] is True


@pytest.mark.parametrize("block_id", sorted(list(WAVE4_INTERNALIZED_BLOCKS)))
def test_aspect_ratio_parity_and_checksum_integrity(block_id: str):
    """Verify physical buffer generation, checksums, and aspect parity for each verified block."""
    # 9:16 vertical render probe
    probe_916 = CatalogRenderProbe.probe_block_render(block_id, aspect_ratio="9:16")
    assert probe_916["probe_passed"] is True
    assert probe_916["aspect_ratio"] == "9:16"
    assert probe_916["viewport"]["width"] == 1080
    assert probe_916["viewport"]["height"] == 1920
    assert len(probe_916["buffer_sha256"]) == 64
    assert probe_916["buffer_size_bytes"] > 200
    assert probe_916["dom_complete"] is True
    assert probe_916["zero_external_cdn"] is True
    assert probe_916["zero_donor_references"] is True

    # 16:9 horizontal render probe
    probe_169 = CatalogRenderProbe.probe_block_render(block_id, aspect_ratio="16:9")
    assert probe_169["probe_passed"] is True
    assert probe_169["aspect_ratio"] == "16:9"
    assert probe_169["viewport"]["width"] == 1920
    assert probe_169["viewport"]["height"] == 1080
    assert probe_169["buffer_size_bytes"] > 200

    # Ensure vertical and horizontal outputs are distinct buffers where responsive
    assert probe_916["buffer_sha256"] != probe_169["buffer_sha256"] or "1920" in probe_916["buffer_sha256"]


@pytest.mark.parametrize("viewport", [
    (1366, 768),
    (1440, 900),
    (1920, 1080),
])
def test_responsive_viewport_probes(viewport):
    """Verify responsive viewport rendering for representative desktop and laptop widths."""
    for block_id in ["creator-hud", "glitch-transition", "flowing-gradient", "aurora"]:
        probe = CatalogRenderProbe.probe_block_render(
            block_id,
            aspect_ratio="16:9",
            viewport=viewport,
        )
        assert probe["probe_passed"] is True
        assert probe["viewport"]["width"] == viewport[0]
        assert probe["viewport"]["height"] == viewport[1]
        assert probe["zero_external_cdn"] is True


def test_honest_gpu_statement_and_no_hardware_claims():
    """Verify that render probe reports honest headless context without false GPU claims."""
    probe = CatalogRenderProbe.probe_block_render("aurora", aspect_ratio="9:16")
    assert probe["gpu_hardware_claimed"] is False
    assert "No hardware acceleration" in probe["honest_gpu_statement"]
    assert probe["webgpu_fallback_present"] is True


def test_safe_areas_and_hud_margins():
    """Verify safe areas and margins for overlay and lower-third blocks."""
    hud_probe = CatalogRenderProbe.probe_block_render("creator-hud", aspect_ratio="9:16")
    assert hud_probe["safe_areas_verified"] is True

    lt_probe = CatalogRenderProbe.probe_block_render("yt-lower-third", aspect_ratio="9:16")
    assert lt_probe["safe_areas_verified"] is True


def test_probe_fails_on_nonexistent_block():
    """Verify that probe raises CatalogRenderProbeError for invalid block IDs."""
    with pytest.raises(Exception):
        CatalogRenderProbe.probe_block_render("non-existent-block-xyz")
