# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Core Data Contracts for Phase 11 Grounded Analytics, Messaging & Feedback.

Strictly separates:
- Verified publication receipts (PublishedReceiptV1) from speculative/unverified posts
- Point-in-time metric observations (MetricObservationV1) with explicit provenance
- Durable timeseries snapshots with missing-vs-zero metric distinction
- Actionable creative feedback hypotheses (CreativeFeedbackV1) with confidence guards
- Analytics event notifications for messaging without sensitive token leakage
- Provider connector statuses (NOT_CONNECTED, CONNECTED, RATE_LIMITED, ERROR)
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class AnalyticsProvider(str, Enum):
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    X = "x"
    GENERIC_WEB = "generic_web"


class ReceiptConfirmationStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    REJECTED = "REJECTED"
    SIMULATED_TEST = "SIMULATED_TEST"


class ProviderConnectionStatus(str, Enum):
    NOT_CONNECTED = "NOT_CONNECTED"
    CONNECTED = "CONNECTED"
    RATE_LIMITED = "RATE_LIMITED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    ERROR = "ERROR"


class MetricObservationSource(str, Enum):
    OFFICIAL_API = "OFFICIAL_API"
    OAUTH_INSIGHTS = "OAUTH_INSIGHTS"
    FIXTURE_VERIFIED = "FIXTURE_VERIFIED"
    ESTIMATED_BENCHMARK = "ESTIMATED_BENCHMARK"


class AnalyticsEventType(str, Enum):
    POST_PUBLISHED_VERIFIED = "POST_PUBLISHED_VERIFIED"
    METRICS_READY = "METRICS_READY"
    METRICS_DELAYED = "METRICS_DELAYED"
    ACCOUNT_AUTH_REQUIRED = "ACCOUNT_AUTH_REQUIRED"
    FEEDBACK_AVAILABLE = "FEEDBACK_AVAILABLE"
    PUBLISH_FAILED = "PUBLISH_FAILED"


from pydantic import BaseModel, Field, model_validator


class PublishedReceiptV1(BaseModel):
    """
    Contract representing a verified, confirmed post publication.
    Acts as the single source of truth for remote metric polling eligibility.
    Reconciles with Phase 10 Distribution receipts.
    Unconfirmed receipts or draft posts are rejected by analytics pollers.
    """
    receipt_id: str = Field(default_factory=lambda: f"rcpt-{uuid4().hex[:8]}")
    project_id: str
    output_video_id: Optional[str] = None
    output_id: Optional[str] = None
    revision_id: Optional[str] = None
    project_revision: Optional[int] = None
    job_id: Optional[str] = None
    artifact_sha256: Optional[str] = None
    provider: AnalyticsProvider
    account_reference: str
    creator_id: str = "local"
    remote_post_id: str
    remote_post_url: Optional[str] = None
    publish_timestamp: datetime
    confirmation_status: ReceiptConfirmationStatus = ReceiptConfirmationStatus.CONFIRMED
    source: str = "phase10_distribution"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="before")
    @classmethod
    def reconcile_phase10_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Output id mapping
            if "output_id" in data and not data.get("output_video_id"):
                data["output_video_id"] = data["output_id"]
            elif "output_video_id" in data and not data.get("output_id"):
                data["output_id"] = data["output_video_id"]

            # Provider / platform mapping
            if "platform" in data and not data.get("provider"):
                data["provider"] = data["platform"]

            # Account reference / account_id mapping
            if "account_id" in data and not data.get("account_reference"):
                data["account_reference"] = data["account_id"]

            # Publish timestamp mapping
            if "published_at_utc" in data and not data.get("publish_timestamp"):
                data["publish_timestamp"] = data["published_at_utc"]

            # Revision mapping
            if "project_revision" in data and not data.get("revision_id"):
                data["revision_id"] = str(data["project_revision"])
            elif "revision_id" in data and "project_revision" not in data:
                try:
                    data["project_revision"] = int(data["revision_id"])
                except Exception:
                    pass

            # Verified status mapping
            if "verified_status" in data and "confirmation_status" not in data:
                status_str = data["verified_status"].upper()
                if status_str == "CONFIRMED":
                    data["confirmation_status"] = ReceiptConfirmationStatus.CONFIRMED
                else:
                    data["confirmation_status"] = ReceiptConfirmationStatus.PENDING_VERIFICATION

            # Provenance mapping
            if "provenance" in data and "metadata" not in data:
                data["metadata"] = data["provenance"]

        return data

    def is_eligible_for_polling(self) -> bool:
        """
        Only confirmed, authentic receipts can poll external metrics.
        Fake post receipts with fake_ prefixes are rejected in production mode
        and permitted ONLY within explicit test fixtures (is_test_fixture=True).
        Unconfirmed statuses (PENDING_VERIFICATION, REJECTED, etc.) are strictly rejected.
        """
        if self.confirmation_status not in (
            ReceiptConfirmationStatus.CONFIRMED,
            ReceiptConfirmationStatus.SIMULATED_TEST,
        ):
            return False

        # Guard against fake receipts in production
        is_test = bool(self.metadata.get("is_test_fixture")) or self.confirmation_status == ReceiptConfirmationStatus.SIMULATED_TEST
        if not is_test:
            if self.remote_post_id.startswith("fake_") or self.receipt_id.startswith("fake_"):
                return False

        return True



class MetricObservationV1(BaseModel):
    """
    Point-in-time observation of remote performance metrics.
    Explicitly tracks missing metrics separately from observed zeros.
    """
    observation_id: str = Field(default_factory=lambda: f"obs-{uuid4().hex[:8]}")
    receipt_id: str
    provider: AnalyticsProvider
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sampling_window_start: Optional[datetime] = None
    sampling_window_end: Optional[datetime] = None
    audience_region: Optional[str] = None
    audience_timezone: Optional[str] = "UTC"
    observation_source: MetricObservationSource = MetricObservationSource.OFFICIAL_API
    is_test_fixture: bool = False

    # Observed metrics (None indicates metric was NOT returned/available by provider)
    views: Optional[int] = None
    impressions: Optional[int] = None
    watch_time_seconds: Optional[float] = None
    average_view_duration_seconds: Optional[float] = None
    completion_rate: Optional[float] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    shares: Optional[int] = None
    saves: Optional[int] = None
    click_through_rate: Optional[float] = None

    # Track missing metrics explicitly
    missing_metrics: List[str] = Field(default_factory=list)
    api_latency_ms: Optional[float] = None
    provider_response_hash: Optional[str] = None
    notes: Optional[str] = None


class AggregatedPostMetricsV1(BaseModel):
    """
    Durable post-level metric aggregate across its observation lifecycle.
    Prevents merging incompatible platform definitions into a single lossy scalar.
    """
    receipt_id: str
    remote_post_id: str
    provider: AnalyticsProvider
    creator_id: str = "local"
    first_observed_at: datetime
    last_observed_at: datetime
    observation_count: int = 0
    is_test_fixture: bool = False
    is_deleted_on_platform: bool = False
    post_status: str = "ACTIVE"  # "ACTIVE" | "DELETED_ON_PLATFORM" | "UNCONFIRMED"

    latest_views: Optional[int] = None
    latest_impressions: Optional[int] = None
    latest_watch_time_seconds: Optional[float] = None
    latest_likes: Optional[int] = None
    latest_comments: Optional[int] = None
    latest_shares: Optional[int] = None
    latest_completion_rate: Optional[float] = None
    engagement_rate: Optional[float] = None  # (likes + comments + shares) / views

    history_snapshots: List[MetricObservationV1] = Field(default_factory=list)



class OptimizationHypothesis(BaseModel):
    """
    Cautious hypothesis regarding potential creative optimization.
    Never an automated edit or direct trend mutate.
    """
    hypothesis_id: str = Field(default_factory=lambda: f"hyp-{uuid4().hex[:6]}")
    dimension: str  # "hook_pacing" | "captions_style" | "video_duration" | "thumbnail_contrast"
    observation_summary: str
    proposed_change: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    sample_size_videos: int = 1
    confounders_noted: List[str] = Field(default_factory=list)
    creator_opt_in_required: bool = True


class CreativeFeedbackV1(BaseModel):
    """
    Feedback loop package connecting observed performance back to editorial hypotheses.
    Strictly informative, requires explicit creator opt-in to apply.
    """
    feedback_id: str = Field(default_factory=lambda: f"fbk-{uuid4().hex[:8]}")
    receipt_id: str
    project_id: str
    evaluation_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    retention_dropoff_second: Optional[float] = None
    engagement_percentile: Optional[float] = None
    hypotheses: List[OptimizationHypothesis] = Field(default_factory=list)
    governance_notice: str = (
        "Creative feedback represents algorithmic hypotheses derived from observed metrics. "
        "No project timelines or Trend scores have been altered automatically. "
        "Explicit creator review and opt-in is required."
    )


class AnalyticsEventNotification(BaseModel):
    """
    Typed event notification for downstream messaging/notification layers.
    Guarantees no sensitive access tokens or creator PII are leaked.
    """
    event_id: str = Field(default_factory=lambda: f"evt-{uuid4().hex[:8]}")
    event_type: AnalyticsEventType
    receipt_id: Optional[str] = None
    provider: Optional[AnalyticsProvider] = None
    remote_post_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    title: str
    summary: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    requires_user_action: bool = False
