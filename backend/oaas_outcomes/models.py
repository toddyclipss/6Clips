# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Data models and contract definitions for OAAS (Outcome-as-a-Service) orchestration."""

from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from uuid import uuid4
from pydantic import BaseModel, Field, ConfigDict


class OutcomeJobState(str, Enum):
    """Linear outcome-first state machine progression and intervention states."""
    REQUESTED = "REQUESTED"
    PLANNED = "PLANNED"
    PRODUCING = "PRODUCING"
    RENDERED = "RENDERED"
    VERIFIED = "VERIFIED"
    READY_FOR_DELIVERY = "READY_FOR_DELIVERY"
    # Exception & intervention states
    NEEDS_APPROVAL = "NEEDS_APPROVAL"
    PENDING_CREDENTIALS = "PENDING_CREDENTIALS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class DurationPolicy(str, Enum):
    EXACT = "EXACT"
    TARGET = "TARGET"
    MAX = "MAX"


class OutcomeRequestContract(BaseModel):
    """Simple user-facing request contract: objective + permitted channels + minimal preferences."""
    contract_id: str = Field(default_factory=lambda: f"req-{uuid4().hex[:10]}")
    user_id: str = Field(default="local")
    session_id: str = Field(default="default_session")
    user_intent: str = Field(..., description="High-level goal described by the user.")
    permitted_channel_targets: List[str] = Field(
        default_factory=lambda: ["youtube_shorts"],
        description="Explicitly authorized publication destination channels."
    )
    minimal_preferences: Dict[str, Any] = Field(
        default_factory=lambda: {
            "aspect_ratio": "9:16",
            "duration_seconds": 60.0,
            "duration_policy": DurationPolicy.TARGET,
            "tolerance_seconds": 3.0,
            "language": "en",
        },
        description="Sensible minimal production preferences."
    )
    project_id: Optional[str] = Field(
        default=None,
        description="Optional existing project ID to build upon or revise, preserving loaded project state."
    )
    editor_actions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Optional list of native motion editing actions (trim, split, reframe, captions, etc.) to apply."
    )
    standing_authorization: bool = Field(
        default=False,
        description="Whether user explicitly gave standing authorization to finalize delivery without manual modal click."
    )
    idempotency_token: str = Field(
        default_factory=lambda: f"idem-{uuid4().hex}",
        description="Token to prevent duplicate dispatches and enforce idempotent retries."
    )
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class OutcomePlan(BaseModel):
    """Execution plan autonomously derived by the Main Agent."""
    plan_id: str = Field(default_factory=lambda: f"plan-{uuid4().hex[:8]}")
    selected_block_id: str = Field(..., description="Verified operable HyperFrames donor block ID.")
    block_category: str = Field(default="general")
    creative_treatment: str = Field(default="standard_high_engagement")
    aspect_ratio: str = Field(default="9:16")
    duration_seconds: float = Field(default=60.0)
    duration_policy: DurationPolicy = Field(default=DurationPolicy.TARGET)
    delivery_formats: List[str] = Field(default_factory=lambda: ["mp4/h264/aac"])
    planned_steps: List[str] = Field(
        default_factory=lambda: [
            "resolve_block",
            "compose_project",
            "render_composition",
            "ffprobe_verify",
            "persist_library",
            "check_delivery_credentials",
        ]
    )
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MediaVerificationResult(BaseModel):
    """Rigorous physical media verification report — no synthetic fixtures or unprobed files."""
    file_path: str
    file_size_bytes: int
    sha256_hash: str
    probe_width: int
    probe_height: int
    probe_duration_sec: float
    video_codec: str
    audio_codec: Optional[str] = None
    is_verified: bool = False
    verification_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error_detail: Optional[str] = None


class Agent5DistributionHandoffContract(BaseModel):
    """
    Immutable contract for handoff to Agent 5 distribution service.
    Fails closed if target channel credentials or providers are not connected.
    """
    handoff_id: str = Field(default_factory=lambda: f"hnd-{uuid4().hex[:10]}")
    job_id: str
    idempotency_token: str
    render_file_sha256: str
    media_path: str
    project_id: str
    revision_id: int
    destination_channel: str
    schedule_window: Optional[Dict[str, str]] = None
    permission_scope: List[str] = Field(default_factory=lambda: ["content_publish", "metadata_write"])
    publish_authorized: bool = Field(default=False, alias="user_authorized")
    provider_status: str = "PENDING_CREDENTIALS"  # CONNECTED | NOT_CONNECTED | PENDING_CREDENTIALS
    fail_closed: bool = True
    error_truth: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    model_config = ConfigDict(populate_by_name=True)

    @property
    def user_authorized(self) -> bool:
        return self.publish_authorized


class StateTransitionEvent(BaseModel):
    """Audit log of individual state transitions."""
    from_state: OutcomeJobState
    to_state: OutcomeJobState
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    reason: str = ""
    error_detail: Optional[str] = None


class OutcomeJobRecord(BaseModel):
    """Durable state record of an OAAS job for crash-resilience and auditability."""
    job_id: str = Field(default_factory=lambda: f"ojob-{uuid4().hex[:12]}")
    state: OutcomeJobState = OutcomeJobState.REQUESTED
    request: OutcomeRequestContract
    plan: Optional[OutcomePlan] = None
    project_id: Optional[str] = None
    revision_id: Optional[int] = None
    media_verification: Optional[MediaVerificationResult] = None
    library_asset_id: Optional[str] = None
    distribution_handoff: Optional[Agent5DistributionHandoffContract] = None
    retries_count: int = 0
    max_retries: int = 3
    error_code: Optional[str] = None
    error_truth: Optional[str] = None
    history: List[StateTransitionEvent] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
