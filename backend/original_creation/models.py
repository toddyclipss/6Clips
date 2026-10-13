# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Data Contracts and Models for Grounded Original Content Creation.

Separates:
- Evidence & claims ledger (verifiable facts from patch notes/official news/creator context)
- Clean spoken teleprompter script (free of bracketed stage/shot directions)
- Scene-by-scene shot list with suggested camera angles and motion graphic overlays
- Factcheck notes with provenance citations
- Production status and honest input requirements (e.g. WAITING_FOR_INPUT for voice)
- Rendered video output metadata and probe statistics
- Adapter shape for canonical ProjectService / Production V1
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class VoiceInputRequirement(str, Enum):
    VOICE_REQUIRED = "VOICE_REQUIRED"
    VOICE_PROVIDED = "VOICE_PROVIDED"
    PROCEDURAL_SYNTHESIS_ALLOWED = "PROCEDURAL_SYNTHESIS_ALLOWED"
    WAITING_FOR_INPUT = "WAITING_FOR_INPUT"


class OriginalCreationStatus(str, Enum):
    PLANNING_ARTIFACT_DRAFT = "PLANNING_ARTIFACT_DRAFT"
    WAITING_FOR_INPUT = "WAITING_FOR_INPUT"
    READY_FOR_COMPOSITION = "READY_FOR_COMPOSITION"
    RENDERING = "RENDERING"
    RENDERED = "RENDERED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class EvidenceLedgerEntry(BaseModel):
    """Single claim verified against authorized primary sources."""
    claim_id: str = Field(default_factory=lambda: f"clm-{uuid4().hex[:6]}")
    claim_text: str
    source_title: str
    source_url: Optional[str] = None
    source_type: str = Field(
        default="official_news",
        description="e.g. official_patch_notes, official_news, creator_context, verified_reference"
    )
    verified: bool = True
    citation: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EvidenceLedger(BaseModel):
    """Collection of traceable claims backing the original video topic."""
    topic: str
    entries: List[EvidenceLedgerEntry] = Field(default_factory=list)
    verification_status: str = Field(default="GROUNDED")  # GROUNDED | PARTIAL | UNVERIFIED
    notes: str = ""


class TeleprompterScript(BaseModel):
    """
    Spoken narration script designed specifically for voiceover/teleprompter display.
    Must contain ONLY clean spoken words without stage directions or bracketed shot descriptions.
    """
    spoken_text: str
    word_count: int
    estimated_read_time_seconds: float
    tone: str = "informative_authoritative"
    language: str = "en"


class ShotListEntry(BaseModel):
    """Visual scene breakdown mapped to timeline intervals."""
    scene_number: int
    timecode_start_sec: float
    timecode_end_sec: float
    visual_description: str
    camera_angle: str = "wide_establishing"
    broll_suggestion: str = ""
    motion_template_id: Optional[str] = None
    overlay_text: Optional[str] = None
    asset_path: Optional[str] = None


class FactcheckNote(BaseModel):
    """Grounded factcheck verifying statements prior to script freeze."""
    claim_id: str
    claim_text: str
    verdict: str = "CONFIRMED"  # CONFIRMED | DISPUTED | OPINION | UNVERIFIED
    source_citation: str
    explanation: str


class VideoProbeStats(BaseModel):
    """Physical MP4 probe metrics verified via ffprobe."""
    width: int
    height: int
    duration_seconds: float
    aspect_ratio: str
    has_audio: bool
    audio_loudness_lufs: Optional[float] = None
    file_size_bytes: int = 0
    codec_name: str = "h264"
    probed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RenderedVideoResult(BaseModel):
    """Metadata for an authentic physically rendered MP4."""
    video_path: str
    duration_seconds: float
    aspect_ratio: str
    width: int
    height: int
    probe_stats: VideoProbeStats
    motion_review_ready: bool = True
    rendered_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class OriginalCompositionSpec(BaseModel):
    """
    Complete planning and production artifact for an original creator video.
    Represents an authorized production spec and tracks physical render when completed.
    """
    spec_id: str = Field(default_factory=lambda: f"orig-{uuid4().hex[:8]}")
    title: str
    topic: str
    target_duration_sec: int = 60
    aspect_ratio: str = "9:16"
    language: str = "en"
    evidence_ledger: EvidenceLedger
    spoken_script: TeleprompterScript
    shot_list: List[ShotListEntry] = Field(default_factory=list)
    factcheck_notes: List[FactcheckNote] = Field(default_factory=list)
    voice_requirement: VoiceInputRequirement = VoiceInputRequirement.WAITING_FOR_INPUT
    voice_asset_id: Optional[str] = None
    voice_asset_path: Optional[str] = None
    facecam_asset_id: Optional[str] = None
    status: OriginalCreationStatus = OriginalCreationStatus.PLANNING_ARTIFACT_DRAFT
    status_reason: str = "Planning artifact generated. Pending voice recording from creator."
    blocked_reason: Optional[str] = None
    rendered_result: Optional[RenderedVideoResult] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ProductionV1Adapter:
    """
    Adapter converting an OriginalCompositionSpec artifact into
    the canonical ProjectService / Production V1 format for rendering and Motion Review.
    Preserves strict read-only boundary with existing pipeline code.
    """

    @staticmethod
    def to_canonical_project_payload(spec: OriginalCompositionSpec, user_id: str = "local") -> Dict[str, Any]:
        """
        Generate project creation dictionary compatible with ProjectService.create_project.
        Truthfully records that physical MP4 is NOT ready until rendered.
        """
        tracks = [
            {
                "id": f"track-video-{spec.spec_id}",
                "type": "video",
                "name": "Visual Scenes",
                "items": [
                    {
                        "id": f"item-scene-{scene.scene_number}",
                        "name": f"Scene {scene.scene_number}: {scene.visual_description[:30]}",
                        "start_time": scene.timecode_start_sec,
                        "duration": round(scene.timecode_end_sec - scene.timecode_start_sec, 2),
                        "asset_type": "broll_or_procedural",
                        "template_id": scene.motion_template_id,
                        "overlay_text": scene.overlay_text,
                        "asset_path": scene.asset_path,
                    }
                    for scene in spec.shot_list
                ],
            },
            {
                "id": f"track-audio-{spec.spec_id}",
                "type": "audio",
                "name": "Narration Voice",
                "items": [
                    {
                        "id": f"item-voice-{spec.spec_id}",
                        "name": "Creator Spoken Track",
                        "start_time": 0.0,
                        "duration": spec.spoken_script.estimated_read_time_seconds,
                        "asset_id": spec.voice_asset_id,
                        "asset_path": spec.voice_asset_path,
                        "status": "ready" if (spec.voice_asset_id or spec.voice_asset_path) else "waiting_for_voice_upload",
                    }
                ],
            },
        ]

        is_rendered = spec.rendered_result is not None and spec.status == OriginalCreationStatus.RENDERED

        return {
            "title": spec.title,
            "user_id": user_id,
            "aspect_ratio": spec.aspect_ratio,
            "target_duration_sec": spec.target_duration_sec,
            "tracks": tracks,
            "metadata": {
                "source_workflow": "original_creation_v1",
                "original_spec_id": spec.spec_id,
                "evidence_claims_count": len(spec.evidence_ledger.entries),
                "script_word_count": spec.spoken_script.word_count,
                "script_clean_text": spec.spoken_script.spoken_text,
                "production_stage": "RENDERED" if is_rendered else "PLANNING_ARTIFACT",
                "rendered_mp4_ready": is_rendered,
                "rendered_video_path": spec.rendered_result.video_path if is_rendered else None,
                "motion_review_ready": is_rendered,
            },
        }
