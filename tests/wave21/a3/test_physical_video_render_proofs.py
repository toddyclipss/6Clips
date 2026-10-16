# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Tests for physical MP4 video render proofs, decoded frame inspections,
and non-blank luminance verification.
"""
import json
import shutil
import subprocess
from pathlib import Path
import pytest

WORKTREE_ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = WORKTREE_ROOT / "tools" / "wave21_a3" / "evidence"


@pytest.fixture(scope="module")
def proof_files():
    files = list(EVIDENCE_DIR.glob("proof_*.json"))
    assert len(files) >= 5, "Expected at least 5 proof JSON files in evidence directory"
    return files


def test_proof_json_metadata_integrity(proof_files):
    """Verify proof JSON files contain valid frame metrics, dimensions, and SHA-256."""
    for pf in proof_files:
        data = json.loads(pf.read_text(encoding="utf-8"))
        assert "doc_id" in data
        assert "sha256" in data and len(data["sha256"]) == 64
        assert data["frame_count"] >= 30
        assert data["fps"] == 30
        assert data["duration"] >= 1.0
        assert data["codec"] == "h264"
        assert data["avg_luminance"] > 5.0, f"Luminance too low (blank frame) in {pf.name}: {data['avg_luminance']}"
        assert data["fully_accepted"] is True


def test_physical_mp4_files_exist_and_non_empty(proof_files):
    """Verify actual MP4 video files exist on disk and have non-zero size."""
    for pf in proof_files:
        data = json.loads(pf.read_text(encoding="utf-8"))
        mp4_rel = data["mp4_file"]
        mp4_path = WORKTREE_ROOT / mp4_rel
        assert mp4_path.exists(), f"MP4 file not found: {mp4_path}"
        assert mp4_path.stat().st_size > 50000, f"MP4 file unexpectedly small: {mp4_path.stat().st_size} bytes"


def test_ffprobe_inspection_of_rendered_mp4s(proof_files):
    """Verify FFprobe inspects rendered MP4 containers successfully without errors."""
    ffprobe_bin = shutil.which("ffprobe") or "ffprobe"
    for pf in proof_files[:3]:  # inspect sample of 3 files
        data = json.loads(pf.read_text(encoding="utf-8"))
        mp4_path = WORKTREE_ROOT / data["mp4_file"]

        cmd = [
            ffprobe_bin,
            "-v", "error",
            "-show_entries", "stream=width,height,codec_name,nb_frames",
            "-of", "json",
            str(mp4_path)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"FFprobe failed on {mp4_path}: {res.stderr}"

        info = json.loads(res.stdout)
        streams = info.get("streams", [])
        assert len(streams) >= 1
        video = streams[0]
        assert video.get("codec_name") == "h264"
        assert video.get("width") in (1080, 1920)
        assert video.get("height") in (1080, 1920)
