# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Platform Support Matrix and Contract Specification (Phase 10 & 11).

Provides:
- Explicit support matrix for YouTube, TikTok, Instagram, and X
- Differentiates video uploads, TikTok inbox drafts, and public posts
- Official endpoint, scope, and payload contract validation
- Offline contract verification (request formation without network side effects)
- Truthful connection and live release status disclosures (NOT_CONNECTED / BLOCKED)
"""
from __future__ import annotations

from enum import Enum
import json
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.distribution.models import (
    DistributionJob,
    PlatformKind,
    PlatformSEOMetadata,
)

logger = logging.getLogger(__name__)


class PublishTargetType(str, Enum):
    """Publishing target variants supported across platforms."""
    PUBLIC_VIDEO_POST = "PUBLIC_VIDEO_POST"
    TIKTOK_INBOX_DRAFT = "TIKTOK_INBOX_DRAFT"
    UNLISTED_MEDIA = "UNLISTED_MEDIA"
    PRIVATE_MEDIA = "PRIVATE_MEDIA"


class PlatformPublishCapability(BaseModel):
    """Specification of official API requirements and constraints for a platform."""
    platform: str
    official_api_name: str
    api_endpoint: str
    required_scopes: List[str]
    supported_targets: List[PublishTargetType]
    max_title_length: int
    max_description_length: int
    max_tags_length: int = 500
    max_duration_seconds: float = 3600.0
    aspect_ratios_supported: List[str] = Field(default_factory=lambda: ["9:16", "16:9"])
    requires_oauth2: bool = True
    live_integration_status: str = "NOT_CONNECTED"
    notes: str = ""


# Official platform capability definitions based on real vendor APIs
PLATFORM_SUPPORT_MATRIX: Dict[str, PlatformPublishCapability] = {
    PlatformKind.YOUTUBE.value: PlatformPublishCapability(
        platform="youtube",
        official_api_name="YouTube Data API v3",
        api_endpoint="https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        required_scopes=[
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube.readonly",
        ],
        supported_targets=[
            PublishTargetType.PUBLIC_VIDEO_POST,
            PublishTargetType.UNLISTED_MEDIA,
            PublishTargetType.PRIVATE_MEDIA,
        ],
        max_title_length=100,
        max_description_length=5000,
        max_tags_length=500,
        max_duration_seconds=43200.0,  # 12 hours
        aspect_ratios_supported=["9:16", "16:9"],
        live_integration_status="NOT_CONNECTED",
        notes="Requires verified Google Cloud OAuth2 client credentials and channel quota.",
    ),
    PlatformKind.TIKTOK.value: PlatformPublishCapability(
        platform="tiktok",
        official_api_name="TikTok Content Posting API v2",
        api_endpoint="https://open.tiktokapis.com/v2/post/publish/video/init/",
        required_scopes=[
            "video.upload",
            "video.publish",
        ],
        supported_targets=[
            PublishTargetType.PUBLIC_VIDEO_POST,
            PublishTargetType.TIKTOK_INBOX_DRAFT,
        ],
        max_title_length=150,  # Caption budget
        max_description_length=2200,
        max_tags_length=100,
        max_duration_seconds=600.0,  # 10 minutes
        aspect_ratios_supported=["9:16"],
        live_integration_status="NOT_CONNECTED",
        notes="Differentiates direct public post from creator inbox draft. Requires TikTok Developer App audit.",
    ),
    PlatformKind.INSTAGRAM.value: PlatformPublishCapability(
        platform="instagram",
        official_api_name="Meta Instagram Graph API v19.0",
        api_endpoint="https://graph.facebook.com/v19.0/{ig_user_id}/media",
        required_scopes=[
            "instagram_content_publish",
            "instagram_basic",
        ],
        supported_targets=[
            PublishTargetType.PUBLIC_VIDEO_POST,
        ],
        max_title_length=0,  # Instagram uses caption only
        max_description_length=2200,
        max_tags_length=30,  # 30 hashtags max
        max_duration_seconds=900.0,  # 15 minutes for Reels
        aspect_ratios_supported=["9:16"],
        live_integration_status="NOT_CONNECTED",
        notes="Instagram Reels require 9:16 aspect ratio and Facebook Business Page linkage.",
    ),
    PlatformKind.X.value: PlatformPublishCapability(
        platform="x",
        official_api_name="X API v2 Tweets & Media Upload",
        api_endpoint="https://api.twitter.com/2/tweets",
        required_scopes=[
            "tweet.write",
            "tweet.read",
            "users.read",
        ],
        supported_targets=[
            PublishTargetType.PUBLIC_VIDEO_POST,
        ],
        max_title_length=280,  # Tweet text length
        max_description_length=280,
        max_tags_length=50,
        max_duration_seconds=140.0,  # 2m 20s standard video
        aspect_ratios_supported=["9:16", "16:9", "1:1"],
        live_integration_status="NOT_CONNECTED",
        notes="Strict 280-character post limit. Requires X Developer portal OAuth2 user context.",
    ),
}


class PlatformMatrixValidator:
    """Validates job requests against official platform capability rules."""

    @classmethod
    def get_capability(cls, platform: str) -> Optional[PlatformPublishCapability]:
        return PLATFORM_SUPPORT_MATRIX.get(platform.lower())

    @classmethod
    def validate_job_against_matrix(
        cls,
        job: DistributionJob,
        target_type: PublishTargetType = PublishTargetType.PUBLIC_VIDEO_POST,
    ) -> List[str]:
        """
        Validate a distribution job against official constraints.
        Returns a list of validation error messages, or an empty list if valid.
        """
        cap = cls.get_capability(job.platform)
        if not cap:
            return [f"Platform '{job.platform}' is not supported in the platform matrix."]

        errors: List[str] = []

        # Target type check
        if target_type not in cap.supported_targets:
            errors.append(
                f"Target type '{target_type.value}' is not supported by {cap.official_api_name}."
            )

        # Aspect ratio check
        seo = job.seo_metadata
        if seo.aspect_ratio not in cap.aspect_ratios_supported:
            errors.append(
                f"Aspect ratio '{seo.aspect_ratio}' is not supported by {job.platform}. Supported: {cap.aspect_ratios_supported}."
            )

        # Title length check
        if cap.max_title_length > 0 and len(seo.title) > cap.max_title_length:
            errors.append(
                f"Title length ({len(seo.title)}) exceeds {job.platform} maximum of {cap.max_title_length} characters."
            )

        # Description / caption length check
        if len(seo.description) > cap.max_description_length:
            errors.append(
                f"Description length ({len(seo.description)}) exceeds {job.platform} maximum of {cap.max_description_length} characters."
            )

        return errors

    @classmethod
    def build_offline_publication_request(
        cls,
        job: DistributionJob,
        token: str,
        target_type: PublishTargetType = PublishTargetType.PUBLIC_VIDEO_POST,
    ) -> Dict[str, Any]:
        """
        Constructs the exact HTTP request headers, URL, and body for contract verification.
        Executes purely in-memory with ZERO network calls.
        """
        cap = cls.get_capability(job.platform)
        if not cap:
            raise ValueError(f"Unknown platform '{job.platform}'")

        seo = job.seo_metadata

        if job.platform == "youtube":
            return {
                "method": "POST",
                "url": cap.api_endpoint,
                "headers": {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json; charset=UTF-8",
                    "X-Upload-Content-Type": "video/mp4",
                },
                "body": {
                    "snippet": {
                        "title": seo.title,
                        "description": seo.description,
                        "tags": seo.tags,
                        "categoryId": "22",
                    },
                    "status": {
                        "privacyStatus": seo.visibility,
                        "selfDeclaredMadeForKids": False,
                    },
                },
                "target_type": target_type.value,
            }

        elif job.platform == "tiktok":
            is_draft = target_type == PublishTargetType.TIKTOK_INBOX_DRAFT
            return {
                "method": "POST",
                "url": cap.api_endpoint,
                "headers": {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json; charset=UTF-8",
                },
                "body": {
                    "post_info": {
                        "title": seo.title or seo.description[:150],
                        "privacy_level": "SELF_ONLY" if is_draft else "PUBLIC_TO_EVERYONE",
                        "disable_duet": False,
                        "disable_stitch": False,
                        "disable_comment": False,
                    },
                    "source_info": {
                        "source": "FILE_UPLOAD",
                        "video_size": 1048576,  # Placeholder size for contract validation
                    },
                },
                "is_inbox_draft": is_draft,
                "target_type": target_type.value,
            }

        elif job.platform == "instagram":
            return {
                "method": "POST",
                "url": cap.api_endpoint.replace("{ig_user_id}", job.account_id),
                "headers": {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                "body": {
                    "media_type": "REELS",
                    "caption": f"{seo.description}\n\n{' '.join(seo.hashtags)}".strip(),
                    "share_to_feed": True,
                },
                "target_type": target_type.value,
            }

        elif job.platform == "x":
            return {
                "method": "POST",
                "url": cap.api_endpoint,
                "headers": {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                "body": {
                    "text": seo.description[:280],
                },
                "target_type": target_type.value,
            }

        raise NotImplementedError(f"Request builder for platform '{job.platform}' not implemented.")
