# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Versioned OutcomeContract and typed data models for 6Clips Outcome-as-a-Service orchestration."""

from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class IntentKind(str, Enum):
    NEW_REQUEST = "NEW_REQUEST"
    CONTINUE = "CONTINUE"
    RETRY_SAME_OPERATION = "RETRY_SAME_OPERATION"
    CHANGE_REQUEST = "CHANGE_REQUEST"


class DurationPolicy(str, Enum):
    EXACT = "EXACT"
    TARGET = "TARGET"
    MAX = "MAX"


class OutcomeState(str, Enum):
    INTENT_CAPTURED = "INTENT_CAPTURED"
    SOURCE_DISCOVERY = "SOURCE_DISCOVERY"
    SOURCE_ACCESS_VERIFIED = "SOURCE_ACCESS_VERIFIED"
    MEDIA_INGESTED = "MEDIA_INGESTED"
    MEDIA_ANALYZED = "MEDIA_ANALYZED"
    HIGHLIGHTS_SELECTED = "HIGHLIGHTS_SELECTED"
    RESULTS_COMPOSED = "RESULTS_COMPOSED"
    RENDER_RUNNING = "RENDER_RUNNING"
    RENDERS_VERIFIED = "RENDERS_VERIFIED"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    # Exception & divergence states
    WAITING_FOR_INPUT = "WAITING_FOR_INPUT"
    PARTIAL = "PARTIAL"
    PAUSED = "PAUSED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class OutputState(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class SourceAsset(BaseModel):
    asset_id: str
    editorial_role: str = Field(default="primary_footage", description="Role e.g. primary_footage, broll, reference")
    permitted_uses: List[str] = Field(default_factory=lambda: ["clip_extraction", "motion_review"])
    acquisition_route: str = Field(default="authorized_fixture", description="e.g. local_upload, authorized_fixture, library_asset, trend_candidate")
    content_hash: Optional[str] = Field(default=None, description="SHA-256 of physical bytes if available")
    local_path: Optional[str] = Field(default=None, description="Internal path on server to local bytes")
    is_accessible: bool = Field(default=True, description="Whether bytes are physically accessible right now")
    rights_verified: bool = Field(default=True, description="Whether lawful reuse permission is confirmed")


class OutputSpec(BaseModel):
    output_id: str
    aspect_ratio: str = Field(default="9:16")
    seconds: float = Field(default=60.0, description="Duration in seconds")
    duration_policy: DurationPolicy = Field(default=DurationPolicy.TARGET)
    tolerance_seconds: float = Field(default=3.0, description="Tolerance in seconds for TARGET policy")
    language: str = Field(default="en")
    editorial_constraints: Dict[str, Any] = Field(default_factory=dict)


class ExecutionLimits(BaseModel):
    max_attempts: int = Field(default=3)
    approved_budget: Optional[float] = None
    stop_policy: str = Field(default="stop_on_error")  # stop_on_error | fallback_partial


class ModelSnapshot(BaseModel):
    selected_model_id: Optional[str] = None
    selected_provider: Optional[str] = None
    selected_effort: Optional[str] = None
    input_revision: Optional[int] = None


class OutcomeContract(BaseModel):
    schema_version: str = "production.v1"
    contract_id: str
    contract_version: int = 1
    intent_kind: IntentKind = IntentKind.NEW_REQUEST
    user_id: str = "local"
    project_id: Optional[str] = None
    job_id: Optional[str] = None
    objective: str
    output_count: int = 3
    outputs: List[OutputSpec] = Field(default_factory=list)
    source_assets: List[SourceAsset] = Field(default_factory=list)
    execution_limits: ExecutionLimits = Field(default_factory=ExecutionLimits)
    snapshot: Optional[ModelSnapshot] = None
    parent_contract_id: Optional[str] = None
    change_reason: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Blocker(BaseModel):
    code: str
    precise_reason: str
    next_action: str


class Checks(BaseModel):
    technical: str = "PASS"  # PASS | FAIL | NOT_RUN
    contract: str = "PASS"   # PASS | FAIL | NOT_RUN
    editorial: str = "NOT_ASSESSED"  # NOT_ASSESSED | PASS | REJECTED


class MediaProbe(BaseModel):
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


class SourceRange(BaseModel):
    asset_id: str
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    editorial_reason: str
    relevance_score: float = 0.0


class OutputResult(BaseModel):
    output_id: str
    project_revision_id: Optional[str] = None
    artifact_id: Optional[str] = None
    snapshot_manifest_ref: Optional[str] = None
    media_probe: Optional[MediaProbe] = None
    source_ranges: List[SourceRange] = Field(default_factory=list)
    checks: Checks = Field(default_factory=Checks)
    preview_ref: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    state: OutputState = OutputState.PENDING
    error_detail: Optional[str] = None


class StepEvent(BaseModel):
    step_name: str
    status: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    detail: Optional[str] = None


class ProductionReport(BaseModel):
    schema_version: str = "production.v1"
    job_id: str
    run_id: str
    contract_version: int = 1
    status: str = "RUNNING"  # RUNNING | COMPLETE | PARTIAL | BLOCKED | CANCELLED
    outputs: List[OutputResult] = Field(default_factory=list)
    blockers: List[Blocker] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    step_events: List[StepEvent] = Field(default_factory=list)


def adapt_contract_to_producer_request(contract: OutcomeContract) -> Any:
    """Adapt an OutcomeContract into a ProductionRequestV1 instance if available, or return compatible dict/contract."""
    try:
        from backend.media_pipeline.models import (
            DurationPolicy as BDurationPolicy,
            ExecutionLimitsV1,
            OutputSpecV1,
            ProductionRequestV1,
            SnapshotV1,
            SourceAssetV1,
        )

        b_sources = [
            SourceAssetV1(
                asset_id=a.asset_id,
                editorial_role=a.editorial_role or "primary_footage",
                permitted_uses=a.permitted_uses or ["clip_extraction", "motion_review"],
                acquisition_route=(
                    a.acquisition_route
                    if a.acquisition_route in {"local_upload", "authorized_fixture", "library_asset", "authorized_partner_api"}
                    else "authorized_fixture"
                ),
                content_hash=a.content_hash,
                local_path=a.local_path,
            )
            for a in contract.source_assets
        ]

        b_outputs = [
            OutputSpecV1(
                output_id=o.output_id,
                aspect_ratio=o.aspect_ratio,
                seconds=o.seconds,
                duration_policy=BDurationPolicy(o.duration_policy.value if hasattr(o.duration_policy, "value") else str(o.duration_policy)),
                tolerance_seconds=o.tolerance_seconds,
                language=o.language,
                editorial_constraints=o.editorial_constraints or {},
            )
            for o in contract.outputs
        ]

        b_limits = ExecutionLimitsV1(
            max_attempts=contract.execution_limits.max_attempts,
            approved_budget=contract.execution_limits.approved_budget,
            stop_policy=contract.execution_limits.stop_policy,
        )

        b_snapshot = SnapshotV1(
            selected_model_id=contract.snapshot.selected_model_id if contract.snapshot else None,
            selected_provider=contract.snapshot.selected_provider if contract.snapshot else None,
            selected_effort=contract.snapshot.selected_effort if contract.snapshot else None,
            input_revision=contract.snapshot.input_revision if contract.snapshot else None,
        ) if contract.snapshot else None

        return ProductionRequestV1(
            schema_version="production.v1",
            run_id=contract.contract_id,
            contract_id=contract.contract_id,
            contract_version=str(contract.contract_version),
            project_id=contract.project_id or f"proj_{contract.contract_id}",
            user_id=contract.user_id,
            source_assets=b_sources,
            outputs=b_outputs,
            execution_limits=b_limits,
            snapshot=b_snapshot,
        )
    except (ImportError, AttributeError, ValueError):
        return contract
