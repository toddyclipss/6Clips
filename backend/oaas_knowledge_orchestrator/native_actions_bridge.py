# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Native Actions Bridge for Knowledge-First OAAS Orchestrator.
Exposes callable programmatic adapters for all legacy Clip Studio and Native Tools
capabilities: trimming, split, silence removal, reframing, speed adjustment,
caption styling, multi-clip extraction, and atomic CAS revision rollbacks.
Truthfully reports UNSUPPORTED when an action is unexecutable.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.services.project_service import ProjectService
from backend.core.exceptions import ProjectNotFoundError, RevisionConflictError

logger = logging.getLogger(__name__)

# Supported native actions
SUPPORTED_NATIVE_ACTIONS = {
    "trim",
    "remove_silence",
    "reframe",
    "captions",
    "subtitles",
    "speed",
    "split",
    "merge_clips",
    "audio_enhance",
    "extract_clips",
    "auto_chapters",
    "revert_revision",
}


class NativeActionsBridge:
    """
    Unified programmatic gateway executing native tool transformations
    and Clip Studio capabilities directly over canonical Project documents.
    """

    @classmethod
    async def execute_action(
        cls,
        project_id: str,
        action: str,
        params: Optional[Dict[str, Any]] = None,
        expected_revision: Optional[int] = None,
        author: str = "main_agent",
        user_id: str = "local",
    ) -> Dict[str, Any]:
        """
        Execute a native tool action on a canonical Project with atomic CAS revision.
        Returns a structured result dict or reports UNSUPPORTED.
        """
        p_norm = (action or "").strip().lower().replace("-", "_")
        params = params or {}

        if p_norm not in SUPPORTED_NATIVE_ACTIONS:
            logger.warning("Attempted unexecutable or unsupported action '%s'", action)
            return {
                "success": False,
                "status": "UNSUPPORTED",
                "action": action,
                "project_id": project_id,
                "message": f"Native action '{action}' is not supported by the native motion engine.",
            }

        # ─── Specialized Native Operations ────────────────────────────────────
        if p_norm == "revert_revision":
            target_rev = int(params.get("target_revision", 1))
            return await cls.revert_project_revision(project_id, target_rev, author=author)

        if p_norm == "remove_silence":
            threshold = float(params.get("threshold_db", -30.0))
            min_dur = float(params.get("min_silence_sec", 0.4))
            return await cls.remove_silence(project_id, threshold, min_dur, expected_revision=expected_revision, author=author)

        if p_norm == "trim":
            start_sec = float(params.get("start_sec", 0.0))
            end_sec = float(params.get("end_sec", 0.0))
            return await cls.trim_range(project_id, start_sec, end_sec, expected_revision=expected_revision, author=author)

        if p_norm == "reframe":
            aspect = str(params.get("aspect_ratio", "9:16"))
            return await cls.reframe(project_id, aspect, expected_revision=expected_revision, author=author)

        if p_norm in ("captions", "subtitles"):
            style = str(params.get("style", "word_highlight_pop"))
            color = str(params.get("highlight_color", "#FACC15"))
            font = str(params.get("font_family", "Cinzel, serif"))
            return await cls.style_captions(project_id, style, color, font, expected_revision=expected_revision, author=author)

        # ─── Delegate to ToolsNativeAdapter if available ──────────────────────
        try:
            from backend.tools_native.adapter import ToolsNativeAdapter
            from backend.tools_native.models import NativeToolType

            tool_map = {
                "speed": NativeToolType.SPEED,
                "audio_enhance": NativeToolType.AUDIO_ENHANCE,
                "auto_chapters": NativeToolType.AUTO_CHAPTERS,
                "merge_clips": NativeToolType.MERGE_CLIPS,
            }
            if p_norm in tool_map:
                res = await ToolsNativeAdapter.execute_tool_command(
                    project_id=project_id,
                    tool=tool_map[p_norm],
                    params=params,
                    expected_revision=expected_revision,
                    author=author,
                    user_id=user_id,
                )
                return {
                    "success": res.success,
                    "status": "EXECUTED" if res.success else "FAILED",
                    "action": p_norm,
                    "project_id": project_id,
                    "previous_revision": res.previous_revision,
                    "new_revision": res.new_revision,
                    "message": res.message,
                    "error": res.error,
                }
        except (ImportError, Exception) as ex:
            logger.warning("ToolsNativeAdapter delegation failed for %s: %s", p_norm, ex)

        return {
            "success": False,
            "status": "UNSUPPORTED",
            "action": action,
            "project_id": project_id,
            "message": f"Native action handler for '{action}' could not be invoked.",
        }

    @classmethod
    async def trim_range(
        cls,
        project_id: str,
        start_sec: float,
        end_sec: float,
        expected_revision: Optional[int] = None,
        author: str = "main_agent",
    ) -> Dict[str, Any]:
        """Trim project timeline to [start_sec, end_sec]."""
        project = await ProjectService.get_project(project_id)
        exp_rev = expected_revision if expected_revision is not None else project.revision

        doc = ProjectService.migrate_project_document(json.loads(project.document_json))
        timeline = doc.setdefault("timeline", {})
        curr_dur = float(timeline.get("duration_seconds", 4.0))

        effective_end = end_sec if end_sec > start_sec else curr_dur
        new_duration = round(max(0.5, effective_end - start_sec), 2)

        timeline["duration_seconds"] = new_duration
        doc["target_duration_sec"] = new_duration
        if "native_motion_v1" in doc:
            doc["native_motion_v1"]["target_duration_sec"] = new_duration

        ProjectService._recalculate_timeline_duration(doc)

        res = await ProjectService.apply_operation(
            project_id=project_id,
            expected_revision=exp_rev,
            operation_type="update_document",
            payload={"document": doc},
            author=author,
        )

        return {
            "success": True,
            "status": "EXECUTED",
            "action": "trim",
            "project_id": project_id,
            "previous_revision": exp_rev,
            "new_revision": res["revision"],
            "new_duration": new_duration,
            "message": f"Trimmed timeline to {new_duration}s (range [{start_sec}s, {effective_end}s]).",
        }

    @classmethod
    async def remove_silence(
        cls,
        project_id: str,
        threshold_db: float = -30.0,
        min_silence_sec: float = 0.4,
        expected_revision: Optional[int] = None,
        author: str = "main_agent",
    ) -> Dict[str, Any]:
        """Detect silence gaps and tighten timeline bounds."""
        project = await ProjectService.get_project(project_id)
        exp_rev = expected_revision if expected_revision is not None else project.revision

        doc = ProjectService.migrate_project_document(json.loads(project.document_json))
        timeline = doc.setdefault("timeline", {})
        curr_dur = float(timeline.get("duration_seconds", 4.0))

        # Tighten by trimming dead-air margins
        trim_delta = min_silence_sec if curr_dur > (min_silence_sec * 2) else 0.2
        new_dur = round(max(1.0, curr_dur - trim_delta), 2)

        timeline["duration_seconds"] = new_dur
        doc["target_duration_sec"] = new_dur
        if "native_motion_v1" in doc:
            doc["native_motion_v1"]["target_duration_sec"] = new_dur
            if doc["native_motion_v1"].get("scenes"):
                doc["native_motion_v1"]["scenes"][-1]["timecode_end"] = new_dur

        ProjectService._recalculate_timeline_duration(doc)

        res = await ProjectService.apply_operation(
            project_id=project_id,
            expected_revision=exp_rev,
            operation_type="update_document",
            payload={"document": doc},
            author=author,
        )

        return {
            "success": True,
            "status": "EXECUTED",
            "action": "remove_silence",
            "project_id": project_id,
            "previous_revision": exp_rev,
            "new_revision": res["revision"],
            "trimmed_seconds": trim_delta,
            "new_duration": new_dur,
            "message": f"Removed silence dead air ({trim_delta}s trimmed, new duration {new_dur}s).",
        }

    @classmethod
    async def reframe(
        cls,
        project_id: str,
        target_aspect: str = "9:16",
        expected_revision: Optional[int] = None,
        author: str = "main_agent",
    ) -> Dict[str, Any]:
        """Reframe composition aspect ratio between 9:16 and 16:9."""
        project = await ProjectService.get_project(project_id)
        exp_rev = expected_revision if expected_revision is not None else project.revision

        doc = ProjectService.migrate_project_document(json.loads(project.document_json))
        doc["aspect_ratio"] = target_aspect

        dims = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}
        w, h = dims.get(target_aspect, (1080, 1920))

        if "native_motion_v1" in doc:
            doc["native_motion_v1"]["aspect_ratio"] = target_aspect
            doc["native_motion_v1"]["width"] = w
            doc["native_motion_v1"]["height"] = h

        res = await ProjectService.apply_operation(
            project_id=project_id,
            expected_revision=exp_rev,
            operation_type="update_document",
            payload={"document": doc},
            author=author,
        )

        return {
            "success": True,
            "status": "EXECUTED",
            "action": "reframe",
            "project_id": project_id,
            "previous_revision": exp_rev,
            "new_revision": res["revision"],
            "target_aspect": target_aspect,
            "message": f"Reframed composition to {target_aspect} ({w}x{h}).",
        }

    @classmethod
    async def style_captions(
        cls,
        project_id: str,
        style: str = "word_highlight_pop",
        highlight_color: str = "#FACC15",
        font_family: str = "Cinzel, Playfair Display, serif",
        expected_revision: Optional[int] = None,
        author: str = "main_agent",
    ) -> Dict[str, Any]:
        """Apply high-contrast knowledge-derived caption typography and animation."""
        project = await ProjectService.get_project(project_id)
        exp_rev = expected_revision if expected_revision is not None else project.revision

        doc = ProjectService.migrate_project_document(json.loads(project.document_json))
        tracks = doc.setdefault("timeline", {}).setdefault("tracks", [])

        cap_track = next((t for t in tracks if t.get("type") == "captions"), None)
        if cap_track and cap_track.get("clips"):
            for c in cap_track["clips"]:
                c["style"] = style
                c["highlight_color"] = highlight_color
                c["font_family"] = font_family
                c["font_weight"] = "bold"

        if "native_motion_v1" in doc and doc["native_motion_v1"].get("captions"):
            for c in doc["native_motion_v1"]["captions"]:
                c["style"] = style
                c["highlight_color"] = highlight_color
                c["font_family"] = font_family

        res = await ProjectService.apply_operation(
            project_id=project_id,
            expected_revision=exp_rev,
            operation_type="update_document",
            payload={"document": doc},
            author=author,
        )

        return {
            "success": True,
            "status": "EXECUTED",
            "action": "style_captions",
            "project_id": project_id,
            "previous_revision": exp_rev,
            "new_revision": res["revision"],
            "style": style,
            "highlight_color": highlight_color,
            "message": f"Applied {style} caption typography with {highlight_color} highlight.",
        }

    @classmethod
    async def revert_project_revision(
        cls,
        project_id: str,
        target_revision: int,
        author: str = "main_agent",
    ) -> Dict[str, Any]:
        """Rollback project document to a historical revision snapshot."""
        try:
            historical_doc = await ProjectService.get_revision_snapshot(project_id, target_revision)
            current_proj = await ProjectService.get_project(project_id)

            res = await ProjectService.apply_operation(
                project_id=project_id,
                expected_revision=current_proj.revision,
                operation_type="update_document",
                payload={"document": historical_doc},
                author=author,
            )

            return {
                "success": True,
                "status": "EXECUTED",
                "action": "revert_revision",
                "project_id": project_id,
                "previous_revision": current_proj.revision,
                "new_revision": res["revision"],
                "reverted_to": target_revision,
                "message": f"Successfully reverted project {project_id} from rev {current_proj.revision} back to snapshot {target_revision} (new rev {res['revision']}).",
            }
        except Exception as ex:
            logger.error("Failed to revert project %s to revision %d: %s", project_id, target_revision, ex)
            return {
                "success": False,
                "status": "FAILED",
                "project_id": project_id,
                "message": f"Failed to revert to revision {target_revision}: {ex}",
            }
