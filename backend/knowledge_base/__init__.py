# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
HyperFrames Motion Design Knowledge Base.
Provides exhaustive, provenance-aware, deterministic motion technique retrieval.
"""
from .models import (
    CapabilityFamily,
    CategoryProvenance,
    KnowledgeChunk,
    KnowledgeDoc,
    RightsFlag,
    SearchFilter,
    SearchResult,
    TestStatus,
)
from .service import KnowledgeBase
from .storage import KnowledgeRepository
from .search import BM25SearchEngine
from .adapter import (
    Agent1SearchRequest,
    Agent1SearchResponse,
    KnowledgeAdapter,
    KnowledgeRef,
    MotionDirectives,
    format_prompt_context,
)

__all__ = [
    "CapabilityFamily",
    "CategoryProvenance",
    "KnowledgeChunk",
    "KnowledgeDoc",
    "RightsFlag",
    "SearchFilter",
    "SearchResult",
    "TestStatus",
    "KnowledgeBase",
    "KnowledgeRepository",
    "BM25SearchEngine",
    "Agent1SearchRequest",
    "Agent1SearchResponse",
    "KnowledgeAdapter",
    "KnowledgeRef",
    "MotionDirectives",
    "format_prompt_context",
]
