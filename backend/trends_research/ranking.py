# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Ranking and Editorial Role Classification Engine.

Implements:
1. Strict separation between:
   - TrendScore (virality velocity and engagement)
   - Source Suitability (physical editing margin)
   - Highlight Quality (semantic content value - NOT_ASSESSED prior to transcript analysis)
2. Transparent missing-vs-zero metric reporting.
3. Automated candidate selection for both creative reference and clip extraction
   without prompting the user for video IDs or project IDs.
4. Specific BLOCKED state reporting and legitimate alternatives when source access fails.
"""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.trends_research.models import (
    AnalysisState,
    DiscoveryItem,
    EditorialRole,
    HighlightQuality,
    PermittedUse,
    PhysicalBytesAvailability,
    SourceSuitability,
    TrendScore,
)

logger = logging.getLogger(__name__)


def classify_source_suitability(
    duration_seconds: Optional[int],
    target_clips: int = 3,
    clip_duration_sec: int = 60,
    has_audio: Optional[bool] = None,
    has_video: Optional[bool] = None,
) -> SourceSuitability:
    """
    Classify video source suitability for multi-clip editing.
    Respects physical requirements and distinguishes references from editable footage.
    """
    min_needed = max(target_clips * clip_duration_sec, 60)
    recommended_min = min_needed + 60

    if duration_seconds is None:
        return SourceSuitability(
            status="unknown_duration",
            is_suitable=False,
            is_editable_source=False,
            is_reference=True,
            trend_role=EditorialRole.CREATIVE_REFERENCE,
            role_label="Research Reference (Duration Unverified)",
            format_category="unknown",
            duration_seconds=None,
            min_required_seconds=min_needed,
            recommended_seconds=recommended_min,
            surplus_seconds=0,
            deficit_seconds=0,
            reason="Duration unverified until media probe; preserved as creative reference.",
        )

    if duration_seconds < min_needed:
        deficit = min_needed - duration_seconds
        return SourceSuitability(
            status="unsuitable_too_short",
            is_suitable=False,
            is_editable_source=False,
            is_reference=True,
            trend_role=EditorialRole.CREATIVE_REFERENCE,
            role_label="Research Reference (Trending Hooks & Pacing)",
            format_category="short_form",
            duration_seconds=duration_seconds,
            min_required_seconds=min_needed,
            recommended_seconds=recommended_min,
            surplus_seconds=0,
            deficit_seconds=deficit,
            reason=(
                f"Short-form content ({duration_seconds}s) serves as a valuable research reference "
                f"for trending hooks and pacing, but lacks sufficient duration for {target_clips} "
                f"distinct {clip_duration_sec}s clips (requires at least {min_needed}s)."
            ),
        )

    if duration_seconds < recommended_min:
        return SourceSuitability(
            status="marginal",
            is_suitable=True,
            is_editable_source=True,
            is_reference=True,
            trend_role=EditorialRole.MARGINAL_SOURCE,
            role_label="Marginal Source Candidate",
            format_category="marginal",
            duration_seconds=duration_seconds,
            min_required_seconds=min_needed,
            recommended_seconds=recommended_min,
            surplus_seconds=0,
            deficit_seconds=0,
            reason=(
                f"Duration ({duration_seconds}s) satisfies the minimum {min_needed}s threshold for "
                f"{target_clips} clips but has limited editorial margin (< {recommended_min}s)."
            ),
        )

    surplus = duration_seconds - recommended_min
    return SourceSuitability(
        status="suitable_longform",
        is_suitable=True,
        is_editable_source=True,
        is_reference=True,
        trend_role=EditorialRole.EDITABLE_SOURCE_CANDIDATE,
        role_label="Substantial Editable Source Footage",
        format_category="long_form",
        duration_seconds=duration_seconds,
        min_required_seconds=min_needed,
        recommended_seconds=recommended_min,
        surplus_seconds=surplus,
        deficit_seconds=0,
        reason=(
            f"Substantial footage ({duration_seconds}s) provides sufficient continuous material "
            f"for {target_clips} distinct {clip_duration_sec}s clips with ample editorial headroom."
        ),
    )


def compute_deterministic_trend_score(
    raw_data: Dict[str, Any],
    provenance: str = "open_web_discovery",
    cache_freshness_seconds: float = 0.0,
) -> TrendScore:
    """
    Compute normalized trend score (0..100) while tracking which metrics were genuinely present
    versus missing (so missing metrics are not fraudulently reported as zero).
    """
    missing: List[str] = []

    def _extract_metric(key: str) -> Optional[int]:
        val = raw_data.get(key)
        if val is None:
            missing.append(key)
            return None
        try:
            parsed = int(val)
            return max(parsed, 0)
        except (ValueError, TypeError):
            missing.append(key)
            return None

    views = _extract_metric("views")
    if views is None:
        views = 0

    likes = _extract_metric("likes")
    comments = _extract_metric("comments")
    shares = _extract_metric("shares")

    upload_dt = raw_data.get("upload_date")
    now_utc = datetime.now(timezone.utc)
    if upload_dt and isinstance(upload_dt, datetime):
        if upload_dt.tzinfo is None:
            upload_dt = upload_dt.replace(tzinfo=timezone.utc)
        hours_active = max((now_utc - upload_dt).total_seconds() / 3600.0, 1.0)
        days_active = max(hours_active / 24.0, 1.0)
    else:
        hours_active = 720.0
        days_active = 30.0

    # Views per hour velocity
    vph = views / hours_active if views > 0 else 0.0
    velocity_factor = min(vph / 5000.0, 1.0)

    # Engagement ratio (likes + comments*2) / views if available
    if likes is not None and views > 0:
        c_count = comments or 0
        engagement_ratio = (likes + c_count * 2.0) / views
        engagement_factor = min(engagement_ratio * 10.0, 1.0)
    else:
        engagement_factor = 0.5  # Neutral assumption when engagement metrics unverified

    recency_factor = 1.0 / (1.0 + days_active / 30.0)
    volume_factor = min(views / 500000.0, 1.0)

    score_ratio = (
        engagement_factor * 0.30
        + velocity_factor * 0.30
        + recency_factor * 0.20
        + volume_factor * 0.20
    )
    final_score = round(min(max(score_ratio * 100.0, 0.0), 100.0), 2)

    return TrendScore(
        virality_score=final_score,
        views=views,
        likes=likes,
        comments=comments,
        shares=shares,
        views_per_hour=round(vph, 2),
        outlier_score=round(raw_data.get("outlier_score", 1.0), 2) if raw_data.get("outlier_score") else None,
        missing_metrics=sorted(list(set(missing))),
        input_provenance=provenance,
        timestamp=now_utc,
        cache_freshness_seconds=cache_freshness_seconds,
    )


def build_discovery_item(
    item_dict: Dict[str, Any],
    provenance: str = "youtube_trends_discovery",
    target_clips: int = 3,
    clip_duration_sec: int = 60,
    cache_freshness: float = 0.0,
) -> DiscoveryItem:
    """Build a strongly-typed DiscoveryItem separating editorial role from physical suitability."""
    item_id = item_dict.get("id") or item_dict.get("video_id") or str(uuid4())
    duration_s = item_dict.get("duration_seconds")
    suitability = classify_source_suitability(
        duration_s, target_clips=target_clips, clip_duration_sec=clip_duration_sec
    )
    trend_score = compute_deterministic_trend_score(
        item_dict, provenance=provenance, cache_freshness_seconds=cache_freshness
    )

    platform = str(item_dict.get("platform", "youtube")).lower()
    vid = item_dict.get("video_id")
    vurl = item_dict.get("video_url") or (f"https://youtube.com/watch?v={vid}" if vid and platform == "youtube" else None)
    embed_url = item_dict.get("embed_url") or (f"https://www.youtube-nocookie.com/embed/{vid}" if vid and platform == "youtube" else None)

    # Determine permitted use and physical byte availability honestly
    permitted_use = PermittedUse.REFERENCE_ONLY
    if item_dict.get("is_creator_owned"):
        permitted_use = PermittedUse.CREATOR_OWNED
    elif item_dict.get("is_public_domain"):
        permitted_use = PermittedUse.PUBLIC_DOMAIN_OR_CC

    bytes_avail = PhysicalBytesAvailability.NOT_FETCHED
    if item_dict.get("is_downloaded") or item_dict.get("local_path"):
        bytes_avail = PhysicalBytesAvailability.AVAILABLE_LOCAL
    elif item_dict.get("stream_url"):
        bytes_avail = PhysicalBytesAvailability.STREAM_ONLY

    # Editorial role defaults to suitability classification
    editorial_role = suitability.trend_role
    if platform == "news":
        editorial_role = EditorialRole.TOPIC_RESEARCH_REFERENCE
        permitted_use = PermittedUse.REFERENCE_ONLY

    return DiscoveryItem(
        id=item_id,
        platform=platform,
        video_id=vid,
        video_url=vurl,
        embed_url=embed_url,
        title=item_dict.get("title", "Untitled Trend"),
        description=str(item_dict.get("description", ""))[:500],
        author=item_dict.get("author", "Unknown Creator"),
        author_url=item_dict.get("author_url"),
        thumbnail_url=item_dict.get("thumbnail_url"),
        upload_date=item_dict.get("upload_date"),
        editorial_role=editorial_role,
        analysis_state=AnalysisState.METADATA_ONLY if bytes_avail == PhysicalBytesAvailability.NOT_FETCHED else AnalysisState.PROBED,
        permitted_use=permitted_use,
        bytes_availability=bytes_avail,
        trend_score=trend_score,
        source_suitability=suitability,
        highlight_quality=HighlightQuality(
            status="NOT_ASSESSED",
            assessed=False,
            score=None,
            reason="Highlight quality requires media ingestion and transcript scoring; not inferable from search metadata.",
        ),
        blocked_reason=item_dict.get("blocked_reason"),
        metadata_provenance={
            "source_service": provenance,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "query_niche": item_dict.get("niche"),
        },
    )


def select_best_editorial_candidates(
    items: List[DiscoveryItem],
    goal: str = "clip_repurposing",
    count: int = 1,
) -> List[DiscoveryItem]:
    """
    Automatically select the most suitable editorial candidate(s) without forcing
    the user to enter IDs or routine parameters.
    - If goal is 'clip_repurposing': selects items with EDITABLE_SOURCE_CANDIDATE first.
    - If goal is 'creative_reference' or 'topic_research': selects items with highest TrendScore.
    """
    if not items:
        return []

    if goal == "clip_repurposing":
        # Prioritize substantial editable sources, then highest virality score
        def _sort_key(item: DiscoveryItem):
            is_editable = 1 if item.editorial_role == EditorialRole.EDITABLE_SOURCE_CANDIDATE else 0
            is_marginal = 1 if item.editorial_role == EditorialRole.MARGINAL_SOURCE else 0
            return (is_editable, is_marginal, item.trend_score.virality_score)

        sorted_items = sorted(items, key=_sort_key, reverse=True)
        return sorted_items[:count]

    # Creative reference: highest trend score regardless of duration
    sorted_items = sorted(items, key=lambda i: i.trend_score.virality_score, reverse=True)
    return sorted_items[:count]


def create_blocked_state_response(
    niche: str,
    reason: str,
    alternatives: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Construct a clear, actionable BLOCKED state when source access is unavailable,
    suggesting legitimate alternatives rather than failing silently.
    """
    default_alts = [
        "Search open YouTube trends without API key via public recency route",
        "Provide direct creator footage or approved gameplay video URL",
        "Synthesize original commentary video using official news / patch notes",
    ]
    return {
        "status": "BLOCKED",
        "niche": niche,
        "reason": reason,
        "suggested_alternatives": alternatives or default_alts,
        "action_required": "Select an authorized source route or provide direct media.",
    }
