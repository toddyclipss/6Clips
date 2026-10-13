# Copyright (c) 2026 ViralMint. All rights reserved.
# Authorial multi-platform trends intelligence engine.
import asyncio
from datetime import datetime, timezone
import json
import logging
import re
from typing import Optional

from sqlalchemy import select

from backend.agents.job_helper import update_job_status
from backend.config import settings
from backend.core.ws_manager import ws_manager
from backend.database import AsyncSessionLocal
from backend.models.trends_result import TrendsResult
from backend.models.user_settings import UserSettings
from backend.trends_research.ranking import classify_source_suitability

logger = logging.getLogger(__name__)

PLATFORM_LIMITS = {
    "youtube": 50,
    "tiktok": 30,
    "douyin": 30,
}

DEFAULT_SEARCH_LIMIT = 15

YTDLP_SEARCH_PLATFORMS = {
    "soundcloud": "scsearch",
    "niconico": "nicosearch",
}

FALLBACK_SEARCH_PREFIX = "ytsearch"
MAX_PLATFORMS_PER_TRENDS = 6
MAX_PLATFORMS_PER_TREND = MAX_PLATFORMS_PER_TRENDS
MAX_PLATFORMS_PER_SCOUT = MAX_PLATFORMS_PER_TRENDS


def compute_virality_score(video: dict) -> float:
    """
    Calculate normalized virality score from 0 to 100.
    Weighted composition:
      - Engagement rate: 30%
      - Velocity (views per hour): 25%
      - Recency decay: 20%
      - Total volume: 15%
      - Positive sentiment / likes: 10%
    Populates views_per_hour and outlier_score directly onto video metadata dict.
    """
    def _read_metric(key: str, default: float) -> float:
        try:
            val = float(video.get(key, default))
        except (TypeError, ValueError):
            return default
        return val if val == val and val not in (float("inf"), float("-inf")) else default

    likes = max(_read_metric("likes", 0), 0)
    views = max(_read_metric("views", 1), 1)
    comments = max(_read_metric("comments", 0), 0)

    upload_dt = video.get("upload_date")
    if upload_dt and isinstance(upload_dt, datetime):
        if upload_dt.tzinfo is None:
            upload_dt = upload_dt.replace(tzinfo=timezone.utc)
        now_utc = datetime.now(timezone.utc)
        hours_active = max((now_utc - upload_dt).total_seconds() / 3600, 1)
        days_active = max(hours_active / 24, 1)
    else:
        hours_active = 720
        days_active = 30

    engagement_ratio = (likes + comments * 2) / views
    recency_factor = 1.0 / (1 + days_active / 30)
    views_factor = min(views / 1_000_000, 1.0)
    likes_factor = min(likes / 100_000, 1.0)

    velocity_vph = views / hours_active
    velocity_factor = min(velocity_vph / 10_000, 1.0)

    video["views_per_hour"] = round(velocity_vph, 1)

    channel_avg = _read_metric("channel_avg_views", 0) or None
    if not channel_avg or channel_avg < 1:
        subscriber_count = _read_metric("subscriber_count", 0)
        channel_avg = max(subscriber_count * 0.03, 100) if subscriber_count > 0 else None
    if channel_avg and channel_avg > 0:
        video["outlier_score"] = round(views / channel_avg, 1)

    score_ratio = (
        engagement_ratio * 0.30
        + velocity_factor * 0.25
        + recency_factor * 0.20
        + views_factor * 0.15
        + likes_factor * 0.10
    )
    return round(min(score_ratio * 100, 100.0), 2)


class TrendsAgent:
    """
    High-velocity trend discovery engine across YouTube, TikTok, Douyin and yt-dlp platforms.
    Runs searches in parallel with resilient fallbacks, virality analysis, and outlier detection.
    """
    _suppress_fallback_warning = False

    async def run(
        self,
        job_id: str,
        niche: str,
        platforms: list[str],
        user_id: str = "local",
    ):
        logger.info("TRENDS START | job=%s niche=%r platforms=%s", job_id[:8], niche, platforms)

        seen: set[str] = set()
        clean_platforms: list[str] = []
        for p in platforms:
            clean = str(p).strip()
            if clean and clean.lower() not in seen:
                seen.add(clean.lower())
                clean_platforms.append(clean)

        if len(clean_platforms) > MAX_PLATFORMS_PER_TRENDS:
            logger.warning(
                "Trends platform list trimmed %d -> %d",
                len(clean_platforms), MAX_PLATFORMS_PER_TRENDS,
            )
            clean_platforms = clean_platforms[:MAX_PLATFORMS_PER_TRENDS]
        platforms = clean_platforms or ["youtube"]

        fallback_platforms = [
            p for p in platforms
            if p not in ("youtube", "tiktok", "douyin")
            and p not in YTDLP_SEARCH_PLATFORMS
        ]
        if len(fallback_platforms) > 1:
            try:
                await ws_manager.send_constraint_warning(
                    constraint="multi_platform_fallback",
                    message=(
                        f"No direct search for {', '.join(fallback_platforms[:6])}"
                        f"{'…' if len(fallback_platforms) > 6 else ''} — "
                        f"showing YouTube cross-posts about \"{niche}\" instead."
                    ),
                    severity="warning",
                    user_id=user_id,
                )
            except Exception:
                pass
            self._suppress_fallback_warning = True

        await update_job_status(job_id, "running", progress_pct=0, current_step="Finding trends...")
        await ws_manager.send_progress(job_id, 0, "Finding trends...", user_id)

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(UserSettings).where(UserSettings.user_id == user_id)
            )
            user_settings = result.scalar_one_or_none()

        tasks = [
            self._fetch_platform_trends(platform, niche, user_settings, user_id=user_id)
            for platform in platforms
        ]
        gathered_results = await asyncio.gather(*tasks, return_exceptions=True)

        all_trends: list[dict] = []
        for idx, res in enumerate(gathered_results):
            platform = platforms[idx]
            if isinstance(res, Exception):
                logger.warning("Trends query failed for platform %s: %s", platform, res)
                await ws_manager.send_constraint_warning(
                    constraint=f"{platform}_trend",
                    message=f"Search failed for {platform}: {res}",
                    severity="warning",
                    user_id=user_id,
                )
                try:
                    fallback_items = await self._ai_search_fallback(platform, niche, user_settings)
                    if fallback_items:
                        logger.info("AI raw search fallback recovered %d results for %s", len(fallback_items), platform)
                        res = fallback_items
                    else:
                        continue
                except Exception as fb_err:
                    logger.debug("AI fallback failed for %s: %s", platform, fb_err)
                    continue

            if res is not None and len(res) == 0:
                try:
                    from backend.core.ai_retry import ai_refine_search
                    refined_term = await ai_refine_search(platform, niche, user_settings)
                    if refined_term:
                        logger.info("Retrying %s trends with refined query: %r", platform, refined_term)
                        await ws_manager.send_progress(job_id, 0, f"Refining search for {platform}...", user_id)
                        retry_res = await self._fetch_platform_trends(platform, refined_term, user_settings, user_id=user_id)
                        if retry_res and not isinstance(retry_res, Exception):
                            res = retry_res
                            logger.info("Refined search discovered %d trends on %s", len(res), platform)
                except Exception as retry_err:
                    logger.debug("Refinement retry failed on %s: %s", platform, retry_err)

            if res:
                all_trends.extend(res)

            pct = ((idx + 1) / len(platforms)) * 80
            await ws_manager.send_progress(job_id, pct, f"Found trends on {platform}", user_id)

        logger.info("Trends engine collected %d items across %d platforms", len(all_trends), len(platforms))

        try:
            await self._enrich_outlier_metrics(all_trends, platforms, user_settings)
        except Exception as enrich_err:
            logger.warning("Outlier enrichment skipped: %s", enrich_err)

        for item in all_trends:
            try:
                item["virality_score"] = compute_virality_score(item)
            except Exception as score_err:
                logger.warning("Virality calculation failed on %s: %s", item.get("video_id", "?"), score_err)
                item["virality_score"] = 0.0

        all_trends.sort(key=lambda x: x["virality_score"], reverse=True)

        await ws_manager.send_progress(job_id, 90, "Saving trends...", user_id)
        saved_items, new_count = await self._save_trends(all_trends, job_id, niche, user_id)

        # Broadcast trends to connected clients
        for platform in platforms:
            platform_items = [
                item for item in saved_items
                if item.get("requested_platform", item["platform"]) == platform
            ]
            if platform_items:
                # Primary plural event
                await ws_manager.send({
                    "type": "trends_results",
                    "job_id": job_id,
                    "platform": platform,
                    "total": len(platform_items),
                    "results": platform_items,
                }, user_id)
                # Backward-compatibility scout event
                await ws_manager.send({
                    "type": "scout_results",
                    "job_id": job_id,
                    "platform": platform,
                    "total": len(platform_items),
                    "results": platform_items,
                }, user_id)
                # Backward-compatibility singular event
                await ws_manager.send({
                    "type": "trend_results",
                    "job_id": job_id,
                    "platform": platform,
                    "total": len(platform_items),
                    "results": platform_items,
                }, user_id)

        total_count = len(all_trends)
        if new_count == total_count:
            step_summary = f"Found {total_count} results"
        elif new_count == 0:
            step_summary = f"Found {total_count} results (all previously saved)"
        else:
            step_summary = f"Found {total_count} results ({new_count} new)"

        await update_job_status(
            job_id, "success",
            progress_pct=100,
            current_step=step_summary,
            output_data={"total_results": total_count, "new_results": new_count},
        )
        await ws_manager.send({
            "type": "job_complete",
            "job_id": job_id,
            "job_type": "trends",
            "result": {"total_results": total_count, "new_results": new_count},
        }, user_id)

    async def _fetch_platform_trends(
        self, platform: str, niche: str, user_settings, user_id: str = "local"
    ) -> list[dict]:
        from backend.core.api_keys import get_youtube_api_key

        logger.info("Executing platform trends search: platform=%s niche=%r", platform, niche)
        if platform == "youtube":
            from backend.services.youtube_trends import search_youtube_trends
            api_key = get_youtube_api_key(user_settings)
            try:
                res = await search_youtube_trends(niche, api_key, PLATFORM_LIMITS["youtube"])
                if res:
                    return res
            except Exception as ex:
                logger.warning("YouTube trends query failed (%s) — activating yt-dlp fallback", ex)
            return await self._scrape_via_ytdlp("youtube", niche, user_id=user_id)

        elif platform == "tiktok":
            if settings.TIKHUB_API_KEY:
                from backend.services.tikhub_client import search_tiktok
                return await search_tiktok(niche, settings.TIKHUB_API_KEY, PLATFORM_LIMITS["tiktok"])
            from backend.core.crypto import decrypt_safe
            cookie = ""
            if user_settings and user_settings.tiktok_cookie_encrypted:
                cookie = decrypt_safe(user_settings.tiktok_cookie_encrypted)
            if cookie:
                from backend.services.tiktok_downloader_svc import scout_tiktok_trending
                return await scout_tiktok_trending(cookie, niche, PLATFORM_LIMITS["tiktok"])
            logger.warning("TikTok: no API key or session cookie configured")
            return []

        elif platform == "douyin":
            if settings.TIKHUB_API_KEY:
                from backend.services.tikhub_client import search_douyin
                return await search_douyin(niche, settings.TIKHUB_API_KEY, PLATFORM_LIMITS["douyin"])
            from backend.core.crypto import decrypt_safe
            cookie = ""
            if user_settings and user_settings.douyin_cookie_encrypted:
                cookie = decrypt_safe(user_settings.douyin_cookie_encrypted)
            if cookie:
                from backend.services.tiktok_downloader_svc import scout_douyin_trending
                return await scout_douyin_trending(cookie, niche, PLATFORM_LIMITS["douyin"])
            logger.warning("Douyin: no API key or session cookie configured")
            return []

        else:
            return await self._scrape_via_ytdlp(platform, niche, user_id=user_id)

    async def _ai_search_fallback(self, platform: str, niche: str, user_settings) -> list[dict]:
        import httpx
        from backend.core.ai_retry import ai_parse_api_response

        search_urls = {
            "youtube": f"https://www.youtube.com/results?search_query={niche}&sp=CAMSAhAB",
            "tiktok": f"https://www.tiktok.com/api/search/general/full/?keyword={niche}&search_source=normal_search",
        }
        target_url = search_urls.get(platform)
        if not target_url:
            return []

        try:
            from backend.core.http_utils import get_default_headers
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(target_url, headers=get_default_headers())
                if resp.status_code != 200:
                    return []
                content = resp.text[:6000]

            parsed_candidates = await ai_parse_api_response(content, platform, niche, user_settings)
            if not parsed_candidates:
                return []

            results = []
            for item in parsed_candidates:
                v_id = item.get("aweme_id") or item.get("video_id", "")
                if not v_id:
                    continue
                results.append({
                    "platform": platform,
                    "video_id": v_id,
                    "video_url": item.get("video_url") or self._resolve_video_url(platform, v_id, item),
                    "embed_url": None,
                    "title": (item.get("desc") or item.get("title") or "")[:200],
                    "description": item.get("desc") or item.get("description") or "",
                    "author": item.get("author", {}).get("nickname") or item.get("author", {}).get("unique_id") or "Unknown",
                    "author_url": "",
                    "thumbnail_url": "",
                    "views": item.get("statistics", {}).get("play_count", 0) or item.get("views", 0),
                    "likes": item.get("statistics", {}).get("digg_count", 0) or item.get("likes", 0),
                    "comments": item.get("statistics", {}).get("comment_count", 0) or item.get("comments", 0),
                    "shares": item.get("statistics", {}).get("share_count", 0) or item.get("shares", 0),
                    "duration_seconds": item.get("video", {}).get("duration") or item.get("duration_seconds"),
                    "upload_date": None,
                })
            return results
        except Exception as err:
            logger.debug("AI fallback failed on %s: %s", platform, err)
            return []

    @staticmethod
    def _resolve_video_url(platform: str, video_id: str, item: dict) -> str:
        if platform == "youtube":
            return f"https://youtube.com/watch?v={video_id}"
        elif platform == "tiktok":
            author = (item.get("author") or {}).get("unique_id", "")
            return f"https://www.tiktok.com/@{author}/video/{video_id}" if author else f"https://www.tiktok.com/video/{video_id}"
        elif platform == "douyin":
            return f"https://www.douyin.com/video/{video_id}"
        return ""

    _build_video_url = _resolve_video_url

    async def _enrich_outlier_metrics(self, results: list[dict], platforms: list[str], user_settings) -> None:
        if "youtube" not in platforms:
            return
        yt_items = [r for r in results if r.get("platform") == "youtube"]
        if not yt_items:
            return

        from backend.core.api_keys import get_youtube_api_key
        api_key = get_youtube_api_key(user_settings)
        if not api_key:
            return

        channel_ids = set()
        for r in yt_items:
            match = re.search(r'/channel/(UC[\w-]+)', r.get("author_url") or "")
            if match:
                channel_ids.add(match.group(1))

        if not channel_ids:
            return

        channel_list = list(channel_ids)[:15]
        try:
            from backend.services.outlier_detection_service import (
                batch_get_channel_baselines,
                enrich_trend_results_with_outliers,
            )
            baselines = await batch_get_channel_baselines(channel_list, api_key)
            if baselines:
                enrich_trend_results_with_outliers(yt_items, baselines)
                logger.info("Enriched %d YouTube trends with channel baseline outliers", len(yt_items))
        except Exception as err:
            logger.warning("Outlier calculation encountered issue: %s", err)

    async def _scrape_via_ytdlp(self, platform: str, niche: str, user_id: str = "local") -> list[dict]:
        search_prefix = YTDLP_SEARCH_PLATFORMS.get(platform)
        is_fallback = search_prefix is None
        if not is_fallback:
            query_niche = niche
        else:
            search_prefix = FALLBACK_SEARCH_PREFIX
            query_niche = f"{platform} {niche}"
            logger.info("Executing universal fallback search for %s on YouTube: %r", platform, query_niche)
            if not self._suppress_fallback_warning:
                try:
                    await ws_manager.send_constraint_warning(
                        constraint=f"{platform}_no_native_search",
                        message=f"No direct {platform} search available — showing YouTube cross-posts about \"{niche}\" instead.",
                        severity="warning",
                        user_id=user_id,
                    )
                except Exception:
                    pass

        limit = PLATFORM_LIMITS.get(platform, DEFAULT_SEARCH_LIMIT)
        if is_fallback:
            import urllib.parse
            query = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(query_niche)}&sp=EgQIAxAB"
        else:
            query = f"{search_prefix}{limit}:{query_niche}"

        def _execute():
            import yt_dlp
            opts = {
                "quiet": True,
                "no_warnings": True,
                "socket_timeout": 30,
            }
            from backend.services.ytdlp_service import _get_cookie_file
            cookie_file = _get_cookie_file()
            if cookie_file:
                opts["cookiefile"] = str(cookie_file)

            if is_fallback:
                with yt_dlp.YoutubeDL({**opts, "extract_flat": True}) as ydl:
                    return ydl.extract_info(query, download=False)

            full_opts = {
                **opts,
                "extract_flat": False,
                "ignoreerrors": True,
                "extractor_retries": 1,
                "retries": 0,
            }
            with yt_dlp.YoutubeDL(full_opts) as ydl:
                info = ydl.extract_info(query, download=False)

            usable = sum(1 for e in (info.get("entries") if info else []) or [] if e)
            if usable == 0:
                with yt_dlp.YoutubeDL({**opts, "extract_flat": True}) as ydl:
                    info = ydl.extract_info(query, download=False)
            return info

        HARD_TIMEOUT = 60
        try:
            from backend.core.executors import download_pool
            info = await asyncio.wait_for(download_pool.run(_execute), timeout=HARD_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning("yt-dlp search for %s exceeded timeout of %ds", platform, HARD_TIMEOUT)
            return []
        except Exception as err:
            logger.warning("yt-dlp search failed for %s: %s", platform, err)
            return []

        if not info:
            return []

        entries = info.get("entries") or []
        results = []
        for entry in entries:
            if not entry:
                continue

            v_url = entry.get("url") or entry.get("webpage_url", "")
            v_id = entry.get("id", "")
            if v_url and not v_url.startswith("http"):
                v_url = entry.get("webpage_url", v_url)

            upload_dt = None
            raw_dt = entry.get("upload_date")
            if raw_dt and len(str(raw_dt)) == 8:
                try:
                    upload_dt = datetime.strptime(str(raw_dt), "%Y%m%d")
                except ValueError:
                    pass
            if not upload_dt and entry.get("timestamp"):
                try:
                    upload_dt = datetime.utcfromtimestamp(entry["timestamp"])
                except Exception:
                    pass
            if not upload_dt and is_fallback:
                upload_dt = datetime.utcnow() - timedelta(days=7)

            target_platform = "youtube" if is_fallback else platform
            results.append({
                "platform": target_platform,
                "requested_platform": platform,
                "video_id": v_id,
                "video_url": v_url,
                "title": entry.get("title", ""),
                "description": (entry.get("description") or "")[:500],
                "author": entry.get("uploader") or entry.get("channel", ""),
                "author_url": entry.get("uploader_url") or entry.get("channel_url", ""),
                "thumbnail_url": entry.get("thumbnail") or (entry.get("thumbnails", [{}])[0].get("url") if entry.get("thumbnails") else None),
                "views": entry.get("view_count", 0) or 0,
                "likes": entry.get("like_count", 0) or 0,
                "comments": entry.get("comment_count", 0) or 0,
                "shares": 0,
                "duration_seconds": entry.get("duration"),
                "upload_date": upload_dt,
            })

        return results

    async def _save_trends(
        self, results: list[dict], job_id: str, niche: str, user_id: str
    ) -> tuple[list[dict], int]:
        """Persist trends into database and format serialized response entities."""
        display_rows: list[dict] = []
        new_count = 0

        async with AsyncSessionLocal() as db:
            existing_res = await db.execute(
                select(TrendsResult.id, TrendsResult.video_id, TrendsResult.platform)
                .where(TrendsResult.user_id == user_id)
            )
            cached_keys: dict[tuple[str, str], str] = {
                (row[1], row[2]): row[0] for row in existing_res.fetchall()
            }

            for item in results:
                key = (item["video_id"], item["platform"])
                if key in cached_keys:
                    rec_id = cached_keys[key]
                else:
                    tr = TrendsResult(
                        user_id=user_id,
                        job_id=job_id,
                        platform=item["platform"],
                        video_id=item["video_id"],
                        video_url=item["video_url"],
                        embed_url=item.get("embed_url"),
                        title=item.get("title"),
                        description=item.get("description"),
                        author=item.get("author"),
                        author_url=item.get("author_url"),
                        thumbnail_url=item.get("thumbnail_url"),
                        views=item.get("views", 0),
                        likes=item.get("likes", 0),
                        comments=item.get("comments", 0),
                        shares=item.get("shares", 0),
                        duration_seconds=item.get("duration_seconds"),
                        upload_date=item.get("upload_date"),
                        virality_score=item.get("virality_score", 0),
                        views_per_hour=item.get("views_per_hour"),
                        outlier_score=item.get("outlier_score"),
                        subscriber_count=item.get("subscriber_count"),
                        channel_avg_views=item.get("channel_avg_views"),
                        niche=niche,
                    )
                    db.add(tr)
                    await db.flush()
                    cached_keys[key] = tr.id
                    rec_id = tr.id
                    new_count += 1

                up_date = item.get("upload_date")
                up_date_str = up_date.isoformat() if hasattr(up_date, "isoformat") else up_date

                suitability = classify_source_suitability(item.get("duration_seconds"))
                display_rows.append({
                    "id": rec_id,
                    "platform": item["platform"],
                    "requested_platform": item.get("requested_platform", item["platform"]),
                    "video_id": item["video_id"],
                    "video_url": item["video_url"],
                    "embed_url": item.get("embed_url"),
                    "title": item.get("title"),
                    "author": item.get("author"),
                    "author_url": item.get("author_url"),
                    "thumbnail_url": item.get("thumbnail_url"),
                    "views": item.get("views", 0),
                    "likes": item.get("likes", 0),
                    "comments": item.get("comments", 0),
                    "shares": item.get("shares", 0),
                    "duration_seconds": item.get("duration_seconds"),
                    "upload_date": up_date_str,
                    "virality_score": item.get("virality_score", 0),
                    "views_per_hour": item.get("views_per_hour"),
                    "outlier_score": item.get("outlier_score"),
                    "editorial_role": suitability.trend_role.value,
                    "role_label": suitability.role_label,
                    "is_editable_source": suitability.is_editable_source,
                    "is_reference": suitability.is_reference,
                    "suitability_status": suitability.status,
                    "suitability_reason": suitability.reason,
                    "permitted_use": "reference_only",
                    "bytes_availability": "not_fetched",
                    "highlight_quality": {
                        "status": "NOT_ASSESSED",
                        "assessed": False,
                        "score": None,
                        "reason": "Highlight quality requires media ingestion and transcript scoring; not inferable from search metadata.",
                    },
                })
            await db.commit()

        logger.info("Persisted %d trends (%d new entities added)", len(display_rows), new_count)
        return display_rows, new_count

    # Internal aliases for compatibility
    _trend_platform = _fetch_platform_trends
    _scout_platform = _fetch_platform_trends
    _trend_via_ytdlp_search = _scrape_via_ytdlp
    _scout_via_ytdlp_search = _scrape_via_ytdlp
    _ai_raw_search_fallback = _ai_search_fallback
    _enrich_with_outlier_scores = _enrich_outlier_metrics
    _save_results = _save_trends


async def run_trends(job_id: str, niche: str, platforms: list[str], user_id: str = "local"):
    """Entry point to launch trends discovery job."""
    await TrendsAgent().run(job_id=job_id, niche=niche, platforms=platforms, user_id=user_id)


# Backward compatibility aliases
run_trend = run_trends
run_scout = run_trends
TrendAgent = TrendsAgent
ScoutAgent = TrendsAgent
