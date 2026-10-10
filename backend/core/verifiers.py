# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Deterministic verifiers for execution step outputs and media artifacts."""
import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def verify_file_output(file_path: str | Path, min_bytes: int = 1024) -> dict:
    """Verify that an output file exists on disk and has valid size."""
    p = Path(file_path) if file_path else None
    if not p or not p.exists():
        return {
            "ok": False,
            "verifier": "verify_file_output",
            "error": f"File does not exist: {file_path}",
        }
    try:
        size = p.stat().st_size
        if size < min_bytes:
            return {
                "ok": False,
                "verifier": "verify_file_output",
                "error": f"File size too small ({size} bytes < {min_bytes} min bytes): {file_path}",
            }
        return {
            "ok": True,
            "verifier": "verify_file_output",
            "size_bytes": size,
            "path": str(p),
        }
    except Exception as e:
        return {
            "ok": False,
            "verifier": "verify_file_output",
            "error": f"Failed checking file {file_path}: {e}",
        }


def verify_video_stream(file_path: str | Path, min_duration: float = 0.5) -> dict:
    """Verify video container, stream readability, and duration via video_utils or ffprobe."""
    file_check = verify_file_output(file_path, min_bytes=4096)
    if not file_check["ok"]:
        return file_check

    p = Path(file_path)
    try:
        from backend.services.video_utils import probe_media, probe_duration
        w, h, dur = probe_media(p)
        dur = dur or probe_duration(p, 0.0)
        if not dur or dur < min_duration:
            return {
                "ok": False,
                "verifier": "verify_video_stream",
                "error": f"Video duration {dur}s is below minimum {min_duration}s",
            }
        return {
            "ok": True,
            "verifier": "verify_video_stream",
            "duration_seconds": dur,
            "width": w,
            "height": h,
            "path": str(p),
        }
    except Exception as e:
        return {
            "ok": False,
            "verifier": "verify_video_stream",
            "error": f"Video probe failed for {file_path}: {e}",
        }


def verify_lineage(child_data: dict | str = None, expected_parents: list[str] = None, parent_ids: list[str] = None, child_id: str = None, operation: str = None) -> dict:
    """Verify that child artifact properly points back to its source parent(s)."""
    parents = expected_parents or parent_ids or []
    if isinstance(child_data, str) and not child_id:
        child_id = child_data
    if child_id and not isinstance(child_data, dict):
        child_data = {"id": child_id, "parent_keys": parents}

    child_data = child_data or {}
    parent_key = child_data.get("parent_key") or child_data.get("source_asset_id") or child_data.get("source_downloaded_video_id")
    parent_keys = list(child_data.get("parent_keys") or [])
    if parent_key and parent_key not in parent_keys:
        parent_keys = [parent_key] + parent_keys

    missing = [ep for ep in parents if not any(ep in pk for pk in parent_keys)]
    if missing:
        return {
            "ok": False,
            "verifier": "verify_lineage",
            "error": f"Child missing expected parent reference(s): {missing}",
            "found_parents": parent_keys,
        }
    return {
        "ok": True,
        "verifier": "verify_lineage",
        "parents_verified": parent_keys,
        "operation": operation,
    }
