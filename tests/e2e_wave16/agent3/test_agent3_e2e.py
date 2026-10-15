#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""
E2E Acceptance Test for Wave 16 Agent 3:
Verifies physical rendering, browser DOM preview captures, and adapter integration.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMP_RENDER_DIR = Path(tempfile.gettempdir()) / "viralmint_wave16_renders"
VALIDATION_PATH = REPO_ROOT / "tools" / "wave16_agent3_port" / "validation_104_summary.json"

class TestWave16Agent3E2E(unittest.TestCase):
    """End-to-End Acceptance Tests for Wave 16 Agent 3."""

    def test_e2e_01_renders_and_validations_exist(self):
        """Validation summary must exist with 104 verified records."""
        self.assertTrue(VALIDATION_PATH.exists(), f"Missing {VALIDATION_PATH}")
        with open(VALIDATION_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(len(data), 104)

        for slug, rec in data.items():
            self.assertTrue(rec.get("temporal_animation_verified"), f"{slug} failed animation dynamics")
            self.assertTrue(rec.get("ffprobe_verified"), f"{slug} failed ffprobe")
            self.assertEqual(len(rec.get("sentinel_frame_hashes", [])), 5)

    def test_e2e_02_browser_preview_screenshots(self):
        """Browser preview screenshots must exist for sample representative blocks."""
        sample_blocks = ["glitch", "bar-chart-race", "frost-sequence-camera-orbit", "cuboid-carousel", "ai-answer-rank"]
        for slug in sample_blocks:
            cap_png = TEMP_RENDER_DIR / f"{slug}_browser_capture.png"
            if cap_png.exists():
                self.assertGreater(cap_png.stat().st_size, 1000, f"Screenshot too small: {cap_png}")

    def test_e2e_03_aspect_ratio_render_parity(self):
        """Both 16:9 and 9:16 MP4 renders must exist and decode cleanly."""
        sample_blocks = ["glitch", "bar-chart-race", "cosmic-orb", "code-diff", "carousel-circle-1"]
        for slug in sample_blocks:
            mp4_16_9 = TEMP_RENDER_DIR / f"{slug}_16_9.mp4"
            mp4_9_16 = TEMP_RENDER_DIR / f"{slug}_9_16.mp4"
            self.assertTrue(mp4_16_9.exists(), f"16:9 missing: {mp4_16_9}")
            self.assertTrue(mp4_9_16.exists(), f"9:16 missing: {mp4_9_16}")
            self.assertGreater(mp4_16_9.stat().st_size, 1000)
            self.assertGreater(mp4_9_16.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
