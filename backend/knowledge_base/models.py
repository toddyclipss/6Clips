# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Data models for the 6Clips HyperFrames Motion Design Knowledge Base.
"""
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class CapabilityFamily(str, Enum):
    """6Clips derived functional capability families."""
    TYPOGRAPHY_KINETIC = "typography_kinetic"
    CAPTIONS_WORD_HIGHLIGHT = "captions_word_highlight"
    DATA_VISUALIZATION = "data_visualization"
    TRANSITION_WIPE = "transition_wipe"
    BACKGROUND_SHADER = "background_shader"
    CAMERA_3D = "camera_3d"
    UI_SIMULATION = "ui_simulation"
    RESPONSIVE_LAYOUT = "responsive_layout"


class CategoryProvenance(str, Enum):
    """Provenance tracking distinguishing canonical donor categories from 6Clips derived taxonomy."""
    DONOR_CANONICAL = "DONOR_CANONICAL"
    DONOR_INFERRED = "DONOR_INFERRED"
    DERIVED_6CLIPS = "DERIVED_6CLIPS"


class RightsFlag(str, Enum):
    """Licensing and redistribution rights flags."""
    VERIFIED_PERMISSIVE = "VERIFIED_PERMISSIVE"
    REFERENCE_ONLY = "REFERENCE_ONLY"
    BLOCKED_RIGHTS = "BLOCKED_RIGHTS"


class TestStatus(BaseModel):
    """Document testing ledger statuses (D0-D5)."""
    D0: str = Field(default="PASS", description="Identity, hash, and provenance verified")
    D1: str = Field(default="PASS", description="Faithful extraction of sections, techniques, equations, parameters")
    D2: str = Field(default="PASS", description="Retrieval relevance verified in benchmark query suite")
    D3: str = Field(default="PENDING", description="Knowledge-to-spec synthesis contract validation")
    D4: str = Field(default="NOT_APPLICABLE", description="Live player playback validation")
    D5: str = Field(default="NOT_APPLICABLE", description="Physical MP4 video render and decode")


class KnowledgeChunk(BaseModel):
    """Atomic retrievable chunk from a knowledge document."""
    chunk_id: str
    doc_id: str
    section_title: str
    content: str
    source_ref: str
    chunk_type: str = "section"


class KnowledgeDoc(BaseModel):
    """First-class curated knowledge document."""
    knowledge_doc_id: str
    version: str = "1.0.0"
    title: str
    summary: str
    source_path: str
    source_hash: str
    source_kind: str
    donor_group: str
    donor_section: str
    category_provenance: CategoryProvenance
    capability_family: CapabilityFamily
    tags: List[str] = Field(default_factory=list)
    principles: List[str] = Field(default_factory=list)
    algorithms: List[str] = Field(default_factory=list)
    equations: List[str] = Field(default_factory=list)
    parameters: List[Dict[str, Any]] = Field(default_factory=list)
    code_references: List[Dict[str, Any]] = Field(default_factory=list)
    dependent_assets: List[str] = Field(default_factory=list)
    runtime_constraints: Dict[str, Any] = Field(default_factory=dict)
    rights: RightsFlag = RightsFlag.VERIFIED_PERMISSIVE
    rights_reason: str = ""
    confidence: float = 1.0
    test_status: TestStatus = Field(default_factory=TestStatus)
    chunks: List[KnowledgeChunk] = Field(default_factory=list)


class SearchFilter(BaseModel):
    """Multi-faceted filter criteria for knowledge queries."""
    capability_family: Optional[Union[CapabilityFamily, str]] = None
    donor_group: Optional[str] = None
    rights: Optional[Union[RightsFlag, str]] = None
    aspect_ratio: Optional[str] = None
    captions_suitability: Optional[bool] = None
    technique: Optional[str] = None
    tag: Optional[str] = None
    requires_webgpu: Optional[bool] = None


class SearchResult(BaseModel):
    """Ranked hit returned from the knowledge search engine."""
    knowledge_doc_id: str
    title: str
    score: float
    source_hash: str
    source_ref: str
    donor_group: str
    donor_section: str
    capability_family: str
    techniques: List[str] = Field(default_factory=list)
    principles: List[str] = Field(default_factory=list)
    algorithms: List[str] = Field(default_factory=list)
    equations: List[str] = Field(default_factory=list)
    parameters: List[Dict[str, Any]] = Field(default_factory=list)
    rights: str
    runtime_constraints: Dict[str, Any] = Field(default_factory=dict)
    retrieval_explanation: str
    matched_chunk: Optional[str] = None
