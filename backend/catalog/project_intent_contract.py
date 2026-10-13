# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Catalog Project Intent Contract:
Defines the validated integration interface for adding HyperFrames catalog blocks
into video composition timelines without directly mutating the global ProjectService.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.catalog.manifest_service import CatalogManifestService, CatalogManifestError

logger = logging.getLogger(__name__)


class BlockVariableInput(BaseModel):
    name: str
    value: Any


class AddToProjectIntentRequest(BaseModel):
    """Client request initiating intent to add a catalog block to a composition."""
    project_id: Optional[str] = Field(None, description="Target composition ID if active, or None for draft insertion")
    timeline_track_index: int = Field(0, ge=0, description="Target timeline track index")
    start_time_seconds: float = Field(0.0, ge=0.0, description="Insertion timestamp on timeline in seconds")
    aspect_ratio: str = Field("9:16", description="Target aspect ratio: '9:16' or '16:9'")
    custom_variables: Dict[str, Any] = Field(default_factory=dict, description="User-configured block parameters")


class ValidatedTimelineItem(BaseModel):
    """Standardized timeline item structure ready for ProjectService insertion."""
    item_id: str
    item_type: str = "motion_block"
    block_id: str
    title: str
    start_time: float
    duration: float
    end_time: float
    track_index: int
    aspect_ratio: str
    aspect_support: str
    preview_url: str
    poster_url: str
    variables: Dict[str, Any]
    internalized: bool
    runtime_ready: bool


class AddToProjectIntentResult(BaseModel):
    """Validated intent contract returned to client and coordinator."""
    intent_id: str
    status: str  # "VALIDATED_INTENT", "WARNING_UNVERIFIED"
    block_id: str
    target_project_id: Optional[str]
    timeline_item: ValidatedTimelineItem
    integration_request: Dict[str, Any]


class CatalogProjectIntentAdapter:
    """Validates block readiness and constructs the normalized timeline item payload."""

    @classmethod
    def create_add_to_project_intent(
        cls,
        block_id: str,
        request: AddToProjectIntentRequest,
    ) -> AddToProjectIntentResult:
        CatalogManifestService.validate_block_id(block_id)
        item = CatalogManifestService.get_item(block_id)
        if not item:
            raise CatalogManifestError(f"Block '{block_id}' not found in catalog.")

        # Determine aspect support
        aspect_norm = "9:16" if request.aspect_ratio in ("9:16", "9x16", "vertical") else "16:9"
        aspect_key = "aspect_9_16" if aspect_norm == "9:16" else "aspect_16_9"
        aspect_support = item.get(aspect_key, "CONTAINED_ONLY")

        # Determine readiness
        is_internalized = item.get("internalized", False) or item.get("id") in [
            "aurora", "data-chart", "instagram-follow", "tiktok-follow", "weight-wave", "yt-lower-third"
        ]
        duration = float(item.get("duration", 5.0))
        end_time = round(request.start_time_seconds + duration, 3)

        # Merge custom variables with defaults
        resolved_vars: Dict[str, Any] = {}
        for var_def in item.get("variables", []):
            v_name = var_def.get("name")
            if v_name:
                resolved_vars[v_name] = request.custom_variables.get(v_name, var_def.get("default", ""))

        intent_id = f"intent_{uuid.uuid4().hex[:12]}"
        item_id = f"block_{block_id}_{uuid.uuid4().hex[:8]}"

        status = "VALIDATED_INTENT" if is_internalized else "WARNING_UNVERIFIED"

        timeline_item = ValidatedTimelineItem(
            item_id=item_id,
            item_type="motion_block",
            block_id=block_id,
            title=item.get("title", block_id),
            start_time=request.start_time_seconds,
            duration=duration,
            end_time=end_time,
            track_index=request.timeline_track_index,
            aspect_ratio=aspect_norm,
            aspect_support=aspect_support,
            preview_url=f"/api/catalog/blocks/{block_id}/preview?aspect_ratio={aspect_norm}",
            poster_url=f"/api/catalog/blocks/{block_id}/poster?aspect_ratio={aspect_norm}",
            variables=resolved_vars,
            internalized=is_internalized,
            runtime_ready=is_internalized,
        )

        integration_request = {
            "target_service": "backend.services.project_service.ProjectService",
            "suggested_method": "add_timeline_clip_or_block",
            "parameters": {
                "project_id": request.project_id,
                "timeline_item": timeline_item.model_dump(),
            },
            "coordinator_action_required": True,
        }

        return AddToProjectIntentResult(
            intent_id=intent_id,
            status=status,
            block_id=block_id,
            target_project_id=request.project_id,
            timeline_item=timeline_item,
            integration_request=integration_request,
        )
