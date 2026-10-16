# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Chat Revision Delta Engine for Agent 1.
Operates on the SAME canonical Project document and timeline, applying atomic
CAS mutations driven by natural language user feedback while preserving context.
"""

from __future__ import annotations

import copy
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from backend.core.exceptions import ProjectError, ProjectNotFoundError, RevisionConflictError
from backend.services.project_service import ProjectService
from .security import KnowledgeSecurityValidator

logger = logging.getLogger(__name__)


class RevisionDeltaEngine:
    """
    Interprets natural-language revision feedback and mutates the SAME canonical project
    using atomic Compare-And-Swap (CAS) revisioning.
    """

    @classmethod
    async def apply_feedback_delta(
        cls,
        project_id: str,
        expected_revision: int,
        user_feedback: str,
        author: str = "main_agent",
    ) -> Dict[str, Any]:
        """
        Parse user feedback, apply deterministic delta to project timeline,
        and commit using ProjectService.apply_operation.
        """
        # 1. Security check
        is_safe, sec_err = KnowledgeSecurityValidator.sanitize_and_validate_prompt(user_feedback)
        if not is_safe:
            raise ValueError(f"Security validation failed on feedback: {sec_err}")

        # 2. Load existing project document
        project = await ProjectService.get_project(project_id)
        if project.revision != expected_revision:
            raise RevisionConflictError(
                current_revision=project.revision,
                expected_revision=expected_revision,
                message=f"CAS Conflict: Project is at revision {project.revision}, expected {expected_revision}.",
            )

        doc = ProjectService.migrate_project_document(json.loads(project.document_json))
        timeline = doc.setdefault("timeline", {})
        tracks = timeline.setdefault("tracks", [])

        feedback_lower = user_feedback.lower()
        applied_deltas: List[str] = []

        # ─── Delta 1: Aspect Ratio Change ─────────────────────────────────────
        if "16:9" in feedback_lower or "horizontal" in feedback_lower or "widescreen" in feedback_lower:
            doc["aspect_ratio"] = "16:9"
            if "native_motion_v1" in doc:
                doc["native_motion_v1"]["aspect_ratio"] = "16:9"
                doc["native_motion_v1"]["width"] = 1920
                doc["native_motion_v1"]["height"] = 1080
            applied_deltas.append("reframe_to_16_9")
        elif "9:16" in feedback_lower or "vertical" in feedback_lower:
            doc["aspect_ratio"] = "9:16"
            if "native_motion_v1" in doc:
                doc["native_motion_v1"]["aspect_ratio"] = "9:16"
                doc["native_motion_v1"]["width"] = 1080
                doc["native_motion_v1"]["height"] = 1920
            applied_deltas.append("reframe_to_9_16")

        # ─── Delta 2: Cinematic Typography / Second Title Styling ──────────────
        if "cinematic" in feedback_lower or "title" in feedback_lower or "typography" in feedback_lower:
            overlay_track = next((t for t in tracks if t.get("type") == "overlay"), None)
            if overlay_track and overlay_track.get("clips"):
                # If "second title" is mentioned, target the second clip if available
                target_idx = 1 if ("second" in feedback_lower and len(overlay_track["clips"]) > 1) else 0
                clip = overlay_track["clips"][target_idx]
                props = clip.setdefault("properties", {})
                props["font_family"] = "Cinzel, Playfair Display, serif"
                props["font_size_pt"] = props.get("font_size_pt", 48) + 6
                props["letter_spacing_px"] = 4
                props["color"] = "#F8FAFC"
                props["shadow"] = "0px 4px 20px rgba(0, 0, 0, 0.85)"
                props["easing"] = "ease_in_out_sine"
                applied_deltas.append(f"styled_clip_{clip.get('id')}_cinematic")

            if "native_motion_v1" in doc and doc["native_motion_v1"].get("scenes"):
                scenes = doc["native_motion_v1"]["scenes"]
                target_sc = scenes[1] if ("second" in feedback_lower and len(scenes) > 1) else scenes[0]
                for el in target_sc.get("elements", []):
                    if "title" in el.get("element_type", "") or "statement" in el.get("element_type", ""):
                        el.setdefault("properties", {})["cinematic_mode"] = True
                        el["properties"]["letter_spacing_px"] = 4
                        el["properties"]["easing"] = "ease_in_out_sine"
                        applied_deltas.append(f"styled_motion_element_{el.get('element_id')}")

        # ─── Delta 3: Remove Dead Air / Trim Tail ──────────────────────────────
        if "dead air" in feedback_lower or "trim" in feedback_lower or "tighten" in feedback_lower:
            curr_dur = float(timeline.get("duration_seconds", 4.0))
            trim_amount = 0.5 if curr_dur > 2.5 else 0.2
            new_dur = round(max(1.5, curr_dur - trim_amount), 2)
            timeline["duration_seconds"] = new_dur
            doc["target_duration_sec"] = new_dur
            if "native_motion_v1" in doc:
                doc["native_motion_v1"]["target_duration_sec"] = new_dur
                if doc["native_motion_v1"].get("scenes"):
                    doc["native_motion_v1"]["scenes"][-1]["timecode_end"] = new_dur
            applied_deltas.append(f"trimmed_dead_air_to_{new_dur}s")

        # ─── Delta 4: Synchronize Captions / Emphasized Words ──────────────────
        if "synchronize" in feedback_lower or "caption" in feedback_lower or "words" in feedback_lower:
            cap_track = next((t for t in tracks if t.get("type") == "captions"), None)
            if cap_track and cap_track.get("clips"):
                for c in cap_track["clips"]:
                    c["style"] = "word_highlight_pop_synced"
                    c["highlight_color"] = "#FACC15"  # high-visibility amber/gold
                    c["font_weight"] = "bold"
                applied_deltas.append("synchronized_word_highlight_captions")

            if "native_motion_v1" in doc and doc["native_motion_v1"].get("captions"):
                for c in doc["native_motion_v1"]["captions"]:
                    c["style"] = "word_highlight_pop_synced"
                    c["highlight_color"] = "#FACC15"
                applied_deltas.append("synced_native_motion_captions")

        # ─── Delta 5: Explicit Duration Request ────────────────────────────────
        dur_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:seconds?|secs?|s)\b", user_feedback, re.IGNORECASE)
        if dur_match and not ("dead air" in feedback_lower):
            target_sec = float(dur_match.group(1))
            if 1.0 <= target_sec <= 300.0:
                timeline["duration_seconds"] = target_sec
                doc["target_duration_sec"] = target_sec
                if "native_motion_v1" in doc:
                    doc["native_motion_v1"]["target_duration_sec"] = target_sec
                applied_deltas.append(f"set_exact_duration_{target_sec}s")

        # Recalculate timeline duration and bounds
        ProjectService._recalculate_timeline_duration(doc)

        # Record revision metadata
        doc["last_feedback_delta"] = {
            "feedback": user_feedback,
            "applied_deltas": applied_deltas,
            "base_revision": expected_revision,
        }

        # Atomic CAS update using canonical ProjectService.apply_operation
        res = await ProjectService.apply_operation(
            project_id=project_id,
            expected_revision=expected_revision,
            operation_type="update_document",
            payload={"document": doc},
            author=author,
        )

        logger.info(
            "Applied revision delta on project %s: revision %d -> %d; deltas: %s",
            project_id,
            expected_revision,
            res["revision"],
            applied_deltas,
        )

        return {
            "project_id": project_id,
            "base_revision": expected_revision,
            "resulting_revision": res["revision"],
            "applied_deltas": applied_deltas,
            "document": doc,
        }
