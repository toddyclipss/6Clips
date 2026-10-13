# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Models for Authorized Trends Discovery, Editorial Role Classification,
and Source Suitability Scoring.

Distinctly separates:
- Editorial Role (creative reference vs editable source candidate vs topic research)
- Availability of physical bytes (metadata-only vs locally ingested bytes)
- Permitted uses (reference only vs creator-owned vs transformative fair use)
- Analysis state (discovered vs probed vs ingested vs blocked)
- TrendScore (velocity, volume, recency, outlier ratio)
- Source Suitability (duration margin, editability margin)
- Highlight Quality (semantic/transcript score, NOT_ASSESSED prior to ingestion)
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EditorialRole(str, Enum):
    CREATIVE_REFERENCE = "creative_reference"
    EDITABLE_SOURCE_CANDIDATE = "editable_source_candidate"
    TOPIC_RESEARCH_REFERENCE = "topic_research_reference"
    MARGINAL_SOURCE = "marginal_source"
    UNSUITABLE_RAW = "unsuitable_raw"


class AnalysisState(str, Enum):
    DISCOVERED = "discovered"
    METADATA_ONLY = "metadata_only"
    PROBED = "probed"
    INGESTED = "ingested"
    BLOCKED = "blocked"


class PermittedUse(str, Enum):
    REFERENCE_ONLY = "reference_only"
    TRANSFORMATIVE_FAIR_USE_PENDING = "transformative_fair_use_pending"
    CREATOR_OWNED = "creator_owned"
    PUBLIC_DOMAIN_OR_CC = "public_domain_or_cc"
    UNAUTHORIZED = "unauthorized"


class PhysicalBytesAvailability(str, Enum):
    NOT_FETCHED = "not_fetched"
    AVAILABLE_LOCAL = "available_local"
    STREAM_ONLY = "stream_only"
    FETCH_FAILED = "fetch_failed"
    BLOCKED_RIGHTS = "blocked_rights"


class SourceSuitability(BaseModel):
    """Evaluates physical and structural suitability for video editing/clipping."""
    status: str = Field(description="Suitability classification identifier")
    is_suitable: bool = Field(default=False)
    is_editable_source: bool = Field(default=False)
    is_reference: bool = Field(default=True)
    trend_role: EditorialRole = Field(default=EditorialRole.CREATIVE_REFERENCE)
    role_label: str = Field(default="Research Reference")
    format_category: str = Field(default="unknown")
    duration_seconds: Optional[int] = Field(default=None)
    min_required_seconds: int = Field(default=180)
    recommended_seconds: int = Field(default=240)
    surplus_seconds: int = Field(default=0)
    deficit_seconds: int = Field(default=0)
    reason: str = Field(default="")


class TrendScore(BaseModel):
    """
    Normalized virality and trend momentum scoring.
    Maintains transparency by distinguishing zero values from missing metrics.
    """
    virality_score: float = Field(ge=0.0, le=100.0, default=0.0)
    views: int = Field(default=0)
    likes: Optional[int] = Field(default=None)
    comments: Optional[int] = Field(default=None)
    shares: Optional[int] = Field(default=None)
    views_per_hour: Optional[float] = Field(default=None)
    outlier_score: Optional[float] = Field(default=None)
    missing_metrics: List[str] = Field(default_factory=list)
    input_provenance: str = Field(default="unknown_source")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cache_freshness_seconds: float = Field(default=0.0)


class HighlightQuality(BaseModel):
    """
    Semantic highlight quality. Must remain NOT_ASSESSED until
    physical bytes and full speech transcripts are probed.
    """
    status: str = Field(default="NOT_ASSESSED")
    assessed: bool = Field(default=False)
    score: Optional[float] = Field(default=None)
    reason: str = Field(
        default="Highlight quality requires media ingestion and transcript scoring; not inferable from search metadata."
    )


class DiscoveryItem(BaseModel):
    """Unified discovery item contract preserving source lineage and role."""
    id: str
    platform: str
    video_id: Optional[str] = None
    video_url: Optional[str] = None
    embed_url: Optional[str] = None
    title: str
    description: str = ""
    author: str = ""
    author_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    upload_date: Optional[datetime] = None
    editorial_role: EditorialRole = EditorialRole.CREATIVE_REFERENCE
    analysis_state: AnalysisState = AnalysisState.DISCOVERED
    permitted_use: PermittedUse = PermittedUse.REFERENCE_ONLY
    bytes_availability: PhysicalBytesAvailability = PhysicalBytesAvailability.NOT_FETCHED
    trend_score: TrendScore
    source_suitability: SourceSuitability
    highlight_quality: HighlightQuality = Field(default_factory=HighlightQuality)
    blocked_reason: Optional[str] = None
    metadata_provenance: Dict[str, Any] = Field(default_factory=dict)
