# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Native Command Executor: Executes canonical commands over ProjectRevision CAS documents atomically.
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.oaas_editor_native.models import (
    NativeCommandRequest,
    NativeCommandResult,
    NativeCommandType,
)

logger = logging.getLogger(__name__)


class CASConcurrencyError(Exception):
    """Raised when target_revision_id does not match the active document revision."""
    pass


class CommandExecutionError(Exception):
    """Raised when command execution fails due to invalid parameters or missing targets."""
    pass


class NativeCommandExecutor:
    """
    Atomic command executor modifying immutable project revision documents.
    All edits (formerly in Clip Studio, Tools, or Motion) operate on the EXACT SAME
    document and revision chain, preventing secondary state forks.
    """

    @classmethod
    def compute_document_hash(cls, document: Dict[str, Any]) -> str:
        serialized = json.dumps(document, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def execute(
        cls,
        current_document: Dict[str, Any],
        current_revision_id: int,
        request: NativeCommandRequest,
    ) -> tuple[Dict[str, Any], NativeCommandResult]:
        """
        Execute command on current_document:
        1. Validate CAS revision concurrency
        2. Deep-copy document for immutability
        3. Dispatch to specific command mutation handler
        4. Recompute canonical document hash and increment revision
        5. Return new document and execution receipt
        """
        if request.target_revision_id != current_revision_id:
            raise CASConcurrencyError(
                f"CAS Concurrency Rejection: target revision {request.target_revision_id} "
                f"does not match current revision {current_revision_id}."
            )

        new_doc = copy.deepcopy(current_document)
        action = request.action
        params = request.parameters

        try:
            if action == NativeCommandType.SPLIT:
                cls._handle_split(new_doc, params)
            elif action == NativeCommandType.TRIM:
                cls._handle_trim(new_doc, params)
            elif action == NativeCommandType.SLIP:
                cls._handle_slip(new_doc, params)
            elif action == NativeCommandType.RIPPLE_DELETE:
                cls._handle_ripple_delete(new_doc, params)
            elif action == NativeCommandType.DELETE_CLIP:
                cls._handle_delete_clip(new_doc, params)
            elif action == NativeCommandType.CROP:
                cls._handle_crop(new_doc, params)
            elif action == NativeCommandType.REFRAME:
                cls._handle_reframe(new_doc, params)
            elif action == NativeCommandType.TRANSFORM:
                cls._handle_transform(new_doc, params)
            elif action == NativeCommandType.SPEED:
                cls._handle_speed(new_doc, params)
            elif action == NativeCommandType.CAPTIONS_EDIT:
                cls._handle_captions_edit(new_doc, params)
            elif action == NativeCommandType.REMOVE_SILENCE:
                cls._handle_remove_silence(new_doc, params)
            elif action == NativeCommandType.VARIABLE_MUTATE:
                cls._handle_variable_mutate(new_doc, params)
            elif action == NativeCommandType.GRAPHIC_INSERT:
                cls._handle_graphic_insert(new_doc, params)
            elif action == NativeCommandType.WATERMARK:
                cls._handle_watermark(new_doc, params)
            elif action == NativeCommandType.RANGE_SELECT:
                cls._handle_range_select(new_doc, params)
            elif action == NativeCommandType.METADATA:
                cls._handle_metadata(new_doc, params)
            else:
                # Other operations record execution into document metadata
                cls._handle_generic_tool(new_doc, action.value, params)

        except Exception as e:
            logger.error("NativeCommandExecutor failed: %s", str(e), exc_info=True)
            return current_document, NativeCommandResult(
                command_id=request.command_id,
                success=False,
                project_id=request.project_id,
                previous_revision_id=current_revision_id,
                error_code="EXECUTION_FAILED",
                error_message=str(e),
            )

        new_rev_id = current_revision_id + 1
        new_doc["revision_number"] = new_rev_id
        new_hash = cls.compute_document_hash(new_doc)
        new_doc["document_sha256"] = new_hash

        result = NativeCommandResult(
            command_id=request.command_id,
            success=True,
            project_id=request.project_id,
            previous_revision_id=current_revision_id,
            new_revision_id=new_rev_id,
            new_document_hash=new_hash,
            metadata={"action": action.value, "parameters": params},
        )
        return new_doc, result

    # ── Command Mutation Handlers ─────────────────────────────────────────────

    @classmethod
    def _find_clip(cls, doc: Dict[str, Any], clip_id: str) -> Optional[Dict[str, Any]]:
        tracks = doc.get("tracks", [])
        for t in tracks:
            for c in t.get("clips", []):
                if c.get("id") == clip_id:
                    return c
        return None

    @classmethod
    def _handle_split(cls, doc: Dict[str, Any], params: Dict[str, Any]) -> None:
        clip_id = params.get("clip_id")
        split_time = params.get("split_time", 0.0)
        tracks = doc.get("tracks", [])

        for t in tracks:
            clips = t.get("clips", [])
            for i, c in enumerate(clips):
                if c.get("id") == clip_id:
                    orig_duration = c.get("duration", 5.0)
                    if split_time <= 0 or split_time >= orig_duration:
                        raise CommandExecutionError(f"Split time {split_time} must be between 0 and {orig_duration}.")

                    # Update first clip
                    c["duration"] = split_time
                    # Create second clip
                    second_clip = copy.deepcopy(c)
                    second_clip["id"] = f"{clip_id}_split_{uuid4().hex[:6]}"
                    second_clip["start_time"] = c.get("start_time", 0.0) + split_time
                    second_clip["source_offset"] = c.get("source_offset", 0.0) + split_time
                    second_clip["duration"] = orig_duration - split_time
                    clips.insert(i + 1, second_clip)
                    return
        raise CommandExecutionError(f"Clip '{clip_id}' not found.")

    @classmethod
    def _handle_trim(cls, doc: Dict[str, Any], params: Dict[str, Any]) -> None:
        clip_id = params.get("clip_id")
        trim_start = params.get("trim_start", 0.0)
        trim_end = params.get("trim_end", 0.0)
        clip = cls._find_clip(doc, clip_id)
        if not clip:
            raise CommandExecutionError(f"Clip '{clip_id}' not found.")
        clip["trim_start"] = trim_start
        clip["trim_end"] = trim_end
        clip["duration"] = max(0.1, clip.get("duration", 5.0) - trim_start - trim_end)

    @classmethod
    def _handle_slip(cls, doc: Dict[str, Any], params: Dict[str, Any]) -> None:
        clip_id = params.get("clip_id")
        offset_delta = params.get("offset_delta", 0.0)
        clip = cls._find_clip(doc, clip_id)
        if not clip:
            raise CommandExecutionError(f"Clip '{clip_id}' not found.")
        clip["source_offset"] = clip.get("source_offset", 0.0) + offset_delta

    @classmethod
    def _handle_ripple_delete(cls, doc: Dict[str, Any], params: Dict[str, Any]) -> None:
        clip_id = params.get("clip_id")
        for t in doc.get("tracks", []):
            clips = t.get("clips", [])
            for i, c in enumerate(clips):
                if c.get("id") == clip_id:
                    deleted_dur = c.get("duration", 0.0)
                    clips.pop(i)
                    # Shift subsequent clips left
                    for next_clip in clips[i:]:
                        next_clip["start_time"] = max(0.0, next_clip.get("start_time", 0.0) - deleted_dur)
                    return
        raise CommandExecutionError(f"Clip '{clip_id}' not found.")

    @classmethod
    def _handle_delete_clip(cls, doc: Dict[str, Any], params: Dict[str, Any]) -> None:
        clip_id = params.get("clip_id")
        for t in doc.get("tracks", []):
            t["clips"] = [c for c in t.get("clips", []) if c.get("id") != clip_id]

    @classmethod
    def _handle_crop(cls, doc: Dict[str, Any], params: Dict[str, Any]) -> None:
        clip_id = params.get("clip_id")
        clip = cls._find_clip(doc, clip_id)
        if not clip:
            raise CommandExecutionError(f"Clip '{clip_id}' not found.")
        clip["crop"] = {
            "aspect_ratio": params.get("aspect_ratio", "9:16"),
            "x": params.get("x", 0),
            "y": params.get("y", 0),
            "width": params.get("width", 100),
            "height": params.get("height", 100),
        }

    @classmethod
    def _handle_reframe(cls, doc: Dict[str, Any], params: Dict[str, Any]) -> None:
        aspect = params.get("aspect_ratio", "9:16")
        doc["aspect_ratio"] = aspect
        clip_id = params.get("clip_id")
        if clip_id:
            clip = cls._find_clip(doc, clip_id)
            if clip:
                clip["reframe"] = {"mode": "auto_center", "aspect_ratio": aspect}

    @classmethod
    def _handle_transform(cls, doc: Dict[str, Any], params: Dict[str, Any]) -> None:
        clip_id = params.get("clip_id")
        clip = cls._find_clip(doc, clip_id)
        if not clip:
            raise CommandExecutionError(f"Clip '{clip_id}' not found.")
        clip["transform"] = {
            "scale": params.get("scale", 1.0),
            "rotation": params.get("rotation", 0),
            "position_x": params.get("position_x", 0),
            "position_y": params.get("position_y", 0),
        }

    @classmethod
    def _handle_speed(cls, doc: Dict[str, Any], params: Dict[str, Any]) -> None:
        clip_id = params.get("clip_id")
        speed = params.get("speed", 1.0)
        clip = cls._find_clip(doc, clip_id)
        if not clip:
            raise CommandExecutionError(f"Clip '{clip_id}' not found.")
        clip["speed"] = speed
        orig_dur = clip.get("duration", 5.0)
        clip["duration"] = orig_dur / speed if speed > 0 else orig_dur

    @classmethod
    def _handle_captions_edit(cls, doc: Dict[str, Any], params: Dict[str, Any]) -> None:
        overrides = params.get("overrides", {})
        if "caption_overrides" not in doc:
            doc["caption_overrides"] = {}
        doc["caption_overrides"].update(overrides)

    @classmethod
    def _handle_remove_silence(cls, doc: Dict[str, Any], params: Dict[str, Any]) -> None:
        threshold_db = params.get("threshold_db", -30.0)
        min_duration = params.get("min_duration", 0.5)
        doc["silence_settings"] = {
            "threshold_db": threshold_db,
            "min_duration": min_duration,
            "applied": True,
        }

    @classmethod
    def _handle_variable_mutate(cls, doc: Dict[str, Any], params: Dict[str, Any]) -> None:
        key = params.get("key")
        value = params.get("value")
        if not key:
            raise CommandExecutionError("Variable key is required.")
        if "variables" not in doc:
            doc["variables"] = {}
        doc["variables"][key] = value

    @classmethod
    def _handle_graphic_insert(cls, doc: Dict[str, Any], params: Dict[str, Any]) -> None:
        block_id = params.get("block_id")
        if not block_id:
            raise CommandExecutionError("block_id is required.")
        if "blocks" not in doc:
            doc["blocks"] = []
        new_block = {
            "id": f"{block_id}_{uuid4().hex[:6]}",
            "block_slug": block_id,
            "start_time": params.get("start_time", 0.0),
            "duration": params.get("duration", 5.0),
            "variables": params.get("variables", {}),
        }
        doc["blocks"].append(new_block)

    @classmethod
    def _handle_watermark(cls, doc: Dict[str, Any], params: Dict[str, Any]) -> None:
        doc["watermark"] = {
            "image_path": params.get("image_path", ""),
            "position": params.get("position", "bottom_right"),
            "opacity": params.get("opacity", 0.8),
        }

    @classmethod
    def _handle_range_select(cls, doc: Dict[str, Any], params: Dict[str, Any]) -> None:
        doc["bench_ranges"] = {
            "in_point": params.get("in_point", 0.0),
            "out_point": params.get("out_point", 10.0),
        }

    @classmethod
    def _handle_metadata(cls, doc: Dict[str, Any], params: Dict[str, Any]) -> None:
        if "metadata" not in doc:
            doc["metadata"] = {}
        doc["metadata"].update(params)

    @classmethod
    def _handle_generic_tool(cls, doc: Dict[str, Any], action_name: str, params: Dict[str, Any]) -> None:
        if "tool_actions" not in doc:
            doc["tool_actions"] = []
        doc["tool_actions"].append({"action": action_name, "params": params})
