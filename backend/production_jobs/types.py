# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Data contracts and classifications for durable production jobs and recovery."""

import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class ErrorClassification(str, Enum):
    TRANSIENT_RENDER_IO = "TRANSIENT_RENDER_IO"
    INTERRUPTED_CRASH = "INTERRUPTED_CRASH"
    CORRUPTED_ARTIFACT = "CORRUPTED_ARTIFACT"
    SOURCE_INACCESSIBLE = "SOURCE_INACCESSIBLE"
    RIGHTS_VIOLATION = "RIGHTS_VIOLATION"
    CODEC_OR_FORMAT_UNSUPPORTED = "CODEC_OR_FORMAT_UNSUPPORTED"
    USER_CANCELLED = "USER_CANCELLED"
    UNKNOWN_EXECUTION_ERROR = "UNKNOWN_EXECUTION_ERROR"


class RecoveryClassification(str, Enum):
    SAFE_RETRY = "SAFE_RETRY"
    RESUME = "RESUME"
    OPERATOR_ACTION_REQUIRED = "OPERATOR_ACTION_REQUIRED"
    HARD_BLOCKER = "HARD_BLOCKER"


class OutputCheckpoint(BaseModel):
    output_id: str
    state: str = "PENDING"  # PENDING, PROCESSING, SUCCEEDED, FAILED, CANCELLED
    attempts: int = 0
    max_attempts: int = 3
    artifact_id: Optional[str] = None
    file_path: Optional[str] = None
    file_hash: Optional[str] = None
    file_size_bytes: Optional[int] = None
    error_detail: Optional[str] = None
    error_classification: Optional[str] = None
    recovery_action: Optional[str] = None
    updated_at: str = Field(default_factory=_utc_now_iso)


class StateTransitionRecord(BaseModel):
    timestamp: str = Field(default_factory=_utc_now_iso)
    from_state: str
    to_state: str
    detail: Optional[str] = None


class JobRecord(BaseModel):
    job_id: str
    request_fingerprint: str
    run_id: str
    contract_id: Optional[str] = None
    project_id: Optional[str] = None
    user_id: str = "local"
    status: str = "PENDING"  # RUNNING, COMPLETE, PARTIAL, BLOCKED, CANCELLED, FAILED
    created_at: str = Field(default_factory=_utc_now_iso)
    updated_at: str = Field(default_factory=_utc_now_iso)
    immutable_request: Dict[str, Any] = Field(default_factory=dict)
    output_checkpoints: Dict[str, OutputCheckpoint] = Field(default_factory=dict)
    transitions: List[StateTransitionRecord] = Field(default_factory=list)
    step_events: List[Dict[str, Any]] = Field(default_factory=list)
    blockers: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    attempted_effects: List[str] = Field(default_factory=list)
    cancelled: bool = False
