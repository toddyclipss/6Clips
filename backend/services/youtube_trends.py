# Copyright (c) 2026 ViralMint. All rights reserved.
# Authorial YouTube trends discovery service.
import asyncio
from datetime import datetime, timedelta
import logging
import re
from typing import Optional
import unicodedata

logger = logging.getLogger(__name__)


def _detect_query_language(text: str) -> str:
    """Detect language profile of the search query for relevance tuning."""
    cjk = 0
    for ch in text:
        name = unicodedata.name(ch, "")
        if "CJK" in name or "HIRAGANA" in name or "KATAKANA" in name:
            cjk += 1
    if cjk > 0:
        has_kana = any("HIRAGANA" in unicodedata.name(c, "") or "KATAKANA" in unicodedata.name(c, "") for c in text)
        return "ja" if has_kana else "zh"
    if any("\uAC00" <= ch <= "\uD7A3" or "\u1100" <= ch <= "\u11FF" for ch in text):
        return "ko"
    return "en"


def _format_search_cutoff(days: int = 30) -> str:
    """Compute ISO timestamp cutoff for trending video recency."""
    dt = datetime.utcnow() - timedelta(days=days)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso_duration(duration_str: str) -> Optional[int]:
    """Convert ISO-8601 duration string (e.g. PT1H4M20S) to total seconds."""
    if not duration_str:
        return None
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration_str)
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours or 0) * 3600 + int(minutes or 0) * 60 + int(seconds or 0)


def _parse_publish_date(date_str: str) -> Optional[datetime]:
    """Parse YouTube API timestamp into naive UTC datetime."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def _parse_relative_time(text: str) -> datetime:
    """Parse relative time string (e.g. '3 days ago', '14 hours ago') into UTC datetime."""
    now = datetime.utcnow()
    if not text:
        return now
    t = text.lower().strip()
    m_hour = re.search(r"(\d+)\s*(?:hour|hr|h)\b", t)
    if m_hour:
        return now - timedelta(hours=int(m_hour.group(1)))
    m_day = re.search(r"(\d+)\s*(?:day|d)\b", t)
    if m_day:
        return now - timedelta(days=int(m_day.group(1)))
    m_week = re.search(r"(\d+)\s*(?:week|w)\b", t)
    if m_week:
        return now - timedelta(days=int(m_week.group(1)) * 7)
    m_month = re.search(r"(\d+)\s*(?:month|m)\b", t)
    if m_month:
        return now - timedelta(days=int(m_month.group(1)) * 30)
    m_min = re.search(r"(\d+)\s*(?:minute|min|m)\b", t)
    if m_min:
        return now - timedelta(minutes=int(m_min.group(1)))
    return now


def _parse_views_string(text: str) -> int:
    """Parse view count text (e.g. '65,288 views', '1.2M views') into integer."""
    if not text:
        return 0
    m_m = re.search(r"([\d\.]+)\s*m\b", text, re.I)
    if m_m:
        return int(float(m_m.group(1)) * 1_000_000)
    m_k = re.search(r"([\d\.]+)\s*k\b", text, re.I)
    if m_k:
        return int(float(m_k.group(1)) * 1_000)
    m_num = re.search(r"(\d[\d\s,\.]*)", text)
    if m_num:
        clean = re.sub(r"[^\d]", "", m_num.group(1))
        return int(clean) if clean else 0
    return 0


def classify_suitability_for_clips(
    duration_seconds: Optional[int],
    target_clips: int = 3,
    clip_duration_sec: int = 60,
) -> dict:
    """Classify video duration suitability for multi-clip long-form extraction."""
    min_needed = target_clips * clip_duration_sec
    recommended_min = min_needed + 60
    if duration_seconds is None:
        return {
            "status": "unknown_duration",
            "is_suitable": False,
            "is_editable_source": False,
            "is_reference": True,
            "trend_role": "creative_reference",
            "role_label": "Research Reference (Duration Unverified)",
            "format_category": "unknown",
            "min_required_seconds": min_needed,
            "recommended_seconds": recommended_min,
            "reason": "Duration unverified until media probe; preserved as research reference.",
        }
    if duration_seconds < min_needed:
        return {
            "status": "unsuitable_too_short",
            "is_suitable": False,
            "is_editable_source": False,
            "is_reference": True,
            "trend_role": "creative_reference",
            "role_label": "Research Reference (Trending Hooks & Pacing)",
            "format_category": "short_form",
            "min_required_seconds": min_needed,
            "recommended_seconds": recommended_min,
            "deficit_seconds": min_needed - duration_seconds,
            "reason": f"Short-form content ({duration_seconds}s) serves as a valuable research reference for trending hooks and pacing, but is unsuitable as raw footage for {target_clips} distinct {clip_duration_sec}s clips.",
        }
    if duration_seconds < recommended_min:
        return {
            "status": "marginal",
            "is_suitable": True,
            "is_editable_source": True,
            "is_reference": True,
            "trend_role": "marginal_source",
            "role_label": "Marginal Source Candidate",
            "format_category": "marginal",
            "min_required_seconds": min_needed,
            "recommended_seconds": recommended_min,
            "reason": f"Duration ({duration_seconds}s) allows {target_clips} clips with limited editorial margin.",
        }
    return {
        "status": "suitable_longform",
        "is_suitable": True,
        "is_editable_source": True,
        "is_reference": True,
        "trend_role": "editable_source_candidate",
        "role_label": "Substantial Editable Source Footage",
        "format_category": "long_form",
        "min_required_seconds": min_needed,
        "recommended_seconds": recommended_min,
        "surplus_seconds": duration_seconds - recommended_min,
        "reason": f"Substantial footage ({duration_seconds}s) provides sufficient continuous material for {target_clips} distinct {clip_duration_sec}s clips.",
    }


def _search_youtube_public_recent(
    niche: str,
    max_results: int = 50,
    video_duration: str = "any",
    target_clips: int = 3,
    clip_duration_sec: int = 60,
) -> list[dict]:
    """Search YouTube for recent videos via public endpoint without API key."""
    import json
    import urllib.parse
    import urllib.request

    query_encoded = urllib.parse.quote_plus(niche)
    # Use duration-specific sp parameter if requested, or upload this month (EgQIAxAB)
    if video_duration == "medium":
        sp_token = "EgIYAw%3D%3D"
    elif video_duration == "long":
        sp_token = "EgIYAg%3D%3D"
    elif video_duration == "short":
        sp_token = "EgIYAQ%3D%3D"
    else:
        sp_token = "EgQIAxAB"
    url = f"https://www.youtube.com/results?search_query={query_encoded}&sp={sp_token}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="ignore")
        idx = html.find("ytInitialData =")
        if idx == -1:
            return []
        end = html.find(";</script>", idx)
        data = json.loads(html[idx + len("ytInitialData ="):end].strip())

        contents = (
            data.get("contents", {})
            .get("twoColumnSearchResultsRenderer", {})
            .get("primaryContents", {})
            .get("sectionListRenderer", {})
            .get("contents", [])
        )
        trends = []
        candidates = []
        for sec in contents:
            items = sec.get("itemSectionRenderer", {}).get("contents", [])
            for item in items:
                v = item.get("videoRenderer")
                if not v:
                    continue
                vid = v.get("videoId")
                if not vid:
                    continue
                title = v.get("title", {}).get("runs", [{}])[0].get("text", "")
                pub_text = v.get("publishedTimeText", {}).get("simpleText", "")
                view_text = v.get("viewCountText", {}).get("simpleText", "")
                uploader = v.get("ownerText", {}).get("runs", [{}])[0].get("text", "")
                uploader_nav = (
                    v.get("ownerText", {})
                    .get("runs", [{}])[0]
                    .get("navigationEndpoint", {})
                    .get("browseEndpoint", {})
                    .get("browseId", "")
                )
                thumbs = v.get("thumbnail", {}).get("thumbnails", [])
                thumb_url = thumbs[-1].get("url") if thumbs else f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
                length_text = v.get("lengthText", {}).get("simpleText", "")

                duration_s = None
                if length_text:
                    parts = [int(p) for p in length_text.split(":") if p.isdigit()]
                    if len(parts) == 2:
                        duration_s = parts[0] * 60 + parts[1]
                    elif len(parts) == 3:
                        duration_s = parts[0] * 3600 + parts[1] * 60 + parts[2]

                suitability = classify_suitability_for_clips(duration_s, target_clips=target_clips, clip_duration_sec=clip_duration_sec)

                candidates.append({
                    "platform": "youtube",
                    "requested_platform": "youtube",
                    "video_id": vid,
                    "video_url": f"https://youtube.com/watch?v={vid}",
                    "embed_url": f"https://www.youtube-nocookie.com/embed/{vid}",
                    "title": title,
                    "description": "",
                    "author": uploader,
                    "author_url": f"https://youtube.com/channel/{uploader_nav}" if uploader_nav else "",
                    "thumbnail_url": thumb_url,
                    "views": _parse_views_string(view_text),
                    "likes": 0,
                    "comments": 0,
                    "shares": 0,
                    "duration_seconds": duration_s,
                    "upload_date": _parse_relative_time(pub_text),
                    "aspect_ratio_status": "unverified_prior_to_ingest",
                    "suitability_for_3x60s": suitability,
                })

        # Apply video_duration filter strictly if requested (NEVER fallback to shorts on medium/long)
        if video_duration == "medium":
            matched = [c for c in candidates if c.get("duration_seconds") and 240 <= c["duration_seconds"] <= 1200]
            if not matched:
                matched = [c for c in candidates if c.get("duration_seconds") and c["duration_seconds"] >= 180]
            trends = matched
        elif video_duration == "long":
            matched = [c for c in candidates if c.get("duration_seconds") and c["duration_seconds"] > 1200]
            trends = matched
        elif video_duration == "short":
            matched = [c for c in candidates if c.get("duration_seconds") and c["duration_seconds"] < 240]
            trends = matched
        else:
            trends = candidates

        return trends[:max_results]
    except Exception as ex:
        logger.warning("YouTube public recency search failed: %s", ex)
        return []


async def search_youtube_trends(
    niche: str,
    api_key: Optional[str] = None,
    max_results: int = 50,
    video_duration: str = "any",
    purpose: str = "trend_research",
    target_clips: int = 3,
    clip_duration_sec: int = 60,
) -> list[dict]:
    """
    Search YouTube for high-velocity trending videos in a given niche.
    Ensures recency by filtering strictly for videos uploaded in the past 30 days.
    Supports purpose: 'trend_research' (creative references) vs 'editable_source_search' (footage suitable for editing).
    Supports video_duration: 'medium' (4-20m), 'long' (>20m), 'short' (<4m), or 'any'.
    """
    if purpose == "editable_source_search" and video_duration == "any":
        video_duration = "medium"
    if api_key:
        try:
            from googleapiclient.discovery import build

            def _execute_search():
                client = build("youtube", "v3", developerKey=api_key)
                lang = _detect_query_language(niche)

                kwargs = {
                    "q": niche,
                    "part": "id,snippet",
                    "type": "video",
                    "order": "viewCount",
                    "maxResults": min(max_results, 50),
                    "publishedAfter": _format_search_cutoff(30),
                    "relevanceLanguage": lang,
                }
                if video_duration in ("medium", "long", "short"):
                    kwargs["videoDuration"] = video_duration

                search_query = client.search().list(**kwargs)
                search_resp = search_query.execute()

                video_ids = [
                    item["id"]["videoId"]
                    for item in search_resp.get("items", [])
                    if item.get("id", {}).get("videoId")
                ]
                if not video_ids:
                    return []

                videos_query = client.videos().list(
                    part="snippet,statistics,contentDetails",
                    id=",".join(video_ids),
                )
                videos_resp = videos_query.execute()

                trends = []
                for item in videos_resp.get("items", []):
                    snippet = item.get("snippet", {})
                    stats = item.get("statistics", {})
                    content = item.get("contentDetails", {})
                    vid = item.get("id", "")
                    dur_s = _parse_iso_duration(content.get("duration", ""))
                    suitability = classify_suitability_for_clips(dur_s, target_clips=target_clips, clip_duration_sec=clip_duration_sec)

                    trends.append({
                        "platform": "youtube",
                        "video_id": vid,
                        "video_url": f"https://youtube.com/watch?v={vid}",
                        "embed_url": f"https://www.youtube-nocookie.com/embed/{vid}",
                        "title": snippet.get("title", ""),
                        "description": snippet.get("description", "")[:500],
                        "author": snippet.get("channelTitle", ""),
                        "author_url": f"https://youtube.com/channel/{snippet.get('channelId', '')}",
                        "thumbnail_url": (
                            snippet.get("thumbnails", {}).get("maxres", {}).get("url")
                            or snippet.get("thumbnails", {}).get("standard", {}).get("url")
                            or snippet.get("thumbnails", {}).get("high", {}).get("url")
                            or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
                        ),
                        "views": int(stats.get("viewCount", 0)),
                        "likes": int(stats.get("likeCount", 0)),
                        "comments": int(stats.get("commentCount", 0)),
                        "shares": 0,
                        "duration_seconds": dur_s,
                        "upload_date": _parse_publish_date(snippet.get("publishedAt")),
                        "aspect_ratio_status": "unverified_prior_to_ingest",
                        "suitability_for_3x60s": suitability,
                    })
                return trends

            res = await asyncio.to_thread(_execute_search)
            if res:
                return res
        except Exception as api_err:
            logger.warning("YouTube Data API call error (%s) — falling back to public recency search", api_err)

    # Public recency search (no API key required, strictly recent this month)
    return await asyncio.to_thread(_search_youtube_public_recent, niche, max_results, video_duration, target_clips, clip_duration_sec)


# Compatibility aliases
search_youtube = search_youtube_trends

