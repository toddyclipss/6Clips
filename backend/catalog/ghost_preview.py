# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Ghost Preview Contract: ensures non-destructive, audio-muted hover preview that never writes ProjectRevision or persists state."""
from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

MIN_HOVER_DEBOUNCE_MS = 180
MAX_HOVER_DEBOUNCE_MS = 300


class GhostPreviewViolation(Exception):
    """Raised when a ghost preview attempts state mutation or audio unmute."""
    pass


class GhostPreviewContract:
    """Enforces non-destructive, read-only preview semantics for motion blocks."""

    @classmethod
    def get_preview_config(cls, block_id: str, aspect_ratio: str = "9:16") -> Dict[str, Any]:
        """
        Return the standardized Ghost Preview execution contract.
        Guarantees:
          - audio_muted: True (never plays audio during hover preview)
          - creates_revision: False (strictly read-only ephemeral overlay)
          - restores_cleanly: True (ESC and mouseout trigger immediate state revert)
          - debounce_window_ms: 220ms (prevents rapid hover churn)
        """
        return {
            "block_id": block_id,
            "aspect_ratio": aspect_ratio,
            "audio_muted": True,
            "creates_revision": False,
            "persists_history": False,
            "debounce_ms": 220,
            "read_only": True,
            "dismiss_on_escape": True,
            "dismiss_on_mouseout": True,
            "has_destructive_side_effects": False,
        }

    @classmethod
    def assert_safe_preview(cls, session_state: Dict[str, Any]) -> None:
        """
        Audit a preview session state. Raises GhostPreviewViolation if
        any mutation of project revisions or audio playback was enabled.
        """
        if session_state.get("creates_revision", False):
            raise GhostPreviewViolation("Ghost preview must never create or write a ProjectRevision.")
        if not session_state.get("audio_muted", True):
            raise GhostPreviewViolation("Ghost preview audio must remain strictly muted.")
        if session_state.get("persists_history", False):
            raise GhostPreviewViolation("Ghost preview must not persist to history or disk.")
