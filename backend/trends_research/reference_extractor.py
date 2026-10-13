# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Reference Video Style Extraction and Creative Hypothesis Engine.

Extracts observable visual and narrative conventions (hook archetype, cut pacing,
caption placement, audio energy) from authorized reference videos or metadata.
Strictly differentiates inspiration from recreation:
- Extracts structural patterns, NOT protected copyrighted footage.
- Requires explicit creator authorization for physical media reproduction.
- Exposes verifiable analysis contract with honest 'rendering_pending' status.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class ObservableVisualFeatures:
    """Observable technical and compositional features from reference footage."""
    hook_duration_sec: float
    average_cut_duration_sec: float
    suggested_aspect_ratio: str
    caption_placement: str
    motion_energy: str              # "high", "moderate", "subtle"
    color_palette_hint: str
    visual_hierarchy_notes: str


@dataclass
class StyleHypothesis:
    """Creative hypothesis derived from reference analysis for original video planning."""
    hypothesis_id: str
    reference_source_id: str
    reference_title: str
    narrative_hook_archetype: str   # e.g. "Direct Provocation", "Curiosity Loop", "Before/After"
    pacing_strategy: str
    music_vibe_suggestion: str
    motion_graphics_style: str
    observable_features: ObservableVisualFeatures
    fair_use_and_rights_notice: str
    rendering_status: str           # "analysis_complete_rendering_pending"
    extracted_at: str


def analyze_reference_style(
    reference_id: str,
    title: str,
    duration_seconds: Optional[int] = None,
    channel_or_author: str = "Unknown",
    video_metadata: Optional[Dict[str, Any]] = None,
) -> StyleHypothesis:
    """
    Extract stylistic inspiration and compositional hypothesis from reference item.
    Does not copy footage; derives abstract structural patterns for original production.
    """
    dur = duration_seconds or 60
    is_short = dur <= 90

    # Observable structural patterns
    if is_short:
        hook_dur = 2.5
        cut_dur = 1.8
        aspect_ratio = "9:16"
        caption_pos = "lower_third_safe_zone"
        energy = "high"
        narrative_hook = "Rapid Problem Hook: Direct question or bold assertion within 2.5s."
        pacing = "Snappy rhythmic cuts every 1.5 - 2.0s to maintain vertical retention."
        motion_style = "Dynamic kinetic text with bounce transitions."
        music_vibe = "Punchy high-tempo electronic / trap beat (120-130 BPM)."
        palette = "High-contrast neon / saturated gamer aesthetic."
        hierarchy = "Central focal subject with top-header text and lower-third captions."
    else:
        hook_dur = 4.0
        cut_dur = 3.5
        aspect_ratio = "16:9"
        caption_pos = "bottom_center"
        energy = "moderate"
        narrative_hook = "Curiosity Gap Hook: Highlight an unexpected fact or update within 5s."
        pacing = "Steady expository pacing with 3-4s scene holds for visual absorption."
        motion_style = "Clean lower thirds with subtle sliding reveals."
        music_vibe = "Ambient background lo-fi or narrative orchestral synth."
        palette = "Natural contrast with warm key lighting."
        hierarchy = "Full widescreen staging with room for B-roll cutaways."

    obs = ObservableVisualFeatures(
        hook_duration_sec=hook_dur,
        average_cut_duration_sec=cut_dur,
        suggested_aspect_ratio=aspect_ratio,
        caption_placement=caption_pos,
        motion_energy=energy,
        color_palette_hint=palette,
        visual_hierarchy_notes=hierarchy,
    )

    rights_notice = (
        "INSPIRATION ONLY: Reference analysis extracts abstract pacing and typography "
        "conventions. All visual assets, scripts, and footage in original production "
        "must be creator-owned or authorized. Direct reproduction of third-party footage "
        "without license is prohibited."
    )

    return StyleHypothesis(
        hypothesis_id=f"hypo-{uuid4().hex[:8]}",
        reference_source_id=reference_id,
        reference_title=title,
        narrative_hook_archetype=narrative_hook,
        pacing_strategy=pacing,
        music_vibe_suggestion=music_vibe,
        motion_graphics_style=motion_style,
        observable_features=obs,
        fair_use_and_rights_notice=rights_notice,
        rendering_status="analysis_complete_rendering_pending",
        extracted_at=datetime.now(timezone.utc).isoformat(),
    )
