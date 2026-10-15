# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Typed domain models for Wave 19 Native Tools.
Provides strict schemas for all 21 legacy tools executing as native Motion actions
and Main Agent-callable commands with CAS ProjectRevision mutation.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class NativeToolType(str, Enum):
    """The 21 original tools recovered from ViralMint-Legado."""
    CAPTIONS = "captions"
    REFRAME = "reframe"
    AUDIO_ENHANCE = "audio-enhance"
    WATERMARK = "watermark"
    MERGE_CLIPS = "merge-clips"
    REMOVE_SILENCE = "remove-silence"
    TRANSLATE = "translate"
    HOOK_ANALYSIS = "hook-analysis"
    ENHANCE_PROMPT = "enhance-prompt"
    VOICEOVER = "voiceover"
    TRANSFORM = "transform"
    MUSIC_VISUALIZER = "music-visualizer"
    GIF = "gif"
    SPEED = "speed"
    METADATA = "metadata"
    AUTO_CHAPTERS = "auto-chapters"
    TRIM = "trim"
    SUBTITLES = "subtitles"
    COMPRESS = "compress"
    CROP = "crop"
    AUTO_ZOOM = "auto-zoom"
    
    # Ingestion capability (Decision #5: Chat-first agent-operated, no consumer form)
    VIDEO_DOWNLOAD = "video-download"


class ToolExecutionMode(str, Enum):
    """Execution mode of the native tool."""
    INSPECTOR = "inspector"        # Contextual affordance in Refine Right Inspector
    AGENT_COMMAND = "agent_command"# Natural-language Main Agent goal execution
    CAS_MUTATION = "cas_mutation"  # Direct atomic document revision mutation
    EXPORT_PIPE = "export_pipe"    # Render pipeline parameter configuration


class ToolDescriptor(BaseModel):
    """Metadata specification for a native tool capability."""
    slug: NativeToolType
    title: str
    category: str
    description: str
    legacy_endpoint: str
    legacy_frontend: str
    primary_mode: ToolExecutionMode
    cas_mutation_key: str
    required_params: List[str] = Field(default_factory=list)
    default_params: Dict[str, Any] = Field(default_factory=dict)
    is_agent_callable: bool = True
    is_inspector_exposed: bool = True


class ToolActionRequest(BaseModel):
    """Standardized request envelope for executing a native tool."""
    project_id: str
    tool_type: NativeToolType
    params: Dict[str, Any] = Field(default_factory=dict)
    expected_revision: Optional[int] = None
    idempotency_key: Optional[str] = None
    author: str = "main_agent"
    user_id: str = "local"


class ToolActionResult(BaseModel):
    """Standardized result envelope for an executed native tool."""
    success: bool
    tool_type: NativeToolType
    project_id: str
    previous_revision: int
    new_revision: int
    document_delta: Dict[str, Any] = Field(default_factory=dict)
    artifact_path: Optional[str] = None
    execution_time_ms: float = 0.0
    message: str = ""
    error: Optional[str] = None
