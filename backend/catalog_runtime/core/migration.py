# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Legacy Block Migration Manager for Wave 15 Catalog Runtime Core.
Safely manages existing user projects containing the retired 6Clips-authored blocks:
- 'creator-hud'
- 'glitch-transition'

Invariants:
1. NEVER deletes project data or clips as a side effect.
2. Flags affected projects with REQUIRES_MIGRATION and provides non-destructive migration diagnostics.
3. Provides deterministic mapping to verified original donor blocks when migration is confirmed.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from backend.catalog_runtime.core.taxonomy import RETIRED_6CLIPS_BLOCK_IDS

logger = logging.getLogger(__name__)

# Recommended source-faithful donor alternatives for retired blocks
RECOMMENDED_DONOR_MAPPINGS: Dict[str, str] = {
    "creator-hud": "yt-lower-third",
    "glitch-transition": "transitions-wipe",
}


class LegacyBlockMigrationManager:
    """Detects and reconciles retired 6Clips blocks in user project documents."""

    @classmethod
    def detect_retired_blocks(cls, doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Scans a project document for occurrences of retired 6Clips blocks across tracks, clips, and code files.
        """
        if not isinstance(doc, dict):
            return []

        occurrences: List[Dict[str, Any]] = []
        timeline = doc.get("timeline") or {}
        tracks = timeline.get("tracks") or []

        for track_idx, t in enumerate(tracks):
            track_id = t.get("id", f"track_{track_idx}")
            for clip_idx, c in enumerate(t.get("clips") or []):
                bid = c.get("block_id") or ""
                ctype = c.get("type") or ""
                target_id = bid if bid in RETIRED_6CLIPS_BLOCK_IDS else (ctype if ctype in RETIRED_6CLIPS_BLOCK_IDS else None)
                if target_id:
                    occurrences.append({
                        "location": "timeline_clip",
                        "track_id": track_id,
                        "clip_id": c.get("id", f"clip_{clip_idx}"),
                        "retired_block_id": target_id,
                        "recommended_replacement": RECOMMENDED_DONOR_MAPPINGS.get(target_id),
                    })

        # Scan code files
        code_sec = doc.get("code") or {}
        files = code_sec.get("files") or []
        for f in files:
            f_bid = f.get("block_id")
            if f_bid in RETIRED_6CLIPS_BLOCK_IDS:
                occurrences.append({
                    "location": "code_file",
                    "file_id": f.get("id"),
                    "file_path": f.get("path"),
                    "retired_block_id": f_bid,
                    "recommended_replacement": RECOMMENDED_DONOR_MAPPINGS.get(f_bid),
                })

        return occurrences

    @classmethod
    def inspect_and_mark_migration(cls, doc: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
        """
        Non-destructively inspects project document.
        If retired blocks are found, flags document metadata with REQUIRES_MIGRATION without modifying clips.
        Returns (document, requires_migration).
        """
        if not isinstance(doc, dict):
            return doc, False

        occurrences = cls.detect_retired_blocks(doc)
        meta = doc.setdefault("metadata", {})

        if occurrences:
            meta["requires_migration"] = True
            meta["migration_status"] = "REQUIRES_MIGRATION"
            meta["retired_blocks_detected"] = sorted(list({o["retired_block_id"] for o in occurrences}))
            meta["migration_diagnostics"] = occurrences
            meta["recommended_mappings"] = {
                b: RECOMMENDED_DONOR_MAPPINGS.get(b) for b in meta["retired_blocks_detected"]
            }
            logger.info("Project flagged with REQUIRES_MIGRATION: %s", meta["retired_blocks_detected"])
            return doc, True
        else:
            meta["requires_migration"] = False
            meta["migration_status"] = "MIGRATED_OR_CLEAN"
            return doc, False

    @classmethod
    def apply_migration(
        cls,
        doc: Dict[str, Any],
        mapping_overrides: Optional[Dict[str, str]] = None,
        user_consented: bool = True,
    ) -> Dict[str, Any]:
        """
        Applies verified migration to donor-faithful replacements when user has consented.
        Preserves all other project properties, timings, variables, and track layout.
        """
        if not user_consented:
            doc, _ = cls.inspect_and_mark_migration(doc)
            return doc

        mappings = dict(RECOMMENDED_DONOR_MAPPINGS)
        if mapping_overrides:
            mappings.update(mapping_overrides)

        timeline = doc.get("timeline") or {}
        tracks = timeline.get("tracks") or []
        migrated_count = 0

        for t in tracks:
            for c in t.get("clips") or []:
                bid = c.get("block_id")
                if bid in mappings:
                    replacement = mappings[bid]
                    c["block_id"] = replacement
                    c["migrated_from"] = bid
                    c["block_name"] = replacement
                    migrated_count += 1

        # Update metadata
        meta = doc.setdefault("metadata", {})
        meta["requires_migration"] = False
        meta["migration_status"] = "MIGRATION_COMPLETED"
        meta["migrated_clips_count"] = migrated_count

        return doc
