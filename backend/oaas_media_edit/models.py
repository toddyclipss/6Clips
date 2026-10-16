# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Typed Contracts and Data Models for Source-Backed Media Editing and Lineage.

Establishes strict, typed specifications for EDIT_EXISTING_VIDEO operations:
- Source video ingestion and stream analysis
- Bounded timecode trimming and reframe transformations
- Canonical ProjectRevision mutation tracking
- Cryptographic and visual perceptual lineage verification
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field


class EditIntentType(str, Enum):
    """Classification of video creation/editing intent."""
    EDIT_EXISTING_VIDEO = "EDIT_EXISTING_VIDEO"
    GENERATE_NEW_VIDEO = "GENERATE_NEW_VIDEO"


class SourceStreamInfo(BaseModel):
    """Stream-level metadata extracted via ffprobe."""
    model_config = ConfigDict(extra="ignore")

    index: int
    codec_name: str
    codec_type: str  # "video" or "audio"
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    channels: Optional[int] = None
    sample_rate: Optional[int] = None
    duration_sec: Optional[float] = None
    bit_rate: Optional[int] = None


class SourceMediaAnalysis(BaseModel):
    """In-depth forensic and visual analysis of an authentic input source video."""
    model_config = ConfigDict(extra="ignore")

    file_path: str
    sha256_hash: str
    file_size_bytes: int
    duration_sec: float
    aspect_ratio: str  # e.g. "16:9", "9:16", "1:1"
    resolution: Tuple[int, int]  # (width, height)
    fps: float
    has_video: bool = True
    has_audio: bool = False
    video_codec: str
    audio_codec: Optional[str] = None
    streams: List[SourceStreamInfo] = Field(default_factory=list)

    # Frame-level authenticity metrics (sampled at equidistant time offsets)
    sampled_timestamps: List[float] = Field(default_factory=list)
    sampled_luminance: List[float] = Field(default_factory=list)
    sampled_stddev: List[float] = Field(default_factory=list)
    motion_deltas: List[float] = Field(default_factory=list)
    is_authentic_footage: bool = True
    is_static_black: bool = False

    # Audio & speech inspection
    audio_channels: Optional[int] = None
    audio_sample_rate: Optional[int] = None
    detected_language: Optional[str] = None
    word_timestamps: List[Dict[str, Any]] = Field(default_factory=list)
    analyzed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EditExistingMediaContract(BaseModel):
    """
    Typed adapter contract for editing an existing acquired video asset.
    Governs source file provenance, requested cuts, reframing, and language.
    """
    model_config = ConfigDict(extra="ignore")

    original_url: str = Field(..., description="Original remote URL (preserves exact casing and ID)")
    asset_id: str = Field(default_factory=lambda: f"asset-{uuid4().hex[:10]}")
    file_path: str = Field(..., description="Physical path to authentic acquired media")
    source_sha256: str = Field(..., description="SHA-256 fingerprint of the acquired source file")
    source_duration: float = Field(..., gt=0.0)
    source_resolution: Tuple[int, int] = Field(..., description="(width, height)")
    source_fps: float = Field(default=30.0)
    has_audio: bool = True
    audio_codec: Optional[str] = None

    # Temporal edits and cuts: list of [start_sec, end_sec] intervals
    source_intervals: List[Tuple[float, float]] = Field(
        default_factory=lambda: [(0.0, 5.0)],
        description="Explicit source [in, out] timecode intervals to include in the edit."
    )
    target_duration: float = Field(default=5.0, gt=0.0, le=120.0)
    target_aspect_ratio: str = Field(default="9:16", description="Target deliverable aspect ratio ('9:16', '16:9', '1:1')")
    target_language: str = Field(default="en", description="Target language directive ('en', 'pt', 'auto')")
    reframe_mode: str = Field(default="vertical_blur_fill", description="Reframing technique: 'vertical_blur_fill', 'crop_center', 'fit'")

    # Captions & overlays
    caption_timings: List[Dict[str, Any]] = Field(default_factory=list)
    caption_style: str = "viral"
    export_profile: str = "mp4_h264_aac"

    # Project linkage
    project_id: Optional[str] = None
    user_id: str = "local"
    run_id: Optional[str] = None
    lineage_metadata: Dict[str, Any] = Field(default_factory=dict)


class SourceLineageVerification(BaseModel):
    """
    Deterministic predicate verifying that rendered output is physically
    derived from the genuine source asset and recorded on the canonical timeline.
    """
    model_config = ConfigDict(extra="ignore")

    is_verified: bool
    source_sha256: str
    rendered_sha256: str
    timeline_has_source_clip: bool
    timeline_clip_id: Optional[str] = None
    timeline_asset_id: Optional[str] = None
    trim_start: float = 0.0
    trim_end: float = 0.0
    rendered_duration: float = 0.0
    duration_matches_target: bool = False
    visual_frames_authentic: bool = False
    visual_correlation_score: float = 0.0
    frame_luminance_mean: float = 0.0
    frame_stddev_mean: float = 0.0
    not_static_black: bool = False
    not_title_card_only: bool = False
    audio_intact: bool = False
    rejection_reason: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class EditExecutionResult(BaseModel):
    """Outcome envelope returned by EditExistingMediaAdapter."""
    model_config = ConfigDict(extra="ignore")

    success: bool
    project_id: str
    revision_id: int
    asset_id: str
    clip_id: str
    rendered_mp4_path: Optional[str] = None
    rendered_sha256: Optional[str] = None
    rendered_duration_sec: Optional[float] = None
    rendered_resolution: Optional[Tuple[int, int]] = None
    source_intervals: List[Tuple[float, float]] = Field(default_factory=list)
    target_aspect_ratio: str = "9:16"
    lineage_verified: bool = False
    lineage_verification: Optional[SourceLineageVerification] = None
    blocker_code: Optional[str] = None
    blocker_reason: Optional[str] = None
    completed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
