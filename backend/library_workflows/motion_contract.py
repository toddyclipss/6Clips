# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Motion Contract: documented public contract and data transfer object for 'Use in Motion' and drag-and-drop workflows."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

MIME_MOTION_ASSET = "application/x-6clips-asset"
VALID_INTENT_ACTIONS = {"add_track", "replace_source", "broll_overlay", "audio_bed"}
PERMITTED_USES_DEFAULT = ["timeline_motion", "derivative_clips", "commercial_creator"]


class MotionContractError(Exception):
    """Raised when an asset does not fulfill motion workflow contracts."""
    pass


@dataclass
class MotionAssetIntent:
    """Documented contract for injecting or dropping a Library asset into the Motion timeline."""
    asset_id: str
    key: str
    title: str
    media_type: str  # "video", "audio", "image"
    stream_url: str
    duration_seconds: float = 0.0
    aspect_ratio: Optional[str] = "9:16"
    source_provenance: str = "library_user_asset"
    permitted_uses: List[str] = field(default_factory=lambda: list(PERMITTED_USES_DEFAULT))
    intent_action: str = "add_track"
    target_track: Optional[str] = None
    target_start_time_seconds: float = 0.0
    file_sha256: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_dnd_json(self) -> str:
        """Serialize into Drag-and-Drop payload string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MotionAssetIntent:
        return cls(**data)


class MotionContractManager:
    """Validates and constructs MotionAssetIntent instances from Library assets."""

    @classmethod
    async def create_motion_intent(
        cls,
        key: str,
        db: AsyncSession,
        intent_action: str = "add_track",
        target_track: Optional[str] = None,
        target_start_time_seconds: float = 0.0,
    ) -> MotionAssetIntent:
        """
        Validate physical asset and construct a fully qualified MotionAssetIntent.
        Raises MotionContractError if asset does not exist or lacks permitted uses.
        """
        if intent_action not in VALID_INTENT_ACTIONS:
            raise MotionContractError(
                f"Invalid intent_action '{intent_action}'. Valid: {', '.join(sorted(VALID_INTENT_ACTIONS))}"
            )

        from backend.services.library_service import LibraryService, MissingMediaError

        try:
            file_path, meta = await LibraryService.resolve_asset_file(key, db)
        except MissingMediaError as me:
            raise MotionContractError(f"Cannot add missing media to Motion: {me}") from me

        # Verify physical file existence
        if not file_path.is_file():
            raise MotionContractError(f"Asset file physically missing on disk: {file_path}")

        media_type = meta.get("media", "video")
        title = meta.get("title", "Asset")
        stream_url = meta.get("stream_url") or f"/api/library/asset/{meta.get('id')}"
        duration = float(meta.get("duration_seconds") or 0.0)
        aspect = meta.get("aspect") or "9:16"
        producer = meta.get("producer") or "library"
        sha256 = LibraryService.compute_sha256(file_path)

        # Default track selection if none provided
        if not target_track:
            target_track = "video_primary" if media_type == "video" else "audio_bed" if media_type == "audio" else "overlay"

        return MotionAssetIntent(
            asset_id=meta.get("id", key),
            key=key,
            title=title,
            media_type=media_type,
            stream_url=stream_url,
            duration_seconds=duration,
            aspect_ratio=aspect,
            source_provenance=f"{meta.get('origin', 'imported')}:{producer}",
            permitted_uses=list(PERMITTED_USES_DEFAULT),
            intent_action=intent_action,
            target_track=target_track,
            target_start_time_seconds=max(0.0, float(target_start_time_seconds)),
            file_sha256=sha256,
        )

    @classmethod
    def validate_intent(cls, intent: MotionAssetIntent) -> None:
        """Verify contract integrity."""
        if not intent.asset_id or not intent.key:
            raise MotionContractError("Motion intent requires valid asset_id and key.")
        if intent.intent_action not in VALID_INTENT_ACTIONS:
            raise MotionContractError(f"Invalid intent action '{intent.intent_action}'.")
        if not intent.permitted_uses or "timeline_motion" not in intent.permitted_uses:
            raise MotionContractError("Asset rights policy forbids timeline_motion use.")
