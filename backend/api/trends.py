# Copyright (c) 2026 ViralMint. All rights reserved.
# Authorial trends API router — discovery, queries, velocity & download orchestration.
import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, select

from backend.agents.job_helper import create_job
from backend.database import AsyncSessionLocal
from backend.models.trends_result import TrendsResult, TrendsResult as TrendResult

logger = logging.getLogger(__name__)
router = APIRouter()


class TrendsStartRequest(BaseModel):
    niche: str
    platforms: list[str] = ["youtube"]


# Compatibility alias
TrendStartRequest = TrendsStartRequest
ScoutStartRequest = TrendsStartRequest


@router.post("/trends/start")
@router.post("/trend/start")
@router.post("/scout/start")
async def start_trends(req: TrendsStartRequest):
    """Start an asynchronous trends discovery job across selected platforms."""
    from backend.core.task_runner import dispatch, run_trends
    job = await create_job("trends", "local", {"niche": req.niche, "platforms": req.platforms})
    dispatch(run_trends(job_id=job.id, niche=req.niche, platforms=req.platforms, user_id="local"))
    return {"job_id": job.id}


@router.get("/trends/results")
@router.get("/trend/results")
@router.get("/scout/results")
async def get_trends_results(
    job_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """Retrieve indexed trends results, optionally filtered by job_id."""
    async with AsyncSessionLocal() as db:
        query = (
            select(TrendsResult)
            .where(TrendsResult.user_id == "local")
            .order_by(TrendsResult.virality_score.desc().nullslast(), TrendsResult.created_at.desc())
        )
        if job_id:
            query = query.where(TrendsResult.job_id == job_id)
        query = query.offset(offset).limit(limit)

        result = await db.execute(query)
        results = result.scalars().all()

        from sqlalchemy import func
        count_query = select(func.count(TrendsResult.id)).where(TrendsResult.user_id == "local")
        if job_id:
            count_query = count_query.where(TrendsResult.job_id == job_id)
        total = (await db.execute(count_query)).scalar()

    return {
        "total": total,
        "results": [
            {
                "id": r.id,
                "platform": r.platform,
                "video_id": r.video_id,
                "video_url": r.video_url,
                "embed_url": r.embed_url,
                "title": r.title,
                "description": r.description,
                "author": r.author,
                "author_url": r.author_url,
                "thumbnail_url": r.thumbnail_url,
                "views": r.views,
                "likes": r.likes,
                "comments": r.comments,
                "shares": r.shares,
                "duration_seconds": r.duration_seconds,
                "upload_date": r.upload_date.isoformat() if r.upload_date else None,
                "virality_score": r.virality_score,
                "niche": r.niche,
                "is_downloaded": r.is_downloaded,
                "is_analyzed": r.is_analyzed,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in results
        ],
    }


@router.get("/trends/results/{result_id}")
@router.get("/trend/results/{result_id}")
@router.get("/scout/results/{result_id}")
async def get_trends_result(result_id: str):
    """Retrieve detailed metadata for a single indexed trend result."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(TrendsResult).where(TrendsResult.id == result_id))
        r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Result not found")
    return {
        "id": r.id,
        "platform": r.platform,
        "video_id": r.video_id,
        "video_url": r.video_url,
        "embed_url": r.embed_url,
        "title": r.title,
        "description": r.description,
        "author": r.author,
        "thumbnail_url": r.thumbnail_url,
        "views": r.views,
        "likes": r.likes,
        "comments": r.comments,
        "virality_score": r.virality_score,
        "niche": r.niche,
    }


class DownloadRequest(BaseModel):
    trend_result_ids: list[str] = []
    trends_result_ids: list[str] = []
    scout_result_ids: list[str] = []


# Compatibility alias
ScoutDownloadRequest = DownloadRequest


@router.post("/trends/download")
@router.post("/trend/download")
@router.post("/scout/download")
async def start_trends_download(req: DownloadRequest):
    """Dispatch download and analysis pipeline for selected trend records."""
    ids = req.trends_result_ids or req.trend_result_ids or req.scout_result_ids or []
    if not ids:
        raise HTTPException(status_code=400, detail="No results selected")
    if len(ids) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 videos per batch")

    from backend.core.task_runner import dispatch, run_download
    job = await create_job("download", "local", {"trend_result_ids": ids, "scout_result_ids": ids})
    dispatch(run_download(job_id=job.id, trend_result_ids=ids, scout_result_ids=ids, user_id="local"))
    return {"job_id": job.id, "count": len(ids)}


@router.get("/trends/suggest")
@router.get("/trend/suggest")
@router.get("/scout/suggest")
async def suggest_keywords(q: str = "", lang: str = "en"):
    """YouTube search autocomplete suggestions without requiring an API key."""
    if not q or len(q.strip()) < 2:
        return {"suggestions": []}
    from backend.services.youtube_suggest_service import get_suggestions
    suggestions = await get_suggestions(q.strip(), language=lang, max_results=10)
    return {"query": q, "suggestions": suggestions}


@router.get("/trends/search-demand")
@router.get("/trend/search-demand")
@router.get("/scout/search-demand")
async def search_demand(niche: str = "", lang: str = "en"):
    """Search demand breakdown revealing search intention and demand clusters."""
    if not niche or len(niche.strip()) < 2:
        raise HTTPException(status_code=400, detail="Niche must be at least 2 characters")
    from backend.services.youtube_suggest_service import get_search_demand
    return await get_search_demand(niche.strip(), language=lang)


@router.get("/trends/keyword-score")
@router.get("/trend/keyword-score")
@router.get("/scout/keyword-score")
async def keyword_score(keyword: str):
    """Opportunity score for a keyword evaluating search volume against creator competition."""
    if not keyword or len(keyword.strip()) < 2:
        raise HTTPException(status_code=400, detail="Keyword must be at least 2 characters")
    from backend.services.keyword_score_service import score_keyword
    return await score_keyword(keyword.strip())


@router.get("/trends/rising-keywords")
@router.get("/trend/rising-keywords")
@router.get("/scout/rising-keywords")
async def rising_keywords(niche: str = ""):
    """Discover rising trend keywords correlated with a niche using Google Trends."""
    if not niche or len(niche.strip()) < 2:
        raise HTTPException(status_code=400, detail="Niche must be at least 2 characters")
    from backend.services.keyword_score_service import discover_rising_keywords
    results = await discover_rising_keywords(niche.strip())
    return {"niche": niche, "keywords": results, "count": len(results)}


@router.get("/trends/cross-platform")
@router.get("/trend/cross-platform")
@router.get("/scout/cross-platform")
async def cross_platform_check(keyword: str = ""):
    """Check multi-platform momentum across Google Trends, YouTube, and Reddit."""
    if not keyword or len(keyword.strip()) < 2:
        raise HTTPException(status_code=400, detail="Keyword must be at least 2 characters")
    from backend.services.trends_velocity_service import cross_platform_correlation
    return await cross_platform_correlation(keyword.strip())


@router.get("/trends/trend-velocity")
@router.get("/trend/trend-velocity")
@router.get("/trends/velocity")
@router.get("/scout/trend-velocity")
async def check_trends_velocity(keyword: str = None):
    """Check velocity indicators for a specific keyword or all user niches."""
    if keyword:
        from backend.services.trends_velocity_service import check_keyword_trends_velocity
        alert = await check_keyword_trends_velocity(keyword.strip())
        return {
            "keyword": alert.keyword,
            "current_interest": alert.current_interest,
            "baseline_interest": alert.baseline_interest,
            "velocity": alert.velocity_multiplier,
            "alert_level": alert.alert_level,
        }
    else:
        from backend.services.trends_velocity_service import check_user_keywords_velocity
        alerts = await check_user_keywords_velocity()
        return {
            "alerts": [
                {
                    "keyword": a.keyword,
                    "current_interest": a.current_interest,
                    "baseline_interest": a.baseline_interest,
                    "velocity": a.velocity_multiplier,
                    "alert_level": a.alert_level,
                }
                for a in alerts
            ]
        }


@router.delete("/trends/results/{result_id}")
@router.delete("/trend/results/{result_id}")
@router.delete("/scout/results/{result_id}")
async def delete_trends_result(result_id: str):
    """Delete an indexed trends result entity."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(TrendsResult).where(TrendsResult.id == result_id))
        r = result.scalar_one_or_none()
        if not r:
            raise HTTPException(status_code=404, detail="Result not found")
        await db.delete(r)
        await db.commit()
    return {"message": "Deleted"}


@router.post("/trends/viral-formula")
@router.post("/trend/viral-formula")
@router.post("/scout/viral-formula")
async def generate_formula(body: dict = None):
    """Synthesize cross-video viral formula from analyzed videos in a niche."""
    from backend.core.ai_provider import get_ai_client
    from backend.models.downloaded_video import DownloadedVideo
    from backend.models.user_settings import UserSettings
    from backend.models.viral_formula import ViralFormula
    from backend.services.viral_formula_service import generate_viral_formula

    body = body or {}
    niche = body.get("niche", "").strip()
    video_ids = body.get("video_ids")

    if not niche:
        raise HTTPException(status_code=400, detail="Niche is required")

    async with AsyncSessionLocal() as db:
        if video_ids:
            result = await db.execute(
                select(DownloadedVideo).where(
                    and_(DownloadedVideo.id.in_(video_ids), DownloadedVideo.insights_json != None)
                )
            )
        else:
            result = await db.execute(
                select(DownloadedVideo)
                .join(TrendsResult, TrendsResult.id == DownloadedVideo.scout_result_id)
                .where(
                    and_(
                        TrendsResult.niche.ilike(f"%{niche}%"),
                        DownloadedVideo.insights_json != None,
                    )
                )
                .limit(15)
            )
        videos = result.scalars().all()

    if len(videos) < 3:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least 3 analyzed videos for a viral formula (found {len(videos)}). "
                   f"Download and analyze more videos in the '{niche}' niche first.",
        )

    analyses = []
    used_ids = []
    for v in videos:
        try:
            insights = json.loads(v.insights_json)
            analyses.append(insights)
            used_ids.append(v.id)
        except (json.JSONDecodeError, TypeError):
            continue

    if len(analyses) < 3:
        raise HTTPException(status_code=400, detail="Not enough valid analyses found")

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(UserSettings).where(UserSettings.user_id == "local"))
        user_settings = result.scalar_one_or_none()

    ai = get_ai_client(user_settings)
    formula = await generate_viral_formula(niche, analyses, ai)

    if not formula:
        raise HTTPException(status_code=500, detail="Failed to generate viral formula")

    async with AsyncSessionLocal() as db:
        vf = ViralFormula(
            niche=niche,
            formula_json=json.dumps(formula),
            video_count=len(analyses),
            source_video_ids_json=json.dumps(used_ids),
        )
        db.add(vf)
        await db.commit()
        await db.refresh(vf)

    return {
        "id": vf.id,
        "niche": niche,
        "formula": formula,
        "video_count": len(analyses),
        "created_at": vf.created_at.isoformat(),
    }


@router.get("/trends/viral-formulas")
@router.get("/trend/viral-formulas")
@router.get("/scout/viral-formulas")
async def list_formulas(niche: str = None):
    """List saved viral formulas, optionally filtered by niche."""
    from backend.models.viral_formula import ViralFormula

    async with AsyncSessionLocal() as db:
        query = select(ViralFormula).order_by(ViralFormula.created_at.desc()).limit(20)
        if niche:
            query = query.where(ViralFormula.niche.ilike(f"%{niche}%"))
        result = await db.execute(query)
        formulas = result.scalars().all()

    return {
        "formulas": [
            {
                "id": f.id,
                "niche": f.niche,
                "formula": json.loads(f.formula_json),
                "video_count": f.video_count,
                "created_at": f.created_at.isoformat(),
            }
            for f in formulas
        ]
    }
