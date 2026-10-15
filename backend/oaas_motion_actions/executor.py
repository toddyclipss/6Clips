# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Native Motion Action Executor.

Applies typed editor commands directly against canonical ProjectService documents
using atomic Compare-And-Swap (CAS) revisioning, optimistic concurrency controls,
and deterministic pre/postcondition validation.
"""

from __future__ import annotations

import copy
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from backend.core.exceptions import (
    IdempotencyConflictError,
    ProjectError,
    ProjectNotFoundError,
    RevisionConflictError,
)
from backend.oaas_outcomes.block_selector import BlockSelector
from backend.services.project_service import ProjectService
from .capability_catalog import CapabilityDiscovery
from .models import (
    ActionExecutionStatus,
    AudioAdjustActionParams,
    CaptionItem,
    CaptionsEditActionParams,
    CropActionParams,
    DeleteClipActionParams,
    ExportActionParams,
    GraphicInsertActionParams,
    MotionActionEnvelope,
    MotionActionResult,
    MotionActionType,
    RangeSelectActionParams,
    ReframeActionParams,
    RippleDeleteActionParams,
    SceneDetectActionParams,
    SpeechTranscribeActionParams,
    SpeedActionParams,
    SplitActionParams,
    TrimActionParams,
)

logger = logging.getLogger(__name__)


class NativeMotionActionExecutor:
    """Dispatches typed editing actions over canonical ProjectService documents."""

    @classmethod
    async def execute_action(cls, envelope: MotionActionEnvelope) -> MotionActionResult:
        """
        Validate, prepare, and execute a typed MotionActionEnvelope over a versioned project.
        Enforces atomic CAS concurrency, idempotency, and pre/postconditions.
        """
        # 1. Capability support verification
        supported, cap_reason = CapabilityDiscovery.is_action_supported(envelope.action_type)
        if not supported:
            return MotionActionResult(
                action_type=envelope.action_type,
                project_id=envelope.project_id,
                base_revision=envelope.expected_revision,
                resulting_revision=envelope.expected_revision,
                applied=False,
                status=ActionExecutionStatus.CAPABILITY_UNSUPPORTED,
                detail=f"Action '{envelope.action_type.value}' is unsupported: {cap_reason}",
            )

        # 2. Parameter schema validation
        validated_params, err = cls._validate_parameters(envelope.action_type, envelope.params)
        if err:
            return MotionActionResult(
                action_type=envelope.action_type,
                project_id=envelope.project_id,
                base_revision=envelope.expected_revision,
                resulting_revision=envelope.expected_revision,
                applied=False,
                status=ActionExecutionStatus.PRECONDITION_FAILED,
                detail=f"Parameter validation failed: {err}",
            )

        # 3. Project existence and concurrency check
        try:
            project = await ProjectService.get_project(envelope.project_id)
        except ProjectNotFoundError:
            return MotionActionResult(
                action_type=envelope.action_type,
                project_id=envelope.project_id,
                base_revision=envelope.expected_revision,
                resulting_revision=envelope.expected_revision,
                applied=False,
                status=ActionExecutionStatus.PRECONDITION_FAILED,
                detail=f"Project '{envelope.project_id}' not found.",
            )

        if project.revision != envelope.expected_revision and not envelope.idempotency_key:
            return MotionActionResult(
                action_type=envelope.action_type,
                project_id=envelope.project_id,
                base_revision=envelope.expected_revision,
                resulting_revision=project.revision,
                applied=False,
                status=ActionExecutionStatus.CAS_CONFLICT,
                detail=f"CAS revision mismatch: project has revision {project.revision}, expected {envelope.expected_revision}.",
            )

        # 4. Construct operation payload and apply through ProjectService
        try:
            op_type, op_payload, affected_clips = cls._build_operation(
                envelope.action_type,
                validated_params,
                project_doc=json.loads(project.document_json),
            )
        except Exception as ex:
            return MotionActionResult(
                action_type=envelope.action_type,
                project_id=envelope.project_id,
                base_revision=envelope.expected_revision,
                resulting_revision=envelope.expected_revision,
                applied=False,
                status=ActionExecutionStatus.PRECONDITION_FAILED,
                detail=f"Precondition failed: {str(ex)}",
            )

        # 5. Apply atomic CAS mutation through ProjectService
        try:
            res = await ProjectService.apply_operation(
                project_id=envelope.project_id,
                expected_revision=envelope.expected_revision,
                operation_type=op_type,
                payload=op_payload,
                idempotency_key=envelope.idempotency_key,
                author=envelope.author,
            )

            is_replay = res.get("idempotent_replay", False)
            resulting_rev = res.get("revision", envelope.expected_revision + 1)
            doc_result = res.get("document", {})

            summary = {
                "tracks_count": len(doc_result.get("timeline", {}).get("tracks", [])),
                "total_duration": doc_result.get("timeline", {}).get("duration_seconds", 0.0),
                "aspect_ratio": doc_result.get("aspect_ratio", "9:16"),
            }

            status = ActionExecutionStatus.IDEMPOTENT_REPLAY if is_replay else ActionExecutionStatus.SUCCESS
            detail = f"Action '{envelope.action_type.value}' successfully {'replayed' if is_replay else 'applied'}."

            return MotionActionResult(
                action_type=envelope.action_type,
                project_id=envelope.project_id,
                base_revision=envelope.expected_revision,
                resulting_revision=resulting_rev,
                applied=res.get("applied", False),
                idempotent_replay=is_replay,
                affected_clip_ids=affected_clips,
                document_summary=summary,
                status=status,
                detail=detail,
            )

        except RevisionConflictError as rce:
            return MotionActionResult(
                action_type=envelope.action_type,
                project_id=envelope.project_id,
                base_revision=envelope.expected_revision,
                resulting_revision=rce.current_revision,
                applied=False,
                status=ActionExecutionStatus.CAS_CONFLICT,
                detail=f"Revision conflict: {str(rce)}",
            )
        except IdempotencyConflictError as ice:
            return MotionActionResult(
                action_type=envelope.action_type,
                project_id=envelope.project_id,
                base_revision=envelope.expected_revision,
                resulting_revision=ice.existing_revision,
                applied=False,
                status=ActionExecutionStatus.CAS_CONFLICT,
                detail=f"Idempotency conflict: {str(ice)}",
            )
        except Exception as ex:
            logger.exception("Error executing motion action %s on %s: %s", envelope.action_type, envelope.project_id, ex)
            return MotionActionResult(
                action_type=envelope.action_type,
                project_id=envelope.project_id,
                base_revision=envelope.expected_revision,
                resulting_revision=envelope.expected_revision,
                applied=False,
                status=ActionExecutionStatus.EXECUTION_ERROR,
                detail=f"Execution error: {str(ex)}",
            )

    @classmethod
    def _validate_parameters(
        cls, action_type: MotionActionType, raw_params: Dict[str, Any]
    ) -> Tuple[Optional[BaseModel], Optional[str]]:
        """Validate raw dictionary against typed Pydantic parameter model."""
        schema_map = {
            MotionActionType.TRIM: TrimActionParams,
            MotionActionType.SPLIT: SplitActionParams,
            MotionActionType.RANGE_SELECT: RangeSelectActionParams,
            MotionActionType.RIPPLE_DELETE: RippleDeleteActionParams,
            MotionActionType.DELETE_CLIP: DeleteClipActionParams,
            MotionActionType.REFRAME: ReframeActionParams,
            MotionActionType.CROP: CropActionParams,
            MotionActionType.SPEED: SpeedActionParams,
            MotionActionType.SCENE_DETECT: SceneDetectActionParams,
            MotionActionType.SPEECH_TRANSCRIBE: SpeechTranscribeActionParams,
            MotionActionType.CAPTIONS_EDIT: CaptionsEditActionParams,
            MotionActionType.AUDIO_ADJUST: AudioAdjustActionParams,
            MotionActionType.GRAPHIC_INSERT: GraphicInsertActionParams,
            MotionActionType.EXPORT: ExportActionParams,
        }

        model_cls = schema_map.get(action_type)
        if not model_cls:
            return None, f"No validation schema registered for action '{action_type}'."

        try:
            validated = model_cls.model_validate(raw_params)
            return validated, None
        except Exception as e:
            return None, str(e)

    @classmethod
    def _build_operation(
        cls,
        action_type: MotionActionType,
        params: Any,
        project_doc: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any], List[str]]:
        """
        Translate the typed Motion Action into the underlying ProjectService operation.
        Returns (operation_type, payload, affected_clip_ids).
        """
        tracks = project_doc.get("timeline", {}).get("tracks", [])

        if action_type == MotionActionType.TRIM:
            p: TrimActionParams = params
            clip, _ = cls._find_clip(tracks, p.clip_id)
            if not clip:
                raise ValueError(f"Clip '{p.clip_id}' not found in project timeline.")

            patch = {"trim_start": p.trim_start}
            if p.trim_end is not None:
                patch["trim_end"] = p.trim_end
                patch["duration"] = round(p.trim_end - p.trim_start, 3)

            return "update_clip", {"clip_id": p.clip_id, "patch": patch}, [p.clip_id]

        elif action_type == MotionActionType.SPLIT:
            p: SplitActionParams = params
            clip, track = cls._find_clip(tracks, p.clip_id)
            if not clip:
                raise ValueError(f"Clip '{p.clip_id}' not found in project timeline.")

            clip_start = float(clip.get("start", 0.0))
            clip_dur = float(clip.get("duration", 0.0))
            clip_end = clip_start + clip_dur

            if p.split_time <= clip_start or p.split_time >= clip_end:
                raise ValueError(
                    f"split_time ({p.split_time}s) must fall strictly inside clip boundary [{clip_start}s, {clip_end}s]."
                )

            # Mutate document using split logic
            new_doc = copy.deepcopy(project_doc)
            trks = new_doc.get("timeline", {}).get("tracks", [])
            target_clip, target_track = cls._find_clip(trks, p.clip_id)

            split_offset = p.split_time - clip_start
            first_dur = split_offset
            second_dur = clip_dur - split_offset

            # Clip 1 takes first part
            target_clip["duration"] = round(first_dur, 3)
            orig_trim_start = float(target_clip.get("trim_start", 0.0))
            target_clip["trim_end"] = round(orig_trim_start + first_dur, 3)

            # Clip 2 takes second part
            new_clip_id = f"{p.clip_id}_split_{uuid4().hex[:6]}"
            second_clip = copy.deepcopy(target_clip)
            second_clip["id"] = new_clip_id
            second_clip["start"] = round(p.split_time, 3)
            second_clip["duration"] = round(second_dur, 3)
            second_clip["trim_start"] = round(orig_trim_start + first_dur, 3)
            if "trim_end" in clip:
                second_clip["trim_end"] = clip["trim_end"]

            # Insert second clip right after first
            clip_idx = target_track["clips"].index(target_clip)
            target_track["clips"].insert(clip_idx + 1, second_clip)

            return "update_document", {"document": new_doc}, [p.clip_id, new_clip_id]

        elif action_type == MotionActionType.RANGE_SELECT:
            p: RangeSelectActionParams = params
            return "set_bench_ranges", {
                "source_id": p.source_id,
                "ranges": [{"in": p.in_point, "out": p.out_point, "label": p.label or "selection"}],
            }, []

        elif action_type == MotionActionType.RIPPLE_DELETE:
            p: RippleDeleteActionParams = params
            clip, track = cls._find_clip(tracks, p.clip_id)
            if not clip:
                raise ValueError(f"Clip '{p.clip_id}' not found in project timeline.")

            deleted_dur = float(clip.get("duration", 0.0))
            deleted_start = float(clip.get("start", 0.0))

            new_doc = copy.deepcopy(project_doc)
            trks = new_doc.get("timeline", {}).get("tracks", [])
            _, target_track = cls._find_clip(trks, p.clip_id)

            # Remove clip and shift all subsequent clips left
            target_track["clips"] = [c for c in target_track["clips"] if c.get("id") != p.clip_id]
            affected = [p.clip_id]
            for c in target_track["clips"]:
                c_start = float(c.get("start", 0.0))
                if c_start > deleted_start:
                    c["start"] = max(0.0, round(c_start - deleted_dur, 3))
                    affected.append(c["id"])

            return "update_document", {"document": new_doc}, affected

        elif action_type == MotionActionType.DELETE_CLIP:
            p: DeleteClipActionParams = params
            return "remove_clip", {"clip_id": p.clip_id}, [p.clip_id]

        elif action_type == MotionActionType.REFRAME:
            p: ReframeActionParams = params
            return "patch_document", {
                "patch": {
                    "aspect_ratio": p.aspect_ratio,
                    "reframe_preset": p.preset,
                }
            }, []

        elif action_type == MotionActionType.CROP:
            p: CropActionParams = params
            target_clip_id = p.clip_id
            if not target_clip_id:
                # Find first video clip
                for t in tracks:
                    for c in t.get("clips", []):
                        if c.get("type", "video") == "video":
                            target_clip_id = c.get("id")
                            break
                    if target_clip_id:
                        break
            if not target_clip_id:
                raise ValueError("No video clip found to crop.")

            crop_patch = {
                "crop": {
                    "x": p.crop_x,
                    "y": p.crop_y,
                    "w": p.crop_w,
                    "h": p.crop_h,
                }
            }
            return "update_clip", {"clip_id": target_clip_id, "patch": crop_patch}, [target_clip_id]

        elif action_type == MotionActionType.SPEED:
            p: SpeedActionParams = params
            clip, _ = cls._find_clip(tracks, p.clip_id)
            if not clip:
                raise ValueError(f"Clip '{p.clip_id}' not found in project timeline.")

            orig_dur = float(clip.get("duration", 1.0))
            new_dur = round(orig_dur / p.speed_factor, 3)
            patch = {
                "speed": p.speed_factor,
                "duration": new_dur,
                "maintain_pitch": p.maintain_pitch,
            }
            return "update_clip", {"clip_id": p.clip_id, "patch": patch}, [p.clip_id]

        elif action_type == MotionActionType.CAPTIONS_EDIT:
            p: CaptionsEditActionParams = params
            formatted_clips = []
            for idx, c in enumerate(p.captions):
                formatted_clips.append({
                    "id": f"cap_{idx}_{uuid4().hex[:6]}",
                    "type": "caption",
                    "start": c.start,
                    "duration": round(c.end - c.start, 3),
                    "text": c.text,
                    "style": p.style,
                    "font_size": p.font_size,
                    "color": p.color,
                })
            return "set_captions", {"captions": formatted_clips}, [c["id"] for c in formatted_clips]

        elif action_type == MotionActionType.AUDIO_ADJUST:
            p: AudioAdjustActionParams = params
            patch: Dict[str, Any] = {}
            if p.volume is not None:
                patch["volume"] = p.volume
            if p.mute is not None:
                patch["muted"] = p.mute
            if p.remove_audio is not None:
                patch["strip_audio"] = p.remove_audio

            # Find audio track or apply to main track
            target_track = next((t for t in tracks if t.get("type") == "audio"), None)
            if not target_track and tracks:
                target_track = tracks[0]

            new_doc = copy.deepcopy(project_doc)
            if target_track:
                for t in new_doc.get("timeline", {}).get("tracks", []):
                    if t.get("id") == target_track.get("id"):
                        t.update(patch)
                        break

            return "update_document", {"document": new_doc}, []

        elif action_type == MotionActionType.GRAPHIC_INSERT:
            p: GraphicInsertActionParams = params
            # Validate block operability
            if not BlockSelector.is_operable(p.block_id):
                avail, reason = BlockSelector.check_block_availability(p.block_id)
                raise ValueError(f"Block '{p.block_id}' is not operable ({reason}).")

            block_payload = {
                "block_id": p.block_id,
                "track_id": p.track_id or "track_overlay",
                "timecode_start": p.timecode_start,
                "duration": p.duration,
                "variables": p.variables or {},
                "title": p.block_id.replace("-", " ").title(),
            }
            if p.layer_order is not None:
                block_payload["layer_order"] = p.layer_order

            return "add_block", block_payload, [p.block_id]

        elif action_type == MotionActionType.EXPORT:
            p: ExportActionParams = params
            patch = {
                "export_settings": {
                    "format": p.format,
                    "resolution": p.resolution,
                    "fps": p.fps,
                    "quality": p.quality,
                }
            }
            return "patch_document", {"patch": patch}, []

        elif action_type in (MotionActionType.SCENE_DETECT, MotionActionType.SPEECH_TRANSCRIBE):
            # Annotate document with editorial analysis markers
            return "patch_document", {
                "patch": {
                    f"{action_type.value}_analysis": params.model_dump(),
                }
            }, []

        raise ValueError(f"Unhandled action type: '{action_type}'.")

    @classmethod
    def _find_clip(cls, tracks: List[Dict[str, Any]], clip_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Find clip by ID across all timeline tracks."""
        for t in tracks:
            for c in t.get("clips", []):
                if c.get("id") == clip_id:
                    return c, t
        return None, None
