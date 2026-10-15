# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Project Block Migrator for Wave 16 Catalog Replacement and Legacy Preservation.

Implements safe, non-destructive migration contracts for user projects
referencing retired 6Clips-authored blocks ('creator-hud', 'glitch-transition'):
- Inspection & diagnostics without data loss
- Safe migration marking clips with backward-compatibility metadata
- Idempotency & Rollback contracts
- Export-safe rendering adapter preserving timeline integrity
- Revision-safe migration supporting canonical ProjectRevision and CAS tracking
- Public catalog filtering guaranteeing retired blocks are never offered as donor choices
"""
from __future__ import annotations

import copy
import enum
import hashlib
import json
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

# Verified donor-origin replacement mapping (compatible donor worklet for export)
EXPORT_SAFE_SUBSTITUTIONS: Dict[str, str] = {
    "creator-hud": "yt-lower-third",        # Compatible broadcast lower third
    "glitch-transition": "transitions-push", # Clean donor transition
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
        cas_hash: Optional[str] = None,
    ):
        self.status = status
        self.document = document
        self.affected_count = affected_count
        self.details = details
        self.rollback_snapshot = rollback_snapshot
        self.error = error
        self.cas_hash = cas_hash

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "affected_count": self.affected_count,
            "details": self.details,
            "has_rollback_snapshot": self.rollback_snapshot is not None,
            "cas_hash": self.cas_hash,
            "error": self.error,
        }


def compute_document_cas(doc: Dict[str, Any]) -> str:
    """Computes deterministic SHA-256 CAS hash of project document."""
    raw = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class ProjectBlockMigrator:
    """Manages non-destructive migration and export compatibility for projects referencing retired blocks."""

    @classmethod
    def filter_public_donor_catalog(cls, block_ids: List[str]) -> List[str]:
        """Filters out retired 6Clips blocks from public donor catalog offerings."""
        return [bid for bid in block_ids if bid not in RETIRED_BLOCK_IDS]

    @classmethod
    def is_retired_block(cls, block_id: str) -> bool:
        """Checks if a given block ID is a retired 6Clips-authored block."""
        return block_id in RETIRED_BLOCK_IDS

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
        Creates an exact deep-copy rollback snapshot before applying changes.
        """
        inspection = cls.inspect_document(doc)
        if not inspection["has_retired_blocks"]:
            return MigrationResult(
                status=MigrationStatus.VERIFIED_CURRENT,
                document=doc,
                affected_count=0,
                details=[],
                rollback_snapshot=None,
                cas_hash=compute_document_cas(doc),
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
                        replacement_id = EXPORT_SAFE_SUBSTITUTIONS.get(block_id, "yt-lower-third")
                        clip["block_id"] = replacement_id
                        clip["migrated_from"] = original_block
                        clip["migration_policy"] = "SUBSTITUTE_DONOR_ORIGINAL"
                    else:
                        # Non-destructive snapshot preservation
                        clip["is_legacy_retired"] = True
                        clip["legacy_retirement_notice"] = (
                            f"6Clips authored block '{original_block}' was retired from public donor catalog in Wave 15/16"
                        )
                        clip["migration_policy"] = "PRESERVE_SNAPSHOT"

                    details.append({
                        "clip_id": clip_id,
                        "original_block": original_block,
                        "new_block": clip.get("block_id"),
                        "policy": clip.get("migration_policy"),
                    })

        # Record migration header in document metadata
        meta = migrated_doc.setdefault("metadata", {})
        meta["wave16_migration"] = {
            "applied": True,
            "migrated_clips_count": len(details),
            "retired_blocks": inspection["retired_blocks_found"],
            "policy": "SUBSTITUTE" if substitute_donor_counterparts else "PRESERVE_SNAPSHOT",
        }

        cas = compute_document_cas(migrated_doc)

        return MigrationResult(
            status=MigrationStatus.MIGRATED_SUCCESS,
            document=migrated_doc,
            affected_count=len(details),
            details=details,
            rollback_snapshot=rollback_snapshot,
            cas_hash=cas,
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
        cas = compute_document_cas(restored_doc)
        return MigrationResult(
            status=MigrationStatus.ROLLBACK_SUCCESS,
            document=restored_doc,
            affected_count=migrated_result.affected_count,
            details=[{"action": "ROLLBACK_RESTORED"}],
            rollback_snapshot=None,
            cas_hash=cas,
        )

    @classmethod
    def prepare_export_safe_document(cls, doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates an export-safe clone of a project document for physical FFmpeg rendering.
        If a clip references a retired block ('creator-hud', 'glitch-transition'), this adapter
        ensures the export pipeline has a valid offline renderable worklet without modifying
        the user's canonical project database or revision history.
        """
        export_doc = copy.deepcopy(doc)
        timeline = export_doc.get("timeline", {})
        tracks = timeline.get("tracks", []) if isinstance(timeline, dict) else []

        for track in tracks:
            clips = track.get("clips", []) if isinstance(track, dict) else []
            for clip in clips:
                block_id = clip.get("block_id") or clip.get("blockName") or clip.get("type")
                if block_id in RETIRED_BLOCK_IDS or clip.get("is_legacy_retired"):
                    substitute_block = EXPORT_SAFE_SUBSTITUTIONS.get(block_id, "yt-lower-third")
                    # Preserve all timing, transforms, cuts and user custom data
                    clip["_export_adapter"] = {
                        "original_block_id": block_id,
                        "export_render_block_id": substitute_block,
                        "is_legacy_fallback": True,
                    }
                    clip["block_id"] = substitute_block

        meta = export_doc.setdefault("metadata", {})
        meta["export_safe_adapted"] = True
        return export_doc

    @classmethod
    def migrate_project_revision(
        cls,
        revision_record: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Migrates a canonical ProjectRevision record.
        Preserves revision_id, parent_revision_id, version_counter, and updates cas_hash.
        """
        rev = copy.deepcopy(revision_record)
        doc = rev.get("document", {})
        migrated_res = cls.migrate_document(doc, substitute_donor_counterparts=False)

        rev["document"] = migrated_res.document
        rev["cas_hash"] = migrated_res.cas_hash
        rev["previous_revision_id"] = rev.get("revision_id")
        rev["version_counter"] = rev.get("version_counter", 1) + 1

        history = rev.setdefault("revision_history", [])
        history.append({
            "action": "WAVE16_NON_DESTRUCTIVE_MIGRATION",
            "status": migrated_res.status.value,
            "affected_count": migrated_res.affected_count,
            "cas_hash": migrated_res.cas_hash,
        })

        return rev
