# Copyright (c) 2026 ViralMint. All rights reserved.
# Deterministic viral opportunity scoring service.
from datetime import datetime, timezone
import math
from typing import Any, Optional


SCORE_VERSION = "v2.0_deterministic"


def calculate_viral_opportunity_score(
    video: dict[str, Any],
    cohort: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """
    Calculate a documented, deterministic, bounded 0-100 viral opportunity score
    using genuinely available signals:
      - View velocity (views per hour) relative to publication age
      - Recency decay (fresher uploads receive higher opportunity rank)
      - Absolute view volume (log-scaled)
      - Relative cohort percentile within the comparable search results
      - Engagement rate (likes + comments) when available, gracefully re-weighted when unavailable.

    Returns a dictionary containing the final score, breakdown, metadata, and unavailable fields.
    """
    def _read_metric(key: str, default: float) -> float:
        try:
            val = float(video.get(key, default) or default)
        except (TypeError, ValueError):
            return default
        return val if val == val and val not in (float("inf"), float("-inf")) else default

    raw_views = video.get("views")
    unavailable_fields = []
    if raw_views is None:
        unavailable_fields.append("views")
        if video.get("likes") is None:
            unavailable_fields.append("likes")
        if video.get("comments") is None:
            unavailable_fields.append("comments")
        if not video.get("upload_date"):
            unavailable_fields.append("upload_date")
        return {
            "score": None,
            "score_version": SCORE_VERSION,
            "views_per_hour": 0.0,
            "breakdown": {},
            "unavailable_fields": unavailable_fields,
            "status": "not_scored",
        }

    views = max(_read_metric("views", 0.0), 0.0)
    raw_likes = video.get("likes")
    raw_comments = video.get("comments")

    has_likes = raw_likes is not None and int(raw_likes) > 0
    has_comments = raw_comments is not None and int(raw_comments) > 0
    if not has_likes:
        unavailable_fields.append("likes")
    if not has_comments:
        unavailable_fields.append("comments")

    likes = max(_read_metric("likes", 0.0), 0.0)
    comments = max(_read_metric("comments", 0.0), 0.0)

    # 1. Publication age and velocity
    upload_dt = video.get("upload_date")
    if upload_dt:
        if isinstance(upload_dt, str):
            try:
                upload_dt = datetime.fromisoformat(upload_dt.replace("Z", "+00:00"))
            except Exception:
                upload_dt = None

    if upload_dt and isinstance(upload_dt, datetime):
        if upload_dt.tzinfo is None:
            upload_dt = upload_dt.replace(tzinfo=timezone.utc)
        now_utc = datetime.now(timezone.utc)
        diff_hours = (now_utc - upload_dt).total_seconds() / 3600.0
        hours_active = max(diff_hours, 1.0)
        days_active = max(hours_active / 24.0, 0.04)
    else:
        # Default publication window: 30 days
        hours_active = 720.0
        days_active = 30.0
        unavailable_fields.append("upload_date")

    vph = views / hours_active
    video["views_per_hour"] = round(vph, 1)

    # 2. Components [0.0 - 1.0]
    # Velocity factor: log scale benchmarked against 10,000 vph
    # 10 vph -> ~0.25, 100 vph -> 0.50, 1,000 vph -> 0.75, 10,000+ vph -> 1.0
    vel_log = math.log10(max(vph, 1.0))
    velocity_factor = min(max(vel_log / 4.0, 0.0), 1.0)

    # Recency factor: hyperbola with half-life around 14 days
    recency_factor = 1.0 / (1.0 + (days_active / 14.0))

    # Volume factor: log scale benchmarked against 10,000,000 views
    vol_log = math.log10(max(views, 1.0))
    volume_factor = min(max(vol_log / 7.0, 0.0), 1.0)

    # 3. Cohort percentile
    cohort_factor = 0.5
    if cohort and len(cohort) > 1:
        cohort_views = sorted([float(c.get("views") or 0.0) for c in cohort])
        rank = sum(1 for cv in cohort_views if views >= cv)
        cohort_factor = rank / len(cohort_views)

    # 4. Outlier score
    channel_avg = _read_metric("channel_avg_views", 0.0) or None
    if not channel_avg or channel_avg < 1:
        sub_count = _read_metric("subscriber_count", 0.0)
        channel_avg = max(sub_count * 0.03, 100.0) if sub_count > 0 else None
    if channel_avg and channel_avg > 0:
        video["outlier_score"] = round(views / channel_avg, 1)

    # 5. Weighted composition
    has_engagement = (has_likes or has_comments) and views > 0
    if has_engagement:
        engagement_ratio = (likes + (comments * 2.0)) / max(views, 1.0)
        # 8% engagement is 1.0
        engagement_factor = min(max(engagement_ratio / 0.08, 0.0), 1.0)
        # Weights: Velocity 30%, Recency 25%, Cohort 20%, Volume 15%, Engagement 10%
        raw_score = (
            (velocity_factor * 0.30)
            + (recency_factor * 0.25)
            + (cohort_factor * 0.20)
            + (volume_factor * 0.15)
            + (engagement_factor * 0.10)
        )
    else:
        # Re-weighted without engagement: Velocity 35%, Recency 30%, Cohort 20%, Volume 15%
        engagement_factor = None
        raw_score = (
            (velocity_factor * 0.35)
            + (recency_factor * 0.30)
            + (cohort_factor * 0.20)
            + (volume_factor * 0.15)
        )

    # Bound strictly between 0.0 and 100.0
    if views == 0.0:
        final_score = 0.0
    else:
        final_score = round(min(max(raw_score * 100.0, 0.0), 100.0), 1)

    return {
        "score": final_score,
        "score_version": SCORE_VERSION,
        "calculated_at": datetime.now(timezone.utc).isoformat(),
        "views_per_hour": round(vph, 1),
        "outlier_score": video.get("outlier_score"),
        "input_metrics": {
            "views": int(views),
            "likes": int(likes) if has_likes else None,
            "comments": int(comments) if has_comments else None,
            "duration_seconds": video.get("duration_seconds"),
            "hours_active": round(hours_active, 1),
        },
        "unavailable_fields": unavailable_fields,
        "cohort_percentile": round(cohort_factor * 100.0, 1),
        "components": {
            "velocity": round(velocity_factor, 3),
            "recency": round(recency_factor, 3),
            "volume": round(volume_factor, 3),
            "cohort": round(cohort_factor, 3),
            "engagement": round(engagement_factor, 3) if engagement_factor is not None else None,
        },
    }
