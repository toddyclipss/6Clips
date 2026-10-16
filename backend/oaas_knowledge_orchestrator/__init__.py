# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 20 Agent 1: Knowledge-First OAAS Orchestration Layer.
Provides typed chat request handling, knowledge retrieval boundaries,
original native motion generation adapters, CAS project revisions,
truthful state transitions, and immutable deliverable evidence.
"""

from .models import (
    CreativeRationale,
    ImmutableRunEvidence,
    KnowledgeCitation,
    KnowledgeOrchestratorResponse,
    KnowledgeOrchestratorState,
    NativeMotionSpecContract,
    RevisionRequestContract,
    VideoRequestContract,
)
from .native_actions_bridge import NativeActionsBridge
from .orchestrator import KnowledgeChatOrchestrator
from .state_machine import KnowledgeOrchestratorStateMachine

__all__ = [
    "KnowledgeChatOrchestrator",
    "KnowledgeOrchestratorStateMachine",
    "NativeActionsBridge",
    "KnowledgeOrchestratorState",
    "VideoRequestContract",
    "RevisionRequestContract",
    "KnowledgeOrchestratorResponse",
    "KnowledgeCitation",
    "CreativeRationale",
    "NativeMotionSpecContract",
    "ImmutableRunEvidence",
]
