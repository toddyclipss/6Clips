# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
OAAS Motion Action Adapter for Main Agent and Agent 5 Integration.

Provides an authoritative, high-level interface to execute native motion editing
commands, run sequential batch operations with dynamic revision tracking, inspect
timeline state, and revert actions safely over canonical Project documents.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.core.exceptions import ProjectNotFoundError
from backend.services.project_service import ProjectService
from .capability_catalog import CapabilityDiscovery
from .executor import NativeMotionActionExecutor
from .models import (
    ActionExecutionStatus,
    MotionActionEnvelope,
    MotionActionResult,
    MotionActionType,
)

logger = logging.getLogger(__name__)


class OAASMotionActionAdapter:
    """
    Public integration bridge for the Main Agent and downstream integration agents (Agent 5).
    Enables autonomous execution of native Motion Graphics editing actions without
    spawning legacy Clip Studio or Tools dashboards.
    """

    @classmethod
    async def execute_action(cls, envelope: MotionActionEnvelope) -> MotionActionResult:
        """Execute a fully constructed MotionActionEnvelope."""
        return await NativeMotionActionExecutor.execute_action(envelope)

    @classmethod
    async def execute_command(
        cls,
        project_id: str,
        action: str | MotionActionType,
        params: Optional[Dict[str, Any]] = None,
        expected_revision: Optional[int] = None,
        idempotency_key: Optional[str] = None,
        author: str = "main_agent",
        user_id: str = "local",
    ) -> MotionActionResult:
        """
        Convenience method to execute a native motion editing action by name.
        If expected_revision is omitted, loads current project revision dynamically.
        """
        # Parse action type
        if isinstance(action, str):
            try:
                act_type = MotionActionType(action.lower().replace("-", "_"))
            except ValueError:
                # Attempt alias mapping
                act_type = cls._resolve_action_alias(action)
                if not act_type:
                    return MotionActionResult(
                        action_type=MotionActionType.TRIM,  # dummy fallback
                        project_id=project_id,
                        base_revision=expected_revision or 1,
                        resulting_revision=expected_revision or 1,
                        applied=False,
                        status=ActionExecutionStatus.CAPABILITY_UNSUPPORTED,
                        detail=f"Unknown or unmapped action name: '{action}'.",
                    )
        else:
            act_type = action

        # Resolve expected revision if not provided
        if expected_revision is None:
            try:
                proj = await ProjectService.get_project(project_id)
                expected_revision = proj.revision
            except ProjectNotFoundError:
                return MotionActionResult(
                    action_type=act_type,
                    project_id=project_id,
                    base_revision=1,
                    resulting_revision=1,
                    applied=False,
                    status=ActionExecutionStatus.PRECONDITION_FAILED,
                    detail=f"Project '{project_id}' not found.",
                )

        envelope = MotionActionEnvelope(
            action_type=act_type,
            project_id=project_id,
            expected_revision=expected_revision,
            params=params or {},
            idempotency_key=idempotency_key,
            author=author,
            user_id=user_id,
        )

        return await NativeMotionActionExecutor.execute_action(envelope)

    @classmethod
    async def batch_execute(
        cls,
        project_id: str,
        commands: List[Dict[str, Any]],
        author: str = "main_agent",
        user_id: str = "local",
    ) -> List[MotionActionResult]:
        """
        Execute a sequence of native editing actions atomically updating expected revision.
        Stops on the first failure or conflict.
        """
        results: List[MotionActionResult] = []
        proj = await ProjectService.get_project(project_id)
        current_rev = proj.revision

        for cmd in commands:
            action_name = cmd.get("action")
            params = cmd.get("params", {})
            idem_key = cmd.get("idempotency_key")

            res = await cls.execute_command(
                project_id=project_id,
                action=action_name,
                params=params,
                expected_revision=current_rev,
                idempotency_key=idem_key,
                author=author,
                user_id=user_id,
            )
            results.append(res)

            if res.status not in (ActionExecutionStatus.SUCCESS, ActionExecutionStatus.IDEMPOTENT_REPLAY):
                logger.warning("Batch action halted at %s due to status %s: %s", action_name, res.status, res.detail)
                break

            current_rev = res.resulting_revision

        return results

    @classmethod
    async def undo_last_action(
        cls,
        project_id: str,
        author: str = "main_agent",
    ) -> MotionActionResult:
        """
        Revert the project to the snapshot of the preceding revision.
        Fails if project is already at baseline revision 1.
        """
        proj = await ProjectService.get_project(project_id)
        if proj.revision <= 1:
            return MotionActionResult(
                action_type=MotionActionType.TRIM,
                project_id=project_id,
                base_revision=proj.revision,
                resulting_revision=proj.revision,
                applied=False,
                status=ActionExecutionStatus.PRECONDITION_FAILED,
                detail=f"Cannot undo: project is already at initial revision {proj.revision}.",
            )

        prev_revision_num = proj.revision - 1
        prev_snapshot = await ProjectService.get_revision_snapshot(project_id, prev_revision_num)

        # Apply revision rollback via update_document
        res = await ProjectService.apply_operation(
            project_id=project_id,
            expected_revision=proj.revision,
            operation_type="update_document",
            payload={"document": prev_snapshot},
            author=author,
        )

        return MotionActionResult(
            action_type=MotionActionType.TRIM,  # Rollback marker
            project_id=project_id,
            base_revision=proj.revision,
            resulting_revision=res.get("revision", proj.revision + 1),
            applied=True,
            status=ActionExecutionStatus.SUCCESS,
            detail=f"Successfully rolled back project to state of revision {prev_revision_num}.",
        )

    @classmethod
    async def get_timeline_summary(cls, project_id: str) -> Dict[str, Any]:
        """Fetch high-level timeline and track summary for a project."""
        proj = await ProjectService.get_project(project_id)
        doc = json.loads(proj.document_json)
        timeline = doc.get("timeline", {})
        tracks = timeline.get("tracks", [])

        clips_summary = []
        for t in tracks:
            for c in t.get("clips", []):
                clips_summary.append({
                    "id": c.get("id"),
                    "track_id": t.get("id"),
                    "type": c.get("type", "video"),
                    "start": c.get("start", 0.0),
                    "duration": c.get("duration", 0.0),
                    "title": c.get("title") or c.get("id"),
                })

        return {
            "project_id": project_id,
            "revision": proj.revision,
            "aspect_ratio": doc.get("aspect_ratio", proj.aspect_ratio or "9:16"),
            "duration_seconds": timeline.get("duration_seconds", 0.0),
            "tracks_count": len(tracks),
            "clips_count": len(clips_summary),
            "clips": clips_summary,
            "captions_count": len(doc.get("timeline", {}).get("tracks", [{}])[0].get("clips", []))
            if any(t.get("type") == "captions" for t in tracks) else 0,
        }

    @classmethod
    def get_capabilities_inventory(cls) -> List[Dict[str, Any]]:
        """Return the authoritative 30-workflow capability crosswalk."""
        return CapabilityDiscovery.get_full_crosswalk_inventory()

    @classmethod
    def _resolve_action_alias(cls, alias: str) -> Optional[MotionActionType]:
        """Map legacy tool names and aliases to canonical MotionActionType."""
        a = alias.lower().replace("-", "_")
        alias_map = {
            "cut": MotionActionType.TRIM,
            "trim_video": MotionActionType.TRIM,
            "slip": MotionActionType.TRIM,
            "split_clip": MotionActionType.SPLIT,
            "cut_silence": MotionActionType.RIPPLE_DELETE,
            "remove_silence": MotionActionType.RIPPLE_DELETE,
            "extract_clips": MotionActionType.RANGE_SELECT,
            "bench_range": MotionActionType.RANGE_SELECT,
            "set_bench_ranges": MotionActionType.RANGE_SELECT,
            "filmstrip_range": MotionActionType.RANGE_SELECT,
            "mute": MotionActionType.AUDIO_ADJUST,
            "remove_audio": MotionActionType.AUDIO_ADJUST,
            "volume": MotionActionType.AUDIO_ADJUST,
            "audio_enhance": MotionActionType.AUDIO_ADJUST,
            "aspect_ratio": MotionActionType.REFRAME,
            "reframe_vertical": MotionActionType.REFRAME,
            "captions": MotionActionType.CAPTIONS_EDIT,
            "subtitles": MotionActionType.CAPTIONS_EDIT,
            "add_captions": MotionActionType.CAPTIONS_EDIT,
            "watermark": MotionActionType.GRAPHIC_INSERT,
            "add_block": MotionActionType.GRAPHIC_INSERT,
            "insert_graphic": MotionActionType.GRAPHIC_INSERT,
            "render_mp4": MotionActionType.EXPORT,
        }
        return alias_map.get(a)
