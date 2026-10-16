# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Strict, typed, secure Pydantic schema for native_motion_v1.

Defines the complete composition specification for the 6Clips Knowledge-to-Motion
Engine. Rejects unsafe executable code, invalid timebases, offscreen layouts, and
unbounded parameters.
"""

from __future__ import annotations

import re
import math
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator


# ============================================================================
# Security & Sanitization Constants
# ============================================================================

# Dangerous patterns forbidden in any text or property field
UNSAFE_PATTERNS = [
    re.compile(r"<script[\s>]", re.IGNORECASE),
    re.compile(r"</script>", re.IGNORECASE),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"on\w+\s*=", re.IGNORECASE),  # e.g., onerror=, onload=
    re.compile(r"eval\s*\(", re.IGNORECASE),
    re.compile(r"exec\s*\(", re.IGNORECASE),
    re.compile(r"__import__", re.IGNORECASE),
    re.compile(r"document\.cookie", re.IGNORECASE),
    re.compile(r"window\.localStorage", re.IGNORECASE),
    re.compile(r"window\.sessionStorage", re.IGNORECASE),
    re.compile(r"fetch\s*\(", re.IGNORECASE),
    re.compile(r"XMLHttpRequest", re.IGNORECASE),
    re.compile(r"WebSocket", re.IGNORECASE),
    re.compile(r"child_process", re.IGNORECASE),
    re.compile(r"require\s*\(", re.IGNORECASE),
    re.compile(r"import\s*\(", re.IGNORECASE),
]

COLOR_REGEX = re.compile(
    r"^(#[0-9a-fA-F]{3,8}|rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+(\s*,\s*[\d.]+\s*)?\)|hsla?\(\s*[\d.]+\s*,\s*[\d.]+%?\s*,\s*[\d.]+%?(\s*,\s*[\d.]+\s*)?\)|transparent|currentColor|[a-zA-Z]+)$"
)

SAFE_FONTS = {
    "Inter", "Roboto", "Montserrat", "Playfair Display", "Space Grotesk",
    "JetBrains Mono", "Poppins", "Outfit", "Oswald", "Cinzel", "Arial",
    "Helvetica", "Georgia", "Courier New", "sans-serif", "serif", "monospace"
}


def sanitize_string(val: str, field_name: str = "field") -> str:
    """Ensure string does not contain malicious script or executable injection patterns."""
    if not isinstance(val, str):
        return str(val)
    for pattern in UNSAFE_PATTERNS:
        if pattern.search(val):
            raise ValueError(f"Unsafe executable pattern detected in {field_name}: {val[:60]!r}")
    return val


# ============================================================================
# Knowledge Provenance & Intent Models
# ============================================================================

class KnowledgeRef(BaseModel):
    """Immutable provenance citation referencing HyperFrames/6Clips technique docs."""
    doc_id: str = Field(..., description="Unique document ID (e.g. 'doc-kinetic-typog-01')")
    source_path: str = Field(..., description="Source path within knowledge corpus")
    content_hash: str = Field(..., description="SHA-256 fingerprint of the source document")
    section: str = Field(..., description="Specific section or technique heading cited")
    principles: List[str] = Field(default_factory=list, description="Design principles applied")

    @field_validator("doc_id", "source_path", "section")
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        return sanitize_string(v)


class CreativeBrief(BaseModel):
    """High-level creative intent supplied by the user or Main Agent."""
    topic: str = Field(..., min_length=1, max_length=500)
    intent: str = Field("explain", description="Creative goal: explain, hype, cinematic, data, story")
    tone: str = Field("dynamic", description="Visual tone: minimal, tech, luxurious, punchy, editorial")
    target_audience: Optional[str] = Field("general", max_length=200)
    raw_prompt: Optional[str] = Field(None, max_length=2000)

    @field_validator("topic", "intent", "tone", "target_audience", "raw_prompt")
    @classmethod
    def sanitize(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return sanitize_string(v)


class Constraints(BaseModel):
    """Production runtime and platform constraints."""
    aspect_ratio: Literal["9:16", "16:9", "1:1", "4:5"] = "9:16"
    max_duration_seconds: float = Field(60.0, gt=0, le=300.0)
    target_fps: int = Field(30, ge=15, le=60)
    render_quality: Literal["draft", "standard", "high"] = "standard"
    max_particle_count: int = Field(1000, le=2000)
    offline_only: bool = Field(True, description="Enforce 0 network egress during playback/render")


class SafeZoneSpec(BaseModel):
    """UI safe area margins (percentage 0.0-1.0 from edges)."""
    top: float = Field(0.12, ge=0.0, le=0.4)
    bottom: float = Field(0.18, ge=0.0, le=0.4)
    left: float = Field(0.08, ge=0.0, le=0.3)
    right: float = Field(0.08, ge=0.0, le=0.3)


# ============================================================================
# Typography & Visual Token Models
# ============================================================================

class TypographySpec(BaseModel):
    """Strictly styled typography specification using legally usable safe fonts."""
    font_family: str = Field("Inter, sans-serif")
    font_size: float = Field(48.0, gt=4.0, le=300.0)
    font_weight: Union[int, str] = Field(700)
    letter_spacing: float = Field(0.0, ge=-10.0, le=50.0)
    line_height: float = Field(1.2, ge=0.5, le=3.0)
    text_align: Literal["left", "center", "right"] = "center"
    fill: str = Field("#FFFFFF")
    stroke: Optional[str] = Field(None)
    stroke_width: float = Field(0.0, ge=0.0, le=20.0)
    shadow: Optional[str] = Field(None)

    @field_validator("fill", "stroke")
    @classmethod
    def validate_color(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = sanitize_string(v)
        if not COLOR_REGEX.match(v):
            raise ValueError(f"Invalid CSS color: {v}")
        return v

    @field_validator("font_family")
    @classmethod
    def validate_font(cls, v: str) -> str:
        v = sanitize_string(v)
        # Check against safe font list tokens
        tokens = [t.strip().strip("'\"") for t in v.split(",")]
        has_safe = any(t in SAFE_FONTS for t in tokens)
        if not has_safe:
            # Fall back to safe sans-serif stack
            return "Inter, sans-serif"
        return v


# ============================================================================
# Keyframe & Animation Curves
# ============================================================================

EasingCurve = Literal[
    "linear",
    "ease_in",
    "ease_out",
    "ease_in_out",
    "back_out",
    "elastic_out",
    "bounce_out",
    "power2_in_out",
    "power4_out",
    "steps_4",
]


class KeyframeSpec(BaseModel):
    """Interpolation keyframe at a specified time offset within an element."""
    time: float = Field(..., ge=0.0, description="Offset in seconds from element start")
    properties: Dict[str, Union[float, str, int, bool]] = Field(
        ..., description="Target property values at this keyframe"
    )
    easing: EasingCurve = "ease_out"

    @field_validator("properties")
    @classmethod
    def validate_props(cls, props: Dict[str, Any]) -> Dict[str, Any]:
        sanitized = {}
        for k, v in props.items():
            k_clean = sanitize_string(str(k))
            if isinstance(v, str):
                v = sanitize_string(v)
            sanitized[k_clean] = v
        return sanitized


# ============================================================================
# Captions & Word-Level Timestamps
# ============================================================================

class WordTimestampSpec(BaseModel):
    """Single speech word with authentic audio alignment."""
    word: str = Field(..., min_length=1, max_length=100)
    start: float = Field(..., ge=0.0)
    end: float = Field(..., ge=0.0)
    confidence: Optional[float] = Field(1.0, ge=0.0, le=1.0)
    emphasis: bool = Field(False)
    color_override: Optional[str] = Field(None)

    @field_validator("word")
    @classmethod
    def clean_word(cls, v: str) -> str:
        return sanitize_string(v)

    @model_validator(mode="after")
    def validate_time(self) -> WordTimestampSpec:
        if self.end < self.start:
            raise ValueError(f"Word end time ({self.end}) must be >= start time ({self.start})")
        return self


# ============================================================================
# Composition Primitive Configurations
# ============================================================================

class TextConfig(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    typography: TypographySpec = Field(default_factory=TypographySpec)
    max_width: Optional[float] = Field(None, gt=0)
    text_transform: Literal["none", "uppercase", "lowercase", "capitalize"] = "none"
    mask_clip_path: Optional[str] = Field(None)

    @field_validator("content")
    @classmethod
    def clean_content(cls, v: str) -> str:
        return sanitize_string(v)


class ShapeConfig(BaseModel):
    shape_type: Literal["rect", "circle", "rounded_rect", "polygon", "path"] = "rounded_rect"
    fill: str = Field("#2563EB")
    stroke: Optional[str] = Field(None)
    stroke_width: float = Field(0.0, ge=0.0, le=50.0)
    corner_radius: float = Field(16.0, ge=0.0, le=500.0)
    path_data: Optional[str] = Field(None, description="SVG path definition d=...")

    @field_validator("fill", "stroke")
    @classmethod
    def clean_color(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = sanitize_string(v)
        if not COLOR_REGEX.match(v):
            raise ValueError(f"Invalid shape color: {v}")
        return v

    @field_validator("path_data")
    @classmethod
    def clean_path(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return sanitize_string(v)


class GradientStop(BaseModel):
    color: str = Field(...)
    position: float = Field(..., ge=0.0, le=1.0)

    @field_validator("color")
    @classmethod
    def clean_color(cls, v: str) -> str:
        v = sanitize_string(v)
        if not COLOR_REGEX.match(v):
            raise ValueError(f"Invalid gradient color: {v}")
        return v


class GradientConfig(BaseModel):
    type: Literal["linear", "radial", "conic"] = "linear"
    angle_degrees: float = Field(135.0, ge=0.0, le=360.0)
    stops: List[GradientStop] = Field(
        default_factory=lambda: [
            GradientStop(color="#0F172A", position=0.0),
            GradientStop(color="#1E293B", position=1.0),
        ]
    )
    animated: bool = Field(False)
    animation_speed: float = Field(1.0, ge=0.1, le=10.0)


class DataPoint(BaseModel):
    label: str = Field(...)
    value: float = Field(...)
    color: Optional[str] = Field(None)

    @field_validator("label")
    @classmethod
    def clean_label(cls, v: str) -> str:
        return sanitize_string(v)


class DataChartConfig(BaseModel):
    chart_type: Literal["bar", "line", "donut", "counter"] = "bar"
    title: Optional[str] = Field(None)
    dataset: List[DataPoint] = Field(default_factory=list)
    show_values: bool = Field(True)
    show_grid: bool = Field(True)
    animated_progress: bool = Field(True)
    bar_corner_radius: float = Field(8.0, ge=0.0, le=30.0)

    @field_validator("title")
    @classmethod
    def clean_title(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return sanitize_string(v)


class ParticlesConfig(BaseModel):
    count: int = Field(50, ge=1, le=2000)
    color: str = Field("#60A5FA")
    speed_range: tuple[float, float] = Field((10.0, 50.0))
    size_range: tuple[float, float] = Field((2.0, 6.0))
    direction: Literal["up", "down", "ambient", "radial"] = "up"
    blend_mode: Literal["screen", "plus-lighter", "normal"] = "screen"

    @field_validator("color")
    @classmethod
    def clean_color(cls, v: str) -> str:
        v = sanitize_string(v)
        if not COLOR_REGEX.match(v):
            raise ValueError(f"Invalid particle color: {v}")
        return v


class ShaderConfig(BaseModel):
    effect_type: Literal["vignette", "glow", "chromatic_aberration", "scanlines", "noise", "blur"] = "vignette"
    intensity: float = Field(0.5, ge=0.0, le=1.0)
    radius: float = Field(10.0, ge=0.0, le=100.0)
    color: Optional[str] = Field(None)


class CaptionsConfig(BaseModel):
    words: List[WordTimestampSpec] = Field(default_factory=list)
    active_color: str = Field("#FBBF24")  # amber-400
    inactive_color: str = Field("#94A3B8")  # slate-400
    typography: TypographySpec = Field(default_factory=TypographySpec)
    animation_mode: Literal["word_pop", "word_highlight", "kinetic_wave", "typewriter", "terminal_decode"] = "word_pop"
    safe_zone_anchor: Literal["bottom", "center", "top"] = "bottom"
    background_veil: bool = Field(True)
    veil_color: str = Field("rgba(15, 23, 42, 0.75)")

    @field_validator("active_color", "inactive_color", "veil_color")
    @classmethod
    def clean_colors(cls, v: str) -> str:
        v = sanitize_string(v)
        if not COLOR_REGEX.match(v):
            raise ValueError(f"Invalid caption color: {v}")
        return v


# ============================================================================
# Element & Scene Specification
# ============================================================================

class ElementTransform(BaseModel):
    x: float = Field(0.0)
    y: float = Field(0.0)
    width: float = Field(100.0, gt=0)
    height: float = Field(100.0, gt=0)
    anchor_x: float = Field(0.5, ge=0.0, le=1.0)
    anchor_y: float = Field(0.5, ge=0.0, le=1.0)
    scale_x: float = Field(1.0, ge=0.0, le=10.0)
    scale_y: float = Field(1.0, ge=0.0, le=10.0)
    rotation_deg: float = Field(0.0)
    opacity: float = Field(1.0, ge=0.0, le=1.0)


class ElementSpec(BaseModel):
    """A distinct visual or audio-reactive layer inside a scene."""
    id: str = Field(..., min_length=1, max_length=80)
    type: Literal["text", "shape", "gradient", "data_chart", "particles", "shader_effect", "captions"] = "text"
    start_time: float = Field(0.0, ge=0.0)
    duration: float = Field(..., gt=0.0)
    z_index: int = Field(0)
    transform: ElementTransform = Field(default_factory=ElementTransform)
    keyframes: List[KeyframeSpec] = Field(default_factory=list)

    # Sub-configurations (discriminated by type)
    text_config: Optional[TextConfig] = None
    shape_config: Optional[ShapeConfig] = None
    gradient_config: Optional[GradientConfig] = None
    chart_config: Optional[DataChartConfig] = None
    particles_config: Optional[ParticlesConfig] = None
    shader_config: Optional[ShaderConfig] = None
    captions_config: Optional[CaptionsConfig] = None

    @field_validator("id")
    @classmethod
    def clean_id(cls, v: str) -> str:
        return sanitize_string(v)


class CameraSpec(BaseModel):
    """Camera projection and perspective move."""
    projection: Literal["2d", "perspective_3d"] = "2d"
    zoom: float = Field(1.0, ge=0.5, le=5.0)
    pan_x: float = Field(0.0)
    pan_y: float = Field(0.0)
    rotation_z: float = Field(0.0)


class SceneSpec(BaseModel):
    """A temporal block containing layers of visual motion."""
    id: str = Field(..., min_length=1, max_length=80)
    start_time: float = Field(0.0, ge=0.0)
    duration: float = Field(..., gt=0.0)
    background_color: str = Field("#0A0A0C")
    camera: CameraSpec = Field(default_factory=CameraSpec)
    elements: List[ElementSpec] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def clean_id(cls, v: str) -> str:
        return sanitize_string(v)

    @field_validator("background_color")
    @classmethod
    def clean_bg(cls, v: str) -> str:
        v = sanitize_string(v)
        if not COLOR_REGEX.match(v):
            raise ValueError(f"Invalid background color: {v}")
        return v


class AudioTrackSpec(BaseModel):
    """Audio stream configuration with authentic source and volume."""
    id: str = Field(..., min_length=1, max_length=80)
    file_path: Optional[str] = Field(None)
    start_time: float = Field(0.0, ge=0.0)
    duration: float = Field(..., gt=0.0)
    volume: float = Field(1.0, ge=0.0, le=2.0)
    fade_in_seconds: float = Field(0.0, ge=0.0)
    fade_out_seconds: float = Field(0.0, ge=0.0)


class RepairLogEntry(BaseModel):
    """Record of an automated self-repair patch applied to the specification."""
    timestamp: str
    issue_type: Literal["wcag_contrast", "text_overlap", "safe_zone_overflow", "blank_frame", "timing_sync"]
    details: str
    patch_applied: Dict[str, Any]
    retry_index: int
    resolved: bool


# ============================================================================
# Root Native Motion Specification (native_motion_v1)
# ============================================================================

class NativeMotionSpec(BaseModel):
    """Canonical root schema for native motion generation (schema_version='native_motion_v1')."""
    schema_version: Literal["native_motion_v1"] = "native_motion_v1"
    id: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=200)
    brief: CreativeBrief
    constraints: Constraints = Field(default_factory=Constraints)
    knowledge_refs: List[KnowledgeRef] = Field(default_factory=list)
    safe_zones: SafeZoneSpec = Field(default_factory=SafeZoneSpec)
    width: int = Field(1080)
    height: int = Field(1920)
    fps: int = Field(30, ge=15, le=60)
    duration_seconds: float = Field(..., gt=0.0, le=300.0)
    scenes: List[SceneSpec] = Field(default_factory=list)
    audio_tracks: List[AudioTrackSpec] = Field(default_factory=list)
    repair_log: List[RepairLogEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_resolution_and_timing(self) -> NativeMotionSpec:
        # Match dimensions to aspect ratio
        aspect = self.constraints.aspect_ratio
        if aspect == "9:16":
            if (self.width, self.height) != (1080, 1920):
                self.width, self.height = 1080, 1920
        elif aspect == "16:9":
            if (self.width, self.height) != (1920, 1080):
                self.width, self.height = 1920, 1080
        elif aspect == "1:1":
            if (self.width, self.height) != (1080, 1080):
                self.width, self.height = 1080, 1080
        elif aspect == "4:5":
            if (self.width, self.height) != (1080, 1350):
                self.width, self.height = 1080, 1350

        # Validate total duration is positive and matches scenes if present
        if not self.scenes:
            raise ValueError("NativeMotionSpec must contain at least one SceneSpec.")

        total_scene_dur = sum(s.duration for s in self.scenes)
        if abs(total_scene_dur - self.duration_seconds) > 0.1:
            # Sync root duration to scene duration sum
            self.duration_seconds = round(total_scene_dur, 3)

        return self
