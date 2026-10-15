# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Data models for Chat-First OAAS Orchestration and Agent-Operated URL Ingestion."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from uuid import uuid4
from pydantic import BaseModel, Field


class ChatGoalStatus(str, Enum):
    """Linear progression of a chat goal outcome."""
    RECEIVED = "RECEIVED"
    INGESTING_MEDIA = "INGESTING_MEDIA"
    PLANNING = "PLANNING"
    PRODUCING = "PRODUCING"
    EDITING = "EDITING"
    RENDERED = "RENDERED"
    VERIFIED = "VERIFIED"
    READY_FOR_DELIVERY = "READY_FOR_DELIVERY"
    PENDING_CREDENTIALS = "PENDING_CREDENTIALS"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class IngestionBlockerCode(str, Enum):
    """Machine-readable security & policy blocker codes for agent URL ingestion."""
    BLOCKED_INVALID_SCHEME = "BLOCKED_INVALID_SCHEME"
    BLOCKED_SSRF_PRIVATE_IP = "BLOCKED_SSRF_PRIVATE_IP"
    BLOCKED_MALFORMED_URL = "BLOCKED_MALFORMED_URL"
    BLOCKED_DISALLOWED_HOST = "BLOCKED_DISALLOWED_HOST"
    BLOCKED_UNAUTHORIZED_STREAM = "BLOCKED_UNAUTHORIZED_STREAM"
    BLOCKED_DURATION_EXCEEDED = "BLOCKED_DURATION_EXCEEDED"
    BLOCKED_FILE_SIZE_EXCEEDED = "BLOCKED_FILE_SIZE_EXCEEDED"
    BLOCKED_RESTRICTED_ACCESS = "BLOCKED_RESTRICTED_ACCESS"
    BLOCKED_FETCH_FAILED = "BLOCKED_FETCH_FAILED"


class UrlIngestionRequest(BaseModel):
    """Request envelope for secure agent-operated video URL ingestion."""
    url: str
    user_authorized: bool = Field(
        default=False,
        description="Whether the user explicitly authorized ingestion and confirmed rights to the video."
    )
    max_duration_sec: float = Field(default=14400.0, description="Max permissible duration in seconds (4h).")
    max_bytes: int = Field(default=2 * 1024 * 1024 * 1024, description="Max permissible file size in bytes (2GB).")
    project_id: Optional[str] = None
    user_id: str = "local"


class UrlIngestionResult(BaseModel):
    """Result of agent-operated URL security validation and ingestion."""
    url: str
    is_allowed: bool
    resolved_ip: Optional[str] = None
    file_path: Optional[str] = None
    duration_sec: Optional[float] = None
    file_size_bytes: Optional[int] = None
    sha256_hash: Optional[str] = None
    blocker_code: Optional[IngestionBlockerCode] = None
    blocker_reason: Optional[str] = None
    asset_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ChatGoalProgressEvent(BaseModel):
    """Progress event emitted during chat goal execution."""
    step: str
    status: ChatGoalStatus
    detail: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ChatGoalOutcomeResponse(BaseModel):
    """Structured response returned to persistent Main Agent chat stream."""
    job_id: str = Field(default_factory=lambda: f"cjob-{uuid4().hex[:10]}")
    project_id: str
    revision_id: int
    status: ChatGoalStatus
    message: str
    artifact_links: List[Dict[str, str]] = Field(default_factory=list)
    preview_details: Dict[str, Any] = Field(default_factory=dict)
    publication_status: str = "NOT_CONNECTED"
    blocker_code: Optional[str] = None
    blocker_reason: Optional[str] = None
    history: List[ChatGoalProgressEvent] = Field(default_factory=list)
    completed_at: Optional[str] = None
