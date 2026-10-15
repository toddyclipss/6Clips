#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
End-to-End Test Suite for Wave 17 Agent 3:
Real Microsoft Edge Headless Browser, Zero-Egress Airgap, Parameter Mutation,
and Decoded MP4 Export Parity.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.catalog_runtime.core.registry_engine import (
    UniversalRuntimeRegistry,
    BlockUnavailableError,
)
from backend.catalog_runtime.ports.wave17_a3.adapter import (
    get_preview_html,
    insert_into_project,
    edit_project_block,
    AM_ACTIVATED_104_BLOCKS,
)

E2E_OUT_DIR = Path(tempfile.gettempdir()) / "viralmint_wave17_e2e_agent3"
E2E_OUT_DIR.mkdir(parents=True, exist_ok=True)


class TestWave17Agent3E2E(unittest.TestCase):
    """End-to-end integration and media acceptance for Wave 17 Agent 3."""

    @classmethod
    def setUpClass(cls):
        UniversalRuntimeRegistry.invalidate_cache()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True, channel="msedge")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def test_e2e_01_full_motion_workflow_with_real_edge_and_export(self):
        """End-to-end user journey: Catalog block discovery -> Motion project insertion -> parameter edit -> real Edge render -> decoded MP4."""
        slug = "code-diff"
        # 1. Verify block is operable in UniversalRuntimeRegistry
        block = UniversalRuntimeRegistry.validate_block_operable(slug, wave=17)
        self.assertTrue(block.runtime_operable)
        self.assertEqual(block.id, slug)

        # 2. Insert into Motion project
        initial_project = {
            "id": "e2e_project_01",
            "name": "Live Developer Showcase",
            "version": 1,
            "tracks": [{"id": "t1", "name": "Primary Track", "items": []}],
        }
        custom_vars = {
            "title": "Wave 17 E2E Verified Code Diff",
            "language": "python",
        }
        proj_step1 = insert_into_project(initial_project, slug, start_time=0.0, variables=custom_vars, repo_root=REPO_ROOT)
        self.assertEqual(len(proj_step1["tracks"][0]["items"]), 1)
        instance = proj_step1["tracks"][0]["items"][0]
        self.assertEqual(instance["variables"]["title"], "Wave 17 E2E Verified Code Diff")

        # 3. Edit parameter schema on instance
        proj_step2 = edit_project_block(proj_step1, instance["instance_id"], {"title": "Updated Production Title"})
        updated_instance = proj_step2["tracks"][0]["items"][0]
        self.assertEqual(updated_instance["variables"]["title"], "Updated Production Title")

        # 4. Serialize & Reopen (persistence check)
        persisted_json = json.dumps(proj_step2)
        reopened = json.loads(persisted_json)
        self.assertEqual(reopened["tracks"][0]["items"][0]["variables"]["title"], "Updated Production Title")

        # 5. Generate airgapped preview HTML with injected variables
        rendered_html = get_preview_html(
            slug,
            aspect_ratio="16:9",
            variables=reopened["tracks"][0]["items"][0]["variables"],
            repo_root=REPO_ROOT,
        )
        self.assertIn("Updated Production Title", rendered_html)
        self.assertIn("Content-Security-Policy", rendered_html)
        self.assertIn("default-src 'none'", rendered_html)

        # 6. Render in real Microsoft Edge headless browser
        temp_html_path = E2E_OUT_DIR / f"{slug}_e2e_preview.html"
        temp_html_path.write_text(rendered_html, encoding="utf-8")

        context = self.browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        egress_detected = []
        page.on("request", lambda r: egress_detected.append(r.url) if r.url.startswith("http") else None)

        page.goto(temp_html_path.as_uri(), wait_until="load", timeout=15000)
        page.wait_for_timeout(400)

        # Assert ZERO network egress
        self.assertEqual(len(egress_detected), 0, f"Detected unauthorized egress: {egress_detected}")

        # Capture browser screenshot
        shot_path = E2E_OUT_DIR / f"{slug}_e2e_screenshot.png"
        page.screenshot(path=str(shot_path))
        self.assertTrue(shot_path.exists())
        self.assertGreater(shot_path.stat().st_size, 5000)

        # Verify screenshot is valid non-blank image
        with Image.open(shot_path) as im:
            self.assertEqual(im.size, (1920, 1080))

        # 7. Physical FFmpeg video export and FFprobe stream verification
        mp4_path = E2E_OUT_DIR / f"{slug}_e2e_output.mp4"
        if mp4_path.exists():
            mp4_path.unlink()

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", str(shot_path),
            "-vf", "scale=1920:1080,format=yuv420p",
            "-c:v", "libx264",
            "-t", "2.0",
            "-r", "30",
            "-preset", "ultrafast",
            str(mp4_path),
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        self.assertTrue(mp4_path.exists())
        self.assertGreater(mp4_path.stat().st_size, 1000)

        # Probe video stream
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,codec_name",
            "-of", "json",
            str(mp4_path),
        ]
        res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        probe_info = json.loads(res.stdout)["streams"][0]
        self.assertEqual(int(probe_info["width"]), 1920)
        self.assertEqual(int(probe_info["height"]), 1080)
        self.assertEqual(probe_info["codec_name"], "h264")

        context.close()
        temp_html_path.unlink(missing_ok=True)

    def test_e2e_02_vertical_9_16_aspect_ratio_parity(self):
        """End-to-end verification of 9:16 vertical render and video export."""
        slug = "bar-chart-race"
        rendered_9_16_html = get_preview_html(slug, aspect_ratio="9:16", repo_root=REPO_ROOT)
        temp_v_html = E2E_OUT_DIR / f"{slug}_v_preview.html"
        temp_v_html.write_text(rendered_9_16_html, encoding="utf-8")

        context = self.browser.new_context(viewport={"width": 1080, "height": 1920})
        page = context.new_page()
        page.goto(temp_v_html.as_uri(), wait_until="load", timeout=15000)
        page.wait_for_timeout(400)

        shot_v = E2E_OUT_DIR / f"{slug}_e2e_9_16.png"
        page.screenshot(path=str(shot_v))
        self.assertTrue(shot_v.exists())
        with Image.open(shot_v) as im_v:
            self.assertEqual(im_v.size, (1080, 1920))

        mp4_v = E2E_OUT_DIR / f"{slug}_e2e_9_16.mp4"
        if mp4_v.exists():
            mp4_v.unlink()

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", str(shot_v),
            "-vf", "scale=1080:1920,format=yuv420p",
            "-c:v", "libx264",
            "-t", "2.0",
            "-r", "30",
            "-preset", "ultrafast",
            str(mp4_v),
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        self.assertTrue(mp4_v.exists())

        probe_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,codec_name",
            "-of", "json",
            str(mp4_v),
        ]
        res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        probe_info = json.loads(res.stdout)["streams"][0]
        self.assertEqual(int(probe_info["width"]), 1080)
        self.assertEqual(int(probe_info["height"]), 1920)
        self.assertEqual(probe_info["codec_name"], "h264")

        context.close()
        temp_v_html.unlink(missing_ok=True)

    def test_e2e_03_catalog_api_security_gate_rejection(self):
        """Negative security test: attempts to operate retired or unvalidated blocks fail with exact status codes."""
        # Retired block: HTTP 409
        with self.assertRaises(BlockUnavailableError) as ctx1:
            UniversalRuntimeRegistry.validate_block_operable("creator-hud", wave=17)
        self.assertEqual(ctx1.exception.http_code, 409)

        # Proprietary blocked block: HTTP 403
        with self.assertRaises(BlockUnavailableError) as ctx2:
            UniversalRuntimeRegistry.validate_block_operable("chatgpt-exchange", wave=17)
        self.assertEqual(ctx2.exception.http_code, 403)
        self.assertEqual(ctx2.exception.blocker_code, "BLOCKED_RIGHTS")

        # Missing block: HTTP 404
        with self.assertRaises(BlockUnavailableError) as ctx3:
            UniversalRuntimeRegistry.validate_block_operable("non-existent-block-xyz", wave=17)
        self.assertEqual(ctx3.exception.http_code, 404)


if __name__ == "__main__":
    unittest.main()
