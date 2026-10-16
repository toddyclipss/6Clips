# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Integration adapters for Agent 1 (Chat/Research) and Agent 4 (Motion Generation).
Provides stable contracts without modifying external agent files.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from .models import (
    CapabilityFamily,
    CaptionStyleDirectives,
    KnowledgeDoc,
    RightsFlag,
    SearchFilter,
    SearchResult,
)
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
    exclude_blocked: bool = True
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
            captions_suitability=request.captions_suitability,
            exclude_blocked=request.exclude_blocked,
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

    def get_caption_style_directives(
        self,
        doc_id_or_identity: str,
        words: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[CaptionStyleDirectives]:
        """Provide specialized typographic and word-highlighting directives for caption engine."""
        doc_id = doc_id_or_identity
        if not doc_id.startswith("caption:"):
            doc_id = f"caption:{doc_id_or_identity}"

        doc = self.kb.get_by_id(doc_id)
        if not doc:
            # Fallback search by identity tag or title
            results = self.kb.search(doc_id_or_identity, filters=SearchFilter(is_caption_identity=True), limit=1)
            if results:
                doc = self.kb.get_by_id(results[0].knowledge_doc_id)

        if not doc:
            return None

        identity_name = doc.caption_identity_name or doc.knowledge_doc_id.replace("caption:", "")

        # Style presets mapped to identity
        presets: Dict[str, Dict[str, str]] = {
            "cream": {"font": "Georgia, serif", "accent": "#FFF8E7", "sec": "#E6D7B9"},
            "editorial": {"font": "Playfair Display, serif", "accent": "#F5F5F0", "sec": "#C0B8A8"},
            "ink": {"font": "Courier New, monospace", "accent": "#1A1A1A", "sec": "#444444"},
            "keynote": {"font": "Inter, sans-serif", "accent": "#FFFFFF", "sec": "#8E8E93"},
            "loud": {"font": "Oswald, sans-serif", "accent": "#FF2A55", "sec": "#FFFFFF"},
            "neon": {"font": "Space Grotesk, sans-serif", "accent": "#00F0FF", "sec": "#FF007F"},
            "glitch": {"font": "JetBrains Mono, monospace", "accent": "#00FF66", "sec": "#FF0055"},
            "chrome": {"font": "Montserrat, sans-serif", "accent": "#E0E8F0", "sec": "#8090A0"},
            "velocity": {"font": "Montserrat, sans-serif", "accent": "#FFCC00", "sec": "#FFFFFF"},
            "anchor": {"font": "Inter, sans-serif", "accent": "#FFCC00", "sec": "#F0F0F0"},
            "terminal": {"font": "JetBrains Mono, monospace", "accent": "#00FF66", "sec": "#33FF33"},
            "neonsign": {"font": "Space Grotesk, sans-serif", "accent": "#FF3366", "sec": "#FFE600"},
            "arcade": {"font": "JetBrains Mono, monospace", "accent": "#FFE600", "sec": "#00F0FF"},
            "vhs": {"font": "Courier New, monospace", "accent": "#00FFCC", "sec": "#FF3366"},
        }
        style = presets.get(identity_name.lower(), {"font": "Inter, sans-serif", "accent": "#FFCC00", "sec": "#FFFFFF"})

        # Build word keyframe mapping template if authentic words provided
        keyframes_template: Dict[str, Any] = {}
        if words:
            word_list = []
            for w in words:
                word_text = str(w.get("word", ""))
                start = float(w.get("start", 0.0))
                end = float(w.get("end", start + 0.2))
                emphasis = bool(w.get("emphasis", False))
                word_list.append({
                    "word": word_text,
                    "start": start,
                    "end": end,
                    "emphasis": emphasis,
                    "highlight_fill": style["accent"] if emphasis else style["sec"],
                    "scale_pop": 1.15 if emphasis else 1.0,
                    "easing": "ease-out"
                })
            keyframes_template = {
                "total_words": len(word_list),
                "words": word_list,
                "strategy": "per_word_karaoke_sweep"
            }

        return CaptionStyleDirectives(
            doc_id=doc.knowledge_doc_id,
            identity_name=identity_name,
            reading_surface=doc.runtime_constraints.get("reading_surface", "scene-embedded column flow"),
            voice_description=doc.summary,
            recommended_for=doc.runtime_constraints.get("recommended_for", "narrative & monologue"),
            scene_needs=doc.runtime_constraints.get("scene_needs", "mid/dark scenes"),
            author_engine=doc.runtime_constraints.get("author_engine", "cinematic"),
            rights_status=doc.rights.value if isinstance(doc.rights, RightsFlag) else str(doc.rights),
            font_family=style["font"],
            accent_color=style["accent"],
            secondary_color=style["sec"],
            background_scrim=True,
            speech_sync_rules=doc.speech_sync_rules or [
                "Word-level timestamp synchronization",
                "Highlight sweep on word start time",
                "Hold state through duration, fade on word end"
            ],
            word_keyframes_template=keyframes_template
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

