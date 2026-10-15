# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
OAAS Chat Ingestion & Stream Orchestration Package.

Provides chat-to-outcome adaptation and agent-operated remote video asset ingestion
with strict SSRF, scheme, and permission validation.
"""

from .models import (
    ChatGoalOutcomeResponse,
    ChatGoalProgressEvent,
    ChatGoalStatus,
    IngestionBlockerCode,
    UrlIngestionRequest,
    UrlIngestionResult,
)
from .security import IngestionSecurityValidator
from .ingestion_service import AgentUrlIngestionService
from .chat_orchestrator import ChatOutcomeOrchestrator

__all__ = [
    "ChatGoalOutcomeResponse",
    "ChatGoalProgressEvent",
    "ChatGoalStatus",
    "IngestionBlockerCode",
    "UrlIngestionRequest",
    "UrlIngestionResult",
    "IngestionSecurityValidator",
    "AgentUrlIngestionService",
    "ChatOutcomeOrchestrator",
]
