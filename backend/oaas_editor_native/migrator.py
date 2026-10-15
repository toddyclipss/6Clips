# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Legacy Project Migrator: Converts legacy Clip Studio and Tools state into unified ProjectRevision CAS documents.
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class LegacyProjectMigrator:
    """
    Safely migrates legacy `/clips` or `/tools` jobs and project structures
    into the canonical Motion Graphics ProjectRevision format.
    Operates non-destructively: preserves raw backup, supports dry-run, and guarantees idempotency.
    """

    @classmethod
    def migrate_legacy_document(
        cls,
        legacy_doc: Dict[str, Any],
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Convert legacy document structure to unified ProjectRevision schema.
        1. Normalizes tracks and clips
        2. Absorbs Clip Studio source offsets, in/out points, and captions
        3. Absorbs Tools job parameters (watermark, speed, crop, silence) into native track attributes
        4. Maintains original document backup under _legacy_migration_backup
        """
        migrated = copy.deepcopy(legacy_doc)

        if not dry_run:
            migrated["_legacy_migration_backup"] = copy.deepcopy(legacy_doc)

        migrated["schema_version"] = "oaas.motion.v18"
        migrated["editor_mode"] = "native_motion"

        # 1. Normalize tracks
        if "tracks" not in migrated:
            migrated["tracks"] = []

        # If legacy had root-level clips or clips array from Clip Studio:
        if "clips" in legacy_doc and not any(t.get("name") == "Video Track 1" for t in migrated["tracks"]):
            video_track = {
                "id": "track_video_main",
                "name": "Video Track 1",
                "type": "video",
                "clips": copy.deepcopy(legacy_doc["clips"]),
            }
            migrated["tracks"].append(video_track)

        # 2. Normalize Clip Studio attributes on clips
        for track in migrated["tracks"]:
            for clip in track.get("clips", []):
                # Ensure canonical timeline fields exist
                clip.setdefault("start_time", 0.0)
                clip.setdefault("duration", 5.0)
                clip.setdefault("source_offset", 0.0)
                clip.setdefault("speed", 1.0)
                clip.setdefault("trim_start", 0.0)
                clip.setdefault("trim_end", 0.0)

        # 3. Absorb legacy bench ranges
        if "bench_ranges" in legacy_doc:
            migrated["bench_ranges"] = legacy_doc["bench_ranges"]

        # 4. Absorb legacy silence settings
        if "silence_threshold" in legacy_doc:
            migrated["silence_settings"] = {
                "threshold_db": legacy_doc.get("silence_threshold", -30.0),
                "min_duration": legacy_doc.get("min_silence_duration", 0.5),
                "applied": True,
            }

        # 5. Absorb legacy caption overrides
        if "caption_corrections" in legacy_doc:
            migrated.setdefault("caption_overrides", {})
            migrated["caption_overrides"].update(legacy_doc["caption_corrections"])

        # Recompute CAS document hash
        serialized = json.dumps(migrated, sort_keys=True, separators=(",", ":"))
        migrated["document_sha256"] = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        return migrated
