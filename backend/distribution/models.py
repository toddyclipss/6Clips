# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Domain models for Phase 10: Approval, SEO, Distribution, and Scheduling."""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class DistributionStatus(str, Enum):
    """Publishing truth table statuses."""
    DRAFT = "DRAFT"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    WAITING_FOR_ACCOUNT = "WAITING_FOR_ACCOUNT"
    READY_TO_SCHEDULE = "READY_TO_SCHEDULE"
    SCHEDULED = "SCHEDULED"
    DISPATCHING = "DISPATCHING"
    PUBLISHED_VERIFIED = "PUBLISHED_VERIFIED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"
    PARTIAL = "PARTIAL"


class AccountState(str, Enum):
    """Account connectivity and authorization state."""
    NOT_CONNECTED = "NOT_CONNECTED"
    INSUFFICIENT_SCOPES = "INSUFFICIENT_SCOPES"
    EXPIRED = "EXPIRED"
    READY = "READY"


class PlatformKind(str, Enum):
    """Supported distribution platforms."""
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    X = "x"


class ApprovalReceipt(BaseModel):
    """Server-authenticated approval acknowledgment contract for exact immutable revision."""
    approval_id: str = Field(default_factory=lambda: f"appr_{uuid4().hex[:12]}")
    output_id: str
    project_id: str
    project_revision: int
    artifact_sha256: str
    approved_by: str
    approved_at_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    consent_for_external_publish: bool = False
    signature: str = ""

    def compute_signature(self, secret: str = "6clips-distribution-secret") -> str:
        """Compute cryptographic HMAC SHA-256 signature binding approval to exact revision and hash."""
        payload = (
            f"{self.output_id}:{self.project_id}:{self.project_revision}:"
            f"{self.artifact_sha256}:{self.approved_by}:{self.approved_at_utc}:"
            f"{self.consent_for_external_publish}"
        )
        return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

    def verify_signature(self, secret: str = "6clips-distribution-secret") -> bool:
        """Verify the signature against tampering."""
        expected = self.compute_signature(secret)
        return hmac.compare_digest(self.signature, expected)


class PlatformSEOMetadata(BaseModel):
    """Platform-specific SEO metadata."""
    platform: str
    title: str = ""
    description: str = ""
    hashtags: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    thumbnail_url: Optional[str] = None
    thumbnail_path: Optional[str] = None
    visibility: str = "public"  # public | unlisted | private
    aspect_ratio: str = "9:16"
    is_ai_draft: bool = False
    creator_notes: Optional[str] = None


class PlatformAccount(BaseModel):
    """Account reference without leaking credentials or tokens."""
    account_id: str
    user_id: str = "local"
    platform: str
    account_name: str
    handle: Optional[str] = None
    state: AccountState = AccountState.NOT_CONNECTED
    granted_scopes: List[str] = Field(default_factory=list)
    required_scopes: List[str] = Field(default_factory=list)
    can_publish: bool = False


class DistributionJob(BaseModel):
    """Typed Distribution Job model."""
    job_id: str = Field(default_factory=lambda: f"dist_{uuid4().hex[:12]}")
    user_id: str = "local"
    output_id: str
    project_id: str
    project_revision: int
    artifact_path: str
    artifact_sha256: str
    approval_receipt_id: str
    platform: str
    account_id: str
    seo_metadata: PlatformSEOMetadata
    scheduled_time_utc: str
    timezone: str = "UTC"
    status: DistributionStatus = DistributionStatus.READY_TO_SCHEDULE
    idempotency_key: str = Field(default_factory=lambda: f"idem_{uuid4().hex}")
    retry_count: int = 0
    max_retries: int = 3
    last_attempt_at: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    error_category: Optional[str] = None  # RETRYABLE | FATAL
    remote_post_id: Optional[str] = None
    remote_post_url: Optional[str] = None
    receipt_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PublishedReceiptV1(BaseModel):
    """Normalized immutable receipt for confirmed remote publications."""
    schema_version: str = "distribution.receipt.v1"
    receipt_id: str = Field(default_factory=lambda: f"rcpt_{uuid4().hex[:12]}")
    job_id: str
    output_id: str
    project_id: str
    project_revision: int
    artifact_sha256: str
    platform: str
    account_id: str
    account_handle: Optional[str] = None
    remote_post_id: str
    remote_post_url: str
    published_at_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    verified_status: str = "CONFIRMED"
    provenance: Dict[str, Any] = Field(default_factory=dict)
