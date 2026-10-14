# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Project Block Migrator for Wave 15 Catalog Replacement.

Implements safe, non-destructive migration contracts for user projects
referencing retired 6Clips-authored blocks ('creator-hud', 'glitch-transition'):
- Inspection & diagnostics without data loss
- Safe migration marking clips with backward-compatibility metadata
- Idempotency & Rollback contracts
- Preservation of timeline integrity
"""
from __future__ import annotations

import copy
import enum
from typing import Any, Dict, List, Optional, Set, Tuple


class MigrationStatus(str, enum.Enum):
    VERIFIED_CURRENT = "VERIFIED_CURRENT"
    REQUIRES_MIGRATION = "REQUIRES_MIGRATION"
    MIGRATED_SUCCESS = "MIGRATED_SUCCESS"
    ROLLBACK_SUCCESS = "ROLLBACK_SUCCESS"
    ERROR = "ERROR"


RETIRED_BLOCK_IDS: Set[str] = {
    "creator-hud",
    "glitch-transition",
}

# Verified donor-origin replacement mapping (or fallback to compatible donor worklet)
REPLACEMENT_RECOMMENDATIONS: Dict[str, str] = {
    "creator-hud": "yt-lower-third",        # Compatible broadcast overlay
    "glitch-transition": "transitions-wipe", # Donor transition
}


class MigrationResult:
    def __init__(
        self,
        status: MigrationStatus,
        document: Dict[str, Any],
        affected_count: int,
        details: List[Dict[str, Any]],
        rollback_snapshot: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ):
        self.status = status
        self.document = document
        self.affected_count = affected_count
        self.details = details
        self.rollback_snapshot = rollback_snapshot
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "affected_count": self.affected_count,
            "details": self.details,
            "has_rollback_snapshot": self.rollback_snapshot is not None,
            "error": self.error,
        }


class ProjectBlockMigrator:
    """Manages non-destructive migration of project documents referencing retired blocks."""

    @classmethod
    def inspect_document(cls, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Inspects project document timeline for retired 6Clips block IDs without mutating."""
        if not doc or not isinstance(doc, dict):
            return {
                "status": MigrationStatus.VERIFIED_CURRENT.value,
                "has_retired_blocks": False,
                "retired_blocks_found": [],
                "affected_clips": [],
            }

        timeline = doc.get("timeline", {})
        tracks = timeline.get("tracks", []) if isinstance(timeline, dict) else []
        affected_clips = []
        found_retired = set()

        for track in tracks:
            clips = track.get("clips", []) if isinstance(track, dict) else []
            for clip in clips:
                if not isinstance(clip, dict):
                    continue
                block_id = clip.get("block_id") or clip.get("blockName") or clip.get("type")
                if block_id in RETIRED_BLOCK_IDS and not clip.get("is_legacy_retired"):
                    found_retired.add(block_id)
                    affected_clips.append({
                        "clip_id": clip.get("id"),
                        "track_id": track.get("id"),
                        "block_id": block_id,
                        "title": clip.get("title", block_id),
                    })

        has_retired = len(found_retired) > 0
        return {
            "status": MigrationStatus.REQUIRES_MIGRATION.value if has_retired else MigrationStatus.VERIFIED_CURRENT.value,
            "has_retired_blocks": has_retired,
            "retired_blocks_found": sorted(list(found_retired)),
            "affected_clips": affected_clips,
        }

    @classmethod
    def migrate_document(
        cls,
        doc: Dict[str, Any],
        substitute_donor_counterparts: bool = False,
    ) -> MigrationResult:
        """
        Executes a deterministic, non-destructive migration of the project document.
        Creates a deep-copy rollback snapshot before applying changes.
        """
        inspection = cls.inspect_document(doc)
        if not inspection["has_retired_blocks"]:
            return MigrationResult(
                status=MigrationStatus.VERIFIED_CURRENT,
                document=doc,
                affected_count=0,
                details=[],
                rollback_snapshot=None,
            )

        # Create exact rollback snapshot
        rollback_snapshot = copy.deepcopy(doc)
        migrated_doc = copy.deepcopy(doc)
        timeline = migrated_doc.get("timeline", {})
        tracks = timeline.get("tracks", [])
        details = []

        for track in tracks:
            clips = track.get("clips", [])
            for clip in clips:
                block_id = clip.get("block_id") or clip.get("blockName") or clip.get("type")
                if block_id in RETIRED_BLOCK_IDS:
                    clip_id = clip.get("id")
                    original_block = block_id
                    
                    if substitute_donor_counterparts:
                        replacement_id = REPLACEMENT_RECOMMENDATIONS.get(block_id, "yt-lower-third")
                        clip["block_id"] = replacement_id
                        clip["migrated_from"] = original_block
                        clip["migration_policy"] = "SUBSTITUTE_DONOR_ORIGINAL"
                    else:
                        # Non-destructive: mark clip as legacy-compatible without altering content
                        clip["is_legacy_retired"] = True
                        clip["legacy_retirement_notice"] = f"6Clips authored block '{original_block}' was retired from public catalog in Wave 15"
                        clip["migration_policy"] = "PRESERVE_SNAPSHOT"

                    details.append({
                        "clip_id": clip_id,
                        "original_block": original_block,
                        "new_block": clip.get("block_id"),
                        "policy": clip.get("migration_policy"),
                    })

        # Record migration header in document metadata
        meta = migrated_doc.setdefault("metadata", {})
        meta["wave15_migration"] = {
            "applied": True,
            "migrated_clips_count": len(details),
            "retired_blocks": inspection["retired_blocks_found"],
        }

        return MigrationResult(
            status=MigrationStatus.MIGRATED_SUCCESS,
            document=migrated_doc,
            affected_count=len(details),
            details=details,
            rollback_snapshot=rollback_snapshot,
        )

    @classmethod
    def rollback_document(
        cls,
        migrated_result: MigrationResult,
    ) -> MigrationResult:
        """Restores the exact document from its rollback snapshot."""
        if not migrated_result.rollback_snapshot:
            return MigrationResult(
                status=MigrationStatus.ERROR,
                document=migrated_result.document,
                affected_count=0,
                details=[],
                error="No rollback snapshot available in migration result",
            )

        restored_doc = copy.deepcopy(migrated_result.rollback_snapshot)
        return MigrationResult(
            status=MigrationStatus.ROLLBACK_SUCCESS,
            document=restored_doc,
            affected_count=migrated_result.affected_count,
            details=[{"action": "ROLLBACK_RESTORED"}],
            rollback_snapshot=None,
        )
