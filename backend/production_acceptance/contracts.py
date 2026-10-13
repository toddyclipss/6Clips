# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Production Path Orchestration Contracts (Wave 8).

Defines typed specifications for:
- GT-05 (V1): 1 authorized gameplay source -> 3 vertical shorts (~60s) with independent projects & review
- GT-06 (V3): 1 authentic ~60-minute recording -> 8-10 minute 16:9 narrative result
- GT-07 (V2): 5 authorized source assets -> 10 distinct editable/rendered outputs
- Source media rights verification, physical probe metadata, lineage tracking,
  and canonical Motion review linking.
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RightsVerificationStatus(str, Enum):
    """Source media rights verification states."""
    AUTHORIZED_USER_MEDIA = "AUTHORIZED_USER_MEDIA"
    COMMERCIAL_CREATOR_LICENSE = "COMMERCIAL_CREATOR_LICENSE"
    UNVERIFIED_THIRD_PARTY = "UNVERIFIED_THIRD_PARTY"
    MALICIOUS_UNAUTHORIZED = "MALICIOUS_UNAUTHORIZED"
    MISSING_PERMITTED_USE = "MISSING_PERMITTED_USE"


class OrchestrationContractStatus(str, Enum):
    """Lifecycle states of a production orchestration contract."""
    CONTRACT_PREPARED = "CONTRACT_PREPARED"
    MEDIA_PROBED = "MEDIA_PROBED"
    ORCHESTRATING = "ORCHESTRATING"
    AWAITING_RENDER = "AWAITING_RENDER"
    RENDERED = "RENDERED"
    MOTION_REVIEW_LINKED = "MOTION_REVIEW_LINKED"
    WAITING_FOR_INPUT = "WAITING_FOR_INPUT"
    NOT_TESTED = "NOT_TESTED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class MediaProbeMetadata(BaseModel):
    """Physical file probe data extracted via container inspect and ffprobe."""
    file_path: str
    container_format: str = "mp4"
    duration_seconds: float = 0.0
    width: int = 0
    height: int = 0
    aspect_ratio: str = "16:9"  # e.g., "16:9", "9:16", "1:1"
    video_codec: Optional[str] = "h264"
    audio_codec: Optional[str] = "aac"
    audio_channels: int = 2
    sample_rate: int = 44100
    bit_rate: int = 0
    file_size_bytes: int = 0
    sha256_hash: str = ""
    magic_bytes_valid: bool = False
    has_audio_stream: bool = True
    synthetic_filler_detected: bool = False
    synthetic_filler_reason: Optional[str] = None


class SourceMediaAsset(BaseModel):
    """Source media asset with verified provenance and rights status."""
    source_id: str
    file_path: str
    rights_status: RightsVerificationStatus = RightsVerificationStatus.UNVERIFIED_THIRD_PARTY
    rights_notes: str = ""
    permitted_uses: List[str] = Field(default_factory=lambda: ["creator_edit", "social_distribution"])
    probe: Optional[MediaProbeMetadata] = None


class V1ExpectedOutputSpec(BaseModel):
    """Specification of an expected output in a V1 (GT-05) 3-clip vertical batch."""
    output_id: str
    project_id: str  # Independent project reference for this short
    target_aspect_ratio: str = "9:16"
    target_duration_min_sec: float = 50.0
    target_duration_max_sec: float = 70.0
    primary_source_id: str
    source_start_sec: float = 0.0
    source_end_sec: float = 60.0
    editorial_focus: str = "gameplay_highlight"
    project_revision: int = 1
    has_subtitles: bool = True
    motion_review_url: str = ""
    output_file_path: Optional[str] = None


class V1ProductionContract(BaseModel):
    """
    Production path contract for V1 (GT-05):
    1 licensed source -> THREE usable independent ~60s vertical clips with provenance,
    subtitles/audio/Review, ffprobe, and independent projects.
    """
    contract_id: str
    gate_id: str = "GT-05"
    project_id: str
    source_gameplay: Optional[SourceMediaAsset] = None
    expected_outputs: List[V1ExpectedOutputSpec] = Field(default_factory=list)
    independent_project_ids: List[str] = Field(default_factory=list)
    status: OrchestrationContractStatus = OrchestrationContractStatus.CONTRACT_PREPARED
    dedupe_policy: Dict[str, Any] = Field(
        default_factory=lambda: {
            "require_unique_hashes": True,
            "prohibit_exact_time_overlap": True,
            "max_allowed_overlap_fraction": 0.15,
            "prohibit_synthetic_filler": True,
        }
    )
    issues: List[str] = Field(default_factory=list)
    required_file_instructions: List[str] = Field(default_factory=list)
    is_real_user_media: bool = False
    notes: str = ""


class V2ExpectedOutputSpec(BaseModel):
    """Specification of an expected output in a V2 (GT-07) 10-clip batch."""
    output_id: str
    target_aspect_ratio: str = "9:16"
    target_duration_min_sec: float = 45.0
    target_duration_max_sec: float = 65.0
    primary_source_id: str
    source_start_sec: float = 0.0
    source_end_sec: float = 60.0
    editorial_focus: str = "viral_hook"
    project_revision: int = 1
    motion_review_url: str = ""


class V2ProductionContract(BaseModel):
    """
    Production path contract for V2 (GT-07):
    5 authorized source assets yielding 10 distinct, editable, rendered outputs.
    """
    contract_id: str
    gate_id: str = "GT-07"
    project_id: str
    sources: List[SourceMediaAsset] = Field(default_factory=list)
    expected_outputs: List[V2ExpectedOutputSpec] = Field(default_factory=list)
    status: OrchestrationContractStatus = OrchestrationContractStatus.CONTRACT_PREPARED
    dedupe_policy: Dict[str, Any] = Field(
        default_factory=lambda: {
            "require_unique_hashes": True,
            "prohibit_exact_time_overlap": True,
            "max_allowed_overlap_fraction": 0.20,
            "prohibit_synthetic_filler": True,
        }
    )
    issues: List[str] = Field(default_factory=list)
    required_file_instructions: List[str] = Field(default_factory=list)
    is_real_user_media: bool = False
    notes: str = ""


class V3NarrativeCut(BaseModel):
    """A narrative cut in the V3 (GT-06) long-form condensation cut list."""
    cut_id: str
    source_start_sec: float
    source_end_sec: float
    duration_sec: float
    scene_name: str = ""
    topic_marker: str = ""
    narration_continuity_summary: str = ""


class V3ProductionContract(BaseModel):
    """
    Production path contract for V3 (GT-06):
    1 authentic ~60-minute recording -> 8-10 minute 16:9 narrative result.
    """
    contract_id: str
    gate_id: str = "GT-06"
    project_id: str
    source_recording: Optional[SourceMediaAsset] = None
    target_aspect_ratio: str = "16:9"
    target_duration_min_sec: float = 480.0  # 8 minutes
    target_duration_max_sec: float = 600.0  # 10 minutes
    narrative_cut_list: List[V3NarrativeCut] = Field(default_factory=list)
    status: OrchestrationContractStatus = OrchestrationContractStatus.CONTRACT_PREPARED
    motion_review_url: str = ""
    issues: List[str] = Field(default_factory=list)
    required_file_instructions: List[str] = Field(default_factory=list)
    is_real_user_media: bool = False
    notes: str = ""


class OrchestrationResult(BaseModel):
    """Execution result of a production acceptance verification."""
    gate_id: str
    status: str  # PASSED | FAILED | NOT_TESTED | WAITING_FOR_INPUT | BLOCKED
    is_real_user_media: bool = False
    artifacts_verified_count: int = 0
    distinct_hashes_count: int = 0
    motion_review_urls: List[str] = Field(default_factory=list)
    independent_project_ids: List[str] = Field(default_factory=list)
    issues: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    required_file_instructions: List[str] = Field(default_factory=list)
    notes: str = ""
