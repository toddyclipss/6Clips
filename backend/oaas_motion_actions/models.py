# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Typed Command Models and Parameter Schemas for Native Motion Editor Actions.

Defines deterministic command types, rigorous schema validations, pre/postcondition
guarantees, and result models for operations executed directly over the canonical
ProjectService and ProjectRevision CAS document.
"""

from __future__ import annotations

from enum import Enum
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field, field_validator, model_validator


class MotionActionType(str, Enum):
    """Canonical set of native editing actions unifying legacy Tools and Clip Studio workflows."""
    TRIM = "trim"
    SPLIT = "split"
    RANGE_SELECT = "range_select"
    RIPPLE_DELETE = "ripple_delete"
    DELETE_CLIP = "delete_clip"
    REFRAME = "reframe"
    CROP = "crop"
    SPEED = "speed"
    SCENE_DETECT = "scene_detect"
    SPEECH_TRANSCRIBE = "speech_transcribe"
    CAPTIONS_EDIT = "captions_edit"
    AUDIO_ADJUST = "audio_adjust"
    GRAPHIC_INSERT = "graphic_insert"
    EXPORT = "export"


class ActionExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    CAPABILITY_UNSUPPORTED = "CAPABILITY_UNSUPPORTED"
    PRECONDITION_FAILED = "PRECONDITION_FAILED"
    CAS_CONFLICT = "CAS_CONFLICT"
    IDEMPOTENT_REPLAY = "IDEMPOTENT_REPLAY"
    EXECUTION_ERROR = "EXECUTION_ERROR"


# ─── Strongly-Typed Action Parameter Schemas ───────────────────────────────────

class TrimActionParams(BaseModel):
    """Parameters for non-destructive trimming of source clip time window."""
    clip_id: str = Field(..., min_length=1, description="Target clip ID to trim.")
    trim_start: float = Field(0.0, ge=0.0, description="Start offset in source media (seconds).")
    trim_end: Optional[float] = Field(None, gt=0.0, description="End offset in source media (seconds).")

    @model_validator(mode="after")
    def validate_bounds(self) -> TrimActionParams:
        if self.trim_end is not None and self.trim_end <= self.trim_start:
            raise ValueError(f"trim_end ({self.trim_end}s) must be strictly greater than trim_start ({self.trim_start}s).")
        return self


class SplitActionParams(BaseModel):
    """Parameters for splitting a single clip at playhead time into two adjacent clips."""
    clip_id: str = Field(..., min_length=1, description="Clip ID to split.")
    split_time: float = Field(..., gt=0.0, description="Timeline split position in seconds.")
    track_id: Optional[str] = Field(None, description="Optional track ID containing the clip.")


class RangeSelectActionParams(BaseModel):
    """Parameters for filmstrip / bench in-and-out sub-clip range selection."""
    source_id: str = Field(..., min_length=1, description="Source media identifier.")
    in_point: float = Field(0.0, ge=0.0, description="In-point mark (seconds).")
    out_point: float = Field(..., gt=0.0, description="Out-point mark (seconds).")
    label: Optional[str] = Field(None, description="Optional range descriptor or hook tag.")

    @model_validator(mode="after")
    def validate_range(self) -> RangeSelectActionParams:
        if self.out_point <= self.in_point:
            raise ValueError(f"out_point ({self.out_point}s) must be greater than in_point ({self.in_point}s).")
        return self


class RippleDeleteActionParams(BaseModel):
    """Parameters for deleting a clip and shifting all subsequent clips left to eliminate gaps."""
    clip_id: str = Field(..., min_length=1, description="Target clip ID to ripple-delete.")
    track_id: Optional[str] = Field(None, description="Optional track ID.")


class DeleteClipActionParams(BaseModel):
    """Parameters for deleting a clip without shifting subsequent clips."""
    clip_id: str = Field(..., min_length=1, description="Target clip ID to delete.")
    track_id: Optional[str] = Field(None, description="Optional track ID.")


class ReframeActionParams(BaseModel):
    """Parameters for vertical / horizontal composition reframing with safe-zone presets."""
    aspect_ratio: str = Field("9:16", description="Target composition aspect ratio (9:16, 16:9, 1:1, 4:5).")
    preset: str = Field("center_crop", description="Reframing preset (center_crop, gameplay_reticle, hud_aware_blur).")

    @field_validator("aspect_ratio")
    @classmethod
    def validate_aspect(cls, v: str) -> str:
        valid_aspects = {"9:16", "16:9", "1:1", "4:5"}
        if v not in valid_aspects:
            raise ValueError(f"aspect_ratio '{v}' not supported. Must be one of {valid_aspects}.")
        return v


class CropActionParams(BaseModel):
    """Parameters for spatial bounding box cropping of visual media."""
    clip_id: Optional[str] = Field(None, description="Clip ID to crop; defaults to active/main video clip.")
    crop_x: int = Field(0, ge=0, description="X coordinate of top-left crop box.")
    crop_y: int = Field(0, ge=0, description="Y coordinate of top-left crop box.")
    crop_w: int = Field(..., gt=0, description="Width of crop box in pixels.")
    crop_h: int = Field(..., gt=0, description="Height of crop box in pixels.")


class SpeedActionParams(BaseModel):
    """Parameters for speed retiming of clip playback rate."""
    clip_id: str = Field(..., min_length=1, description="Target clip ID.")
    speed_factor: float = Field(..., gt=0.0, le=16.0, description="Speed multiplier (0.1x to 16.0x).")
    maintain_pitch: bool = Field(True, description="Whether to pitch-shift audio back to original frequency.")


class SceneDetectActionParams(BaseModel):
    """Parameters for automated scene change detection and marker insertion."""
    video_path: Optional[str] = Field(None, description="Path to video file or uses active project media.")
    threshold: float = Field(27.0, ge=1.0, le=100.0, description="Scene detection intensity threshold.")
    min_scene_duration_sec: float = Field(1.0, ge=0.1, description="Minimum duration for a detected scene.")


class SpeechTranscribeActionParams(BaseModel):
    """Parameters for speech-to-text transcript extraction."""
    video_path: Optional[str] = Field(None, description="Path to video/audio media.")
    language: str = Field("en", description="Spoken language code.")
    model_size: str = Field("base", description="Whisper model tier (tiny, base, small).")


class CaptionItem(BaseModel):
    """Individual subtitle / caption segment."""
    start: float = Field(..., ge=0.0, description="Start timestamp in seconds.")
    end: float = Field(..., gt=0.0, description="End timestamp in seconds.")
    text: str = Field(..., min_length=1, description="Subtitle text.")

    @model_validator(mode="after")
    def validate_bounds(self) -> CaptionItem:
        if self.end <= self.start:
            raise ValueError(f"Caption end ({self.end}s) must be greater than start ({self.start}s).")
        return self


class CaptionsEditActionParams(BaseModel):
    """Parameters for creating, editing, or styling captions track."""
    captions: List[CaptionItem] = Field(..., description="List of caption segments.")
    style: Optional[str] = Field("standard", description="Caption layout style (standard, pop, word_highlight).")
    font_size: Optional[int] = Field(24, ge=10, le=120, description="Caption font size in points.")
    color: Optional[str] = Field("#FFFFFF", description="Hex text color code.")


class AudioAdjustActionParams(BaseModel):
    """Parameters for audio level adjustment, muting, or removal."""
    track_id: Optional[str] = Field(None, description="Audio track ID; defaults to main audio.")
    volume: Optional[float] = Field(None, ge=0.0, le=10.0, description="Volume multiplier (0.0 to 10.0).")
    mute: Optional[bool] = Field(None, description="Set track mute status.")
    remove_audio: Optional[bool] = Field(None, description="Completely strip audio streams.")
    normalize: Optional[bool] = Field(None, description="Apply standard loudness normalization.")


class GraphicInsertActionParams(BaseModel):
    """Parameters for inserting a verified HyperFrames donor block into composition."""
    block_id: str = Field(..., min_length=1, description="Verified operable HyperFrames donor block ID.")
    track_id: Optional[str] = Field("track_overlay", description="Target overlay track ID.")
    timecode_start: float = Field(0.0, ge=0.0, description="Timeline insertion start time.")
    duration: float = Field(5.0, gt=0.0, description="Duration of the motion graphic in seconds.")
    variables: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Customizable block variables.")
    layer_order: Optional[int] = Field(None, description="Z-index layer order.")


class ExportActionParams(BaseModel):
    """Parameters for physical MP4 rendering and export of canonical project."""
    format: str = Field("mp4", description="Output container format (mp4).")
    resolution: str = Field("1080x1920", description="Output pixel dimensions (WIDTHxHEIGHT).")
    fps: int = Field(30, ge=15, le=60, description="Output frame rate.")
    quality: str = Field("high", description="Encoding quality preset (low, medium, high).")


# ─── Command Envelope and Execution Result ────────────────────────────────────

class MotionActionEnvelope(BaseModel):
    """Typed execution envelope submitted to the native motion actions dispatcher."""
    action_type: MotionActionType = Field(..., description="The typed native motion action to execute.")
    project_id: str = Field(..., min_length=1, description="Target Project ID.")
    expected_revision: int = Field(..., ge=1, description="Expected base revision for atomic CAS check.")
    params: Dict[str, Any] = Field(default_factory=dict, description="Raw or parsed action parameters.")
    idempotency_key: Optional[str] = Field(None, description="Optional idempotency key to prevent double execution.")
    user_id: str = Field("local", description="Authorizing user ID.")
    author: str = Field("main_agent", description="Actor applying the action (main_agent, user).")


class MotionActionResult(BaseModel):
    """Authoritative result returned by NativeMotionActionExecutor."""
    action_type: MotionActionType
    project_id: str
    base_revision: int
    resulting_revision: int
    applied: bool
    idempotent_replay: bool = False
    affected_clip_ids: List[str] = Field(default_factory=list)
    document_summary: Dict[str, Any] = Field(default_factory=dict)
    status: ActionExecutionStatus = ActionExecutionStatus.SUCCESS
    detail: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
