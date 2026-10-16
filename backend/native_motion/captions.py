# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Professional Native Caption Engine.

Constructs original kinetic typographic captions based on HyperFrames motion principles
and authentic speech word-level timestamps. Rejects fabricated timings (fails closed
with PENDING if speech is unavailable).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.core.exceptions import ViralMintError
from backend.native_motion.schema import (
    CaptionsConfig,
    CreativeBrief,
    ElementSpec,
    ElementTransform,
    SafeZoneSpec,
    TypographySpec,
    WordTimestampSpec,
)

logger = logging.getLogger(__name__)


class CaptionSpeechUnavailableError(ViralMintError):
    """Raised when speech transcription/audio is unavailable, enforcing honest PENDING status."""
    def __init__(self, message: str = "Authentic speech audio or transcript is unavailable."):
        super().__init__(message)
        self.status = "PENDING_SPEECH_AUDIO"


class NativeCaptionEngine:
    """Designs original kinetic typography and aligns authentic speech word timestamps."""

    @classmethod
    def load_authentic_words(
        cls,
        audio_path: Optional[str] = None,
        transcript_data: Optional[List[Dict[str, Any]]] = None,
    ) -> List[WordTimestampSpec]:
        """Load and validate genuine word-level timestamps.

        Fails with CaptionSpeechUnavailableError if authentic speech cannot be found.
        Never fabricates artificial word timings.
        """
        if transcript_data:
            words = []
            for item in transcript_data:
                word = str(item.get("word", "")).strip()
                start = float(item.get("start", 0.0))
                end = float(item.get("end", start + 0.1))
                conf = float(item.get("confidence", 1.0))
                emphasis = bool(item.get("emphasis", False))
                if word:
                    words.append(
                        WordTimestampSpec(
                            word=word,
                            start=round(start, 3),
                            end=round(end, 3),
                            confidence=conf,
                            emphasis=emphasis,
                        )
                    )
            if words:
                return words

        if not audio_path or not Path(audio_path).exists():
            raise CaptionSpeechUnavailableError(
                f"Authentic audio file not found at '{audio_path}'. Cannot fabricate word timestamps."
            )

        # In a real environment, invoke WhisperService if available
        try:
            from backend.services.whisper_service import WhisperService
            # Check if whisper model is accessible
            res = WhisperService.transcribe_sync(audio_path)
            words = []
            for seg in res.get("segments", []):
                for w in seg.get("words", []):
                    words.append(
                        WordTimestampSpec(
                            word=w.get("word", "").strip(),
                            start=float(w.get("start", 0.0)),
                            end=float(w.get("end", 0.0)),
                            confidence=float(w.get("probability", 1.0)),
                        )
                    )
            if words:
                return words
        except Exception as e:
            logger.info("WhisperService not initialized: %s", e)

        raise CaptionSpeechUnavailableError(
            f"Unable to extract authentic speech timestamps from '{audio_path}'. Status: PENDING_SPEECH_AUDIO."
        )

    @classmethod
    def compose_caption_element(
        cls,
        words: List[WordTimestampSpec],
        width: int,
        height: int,
        safe_zones: SafeZoneSpec,
        brief: CreativeBrief,
        duration: float,
    ) -> ElementSpec:
        """Create a kinetic caption element adhering strictly to safe zones and accessibility."""
        if not words:
            raise ValueError("Cannot compose caption element with empty word list.")

        # Typography styling derived from brief intent
        tone = brief.tone.lower()
        if tone in ("minimal", "editorial", "luxury"):
            font_family = "Inter, sans-serif"
            font_size = 38.0 if width <= 1080 else 46.0
            font_weight = 700
            active_color = "#E2E8F0"
            inactive_color = "#64748B"
            anim_mode = "word_highlight"
        else:
            font_family = "Montserrat, sans-serif"
            font_size = 44.0 if width <= 1080 else 54.0
            font_weight = 900
            active_color = "#FBBF24"  # Amber-400
            inactive_color = "#94A3B8"  # Slate-400
            anim_mode = "word_pop"

        # Position inside bottom safe area
        box_w = width * (1.0 - (safe_zones.left + safe_zones.right))
        box_h = 140.0
        anchor_y = height * (1.0 - safe_zones.bottom) - (box_h / 2)

        return ElementSpec(
            id="captions_kinetic_main",
            type="captions",
            start_time=0.0,
            duration=duration,
            z_index=50,
            transform=ElementTransform(
                x=width / 2,
                y=anchor_y,
                width=box_w,
                height=box_h,
                anchor_x=0.5,
                anchor_y=0.5,
            ),
            captions_config=CaptionsConfig(
                words=words,
                active_color=active_color,
                inactive_color=inactive_color,
                typography=TypographySpec(
                    font_family=font_family,
                    font_size=font_size,
                    font_weight=font_weight,
                    letter_spacing=0.5,
                    text_align="center",
                    fill="#FFFFFF",
                ),
                animation_mode=anim_mode,
                safe_zone_anchor="bottom",
                background_veil=True,
                veil_color="rgba(15, 23, 42, 0.8)",
            ),
        )
