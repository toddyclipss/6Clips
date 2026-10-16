# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Legacy block reference detector for projects, revisions, timelines, and databases."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from backend.knowledge_migration.models import LegacyBlockRef

RETIRED_CUSTOM_BLOCKS: Set[str] = {"creator-hud", "glitch-transition"}


class LegacyBlockDetector:
    """Safe, read-only detector of legacy imported blocks and custom retired blocks."""

    @classmethod
    def is_retired_custom(cls, block_id: str) -> bool:
        return block_id in RETIRED_CUSTOM_BLOCKS

    @classmethod
    def detect_in_clip(
        cls,
        clip: Dict[str, Any],
        track_id: str = "",
        track_type: str = "graphics"
    ) -> Optional[LegacyBlockRef]:
        """Inspect a single timeline clip dictionary for block references."""
        if not isinstance(clip, dict):
            return None

        # Check explicit block_id fields
        block_id = (
            clip.get("block_id")
            or clip.get("blockId")
            or clip.get("template_id")
            or clip.get("catalog_id")
        )

        # Check nested data payload
        data = clip.get("data")
        if not block_id and isinstance(data, dict):
            block_id = data.get("block_id") or data.get("blockId") or data.get("template_id")

        # Check asset_file path for shipped_blocks references
        asset_file = clip.get("asset_file") or clip.get("file") or ""
        asset_str = str(asset_file)
        if not block_id and ("shipped_blocks" in asset_str or "catalog/blocks" in asset_str):
            # Extract slug from path if possible
            parts = asset_str.replace("\\", "/").split("/")
            for i, p in enumerate(parts):
                if p in ("shipped_blocks", "blocks") and i + 1 < len(parts):
                    block_id = parts[i + 1]
                    break

        kind = clip.get("kind") or clip.get("type") or ""
        if not block_id and kind in ("block", "catalog"):
            block_id = clip.get("slug") or "unknown-block"

        if not block_id:
            return None

        variables = clip.get("variables")
        if not isinstance(variables, dict):
            if isinstance(data, dict) and isinstance(data.get("variables"), dict):
                variables = data.get("variables")
            else:
                variables = {}

        return LegacyBlockRef(
            clip_id=str(clip.get("id") or f"clip_{block_id}"),
            block_id=str(block_id),
            track_id=track_id,
            track_type=track_type,
            start_seconds=float(clip.get("start_seconds") or clip.get("start_time") or 0.0),
            duration_seconds=float(clip.get("duration_seconds") or clip.get("duration") or 0.0),
            variables=variables,
            is_retired_custom=cls.is_retired_custom(str(block_id)),
            source_asset_path=asset_str if asset_str else None,
        )

    @classmethod
    def detect_in_project_doc(cls, doc: Dict[str, Any]) -> List[LegacyBlockRef]:
        """Detect all legacy block references in a parsed project document."""
        if not isinstance(doc, dict):
            return []

        refs: List[LegacyBlockRef] = []
        timeline = doc.get("timeline")
        if not isinstance(timeline, dict):
            return refs

        tracks = timeline.get("tracks")
        if not isinstance(tracks, list):
            return refs

        for track in tracks:
            if not isinstance(track, dict):
                continue
            track_id = str(track.get("id") or "")
            track_type = str(track.get("type") or "graphics")
            clips = track.get("clips") or []
            if not isinstance(clips, list):
                continue
            for clip in clips:
                ref = cls.detect_in_clip(clip, track_id=track_id, track_type=track_type)
                if ref:
                    refs.append(ref)

        return refs

    @classmethod
    def scan_database(
        cls,
        db_path: Path,
        mode: str = "ro"
    ) -> Dict[str, List[LegacyBlockRef]]:
        """Scan all projects in a SQLite database in strict read-only mode."""
        if not db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")

        uri = f"file:{db_path.resolve().as_posix()}?mode={mode}"
        conn = sqlite3.connect(uri, uri=True)
        cur = conn.cursor()

        results: Dict[str, List[LegacyBlockRef]] = {}
        rows = cur.execute("SELECT id, document_json FROM projects WHERE document_json IS NOT NULL").fetchall()
        for pid, doc_json in rows:
            try:
                doc = json.loads(doc_json)
                refs = cls.detect_in_project_doc(doc)
                if refs:
                    results[str(pid)] = refs
            except Exception:
                continue

        conn.close()
        return results
