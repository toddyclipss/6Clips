# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Typed Command Models and Schemas for Native Clip Studio Operations.
Unifies legacy Clip Studio capabilities into Motion's single timeline,
single player, and ProjectRevision CAS document.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field, field_validator, model_validator


class ClipStudioActionType(str, Enum):
    """Canonical action types covering all 34 legacy Clip Studio capabilities."""
    SOURCE_SELECT = "source_select"
    SOURCE_PREVIEW = "source_preview"
    FILMSTRIP_GENERATE = "filmstrip_generate"
    FRAME_EXTRACT = "frame_extract"
    SPEECH_TRANSCRIBE = "speech_transcribe"
    SEGMENTS_CACHE = "segments_cache"
    SUGGEST_CLIPS_AI = "suggest_clips_ai"
    PLATFORM_BIAS = "platform_bias"
    GENRE_BIAS = "genre_bias"
    USER_QUERY_FILTER = "user_query_filter"
    BENCH_RANGE_SET = "bench_range_set"
    BENCH_RANGE_SNAP = "bench_range_snap"
    BENCH_RANGE_DEDUP = "bench_range_dedup"
    BENCH_TOPIC_DEDUP = "bench_topic_dedup"
    EXTRACT_CLIPS_AI = "extract_clips_ai"
    EXTRACT_CLIPS_MANUAL = "extract_clips_manual"
    DURATION_FALLBACK = "duration_fallback"
    SILENCE_REMOVE = "silence_remove"
    SEGMENT_RETIME = "segment_retime"
    REFRAME_VERTICAL = "reframe_vertical"
    CAPTIONS_BURN = "captions_burn"
    CAPTIONS_STYLE = "captions_style"
    EMOJI_DENSITY = "emoji_density"
    METADATA_GENERATE = "metadata_generate"
    VIRALITY_SCORE_BREAKDOWN = "virality_score_breakdown"
    THUMBNAIL_GENERATE = "thumbnail_generate"
    THUMBNAIL_REGENERATE = "thumbnail_regenerate"
    CLIP_METADATA_EDIT = "clip_metadata_edit"
    CLIP_STREAM = "clip_stream"
    CLIP_STREAM_ASPECT = "clip_stream_aspect"
    CLIP_DELETE = "clip_delete"
    TIMELINE_PROJECT_MAP = "timeline_project_map"
    PROJECT_REOPEN = "project_reopen"
    PROJECT_EXPORT_MP4 = "project_export_mp4"


class ClipRange(BaseModel):
    """Normalized time range for proposed or manual clip."""
    id: str = Field(default_factory=lambda: f"range_{uuid4().hex[:8]}")
    start: float = Field(..., ge=0.0, description="Start timestamp in seconds.")
    end: float = Field(..., gt=0.0, description="End timestamp in seconds.")
    label: Optional[str] = Field(None, description="Optional label or title.")
    score: Optional[float] = Field(None, ge=1.0, le=10.0, description="Virality score (1-10).")
    hook_score: Optional[float] = Field(None, ge=1.0, le=10.0, description="Hook quality score (1-10).")
    hook_type: Optional[str] = Field("question", description="Detected hook type.")
    reason: Optional[str] = Field(None, description="Reasoning for highlight selection.")
    score_breakdown: Optional[Dict[str, float]] = Field(
        default_factory=lambda: {
            "hook": 8.5,
            "flow": 8.0,
            "value": 8.2,
            "trend": 7.8,
            "shareability": 8.4,
        }
    )

    @model_validator(mode="after")
    def validate_duration(self) -> ClipRange:
        if self.end <= self.start:
            raise ValueError(f"End time ({self.end}s) must be greater than start ({self.start}s).")
        if (self.end - self.start) < 3.0:
            raise ValueError(f"Clip range duration ({self.end - self.start:.1f}s) must be at least 3.0 seconds.")
        return self


class SuggestClipsParams(BaseModel):
    """Parameters for AI-driven clip proposal ('Ask AI')."""
    source_id: str = Field(..., min_length=1, description="Source video identifier.")
    max_clips: int = Field(3, ge=1, le=10, description="Maximum number of candidate clips to suggest.")
    min_duration: Optional[int] = Field(15, ge=5, description="Minimum clip duration in seconds.")
    max_duration: Optional[int] = Field(60, ge=10, description="Maximum clip duration in seconds.")
    target_platform: Optional[str] = Field(None, description="Target platform bias (tiktok, youtube_shorts, reels, linkedin, twitter).")
    genre: Optional[str] = Field(None, description="Genre bias (podcast, interview, tutorial, gaming, etc.).")
    user_query: Optional[str] = Field(None, description="Free-form natural language query filter.")
    whisper_quality: str = Field("balanced", description="Whisper model tier (fast, balanced, accurate, best).")
    force_retranscribe: bool = Field(False, description="Whether to ignore cached transcript.")


class ExtractClipsParams(BaseModel):
    """Parameters for batch clip extraction (AI or manual mode)."""
    source_id: str = Field(..., min_length=1, description="Source video identifier.")
    mode: str = Field("ai", description="Extraction mode ('ai' or 'manual').")
    time_ranges: Optional[List[Dict[str, Any]]] = Field(None, description="Verbatim ranges when mode='manual'.")
    max_clips: Optional[int] = Field(3, ge=1, le=99, description="Target clip count.")
    caption_style: str = Field("viral", description="Caption typography preset.")
    emoji_style: str = Field("moderate", description="AutoEmoji density (none, minimal, moderate, heavy).")
    whisper_quality: str = Field("balanced", description="Whisper model quality.")
    force_retranscribe: bool = Field(False, description="Bypass transcript cache.")
    remove_silence: bool = Field(False, description="Cut dead air pauses > 0.5s.")
    force_vertical: bool = Field(False, description="Reframe to 9:16 portrait with blur-fill.")
    min_duration: Optional[int] = Field(None, description="Min clip length in seconds.")
    max_duration: Optional[int] = Field(None, description="Max clip length in seconds.")
    user_query: Optional[str] = Field(None, description="Topic search filter.")
    target_platform: Optional[str] = Field(None, description="Platform ranker bias.")
    genre: Optional[str] = Field(None, description="Genre ranker bias.")
    allow_duration_fallback: bool = Field(True, description="Slice evenly if AI finds 0 clips.")


class MapClipToProjectParams(BaseModel):
    """Parameters for mapping an extracted clip into Motion's ProjectRevision timeline."""
    project_id: str = Field(..., min_length=1, description="Target Project ID.")
    source_id: str = Field(..., min_length=1, description="Source media asset ID.")
    clip_range: ClipRange = Field(..., description="Clip time window.")
    aspect_ratio: str = Field("9:16", description="Target composition aspect ratio.")
    captions: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Subtitle segments.")
    caption_style: str = Field("viral", description="Caption layout preset.")
    title: Optional[str] = Field(None, description="Title for clip item.")
    track_id: Optional[str] = Field("track_video_main", description="Target media track ID.")


class ClipDeliverable(BaseModel):
    """Physical rendered media deliverable output for an extracted clip."""
    id: str = Field(default_factory=lambda: f"deliv_{uuid4().hex[:8]}")
    clip_id: str
    title: str
    video_path: str
    thumbnail_path: Optional[str] = None
    duration_seconds: float
    aspect_ratio: str
    virality_score: float
    score_breakdown: Dict[str, float]
    ffprobe_meta: Dict[str, Any]
    sha256: str


class ClipStudioActionResult(BaseModel):
    """Result returned by ClipStudioNativeAdapter operations."""
    status: str = Field("SUCCESS", description="Operation status (SUCCESS, ERROR, CAS_CONFLICT).")
    action_type: ClipStudioActionType
    project_id: Optional[str] = None
    base_revision: Optional[int] = None
    resulting_revision: Optional[int] = None
    ranges: List[ClipRange] = Field(default_factory=list)
    deliverables: List[ClipDeliverable] = Field(default_factory=list)
    detail: str = ""
    error: Optional[str] = None
