# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for Phase 10 SEO Adapter: platform constraints, sanitization, and draft generation."""
import pytest

from backend.distribution.models import PlatformKind, PlatformSEOMetadata
from backend.distribution.seo_adapter import SEOAdapter, SEOValidationError


def test_sanitize_text_removes_injection_and_control_chars():
    dirty = "Hello \x00World!\x07 <script>alert('pwned')</script> This is <b>safe</b> text."
    cleaned = SEOAdapter.sanitize_text(dirty)
    assert "\x00" not in cleaned
    assert "\x07" not in cleaned
    assert "<script>" not in cleaned
    assert "<b>" not in cleaned
    assert cleaned == "Hello World!  This is safe text."


def test_sanitize_hashtags_deduplication_and_prefix():
    raw_tags = ["ai", "#AI", "##viral_clips", "invalid#tag!", "creator", "#creator"]
    cleaned = SEOAdapter.sanitize_hashtags(raw_tags)
    assert cleaned == ["#ai", "#viral_clips", "#invalidtag", "#creator"]


def test_youtube_seo_validation_and_shorts_tag():
    meta = PlatformSEOMetadata(
        platform="youtube",
        title="10 Tips for Viral Video Creation",
        description="A great tutorial on video production.",
        hashtags=["#editing", "#workflow"],
        tags=["video tips", "editing tricks"],
        aspect_ratio="9:16",
        visibility="public",
    )
    validated = SEOAdapter.validate_metadata(meta)
    assert validated.title == "10 Tips for Viral Video Creation"
    # Auto-appends #Shorts for vertical video
    assert "#Shorts" in validated.hashtags


def test_youtube_title_length_exceeded():
    meta = PlatformSEOMetadata(
        platform="youtube",
        title="A" * 105,
        description="Normal description",
    )
    with pytest.raises(SEOValidationError) as exc:
        SEOAdapter.validate_metadata(meta)
    assert exc.value.field == "title"


def test_youtube_tags_total_length_exceeded():
    meta = PlatformSEOMetadata(
        platform="youtube",
        title="Normal Title",
        description="Normal description",
        tags=["A" * 100, "B" * 100, "C" * 100, "D" * 100, "E" * 105],  # > 500 chars
    )
    with pytest.raises(SEOValidationError) as exc:
        SEOAdapter.validate_metadata(meta)
    assert exc.value.field == "tags"


def test_tiktok_aspect_ratio_enforcement():
    # Vertical 9:16 allowed
    meta_ok = PlatformSEOMetadata(
        platform="tiktok",
        title="Cool TikTok dance",
        description="Dance challenge #dance",
        aspect_ratio="9:16",
    )
    assert SEOAdapter.validate_metadata(meta_ok).aspect_ratio == "9:16"

    # Horizontal 16:9 rejected
    meta_invalid = PlatformSEOMetadata(
        platform="tiktok",
        title="Horizontal clip",
        description="Dance challenge #dance",
        aspect_ratio="16:9",
    )
    with pytest.raises(SEOValidationError) as exc:
        SEOAdapter.validate_metadata(meta_invalid)
    assert exc.value.field == "aspect_ratio"


def test_x_twitter_280_character_budget():
    meta = PlatformSEOMetadata(
        platform="x",
        title="A" * 260,
        hashtags=["#toolongtag1", "#toolongtag2", "#toolongtag3"],
    )
    # Combined text exceeds 280
    with pytest.raises(SEOValidationError) as exc:
        SEOAdapter.validate_metadata(meta)
    assert exc.value.field == "text"


def test_generate_draft_for_platform():
    draft_yt = SEOAdapter.generate_draft_for_platform(
        platform="youtube",
        base_title="How to Scale Short-Form Content",
        summary="A comprehensive overview of content systems.",
        keywords=["growth", "automation", "scale"],
        aspect_ratio="9:16",
    )
    assert draft_yt.is_ai_draft is True
    assert "#Shorts" in draft_yt.title or "#Shorts" in draft_yt.hashtags
    assert "#growth" in draft_yt.hashtags

    draft_x = SEOAdapter.generate_draft_for_platform(
        platform="x",
        base_title="How to Scale Short-Form Content",
        summary="Brief summary",
        keywords=["growth"],
    )
    assert len(draft_x.title) <= 280
    assert draft_x.is_ai_draft is True
