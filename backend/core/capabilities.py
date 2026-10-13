# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Capability Registry defining typed contracts, preconditions, and surface scopes."""
from dataclasses import dataclass, field
from typing import Callable, Any, Optional
import logging

from backend.core.exceptions import CapabilityPreconditionError

logger = logging.getLogger(__name__)


@dataclass
class Capability:
    name: str
    description: str
    surface: str  # "discover" | "create" | "distribute" | "common"
    required_params: list[str] = field(default_factory=list)
    optional_params: list[str] = field(default_factory=list)
    idempotent: bool = True
    requires_authorization: bool = False
    cost_estimate_usd: float = 0.0


class CapabilityRegistry:
    _registry: dict[str, Capability] = {}

    @classmethod
    def register(cls, cap: Capability) -> None:
        cls._registry[cap.name] = cap

    @classmethod
    def get(cls, name: str) -> Optional[Capability]:
        return cls._registry.get(name)

    @classmethod
    def all(cls) -> list[Capability]:
        return list(cls._registry.values())

    @classmethod
    def list_for_surface(cls, surface: str) -> list[dict]:
        """Return capabilities scoped to a specific workspace surface."""
        return [
            {
                "name": c.name,
                "description": c.description,
                "surface": c.surface,
                "required_params": c.required_params,
                "optional_params": c.optional_params,
                "requires_authorization": c.requires_authorization,
                "idempotent": c.idempotent,
            }
            for c in cls._registry.values()
            if c.surface in (surface, "common")
        ]

    @classmethod
    def validate_input(cls, name: str, payload: dict) -> Capability:
        cap = cls.get(name)
        if not cap:
            raise CapabilityPreconditionError(f"Unknown capability: '{name}'")
        missing = [p for p in cap.required_params if p not in payload or payload[p] is None]
        if missing:
            raise CapabilityPreconditionError(f"Capability '{name}' missing required parameters: {missing}")
        return cap

    @classmethod
    def to_tool_definitions(
        cls,
        surface: Optional[str] = None,
        user_settings: Optional[Any] = None,
    ) -> list[dict]:
        """Convert registered capabilities to provider-compatible function tool definitions.
        Filters out publishing capabilities when platform credentials are not configured."""
        tools = []
        caps = cls.all() if not surface else [c for c in cls.all() if c.surface in (surface, "common")]
        for cap in caps:
            # Publishing tools remain unavailable until genuinely configured in settings
            if cap.name == "upload_youtube":
                has_yt = user_settings and bool(getattr(user_settings, "youtube_credentials_json_encrypted", None))
                if not has_yt:
                    continue
            elif cap.name == "upload_tiktok":
                has_tt = user_settings and bool(
                    getattr(user_settings, "tiktok_cookie_encrypted", None)
                    or getattr(user_settings, "tiktok_upload_token_encrypted", None)
                )
                if not has_tt:
                    continue

            properties = {}
            for param in cap.required_params + cap.optional_params:
                if param == "expected_revision":
                    properties[param] = {
                        "type": "integer",
                        "description": "Current expected project revision number (optimistic concurrency CAS)",
                    }
                elif param == "payload":
                    properties[param] = {
                        "type": "object",
                        "description": "Operation payload dictionary",
                    }
                elif param in ("limit", "max_clips", "max_videos", "start_seconds", "end_seconds", "speed", "days", "font_size"):
                    properties[param] = {
                        "type": "number",
                        "description": f"Numeric parameter for {param}",
                    }
                elif param in ("platforms", "ranges", "time_ranges", "article_ids", "trend_result_ids"):
                    properties[param] = {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": f"List parameter for {param}",
                    }
                else:
                    properties[param] = {
                        "type": "string",
                        "description": f"Parameter {param}",
                    }

            # Prefix description with mutation class
            desc = cap.description
            if cap.name in ("search_catalog", "inspect_media"):
                desc = f"Read-only: {cap.description}"
            elif cap.name == "search_youtube_trends":
                desc = "Read-only: search trending topics via YouTube Data API"
            elif cap.name in ("project_operation", "create_project", "generate_captions"):
                desc = f"Mutating: {cap.description}"

            tools.append({
                "type": "function",
                "function": {
                    "name": cap.name,
                    "description": desc,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": cap.required_params,
                    },
                },
            })
        return tools


# ── Register core capabilities ────────────────────────────────────────────────

CapabilityRegistry.register(Capability(
    name="extract_clips",
    description="Extract viral or manual cut clips from a source video",
    surface="create",
    required_params=["video_id"],
    optional_params=["time_ranges", "max_clips", "caption_style", "min_duration", "max_duration"],
    idempotent=True,
))

CapabilityRegistry.register(Capability(
    name="apply_captions",
    description="Burn word-by-word synchronized subtitles into video",
    surface="create",
    required_params=["video_id"],
    optional_params=["caption_style", "emoji_style"],
    idempotent=True,
))

CapabilityRegistry.register(Capability(
    name="project_operation",
    description="Apply a controlled, versioned operation to a project document",
    surface="create",
    required_params=["project_id", "expected_revision", "operation_type", "payload"],
    optional_params=["idempotency_key", "author"],
    idempotent=True,
))

CapabilityRegistry.register(Capability(
    name="project_render",
    description="Render a video from a frozen project revision",
    surface="create",
    required_params=["project_id"],
    optional_params=["revision", "aspect_ratio"],
    idempotent=True,
))

CapabilityRegistry.register(Capability(
    name="upload_youtube",
    description="Upload a generated video to YouTube channel",
    surface="distribute",
    required_params=["video_id"],
    optional_params=["title", "description", "privacy", "tags"],
    idempotent=False,
    requires_authorization=True,
))

CapabilityRegistry.register(Capability(
    name="upload_tiktok",
    description="Deliver a video to TikTok inbox or channel",
    surface="distribute",
    required_params=["video_id"],
    optional_params=["title", "privacy"],
    idempotent=False,
    requires_authorization=True,
))

CapabilityRegistry.register(Capability(
    name="search_youtube_trends",
    description="Search trending topics and channel metrics via YouTube API. Use purpose='trend_research' for general viral references/Shorts, or purpose='editable_source_search' with video_duration='medium' (4-20 min) or 'long' (>20 min) for editable footage.",
    surface="discover",
    required_params=["query"],
    optional_params=["max_results", "video_duration", "purpose", "target_clips", "clip_duration_sec"],
    idempotent=True,
))

CapabilityRegistry.register(Capability(
    name="ingest_trend",
    description="Ingest a trending video into library and link to active project",
    surface="create",
    required_params=["trend_result_id", "project_id"],
    optional_params=["expected_revision"],
    idempotent=True,
))

CapabilityRegistry.register(Capability(
    name="suggest_clips",
    description="Analyze source video and propose viral timestamp moments for bench review",
    surface="create",
    required_params=["video_id"],
    optional_params=["max_clips", "min_duration", "max_duration", "user_query"],
    idempotent=True,
))

CapabilityRegistry.register(Capability(
    name="set_bench_ranges",
    description="Persist cutting bench ranges for a source video into the project document",
    surface="create",
    required_params=["project_id", "expected_revision", "source_id", "ranges"],
    optional_params=["idempotency_key"],
    idempotent=True,
))

CapabilityRegistry.register(Capability(
    name="tool_trim",
    description="Trim a video asset to a [start, end] window",
    surface="create",
    required_params=["video_id", "start_seconds", "end_seconds"],
    optional_params=["project_id"],
    idempotent=True,
))

CapabilityRegistry.register(Capability(
    name="tool_speed",
    description="Adjust playback speed of a video asset",
    surface="create",
    required_params=["video_id", "speed"],
    optional_params=["keep_pitch", "project_id"],
    idempotent=True,
))

CapabilityRegistry.register(Capability(
    name="tool_crop",
    description="Crop a video asset to normalized rectangle [x, y, w, h]",
    surface="create",
    required_params=["video_id", "x", "y", "w", "h"],
    optional_params=["project_id"],
    idempotent=True,
))

CapabilityRegistry.register(Capability(
    name="tool_reframe",
    description="Reframe landscape video asset to vertical 9:16",
    surface="create",
    required_params=["video_id"],
    optional_params=["project_id"],
    idempotent=True,
))

CapabilityRegistry.register(Capability(
    name="tool_compress",
    description="Compress a video asset with specified resolution and quality level",
    surface="create",
    required_params=["video_id"],
    optional_params=["resolution", "level", "project_id"],
    idempotent=True,
))

CapabilityRegistry.register(Capability(
    name="tool_transform",
    description="Transform video: flip, rotate, loop, volume adjustment",
    surface="create",
    required_params=["video_id", "operation"],
    optional_params=["amount", "project_id"],
    idempotent=True,
))

CapabilityRegistry.register(Capability(
    name="tool_watermark",
    description="Overlay image watermark onto video asset",
    surface="create",
    required_params=["video_id", "logo_path"],
    optional_params=["position", "opacity", "scale", "project_id"],
    idempotent=True,
))

CapabilityRegistry.register(Capability(
    name="search_catalog",
    description="Search normalized HyperFrames motion graphics catalog by query or category",
    surface="create",
    required_params=[],
    optional_params=["query", "category", "limit"],
    idempotent=True,
))

CapabilityRegistry.register(Capability(
    name="inspect_media",
    description="Inspect video and audio properties (streams, duration, FPS, aspect ratio) of source media in the library",
    surface="create",
    required_params=[],
    optional_params=["video_id"],
    idempotent=True,
))

CapabilityRegistry.register(Capability(
    name="create_project",
    description="Construct a new canonical video project through ProjectService",
    surface="create",
    required_params=["name"],
    optional_params=["aspect_ratio"],
    idempotent=True,
))

CapabilityRegistry.register(Capability(
    name="generate_captions",
    description="Generate synchronized captions on the project timeline from source speech transcription",
    surface="create",
    required_params=["project_id", "expected_revision"],
    optional_params=["video_id", "style", "position", "color", "font_size"],
    idempotent=True,
))

