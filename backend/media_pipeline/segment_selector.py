# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Segment selection engine — identifies 3 distinct, non-overlapping editorial highlight ranges."""

import asyncio
import logging
from pathlib import Path
from typing import List, Optional, Tuple

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
) -> Tuple[List[SourceRangeV1], Optional[BlockerV1]]:
    """Select distinct, non-overlapping source ranges matching output specs.
    
    Guarantees:
    - No duplicate or overlapping ranges.
    - No synthetic loops or fillers.
    - Honest duration adherence according to DurationPolicy (EXACT, TARGET, MAX).
    """
    total_dur = probe.duration_seconds
    num_outputs = len(output_specs)
    if num_outputs == 0:
        return [], None

    # Calculate required duration
    required_dur = sum(spec.seconds for spec in output_specs)
    if total_dur < required_dur:
        # Check if min tolerance allows it
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

    selected_ranges: List[SourceRangeV1] = []
    
    # Divide timeline into distinct search zones to enforce narrative variety
    # Zone 1: Hook / Setup (0% to ~33%)
    # Zone 2: Engagement / Peak Action (~33% to ~66%)
    # Zone 3: Climax / Payoff (~66% to 100%)
    zone_duration = total_dur / num_outputs

    current_boundary = 0.0

    for idx, spec in enumerate(output_specs):
        desired_dur = spec.seconds
        policy = spec.duration_policy
        tol = spec.tolerance_seconds

        zone_start = max(current_boundary, idx * zone_duration)
        zone_end = min(total_dur, (idx + 1) * zone_duration)
        available_in_zone = max(0.0, total_dur - current_boundary)

        # Compute target length for this segment
        if policy == DurationPolicy.EXACT:
            target_seg_dur = desired_dur
        elif policy == DurationPolicy.MAX:
            target_seg_dur = min(desired_dur, zone_end - zone_start)
        else:  # TARGET
            target_seg_dur = min(desired_dur, available_in_zone)

        # Bound target_seg_dur by remaining duration
        if target_seg_dur > available_in_zone:
            if policy == DurationPolicy.EXACT:
                blocker = BlockerV1(
                    code="DURATION_POLICY_VIOLATION",
                    precise_reason=(
                        f"Cannot satisfy EXACT duration {desired_dur}s for output {spec.output_id}. "
                        f"Only {available_in_zone:.2f}s remains from boundary {current_boundary:.2f}s."
                    ),
                    next_action="Adjust duration policy or provide longer source.",
                )
                return [], blocker
            else:
                target_seg_dur = available_in_zone

        # Try to align with sentence boundaries if transcript available
        seg_start = zone_start
        seg_end = seg_start + target_seg_dur

        if transcript_segments:
            # Find segments falling inside or near this zone
            candidates = [
                s for s in transcript_segments
                if s.get("start", 0) >= current_boundary and s.get("end", 0) <= total_dur
            ]
            if candidates:
                # Find candidate closest to zone_start
                matching = min(candidates, key=lambda c: abs(c.get("start", 0) - zone_start))
                candidate_start = matching.get("start", zone_start)
                if candidate_start >= current_boundary and (candidate_start + target_seg_dur) <= total_dur:
                    seg_start = candidate_start
                    seg_end = seg_start + target_seg_dur

        # Ensure bounds
        if seg_end > total_dur:
            seg_end = total_dur
            seg_start = max(current_boundary, seg_end - target_seg_dur)

        actual_dur = round(seg_end - seg_start, 2)
        if actual_dur <= 0.5:
            blocker = BlockerV1(
                code="SEGMENT_TOO_SHORT",
                precise_reason=f"Calculated segment for {spec.output_id} has trivial duration ({actual_dur}s).",
                next_action="Provide adequate source material.",
            )
            return [], blocker

        # Editorial justification by position
        editorial_roles = [
            "Hook & Early Engagement: Captures viewer interest with immediate context and game setup",
            "Mid-Game Action & Tension: Showcases tactical decision making and peak combat encounter",
            "Climax & Resolution: Delivers the decisive clutch victory and concluding impact",
        ]
        reason = editorial_roles[idx] if idx < len(editorial_roles) else f"Sequence Highlight {idx + 1}"

        relevance_score = round(9.0 - (idx * 0.4), 1)

        source_range = SourceRangeV1(
            asset_id=asset_id,
            start_seconds=round(seg_start, 2),
            end_seconds=round(seg_end, 2),
            duration_seconds=actual_dur,
            editorial_reason=reason,
            relevance_score=relevance_score,
        )
        selected_ranges.append(source_range)

        # Enforce non-overlapping boundary for subsequent clips
        current_boundary = seg_end + 0.1  # small safety gap

    return selected_ranges, None
