# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Typed Request/Response and Audit Models for Knowledge-First OAAS Orchestration.
Guarantees full provenance, strict schema validation, truthful states,
and immutable run evidence for original video generation and chat-based revisions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field, field_validator, model_validator


class KnowledgeOrchestratorState(str, Enum):
    """
    Truthful state machine lifecycle for Knowledge-Grounded Video Generation.
    Strictly linear progression with explicit failure and blocker branches.
    """
    REQUESTED = "REQUESTED"
    PLANNING = "PLANNING"
    RETRIEVING_KNOWLEDGE = "RETRIEVING_KNOWLEDGE"
    COMPOSING = "COMPOSING"
    VALIDATING = "VALIDATING"
    RENDERING = "RENDERING"
    VIDEO_VERIFIED = "VIDEO_VERIFIED"
    REVIEW_READY = "REVIEW_READY"

    # Terminal / Blocker States (Fail-Closed)
    PENDING_CREDENTIALS = "PENDING_CREDENTIALS"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_TERMINAL = "FAILED_TERMINAL"
    NEEDS_AUTHORIZATION = "NEEDS_AUTHORIZATION"
    BLOCKED = "BLOCKED"


class KnowledgeCitation(BaseModel):
    """
    Traceable citation to an authentic HyperFrames knowledge document (A3 contract).
    Ensures clear attribution without importing prebuilt executable bundles.
    """
    knowledge_doc_id: str = Field(..., description="Unique document ID in the knowledge corpus.")
    source_path: str = Field(..., description="Source path within the donor repository docs.")
    source_hash: str = Field(..., description="SHA-256 fingerprint of the source document.")
    technique: str = Field(..., description="Motion, typography, caption, or layout technique extracted.")
    donor_group: Optional[str] = Field(None, description="Original donor classification.")
    capability_family: Optional[str] = Field(None, description="Derived 6Clips functional capability category.")
    rights: Optional[str] = Field("PERMITTED", description="Rights / licensing status of the technique.")
    runtime_constraints: Optional[str] = Field(None, description="Constraints (e.g. requires WebGL, safe margins).")
    retrieval_explanation: Optional[str] = Field(None, description="Explanation why this technique was retrieved.")


class CreativeRationale(BaseModel):
    """
    Immutable justification of autonomous creative decisions, proving true
    structural originality rather than cosmetic color or text substitutions.
    """
    intent_summary: str = Field(..., description="Structured interpretation of the user chat request.")
    motion_strategy: str = Field(..., description="Chosen kinetic motion and easing principles.")
    typography_strategy: str = Field(..., description="Typography hierarchy, legibility, and safe margins.")
    layout_hierarchy: str = Field(..., description="Spatial layout and responsive coordinates.")
    pacing_and_audio: str = Field(..., description="Temporal pacing, scene transitions, and audio sync.")
    originality_defense: str = Field(
        ...,
        description="Explicit explanation of why the generated composition is structurally original.",
    )


class NativeMotionElement(BaseModel):
    """Individual visual element in native motion composition."""
    element_id: str = Field(..., description="Unique element identifier.")
    element_type: str = Field(..., description="Type: text, kinetic_title, shape, chart, background, caption.")
    start_time: float = Field(0.0, ge=0.0, description="Start offset in seconds.")
    duration: float = Field(..., gt=0.0, description="Duration in seconds.")
    layer_order: int = Field(0, description="Z-index layering order.")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Geometry, style, typography, and animation params.")
    keyframes: List[Dict[str, Any]] = Field(default_factory=list, description="Parametric keyframes and easing curves.")


class NativeMotionScene(BaseModel):
    """Scene segment containing timed native motion elements."""
    scene_number: int = Field(..., ge=1, description="Sequential scene index.")
    timecode_start: float = Field(..., ge=0.0, description="Scene start time in seconds.")
    timecode_end: float = Field(..., gt=0.0, description="Scene end time in seconds.")
    visual_description: str = Field(..., description="Creative description of the scene.")
    elements: List[NativeMotionElement] = Field(default_factory=list, description="Timed elements in the scene.")

    @model_validator(mode="after")
    def validate_bounds(self) -> NativeMotionScene:
        if self.timecode_end <= self.timecode_start:
            raise ValueError(f"timecode_end ({self.timecode_end}) must be greater than timecode_start ({self.timecode_start}).")
        return self


class NativeMotionSpecContract(BaseModel):
    """
    Typed native_motion_v1 representation matching Agent 4 interface contract.
    Contains no executable JS/HTML scripts; purely parametric scene graph.
    """
    spec_version: str = Field("native_motion_v1", description="Schema version identifier.")
    title: str = Field(..., description="Project title.")
    aspect_ratio: str = Field("9:16", description="Composition aspect ratio.")
    target_duration_sec: float = Field(..., gt=0.0, description="Overall composition duration.")
    fps: int = Field(30, ge=15, le=60, description="Frame rate.")
    width: int = Field(1080, gt=0, description="Width in pixels.")
    height: int = Field(1920, gt=0, description="Height in pixels.")
    creative_brief: str = Field(..., description="User brief that directed this composition.")
    knowledge_refs: List[KnowledgeCitation] = Field(default_factory=list, description="Associated knowledge citations.")
    scenes: List[NativeMotionScene] = Field(default_factory=list, description="Sequential motion scenes.")
    audio_ducking: bool = Field(True, description="Whether background audio is ducked during speech.")
    captions: List[Dict[str, Any]] = Field(default_factory=list, description="Timed caption segments with word alignment.")


class ImmutableRunEvidence(BaseModel):
    """
    Durable, auditable evidence trail recorded for each autonomous generation run.
    Contains zero fabricated receipts, real cryptographic hashes, and exact lineage.
    """
    run_id: str = Field(..., description="Unique run identifier.")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO-8601 UTC timestamp.",
    )
    user_id: str = Field("local", description="Authenticated user identifier.")
    session_id: str = Field("default_session", description="Persistent chat session ID.")
    project_id: str = Field(..., description="Associated canonical Project ID.")
    revision_id: int = Field(1, ge=1, description="Resulting canonical Project revision.")
    creative_rationale: CreativeRationale = Field(..., description="Documented creative rationale.")
    knowledge_citations: List[KnowledgeCitation] = Field(default_factory=list, description="Cited knowledge records.")
    applied_actions: List[Dict[str, Any]] = Field(default_factory=list, description="Native editor actions applied.")
    safety_validation: Dict[str, Any] = Field(default_factory=dict, description="Security and bounds audit results.")
    media_artifact: Optional[Dict[str, Any]] = Field(None, description="Decoded MP4 file verification details.")
    authorizations: Dict[str, Any] = Field(default_factory=dict, description="User rights and standing permissions.")
    state_history: List[Dict[str, Any]] = Field(default_factory=list, description="Complete state machine audit log.")


class VideoRequestContract(BaseModel):
    """
    Typed request consumed by handle_video_request() from the existing chat.
    Consumes ordinary natural-language user messages.
    """
    message: str = Field(..., min_length=1, description="Natural-language chat message requesting video.")
    user_id: str = Field("local", description="Authenticated user ID.")
    session_id: str = Field("default_session", description="Persistent chat session ID.")
    project_id: Optional[str] = Field(None, description="Optional existing project ID to modify.")
    output_count: int = Field(1, ge=1, le=10, description="Requested number of independent video deliverables.")
    require_production_knowledge: bool = Field(False, description="When True, fail-closed if production knowledge is unavailable.")
    authorizations: Dict[str, Any] = Field(default_factory=dict, description="Explicit user permissions.")
    preferences: Dict[str, Any] = Field(default_factory=dict, description="Optional preferences (aspect, duration, mood).")
    allow_test_fixture: bool = Field(True, description="Whether isolated test audio fixtures are permitted.")
    idempotency_token: Optional[str] = Field(None, description="Optional idempotency key.")


class RevisionRequestContract(BaseModel):
    """
    Typed request consumed by revise_deliverable() from the existing chat.
    Operates as a delta on the SAME canonical timeline.
    """
    run_id: str = Field(..., min_length=1, description="Previous run ID to revise.")
    user_feedback: str = Field(..., min_length=1, description="Natural language feedback or correction.")
    expected_revision: int = Field(..., ge=1, description="Expected base revision for atomic CAS check.")
    revert_to_revision: Optional[int] = Field(None, ge=1, description="Optional previous revision number to revert to.")
    user_id: str = Field("local", description="Authenticated user ID.")
    authorizations: Dict[str, Any] = Field(default_factory=dict, description="Explicit user permissions.")
    allow_retry: bool = Field(True, description="Whether optimistic CAS retry is enabled.")
    allow_test_fixture: bool = Field(True, description="Whether isolated test audio fixtures are permitted.")
    idempotency_token: Optional[str] = Field(None, description="Optional idempotency key.")


class KnowledgeOrchestratorResponse(BaseModel):
    """
    Authoritative response returned to the existing chat layer and Main Agent.
    Truthfully reflects generation progress, verified media, and delivery status.
    """
    run_id: str = Field(..., description="Unique run identifier.")
    project_id: str = Field(..., description="Canonical project ID.")
    revision_id: int = Field(..., ge=1, description="Canonical project revision.")
    state: KnowledgeOrchestratorState = Field(..., description="Current state machine status.")
    message: str = Field(..., description="Human-readable outcome description.")
    blocker_code: Optional[str] = Field(None, description="Machine-readable blocker code if blocked.")
    blocker_reason: Optional[str] = Field(None, description="Detailed explanation of blocker if blocked.")
    evidence: Optional[ImmutableRunEvidence] = Field(None, description="Immutable run evidence record.")
    artifact_links: List[Dict[str, Any]] = Field(default_factory=list, description="Verified output media artifacts.")
    library_asset_id: Optional[str] = Field(None, description="Primary persisted Library asset ID.")
    library_ids: List[str] = Field(default_factory=list, description="All persisted Library asset IDs.")
    deliverable_url: Optional[str] = Field(None, description="Verified deliverable playback or download URL.")
    output_count: int = Field(1, ge=1, description="Number of distinct deliverables produced.")
    preview_details: Dict[str, Any] = Field(default_factory=dict, description="Summary parameters for review.")
    publication_status: str = Field("NOT_CONNECTED", description="Verified publication status.")
