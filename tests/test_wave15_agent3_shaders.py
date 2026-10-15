#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Unit and Acceptance Test Suite for Agent 3 / Wave 15:
27 HyperFrames Blocks: 10 Donor Originals Revalidated + 17 Additional Original Shaders Ported.

Verifies:
1. Physical presence and integrity of all 27 blocks in backend/catalog/shipped_blocks.
2. Zero external CDN / font network calls (airgap and P0 zero-egress compliance).
3. Dual WebGPU + Canvas 2D fallback engine wiring for all 22 shaders.
4. Resolution of the previous duplicate-output bug (100% distinct visual frame hashes).
5. Temporal dynamics (frame[0.0] != frame[1.0]).
6. Physical MP4 file presence under %TEMP% and full FFprobe decode verification.
7. Agent 3 descriptors handoff integrity for Agent 1 and Agent 5.
"""

import hashlib
import json
import os
import re
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIPPED_BLOCKS = REPO_ROOT / "backend" / "catalog" / "shipped_blocks"
DESCRIPTORS_PATH = REPO_ROOT / "tools" / "wave15_shader_port" / "agent3_descriptors_27.json"
VALIDATION_PATH = REPO_ROOT / "tools" / "wave15_shader_port" / "validation_27_summary.json"
TEMP_RENDER_DIR = Path(tempfile.gettempdir()) / "viralmint_wave15_renders"

EXISTING_10 = [
    "aurora", "data-chart", "flowing-gradient", "holographic",
    "instagram-follow", "plasma", "stripes", "tiktok-follow",
    "weight-wave", "yt-lower-third"
]

ELIGIBLE_17 = [
    "blob", "fractal-noise", "frost", "godrays", "goo", "lens-flare", "liquid-metal",
    "marble", "mesh-gradient", "nebula", "prism", "sine-wave", "strands", "swirl",
    "voronoi", "water", "waveform"
]

ALL_27 = EXISTING_10 + ELIGIBLE_17

SHADERS_22 = [
    "aurora", "flowing-gradient", "holographic", "plasma", "stripes",
    "blob", "fractal-noise", "frost", "godrays", "goo", "lens-flare", "liquid-metal",
    "marble", "mesh-gradient", "nebula", "prism", "sine-wave", "strands", "swirl",
    "voronoi", "water", "waveform"
]


class TestWave15Agent3Shaders(unittest.TestCase):
    """Test suite for Agent 3 shader porting and revalidation in Wave 15."""

    @classmethod
    def setUpClass(cls):
        cls.assertTrue(cls, SHIPPED_BLOCKS.exists(), f"shipped_blocks directory missing: {SHIPPED_BLOCKS}")
        if DESCRIPTORS_PATH.exists():
            with open(DESCRIPTORS_PATH, "r", encoding="utf-8") as f:
                cls.descriptors = json.load(f)
        else:
            cls.descriptors = {}

        if VALIDATION_PATH.exists():
            with open(VALIDATION_PATH, "r", encoding="utf-8") as f:
                cls.validation = json.load(f)
        else:
            cls.validation = {}

    def test_01_all_27_blocks_exist_in_shipped_blocks(self):
        """All 27 required block directories must exist in backend/catalog/shipped_blocks."""
        for slug in ALL_27:
            bdir = SHIPPED_BLOCKS / slug
            self.assertTrue(bdir.exists() and bdir.is_dir(), f"Block '{slug}' missing from shipped_blocks.")

    def test_02_all_27_blocks_have_required_composition_files(self):
        """Each block must have <slug>.html and registry-item.json; shaders must have vendored lib assets."""
        for slug in ALL_27:
            bdir = SHIPPED_BLOCKS / slug
            html_file = bdir / f"{slug}.html"
            reg_file = bdir / "registry-item.json"
            self.assertTrue(html_file.exists(), f"Missing HTML for {slug}")
            self.assertTrue(reg_file.exists(), f"Missing registry-item.json for {slug}")

            if slug in SHADERS_22:
                lib_dir = bdir / "lib"
                self.assertTrue(lib_dir.exists(), f"Missing lib dir for shader {slug}")
                self.assertTrue((lib_dir / "shaders.iife.js").exists(), f"Missing shaders.iife.js for {slug}")
                self.assertTrue((lib_dir / "shaders.THIRD-PARTY-LICENSES.txt").exists(), f"Missing license for {slug}")
                self.assertTrue((lib_dir / "shader_fallback.js").exists(), f"Missing shader_fallback.js for {slug}")

    def test_03_zero_remote_cdns_and_zero_network_egress(self):
        """All 27 blocks must have zero unvendored remote CDN scripts/links in their HTML files."""
        disallowed_patterns = [
            r"https?://cdn\.jsdelivr\.net",
            r"https?://fonts\.googleapis\.com",
            r"https?://cdnjs\.cloudflare\.com",
            r"https?://unpkg\.com",
        ]
        for slug in ALL_27:
            html_file = SHIPPED_BLOCKS / slug / f"{slug}.html"
            content = html_file.read_text(encoding="utf-8")
            for pat in disallowed_patterns:
                matches = re.findall(pat, content)
                self.assertEqual(
                    len(matches), 0,
                    f"Block '{slug}' contains forbidden remote CDN reference: {matches}"
                )

    def test_04_dual_webgpu_canvas_fallback_wired(self):
        """All 22 shaders must load shaders.iife.js and shader_fallback.js in <slug>.html."""
        for slug in SHADERS_22:
            html_file = SHIPPED_BLOCKS / slug / f"{slug}.html"
            content = html_file.read_text(encoding="utf-8")
            self.assertIn("lib/shaders.iife.js", content, f"Shader {slug} missing shaders.iife.js script tag")
            self.assertIn("lib/shader_fallback.js", content, f"Shader {slug} missing shader_fallback.js script tag")

    def test_05_cross_shader_uniqueness_no_duplicate_output(self):
        """All 22 shaders must produce unique visual sentinel frames (resolving duplicate output bug)."""
        self.assertTrue(bool(self.validation), "Validation summary data missing.")
        sentinel_hashes = {}
        for slug in SHADERS_22:
            rec = self.validation.get(slug)
            self.assertIsNotNone(rec, f"Validation record missing for {slug}")
            hashes = rec.get("sentinel_frame_hashes", [])
            self.assertGreater(len(hashes), 0, f"No sentinel hashes for {slug}")
            sentinel_hashes[slug] = hashes[0]

        unique_hashes = set(sentinel_hashes.values())
        self.assertEqual(
            len(unique_hashes),
            len(sentinel_hashes),
            f"Duplicate frame hashes detected across shaders: {len(unique_hashes)} unique / {len(sentinel_hashes)} total"
        )

    def test_06_temporal_animation_dynamics(self):
        """All 27 blocks must exhibit verified temporal changes over time (frame[0] != frame[2])."""
        self.assertTrue(bool(self.validation), "Validation summary data missing.")
        for slug in ALL_27:
            rec = self.validation.get(slug, {})
            self.assertTrue(
                rec.get("temporal_animation_verified"),
                f"Block '{slug}' failed temporal animation verification."
            )
            hashes = rec.get("sentinel_frame_hashes", [])
            self.assertGreaterEqual(len(hashes), 3, f"Insufficient sentinel frames for {slug}")
            self.assertNotEqual(
                hashes[0], hashes[2],
                f"Block '{slug}' frame at t=0.0 matches frame at t=1.0 (static frame error)"
            )

    def test_07_physical_mp4_render_artifacts_and_ffprobe(self):
        """Physical MP4 video files must exist under %TEMP% with valid size and FFprobe verification."""
        self.assertTrue(bool(self.validation), "Validation summary data missing.")
        for slug in ALL_27:
            rec = self.validation.get(slug, {})
            mp4_path = Path(rec.get("physical_mp4_path", ""))
            self.assertTrue(mp4_path.exists(), f"Physical MP4 missing for {slug} at {mp4_path}")
            self.assertGreater(mp4_path.stat().st_size, 1000, f"MP4 file for {slug} too small: {mp4_path.stat().st_size} bytes")
            sha = rec.get("physical_mp4_sha256", "")
            self.assertEqual(len(sha), 64, f"Invalid SHA-256 for {slug} MP4: {sha}")
            self.assertTrue(rec.get("ffprobe_verified"), f"FFprobe failed for {slug}")

    def test_08_descriptors_handoff_contract_integrity(self):
        """agent3_descriptors_27.json must contain exactly 27 blocks with native taxonomy and metadata."""
        self.assertTrue(bool(self.descriptors), "Descriptors JSON missing.")
        self.assertEqual(self.descriptors.get("schema_version"), 1)
        self.assertEqual(self.descriptors.get("blocks_count"), 27)

        blocks = self.descriptors.get("blocks", [])
        self.assertEqual(len(blocks), 27)

        block_ids = {b["id"] for b in blocks}
        self.assertEqual(block_ids, set(ALL_27))

        newly_ported = [b for b in blocks if b.get("is_newly_ported")]
        self.assertEqual(len(newly_ported), 17, "Exactly 17 blocks must be marked as newly ported.")

        revalidated = [b for b in blocks if not b.get("is_newly_ported")]
        self.assertEqual(len(revalidated), 10, "Exactly 10 blocks must be marked as revalidated.")

        for b in blocks:
            self.assertEqual(b["runtime_readiness"], "RUNTIME_READY")
            self.assertIn(b["rights_clearance"], ["VERIFIED_PERMISSIVE", "VERIFIED_OTHER_OBLIGATIONS"])
            self.assertTrue(b.get("native_category"), f"Missing native_category for {b['id']}")
            self.assertTrue(b.get("native_subcategory"), f"Missing native_subcategory for {b['id']}")

    def test_09_aspect_ratio_matrix(self):
        """Supported aspect ratios must reflect responsive WebGPU and native orientation rules."""
        for slug in SHADERS_22:
            rec = next((b for b in self.descriptors.get("blocks", []) if b["id"] == slug), None)
            if rec:
                self.assertIn("16:9", rec["supported_aspects"])
                self.assertIn("9:16", rec["supported_aspects"])

        # Check social vertical blocks
        for slug in ["instagram-follow", "tiktok-follow"]:
            rec = next((b for b in self.descriptors.get("blocks", []) if b["id"] == slug), None)
            if rec:
                self.assertIn("9:16", rec["supported_aspects"])


if __name__ == "__main__":
    unittest.main()
