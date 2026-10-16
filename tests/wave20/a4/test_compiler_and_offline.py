# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for NativeMotionCompiler: offline operation, 0 CDN egress, and project schema."""

import re
from backend.native_motion.compiler import NativeMotionCompiler
from backend.native_motion.generator import NativeMotionGenerator
from backend.native_motion.schema import Constraints, CreativeBrief


def test_compiler_zero_cdn_egress():
    brief = CreativeBrief(topic="Zero Network Test", intent="data", tone="tech")
    spec = NativeMotionGenerator.generate(brief, [], Constraints(aspect_ratio="9:16"), seed=77)
    html = NativeMotionCompiler.compile_to_html(spec)

    # Reject http/https external imports
    assert "https://" not in html, "External HTTPS network reference found in compiled bundle"
    assert "http://" not in html, "External HTTP network reference found in compiled bundle"
    assert "cdnjs.cloudflare.com" not in html
    assert "unpkg.com" not in html
    assert "jsdelivr.net" not in html


def test_compiler_deterministic_frame_stepping_interface():
    brief = CreativeBrief(topic="Frame Stepping API", intent="editorial", tone="minimal")
    spec = NativeMotionGenerator.generate(brief, [], Constraints(aspect_ratio="16:9"), seed=88)
    html = NativeMotionCompiler.compile_to_html(spec)

    assert "window.__seekTime" in html
    assert "window.__seekFrame" in html


def test_compiler_project_document_schema_v2():
    brief = CreativeBrief(topic="Document Format", intent="data", tone="tech")
    spec = NativeMotionGenerator.generate(brief, [], Constraints(aspect_ratio="9:16"), seed=99)
    doc = NativeMotionCompiler.compile_to_project_document(spec)

    assert doc["schema_version"] == 2
    assert "timeline" in doc
    assert doc["timeline"]["fps"] == spec.fps
    assert doc["timeline"]["duration_seconds"] == spec.duration_seconds
    assert len(doc["timeline"]["tracks"]) >= 2
    assert doc["code"]["files"][0]["path"] == "native_motion/spec.json"
