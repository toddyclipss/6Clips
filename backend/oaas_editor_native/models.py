# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Domain models for Native Motion Graphics Editor Commands, Capabilities, and CAS Revisions.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class NativeCommandType(str, Enum):
    """Canonical commands unifying legacy Tools, Clip Studio, and Motion operations."""
    # Timeline & Trimming
    SPLIT = "SPLIT"
    TRIM = "TRIM"
    SLIP = "SLIP"
    RIPPLE_DELETE = "RIPPLE_DELETE"
    DELETE_CLIP = "DELETE_CLIP"
    SNAPPING = "SNAPPING"
    RANGE_SELECT = "RANGE_SELECT"

    # Layout & Video Transformation
    CROP = "CROP"
    REFRAME = "REFRAME"
    TRANSFORM = "TRANSFORM"
    SPEED = "SPEED"
    AUTO_ZOOM = "AUTO_ZOOM"
    WATERMARK = "WATERMARK"
    COMPRESS = "COMPRESS"
    GIF = "GIF"

    # Audio & Speech
    AUDIO_ENHANCE = "AUDIO_ENHANCE"
    REMOVE_SILENCE = "REMOVE_SILENCE"
    VOICEOVER = "VOICEOVER"
    MUSIC_VISUALIZER = "MUSIC_VISUALIZER"
    SUBTITLES = "SUBTITLES"
    CAPTIONS_EDIT = "CAPTIONS_EDIT"
    TRANSLATE = "TRANSLATE"

    # Intelligence & Analysis
    HOOK_ANALYSIS = "HOOK_ANALYSIS"
    ENHANCE_PROMPT = "ENHANCE_PROMPT"
    AUTO_CHAPTERS = "AUTO_CHAPTERS"
    METADATA = "METADATA"
    VIRALITY_SCORE = "VIRALITY_SCORE"

    # Project & Composition
    MERGE_CLIPS = "MERGE_CLIPS"
    GRAPHIC_INSERT = "GRAPHIC_INSERT"
    VARIABLE_MUTATE = "VARIABLE_MUTATE"
    EXPORT = "EXPORT"


class ParityStatus(str, Enum):
    """Implementation parity status for the 30 legacy workflows."""
    NATIVE_END_TO_END = "NATIVE_END_TO_END"
    NATIVE_PARTIAL = "NATIVE_PARTIAL"
    LEGACY_COMPAT_ONLY = "LEGACY_COMPAT_ONLY"
    BLOCKED = "BLOCKED"
    NOT_TESTED = "NOT_TESTED"


class CapabilityDescriptor(BaseModel):
    """Metadata describing a legacy capability mapped into native Motion."""
    capability_id: str
    legacy_source_name: str
    legacy_source_route: str
    native_command: NativeCommandType
    native_ui_location: str  # e.g., "Refine Inspector: Tools Tab", "Timeline Workspace"
    parity_status: ParityStatus
    cas_document_target: str  # e.g., "tracks.clips", "variables", "metadata"
    supports_undo_redo: bool = True
    description: str = ""


class NativeCommandRequest(BaseModel):
    """Request payload for executing a canonical command on a ProjectRevision."""
    command_id: str = Field(default_factory=lambda: f"cmd_{uuid4().hex[:12]}")
    project_id: str
    target_revision_id: int
    action: NativeCommandType
    parameters: Dict[str, Any] = Field(default_factory=dict)
    user_id: str = "local"


class NativeCommandResult(BaseModel):
    """Immutable result of a canonical command execution."""
    command_id: str
    success: bool
    project_id: str
    previous_revision_id: int
    new_revision_id: Optional[int] = None
    new_document_hash: Optional[str] = None
    output_artifact_path: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
