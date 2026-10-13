# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Segment selection engine — identifies 3 distinct, non-overlapping editorial highlight ranges."""

import asyncio
import logging
from pathlib import Path
from typing import Any, List, Optional, Tuple

from backend.media_pipeline.models import (
    BlockerV1,
    DurationPolicy,
    MediaProbeV1,
    OutputSpecV1,
    SourceRangeV1,
)

logger = logging.getLogger(__name__)


class SelectionError(Exception):
    def __init__(self, blocker: BlockerV1):
        super().__init__(blocker.precise_reason)
        self.blocker = blocker


async def extract_transcript_if_needed(media_path: Path, probe: MediaProbeV1) -> list[dict]:
    """Attempt faster-whisper transcription if audio stream exists and is not silent."""
    if probe.audio_codec == "none" or probe.is_silent:
        return []
    try:
        from backend.services.whisper_service import WhisperService
        result = await WhisperService.transcribe(
            media_path,
            quality="fast",
            task="transcribe",
        )
        return result.get("segments", []) if isinstance(result, dict) else []
    except Exception as e:
        logger.warning("Whisper transcription skipped or failed: %s", e)
        return []


def select_editorial_segments(
    probe: MediaProbeV1,
    output_specs: List[OutputSpecV1],
    transcript_segments: list[dict] = None,
    asset_id: str = "primary",
    media_path: Optional[Path] = None,
    audio_profile: Optional[Any] = None,
    scene_cuts: Optional[List[float]] = None,
) -> Tuple[List[SourceRangeV1], Optional[BlockerV1]]:
    """Select distinct, non-overlapping source ranges matching output specs.
    
    Guarantees:
    - Multi-signal candidate ranking using audio energy, speech density, and scene transitions.
    - No duplicate or overlapping ranges.
    - No synthetic loops or fake fillers.
    - Honest duration adherence according to DurationPolicy (EXACT, TARGET, MAX).
    - Transparent provenance, criteria summary, and explicit limitation disclosure.
    """
    from backend.media_intelligence.audio_energy import AudioEnergyProfile, analyze_audio_energy_sync
    from backend.media_intelligence.candidate_ranker import generate_and_rank_segments
    from backend.media_intelligence.scene_analyzer import detect_scene_changes_sync
    total_dur = probe.duration_seconds
    num_outputs = len(output_specs)
    if num_outputs == 0:
        return [], None

    # Calculate required duration
    min_possible = 0.0
    for spec in output_specs:
        if spec.duration_policy == DurationPolicy.EXACT:
            min_possible += spec.seconds
        elif spec.duration_policy == DurationPolicy.MAX:
            min_possible += min(5.0, spec.seconds)
        else:  # TARGET
            min_possible += max(1.0, spec.seconds - spec.tolerance_seconds)

    if total_dur < min_possible:
        blocker = BlockerV1(
            code="INSUFFICIENT_SOURCE_DURATION",
            precise_reason=(
                f"Source duration ({total_dur:.2f}s) is shorter than required minimum "
                f"duration ({min_possible:.2f}s) for {num_outputs} distinct clips. "
                "Repetition, loop, and fake fillers are strictly prohibited."
            ),
            next_action="Provide longer source media or reduce requested clip duration.",
        )
        return [], blocker

    # If physical media path provided and signals not yet computed, extract practical signals
    if media_path and media_path.exists():
        if audio_profile is None and not probe.is_silent and probe.audio_codec != "none":
            try:
                audio_profile = analyze_audio_energy_sync(media_path)
            except Exception as e:
                logger.warning("Audio energy extraction skipped for %s: %s", media_path.name, e)

        if scene_cuts is None:
            try:
                scene_cuts = detect_scene_changes_sync(media_path, max_duration_seconds=total_dur)
            except Exception as e:
                logger.warning("Scene detection skipped for %s: %s", media_path.name, e)

    # Use media-aware candidate generation and ranking engine
    selected_ranges, blocker = generate_and_rank_segments(
        total_duration=total_dur,
        output_specs=output_specs,
        audio_profile=audio_profile,
        scene_cuts=scene_cuts,
        transcript_segments=transcript_segments,
        asset_id=asset_id,
        min_gap_seconds=1.0,
    )

    if blocker:
        return [], blocker

    return selected_ranges, None
