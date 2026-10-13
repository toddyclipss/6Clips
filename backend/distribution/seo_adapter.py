# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Platform-Specific SEO Adapter: validates, formats, and sanitizes metadata per social platform."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from backend.distribution.models import PlatformKind, PlatformSEOMetadata


class SEOValidationError(Exception):
    """Raised when platform SEO constraints are violated."""
    def __init__(self, platform: str, field: str, message: str):
        super().__init__(f"[{platform}] {field}: {message}")
        self.platform = platform
        self.field = field
        self.message = message


class SEOAdapter:
    """Enforces official and documented platform constraints for metadata."""

    # Constraints per platform
    PLATFORM_CONSTRAINTS = {
        PlatformKind.YOUTUBE.value: {
            "title_max": 100,
            "description_max": 5000,
            "tags_total_chars_max": 500,
            "hashtags_max": 15,
            "allowed_visibilities": {"public", "unlisted", "private"},
            "allowed_aspect_ratios": {"9:16", "16:9", "1:1", "4:5"},
        },
        PlatformKind.TIKTOK.value: {
            "title_max": 2200,  # TikTok uses description/caption as main text
            "description_max": 2200,
            "tags_total_chars_max": 0,  # TikTok does not have separate tags; uses hashtags
            "hashtags_max": 20,
            "allowed_visibilities": {"public", "friends", "private"},
            "allowed_aspect_ratios": {"9:16"},  # TikTok is strictly vertical
        },
        PlatformKind.INSTAGRAM.value: {
            "title_max": 2200,
            "description_max": 2200,
            "tags_total_chars_max": 0,
            "hashtags_max": 30,
            "allowed_visibilities": {"public", "private"},
            "allowed_aspect_ratios": {"9:16", "1:1", "4:5"},
        },
        PlatformKind.X.value: {
            "title_max": 280,
            "description_max": 280,
            "tags_total_chars_max": 0,
            "hashtags_max": 5,
            "allowed_visibilities": {"public"},
            "allowed_aspect_ratios": {"9:16", "16:9", "1:1"},
        },
    }

    @staticmethod
    def sanitize_text(text: str) -> str:
        """Sanitize text against null bytes, control characters, and injection attempts."""
        if not text:
            return ""
        # Remove null bytes and control chars (except standard whitespace / newlines)
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        # Strip script tags and their inner content
        cleaned = re.sub(r"<script.*?>.*?</script>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
        # Strip any remaining html tags
        cleaned = re.sub(r"<[^>]*>", "", cleaned)
        return cleaned.strip()

    @staticmethod
    def sanitize_hashtags(tags: List[str]) -> List[str]:
        """Normalize hashtags with '#' prefix, removing illegal characters and duplicates."""
        cleaned_tags = []
        seen = set()
        for tag in tags:
            tag_clean = tag.strip().lstrip("#")
            # Only alphanumeric and underscores
            tag_clean = re.sub(r"[^\w]", "", tag_clean)
            if tag_clean and tag_clean.lower() not in seen:
                seen.add(tag_clean.lower())
                cleaned_tags.append(f"#{tag_clean}")
        return cleaned_tags

    @classmethod
    def validate_metadata(cls, meta: PlatformSEOMetadata) -> PlatformSEOMetadata:
        """Validate metadata against platform constraints and return sanitized copy."""
        platform = meta.platform.lower()
        if platform not in cls.PLATFORM_CONSTRAINTS:
            raise SEOValidationError(platform, "platform", f"Unsupported platform: '{platform}'")

        rules = cls.PLATFORM_CONSTRAINTS[platform]

        # 1. Sanitize text fields
        title = cls.sanitize_text(meta.title)
        desc = cls.sanitize_text(meta.description)
        hashtags = cls.sanitize_hashtags(meta.hashtags)
        tags = [cls.sanitize_text(t) for t in meta.tags if cls.sanitize_text(t)]

        # 2. Validate lengths
        if len(title) > rules["title_max"]:
            raise SEOValidationError(
                platform,
                "title",
                f"Title exceeds maximum length of {rules['title_max']} chars (got {len(title)})."
            )

        if len(desc) > rules["description_max"]:
            raise SEOValidationError(
                platform,
                "description",
                f"Description exceeds maximum length of {rules['description_max']} chars (got {len(desc)})."
            )

        # 3. For X (Twitter), combined title + hashtags must fit in 280 chars
        if platform == PlatformKind.X.value:
            combined = f"{title} {' '.join(hashtags)}".strip()
            if len(combined) > 280:
                raise SEOValidationError(
                    platform,
                    "text",
                    f"Combined post text and hashtags exceed 280 characters ({len(combined)} chars)."
                )

        # 4. Hashtag count limit
        if len(hashtags) > rules["hashtags_max"]:
            raise SEOValidationError(
                platform,
                "hashtags",
                f"Too many hashtags: maximum is {rules['hashtags_max']} (got {len(hashtags)})."
            )

        # 5. YouTube tags total character length
        if platform == PlatformKind.YOUTUBE.value:
            tags_total = sum(len(t) for t in tags) + max(0, len(tags) - 1)
            if tags_total > rules["tags_total_chars_max"]:
                raise SEOValidationError(
                    platform,
                    "tags",
                    f"Tags total character length ({tags_total}) exceeds maximum of {rules['tags_total_chars_max']}."
                )

        # 6. Visibility validation
        if meta.visibility not in rules["allowed_visibilities"]:
            raise SEOValidationError(
                platform,
                "visibility",
                f"Visibility '{meta.visibility}' is not supported for {platform}. Allowed: {rules['allowed_visibilities']}"
            )

        # 7. Aspect ratio validation
        if meta.aspect_ratio not in rules["allowed_aspect_ratios"]:
            raise SEOValidationError(
                platform,
                "aspect_ratio",
                f"Aspect ratio '{meta.aspect_ratio}' is not supported for {platform}. Allowed: {rules['allowed_aspect_ratios']}"
            )

        # 8. Auto-append #Shorts for YouTube 9:16 if not already present
        if platform == PlatformKind.YOUTUBE.value and meta.aspect_ratio == "9:16":
            if not any(h.lower() == "#shorts" for h in hashtags):
                hashtags.append("#Shorts")

        return PlatformSEOMetadata(
            platform=platform,
            title=title,
            description=desc,
            hashtags=hashtags,
            tags=tags,
            thumbnail_url=meta.thumbnail_url,
            thumbnail_path=meta.thumbnail_path,
            visibility=meta.visibility,
            aspect_ratio=meta.aspect_ratio,
            is_ai_draft=meta.is_ai_draft,
            creator_notes=meta.creator_notes,
        )

    @classmethod
    def generate_draft_for_platform(
        cls,
        platform: str,
        base_title: str,
        summary: str,
        keywords: List[str],
        aspect_ratio: str = "9:16",
    ) -> PlatformSEOMetadata:
        """
        Generate a platform-tailored draft metadata object.
        Preserves creator edits by explicitly tagging draft as is_ai_draft=True.
        """
        platform = platform.lower()
        clean_title = cls.sanitize_text(base_title)
        clean_summary = cls.sanitize_text(summary)
        hashtags = cls.sanitize_hashtags([f"#{k}" for k in keywords])

        if platform == PlatformKind.YOUTUBE.value:
            if aspect_ratio == "9:16":
                title = f"{clean_title[:85]} #Shorts" if "#Shorts" not in clean_title else clean_title[:100]
            else:
                title = clean_title[:100]
            desc = f"{clean_summary}\n\n{' '.join(hashtags)}"[:5000]
            tags = [k.replace("#", "") for k in keywords][:15]
            return cls.validate_metadata(PlatformSEOMetadata(
                platform=platform,
                title=title,
                description=desc,
                hashtags=hashtags,
                tags=tags,
                aspect_ratio=aspect_ratio,
                is_ai_draft=True,
            ))

        elif platform == PlatformKind.TIKTOK.value:
            caption = f"{clean_title}\n\n{clean_summary}\n\n{' '.join(hashtags)}"[:2200]
            return cls.validate_metadata(PlatformSEOMetadata(
                platform=platform,
                title=clean_title[:200],
                description=caption,
                hashtags=hashtags[:5],
                aspect_ratio="9:16",
                is_ai_draft=True,
            ))

        elif platform == PlatformKind.INSTAGRAM.value:
            caption = f"{clean_title}\n\n{clean_summary}\n.\n.\n{' '.join(hashtags)}"[:2200]
            return cls.validate_metadata(PlatformSEOMetadata(
                platform=platform,
                title=clean_title[:150],
                description=caption,
                hashtags=hashtags[:10],
                aspect_ratio=aspect_ratio if aspect_ratio in {"9:16", "1:1"} else "9:16",
                is_ai_draft=True,
            ))

        elif platform == PlatformKind.X.value:
            # 280 char limit
            tags_str = " ".join(hashtags[:3])
            budget = 280 - len(tags_str) - 2
            short_text = clean_title[:budget].strip()
            return cls.validate_metadata(PlatformSEOMetadata(
                platform=platform,
                title=short_text,
                description=short_text,
                hashtags=hashtags[:3],
                aspect_ratio=aspect_ratio,
                is_ai_draft=True,
            ))

        raise SEOValidationError(platform, "platform", f"Unsupported platform '{platform}'")
