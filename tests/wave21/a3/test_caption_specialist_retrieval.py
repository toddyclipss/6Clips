# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Tests for caption specialist retrieval, speech synchronization, and karaoke keyframe derivation.
"""
from pathlib import Path
import pytest

from backend.knowledge_base import (
    CapabilityFamily,
    CaptionStyleDirectives,
    KnowledgeAdapter,
    KnowledgeBase,
    SearchFilter,
)

WORKTREE_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def kb():
    return KnowledgeBase()


@pytest.fixture(scope="module")
def adapter(kb):
    return KnowledgeAdapter(kb)


def test_caption_identity_search_filtering(kb):
    """Verify is_caption_identity filter isolates caption identities from generic animation blocks."""
    # Search with caption filter
    cap_filter = SearchFilter(is_caption_identity=True)
    cap_hits = kb.search("light monologue glow emergence", filters=cap_filter, limit=5)

    assert len(cap_hits) > 0
    for h in cap_hits:
        assert h.knowledge_doc_id.startswith("caption:"), f"Expected caption identity, got {h.knowledge_doc_id}"

    # Search with non-caption filter
    non_cap_filter = SearchFilter(is_caption_identity=False)
    non_cap_hits = kb.search("kinetic headline slam", filters=non_cap_filter, limit=5)
    for h in non_cap_hits:
        assert not h.knowledge_doc_id.startswith("caption:"), f"Expected non-caption, got {h.knowledge_doc_id}"


def test_caption_style_directives_cream(adapter):
    """Verify CaptionStyleDirectives for 'cream' identity with speech word timestamps."""
    words = [
        {"word": "Warm", "start": 0.2, "end": 0.6, "emphasis": True},
        {"word": "light", "start": 0.65, "end": 1.1, "emphasis": False},
        {"word": "glow", "start": 1.15, "end": 1.8, "emphasis": True},
    ]

    directives = adapter.get_caption_style_directives("cream", words=words)
    assert isinstance(directives, CaptionStyleDirectives)
    assert directives.identity_name == "cream"
    assert directives.doc_id == "caption:cream"
    assert "serif" in directives.font_family.lower()
    assert directives.accent_color == "#FFF8E7"
    assert len(directives.speech_sync_rules) > 0

    # Keyframes template check
    tmpl = directives.word_keyframes_template
    assert tmpl["total_words"] == 3
    assert tmpl["strategy"] == "per_word_karaoke_sweep"
    assert len(tmpl["words"]) == 3
    assert tmpl["words"][0]["emphasis"] is True
    assert tmpl["words"][0]["highlight_fill"] == "#FFF8E7"


def test_caption_style_directives_anchor(adapter):
    """Verify CaptionStyleDirectives for 'anchor' conservative lower-third style."""
    words = [
        {"word": "Discipline", "start": 0.1, "end": 0.5, "emphasis": True},
        {"word": "matters", "start": 0.55, "end": 1.0, "emphasis": False},
    ]

    directives = adapter.get_caption_style_directives("caption:anchor", words=words)
    assert isinstance(directives, CaptionStyleDirectives)
    assert directives.identity_name == "anchor"
    assert "Inter" in directives.font_family
    assert directives.accent_color == "#FFCC00"
    assert directives.word_keyframes_template["total_words"] == 2


def test_speech_sync_compatibility_filtering(kb):
    """Verify speech_sync_compatible filter selects speech-ready caption models."""
    sf = SearchFilter(speech_sync_compatible=True)
    hits = kb.search("subtitles", filters=sf, limit=5)
    assert len(hits) > 0
    for h in hits:
        assert (
            h.capability_family == CapabilityFamily.CAPTIONS_WORD_HIGHLIGHT.value
            or "caption" in h.knowledge_doc_id
            or "highlight" in h.title.lower()
        )
