# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Integration adapters for Agent 1 (Chat/Research) and Agent 4 (Motion Generation).
Provides stable contracts without modifying external agent files.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from .models import CapabilityFamily, KnowledgeDoc, RightsFlag, SearchFilter, SearchResult
from .service import KnowledgeBase


# ===========================================================================
# Agent 1 Contract: Main Agent Chat / Retrieval Interface
# ===========================================================================

class Agent1SearchRequest(BaseModel):
    """Search request contract for Agent 1 chat retrieval."""
    query: str
    capability_family: Optional[str] = None
    aspect_ratio: Optional[str] = "9:16"
    captions_suitability: Optional[bool] = None
    limit: int = 5


class Agent1SearchResponse(BaseModel):
    """Search response contract for Agent 1 chat retrieval."""
    query: str
    total_hits: int
    results: List[SearchResult]
    context_prompt_snippet: str


def format_prompt_context(results: List[SearchResult], max_length: int = 2500) -> str:
    """Format search results into a clean, LLM-ready motion design prompt block."""
    if not results:
        return "No specific motion design references retrieved."

    lines = ["### HyperFrames Motion Design Directives (Knowledge Corpus):"]
    for i, res in enumerate(results, 1):
        lines.append(f"\n{i}. **{res.title}** [`{res.knowledge_doc_id}`]")
        lines.append(f"   - Family: `{res.capability_family}` | Donor Group: `{res.donor_group}`")
        if res.principles:
            lines.append(f"   - Principles: {'; '.join(res.principles)}")
        if res.algorithms:
            lines.append(f"   - Algorithms: {'; '.join(res.algorithms)}")
        if res.equations:
            lines.append(f"   - Equations/Easing: {'; '.join(res.equations)}")
        if res.runtime_constraints:
            aspects = res.runtime_constraints.get("aspect_ratios", ["16:9", "9:16"])
            lines.append(f"   - Constraints: Aspect ratios {aspects}, WebGPU={res.runtime_constraints.get('requires_webgpu', False)}")
        if res.matched_chunk:
            clean_chunk = res.matched_chunk.replace("\n", " ").strip()
            lines.append(f"   - Reference Excerpt: \"{clean_chunk[:160]}...\"")

    text = "\n".join(lines)
    return text[:max_length]


# ===========================================================================
# Agent 4 Contract: Motion Generator knowledge_refs Interface
# ===========================================================================

class KnowledgeRef(BaseModel):
    """Traceable citation to be recorded into ProjectRevision by Agent 4."""
    knowledge_doc_id: str
    source_hash: str
    source_ref: str
    capability_family: str
    techniques_applied: List[str] = Field(default_factory=list)
    principles_honored: List[str] = Field(default_factory=list)
    equations_applied: List[str] = Field(default_factory=list)


class MotionDirectives(BaseModel):
    """Actionable motion instructions synthesized for Agent 4 native composition."""
    doc_id: str
    title: str
    capability_family: str
    timing_rules: List[str]
    easing_curves: List[str]
    algorithms: List[str]
    parameters: List[Dict[str, Any]]
    aspect_ratios: List[str]
    requires_webgpu: bool
    rights_status: str


class KnowledgeAdapter:
    """Adapter utility for Agent 1 and Agent 4 interactions."""

    def __init__(self, kb: Optional[KnowledgeBase] = None):
        self.kb = kb or KnowledgeBase()

    def handle_agent1_query(self, request: Agent1SearchRequest) -> Agent1SearchResponse:
        """Handle incoming query from Main Agent chat router."""
        filters = SearchFilter(
            capability_family=request.capability_family,
            aspect_ratio=request.aspect_ratio,
            captions_suitability=request.captions_suitability
        )
        hits = self.kb.search(request.query, filters=filters, limit=request.limit)
        context_str = format_prompt_context(hits)
        return Agent1SearchResponse(
            query=request.query,
            total_hits=len(hits),
            results=hits,
            context_prompt_snippet=context_str
        )

    def get_agent4_directives(self, doc_id: str) -> Optional[MotionDirectives]:
        """Provide structured motion parameters and formulas for Agent 4 generator."""
        doc = self.kb.get_by_id(doc_id)
        if not doc:
            return None

        easings = [eq for eq in doc.equations if "easing" in eq.lower()]
        return MotionDirectives(
            doc_id=doc.knowledge_doc_id,
            title=doc.title,
            capability_family=doc.capability_family.value if isinstance(doc.capability_family, CapabilityFamily) else str(doc.capability_family),
            timing_rules=doc.principles,
            easing_curves=easings,
            algorithms=doc.algorithms,
            parameters=doc.parameters,
            aspect_ratios=doc.runtime_constraints.get("aspect_ratios", ["16:9", "9:16"]),
            requires_webgpu=bool(doc.runtime_constraints.get("requires_webgpu", False)),
            rights_status=doc.rights.value if isinstance(doc.rights, RightsFlag) else str(doc.rights)
        )

    def create_knowledge_ref(self, doc_id: str, applied_techniques: Optional[List[str]] = None) -> Optional[KnowledgeRef]:
        """Build a verifiable citation reference for ProjectRevision."""
        doc = self.kb.get_by_id(doc_id)
        if not doc:
            return None

        return KnowledgeRef(
            knowledge_doc_id=doc.knowledge_doc_id,
            source_hash=doc.source_hash,
            source_ref=doc.source_path,
            capability_family=doc.capability_family.value if isinstance(doc.capability_family, CapabilityFamily) else str(doc.capability_family),
            techniques_applied=applied_techniques or doc.algorithms[:3],
            principles_honored=doc.principles[:3],
            equations_applied=doc.equations[:3]
        )
