# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests verifying the 3 physical motion proof MP4 files, stream decodes, and QA criteria."""

import json
from pathlib import Path
from backend.native_motion.renderer import NativeMotionRenderer


def test_physical_proofs_exist_and_verified():
    proofs_dir = Path("tools/wave20_a4/proofs")
    p1 = proofs_dir / "proof1_data_kinetic_9x16.mp4"
    p2 = proofs_dir / "proof2_editorial_16x9.mp4"
    p3 = proofs_dir / "proof3_speech_captions_9x16.mp4"
    report_file = proofs_dir / "verification_report.json"

    assert p1.exists(), f"Missing physical MP4 for Proof 1 at {p1}"
    assert p2.exists(), f"Missing physical MP4 for Proof 2 at {p2}"
    assert p3.exists(), f"Missing physical MP4 for Proof 3 at {p3}"
    assert report_file.exists(), f"Missing verification report at {report_file}"

    # Inspect each with FFprobe
    info1 = NativeMotionRenderer.inspect_mp4(p1)
    assert info1["codec_name"] == "h264"
    assert (info1["width"], info1["height"]) == (1080, 1920)
    assert info1["duration"] >= 2.9
    assert info1["frame_count"] >= 90

    info2 = NativeMotionRenderer.inspect_mp4(p2)
    assert info2["codec_name"] == "h264"
    assert (info2["width"], info2["height"]) == (1920, 1080)
    assert info2["duration"] >= 2.9
    assert info2["frame_count"] >= 90

    info3 = NativeMotionRenderer.inspect_mp4(p3)
    assert info3["codec_name"] == "h264"
    assert (info3["width"], info3["height"]) == (1080, 1920)
    assert info3["duration"] >= 4.4
    assert info3["frame_count"] >= 135
    assert info3["has_audio"] is True
    assert info3["audio_codec"] == "aac"

    # Verify report contents
    with open(report_file, "r", encoding="utf-8") as f:
        rep = json.load(f)

    assert rep["structural_comparison"]["is_topologically_distinct"] is True
    assert rep["structural_comparison"]["zero_imported_blocks_used"] is True
    assert rep["structural_comparison"]["all_proofs_pass_motion_delta"] is True
    assert rep["structural_comparison"]["all_proofs_have_valid_frames"] is True
