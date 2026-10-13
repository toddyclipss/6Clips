# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Production V1 logical contract data models for 6Clips Media Pipeline."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DurationPolicy(str, Enum):
    EXACT = "EXACT"
    TARGET = "TARGET"
    MAX = "MAX"


class BatchStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


class OutputState(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class SourceAssetV1(BaseModel):
    asset_id: str
    editorial_role: str = Field(default="primary_footage", description="Role e.g. primary_footage, broll, reference")
    permitted_uses: List[str] = Field(default_factory=lambda: ["clip_extraction", "motion_review"])
    acquisition_route: str = Field(description="e.g. local_upload, authorized_fixture, library_asset")
    content_hash: Optional[str] = Field(default=None, description="SHA-256 of physical bytes if available")
    local_path: Optional[str] = Field(default=None, description="Internal path on server to local bytes")


class OutputSpecV1(BaseModel):
    output_id: str
    aspect_ratio: str = Field(default="9:16")
    seconds: float = Field(default=60.0, description="Duration in seconds")
    duration_policy: DurationPolicy = Field(default=DurationPolicy.TARGET)
    tolerance_seconds: float = Field(default=3.0, description="Tolerance for TARGET policy")
    language: str = Field(default="en")
    editorial_constraints: Dict[str, Any] = Field(default_factory=dict)


class ExecutionLimitsV1(BaseModel):
    max_attempts: int = Field(default=3)
    approved_budget: Optional[float] = None
    stop_policy: str = Field(default="abort_on_rights_blocker")


class SnapshotV1(BaseModel):
    selected_model_id: Optional[str] = None
    selected_provider: Optional[str] = None
    selected_effort: Optional[str] = None
    input_revision: Optional[int] = None


class ProductionRequestV1(BaseModel):
    schema_version: str = "production.v1"
    run_id: str
    contract_id: str
    contract_version: str = "1.0.0"
    project_id: str
    user_id: str = "local"
    source_assets: List[SourceAssetV1]
    outputs: List[OutputSpecV1]
    execution_limits: ExecutionLimitsV1 = Field(default_factory=ExecutionLimitsV1)
    snapshot: Optional[SnapshotV1] = None


class BlockerV1(BaseModel):
    code: str
    precise_reason: str
    next_action: str


class ChecksV1(BaseModel):
    technical: str = "PASS"  # PASS | FAIL | NOT_RUN
    contract: str = "PASS"   # PASS | FAIL | NOT_RUN
    editorial: str = "NOT_ASSESSED"  # NOT_ASSESSED | PASS | REJECTED


class MediaProbeV1(BaseModel):
    width: int
    height: int
    duration_seconds: float
    video_codec: str
    audio_codec: str
    fps: float
    audio_channels: int
    sample_rate: int
    content_hash: str
    mean_volume_db: Optional[float] = None
    is_silent: bool = False
    is_black: bool = False


class SourceRangeV1(BaseModel):
    asset_id: str
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    editorial_reason: str
    relevance_score: float = 0.0


class OutputResultV1(BaseModel):
    output_id: str
    project_revision_id: Optional[str] = None
    artifact_id: Optional[str] = None
    snapshot_manifest_ref: Optional[str] = None
    media_probe: Optional[MediaProbeV1] = None
    source_ranges: List[SourceRangeV1] = Field(default_factory=list)
    checks: ChecksV1 = Field(default_factory=ChecksV1)
    preview_ref: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    state: OutputState = OutputState.PENDING
    error_detail: Optional[str] = None


class StepEventV1(BaseModel):
    step_name: str
    status: str
    timestamp: str
    detail: Optional[str] = None


class ProductionReportV1(BaseModel):
    schema_version: str = "production.v1"
    job_id: str
    run_id: str
    contract_version: str
    status: BatchStatus = BatchStatus.RUNNING
    outputs: List[OutputResultV1] = Field(default_factory=list)
    blockers: List[BlockerV1] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    step_events: List[StepEventV1] = Field(default_factory=list)
