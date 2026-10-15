# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Backward-compatibility Bridge for Legacy /api/downloaded and /api/videos Endpoints.
Ensures existing scripts and legacy project integrations function seamlessly
by delegating to ClipStudioNativeAdapter while preserving identical REST JSON contracts.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException

from .adapter import clipstudio_native_adapter
from .models import ExtractClipsParams, SuggestClipsParams

logger = logging.getLogger(__name__)

compat_router = APIRouter(tags=["legacy-clipstudio-compat"])


@compat_router.post("/compat/downloaded/{video_id}/suggest-clips")
async def compat_suggest_clips(video_id: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Compatibility endpoint matching legacy POST /api/downloaded/{id}/suggest-clips."""
    payload = body or {}
    params = SuggestClipsParams(
        source_id=video_id,
        max_clips=payload.get("max_clips", 3),
        min_duration=payload.get("min_duration"),
        max_duration=payload.get("max_duration"),
        target_platform=payload.get("target_platform"),
        genre=payload.get("genre"),
        user_query=payload.get("user_query"),
    )
    ranges = await clipstudio_native_adapter.suggest_clips(params)
    return {
        "status": "success",
        "type": "clip_suggestions",
        "suggestions": [
            {
                "id": r.id,
                "start": r.start,
                "end": r.end,
                "title": r.label,
                "score": r.score,
                "hook_score": r.hook_score,
                "hook_type": r.hook_type,
                "reason": r.reason,
                "score_breakdown": r.score_breakdown,
            }
            for r in ranges
        ],
    }
