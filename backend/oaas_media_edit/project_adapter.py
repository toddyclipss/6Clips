# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Safe Call-Site Adapter for Canonical ProjectService.

Applies source-backed editing operations to versioned ProjectRevision documents
without mutating core project_service.py implementations:
- add_asset with verified source media SHA-256 and duration
- add_clip with precise source in/out offsets
- set_aspect_ratio and set_captions
- Revisions N -> N+1 progression for follow-up chat turns
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from backend.core.exceptions import ProjectNotFoundError
from backend.services.project_service import ProjectService
from .models import EditExistingMediaContract, SourceMediaAnalysis

logger = logging.getLogger(__name__)


class SafeProjectEditAdapter:
    """Safe call-site adapter connecting media edit pipeline to ProjectService."""

    @classmethod
    async def get_or_create_project(
        cls,
        project_id: Optional[str] = None,
        user_id: str = "local",
        title: str = "Video Edit",
        aspect_ratio: str = "9:16",
    ) -> Tuple[Any, int]:
        """
        Retrieve existing project or autonomously create a new canonical Project.
        Returns: (project_instance, current_revision).
        """
        project = None
        if project_id:
            try:
                project = await ProjectService.get_project(project_id)
            except ProjectNotFoundError:
                project = None

        if not project:
            project = await ProjectService.create_project(
                name=title,
                aspect_ratio=aspect_ratio,
                user_id=user_id,
            )
            logger.info("Created new canonical project %s for edit workflow", project.id)

        return project, project.revision

    @classmethod
    async def apply_source_edit_operations(
        cls,
        project_id: str,
        expected_revision: int,
        contract: EditExistingMediaContract,
        analysis: SourceMediaAnalysis,
        author: str = "media_edit_agent",
    ) -> Tuple[int, str, str]:
        """
        Apply atomic canonical operations binding source media to the project timeline.
        Returns: (final_revision, asset_id, clip_id).
        """
        current_rev = expected_revision
        asset_id = contract.asset_id or f"asset_{Path(contract.file_path).stem[:12]}"
        clip_id = f"clip_{uuid4().hex[:10]}"

        source_file = Path(contract.file_path)
        w, h = analysis.resolution

        # 1. Operation: add_asset
        await ProjectService.apply_operation(
            project_id=project_id,
            expected_revision=current_rev,
            operation_type="add_asset",
            payload={
                "asset": {
                    "id": asset_id,
                    "name": source_file.name,
                    "type": "video",
                    "file_path": str(source_file.resolve()),
                    "duration": analysis.duration_sec,
                    "width": w,
                    "height": h,
                    "sha256": analysis.sha256_hash,
                },
                "validate": False,
            },
            author=author,
        )
        current_rev += 1

        # 2. Operation: add_clip with exact source in/out offsets
        trim_start, trim_end = contract.source_intervals[0] if contract.source_intervals else (0.0, contract.target_duration)
        clip_duration = round(trim_end - trim_start, 3)

        await ProjectService.apply_operation(
            project_id=project_id,
            expected_revision=current_rev,
            operation_type="add_clip",
            payload={
                "clip": {
                    "id": clip_id,
                    "type": "video",
                    "asset_id": asset_id,
                    "title": f"Source Cut ({clip_duration:.1f}s)",
                    "start_seconds": 0.0,
                    "duration_seconds": clip_duration,
                    "trim_start": trim_start,
                    "trim_end": trim_end,
                    "visible": True,
                    "locked": False,
                },
                "track_id": "track_video_main",
                "track_type": "video",
                "track_name": "Main Media Track",
            },
            author=author,
        )
        current_rev += 1

        # 3. Operation: set_aspect_ratio
        await ProjectService.apply_operation(
            project_id=project_id,
            expected_revision=current_rev,
            operation_type="set_aspect_ratio",
            payload={"aspect_ratio": contract.target_aspect_ratio},
            author=author,
        )
        current_rev += 1

        # 4. Operation: set_captions if supplied
        if contract.caption_timings:
            await ProjectService.apply_operation(
                project_id=project_id,
                expected_revision=current_rev,
                operation_type="set_captions",
                payload={
                    "captions": contract.caption_timings,
                    "style": contract.caption_style or "viral",
                    "language": contract.target_language or "en",
                },
                author=author,
            )
            current_rev += 1

        return current_rev, asset_id, clip_id

    @classmethod
    async def inspect_project_source_lineage(
        cls,
        project_id: str,
        revision_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Inspect canonical project document at given revision to verify source-backed lineage.
        Returns dict with asset and clip verification data.
        """
        project = await ProjectService.get_project(project_id)
        import json
        if hasattr(project, "document_json") and project.document_json:
            doc = json.loads(project.document_json) if isinstance(project.document_json, str) else project.document_json
        elif hasattr(project, "document"):
            doc = project.document
        else:
            doc = {}

        raw_assets = doc.get("assets", {})
        if isinstance(raw_assets, list):
            assets = {a.get("id"): a for a in raw_assets if isinstance(a, dict)}
        elif isinstance(raw_assets, dict):
            assets = raw_assets
        else:
            assets = {}

        clips = doc.get("clips", [])
        timeline = doc.get("timeline", {})
        tracks = doc.get("tracks", []) or timeline.get("tracks", [])

        # Flatten clips from root clips and tracks
        all_clips = list(clips)
        if isinstance(timeline.get("clips"), list):
            all_clips.extend(timeline.get("clips"))
        for tr in tracks:
            if isinstance(tr, dict) and isinstance(tr.get("clips"), list):
                all_clips.extend(tr.get("clips"))

        # Find video clip referencing source asset (take most recent)
        source_clips = [c for c in all_clips if isinstance(c, dict) and c.get("type") == "video" and c.get("asset_id")]

        found_clip = source_clips[-1] if source_clips else None
        found_asset = None
        asset_sha = None

        if found_clip:
            a_id = found_clip.get("asset_id")
            found_asset = assets.get(a_id)
            if isinstance(found_asset, dict):
                asset_sha = found_asset.get("sha256")

        return {
            "project_id": project.id,
            "revision": project.revision,
            "has_source_clip": found_clip is not None,
            "clip_id": found_clip.get("id") if found_clip else None,
            "asset_id": found_clip.get("asset_id") if found_clip else None,
            "trim_start": float(found_clip.get("trim_start", 0.0)) if found_clip else 0.0,
            "trim_end": float(found_clip.get("trim_end", 0.0)) if found_clip else 0.0,
            "clip_duration": float(found_clip.get("duration_seconds", 0.0)) if found_clip else 0.0,
            "asset_sha256": asset_sha,
            "aspect_ratio": doc.get("aspect_ratio", project.aspect_ratio),
        }
