# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Media-aware candidate highlight segment generation, scoring, and optimal deduplication."""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from backend.media_intelligence.audio_energy import AudioEnergyProfile
from backend.media_pipeline.models import (
    BlockerV1,
    DurationPolicy,
    OutputSpecV1,
    SourceRangeV1,
)

logger = logging.getLogger(__name__)


@dataclass
class CandidateSegment:
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    audio_energy_score: float = 5.0
    silence_penalty: float = 0.0
    scene_pacing_score: float = 5.0
    speech_density_score: float = 5.0
    composite_score: float = 5.0
    provenance: str = "HEURISTIC"
    confidence: str = "HEURISTIC"
    criteria_summary: str = ""


def generate_candidate_windows(
    total_duration: float,
    target_duration: float,
    audio_profile: Optional[AudioEnergyProfile] = None,
    scene_cuts: Optional[List[float]] = None,
    transcript_segments: Optional[List[Dict[str, Any]]] = None,
    step_seconds: float = 5.0,
) -> List[CandidateSegment]:
    """Generate candidate segment windows across media timeline and compute multi-signal scores."""
    if total_duration < target_duration:
        return []

    candidates: List[CandidateSegment] = []
    cuts = sorted(scene_cuts or [])
    curr_start = 0.0

    while (curr_start + target_duration) <= (total_duration + 0.01):
        curr_end = round(curr_start + target_duration, 2)
        seg_dur = round(curr_end - curr_start, 2)

        # 1. Audio Energy Score (0.0 to 10.0)
        audio_score = 5.0
        silence_pen = 0.0
        is_audio_available = False

        if audio_profile and not audio_profile.is_silent and audio_profile.windows:
            is_audio_available = True
            seg_energy_db = audio_profile.energy_in_range(curr_start, curr_end)
            sil_ratio = audio_profile.silence_ratio_in_range(curr_start, curr_end)
            silence_pen = round(sil_ratio * 4.0, 2)

            mean_db = audio_profile.mean_rms_db
            peak_db = audio_profile.peak_rms_db
            spread = max(1.0, peak_db - mean_db)
            rel_energy = max(0.0, min(1.0, (seg_energy_db - mean_db) / spread))
            audio_score = round(4.0 + (rel_energy * 6.0), 2)
            audio_score = max(1.0, round(audio_score - silence_pen, 2))

        # 2. Scene Pacing Score (0.0 to 10.0)
        scene_score = 5.0
        is_scene_available = bool(cuts)
        cuts_in_range = 0
        if cuts:
            cuts_in_range = len([c for c in cuts if curr_start <= c <= curr_end])
            if 1 <= cuts_in_range <= 8:
                scene_score = 8.5
            elif cuts_in_range > 8:
                scene_score = 6.0
            else:
                scene_score = 4.0

            near_cut_start = any(abs(c - curr_start) <= 1.5 for c in cuts)
            near_cut_end = any(abs(c - curr_end) <= 1.5 for c in cuts)
            if near_cut_start or near_cut_end:
                scene_score = min(10.0, scene_score + 1.5)

        # 3. Speech / Transcript Density Score (0.0 to 10.0)
        speech_score = 5.0
        is_speech_available = bool(transcript_segments)
        words_count = 0
        if transcript_segments:
            matching_segs = [
                s for s in transcript_segments
                if float(s.get("end", 0)) > curr_start and float(s.get("start", 0)) < curr_end
            ]
            words_count = sum(len(s.get("text", "").split()) for s in matching_segs)
            expected_words = (target_duration / 60.0) * 130.0
            if expected_words > 0:
                ratio = min(2.0, words_count / expected_words)
                speech_score = round(3.0 + min(7.0, ratio * 5.0), 2)

        # 4. Composite Scoring & Provenance Determination
        if is_audio_available and is_scene_available and is_speech_available:
            composite = round(0.40 * audio_score + 0.30 * speech_score + 0.30 * scene_score, 1)
            provenance = "MULTIMODAL_SIGNALS"
            confidence = "HIGH"
            summary = (
                f"Audio RMS: {audio_score}/10, Speech words: {words_count}, Scene cuts: {cuts_in_range}, "
                f"Silence penalty: -{silence_pen}"
            )
        elif is_audio_available and is_scene_available:
            composite = round(0.55 * audio_score + 0.45 * scene_score, 1)
            provenance = "AUDIO_ENERGY_AND_SCENE"
            confidence = "MEDIUM"
            summary = (
                f"Audio RMS: {audio_score}/10, Scene cuts: {cuts_in_range}, Silence penalty: -{silence_pen}"
            )
        elif is_audio_available:
            composite = round(audio_score, 1)
            provenance = "AUDIO_ENERGY_DOMINANT"
            confidence = "MEDIUM"
            summary = f"Audio RMS: {audio_score}/10, Silence penalty: -{silence_pen}"
        elif is_scene_available:
            composite = round(scene_score, 1)
            provenance = "SCENE_PACING_DOMINANT"
            confidence = "LOW"
            summary = f"Scene cuts in range: {cuts_in_range}"
        else:
            center_bias = 1.0 - abs((curr_start + target_duration / 2.0) - (total_duration / 2.0)) / (total_duration / 2.0)
            composite = round(5.0 + (center_bias * 2.0), 1)
            provenance = "HEURISTIC_TEMPORAL_FALLBACK"
            confidence = "HEURISTIC"
            summary = "Uniform temporal search (no audio/scene signals detected; heuristic placement)"

        candidates.append(CandidateSegment(
            start_seconds=round(curr_start, 2),
            end_seconds=round(curr_end, 2),
            duration_seconds=seg_dur,
            audio_energy_score=audio_score,
            silence_penalty=silence_pen,
            scene_pacing_score=scene_score,
            speech_density_score=speech_score,
            composite_score=composite,
            provenance=provenance,
            confidence=confidence,
            criteria_summary=summary,
        ))

        curr_start += step_seconds

    return candidates


def _find_optimal_non_overlapping_combination(
    candidates: List[CandidateSegment],
    num_outputs: int,
    min_gap_seconds: float = 1.0,
) -> List[CandidateSegment]:
    """Find combination of N non-overlapping candidates that maximizes sum of composite scores."""
    if len(candidates) < num_outputs or num_outputs == 0:
        return []

    sorted_cands = sorted(candidates, key=lambda c: c.start_seconds)
    memo: Dict[Tuple[int, int], Tuple[float, List[CandidateSegment]]] = {}

    def search(idx: int, remaining: int) -> Tuple[float, List[CandidateSegment]]:
        if remaining == 0:
            return (0.0, [])
        if idx >= len(sorted_cands):
            return (-float("inf"), [])

        key = (idx, remaining)
        if key in memo:
            return memo[key]

        # Option A: Skip current candidate
        best_score, best_combo = search(idx + 1, remaining)

        # Option B: Pick current candidate
        cand = sorted_cands[idx]
        next_idx = idx + 1
        while next_idx < len(sorted_cands) and sorted_cands[next_idx].start_seconds < (cand.end_seconds + min_gap_seconds):
            next_idx += 1

        sub_score, sub_combo = search(next_idx, remaining - 1)
        if sub_score != -float("inf"):
            cand_total = cand.composite_score + sub_score
            if cand_total > best_score:
                best_score = cand_total
                best_combo = [cand] + sub_combo

        memo[key] = (best_score, best_combo)
        return memo[key]

    total_score, selected_combo = search(0, num_outputs)
    return selected_combo if total_score != -float("inf") else []


def generate_and_rank_segments(
    total_duration: float,
    output_specs: List[OutputSpecV1],
    audio_profile: Optional[AudioEnergyProfile] = None,
    scene_cuts: Optional[List[float]] = None,
    transcript_segments: Optional[List[Dict[str, Any]]] = None,
    asset_id: str = "primary",
    min_gap_seconds: float = 1.0,
) -> Tuple[List[SourceRangeV1], Optional[BlockerV1]]:
    """Select distinct, non-overlapping source ranges using media signals and duration policies."""
    num_outputs = len(output_specs)
    if num_outputs == 0:
        return [], None

    # Check minimum possible duration requirement
    min_required = 0.0
    for spec in output_specs:
        if spec.duration_policy == DurationPolicy.EXACT:
            min_required += spec.seconds
        elif spec.duration_policy == DurationPolicy.MAX:
            min_required += min(5.0, spec.seconds)
        else:  # TARGET
            min_required += max(1.0, spec.seconds - spec.tolerance_seconds)

    if total_duration < min_required:
        blocker = BlockerV1(
            code="INSUFFICIENT_SOURCE_DURATION",
            precise_reason=(
                f"Source duration ({total_duration:.2f}s) is shorter than required minimum "
                f"duration ({min_required:.2f}s) for {num_outputs} distinct clips. "
                "Repetition, looping, and freeze-frame filler are strictly prohibited."
            ),
            next_action="Provide a longer source asset or reduce requested clip duration.",
        )
        return [], blocker

    target_dur = output_specs[0].seconds if output_specs else 60.0
    step = 2.0 if total_duration <= 60 else (3.0 if total_duration <= 180 else 5.0)

    candidates = generate_candidate_windows(
        total_duration=total_duration,
        target_duration=target_dur,
        audio_profile=audio_profile,
        scene_cuts=scene_cuts,
        transcript_segments=transcript_segments,
        step_seconds=step,
    )

    # Use optimal non-overlapping interval combination search
    optimal_combo = _find_optimal_non_overlapping_combination(
        candidates,
        num_outputs=num_outputs,
        min_gap_seconds=min_gap_seconds,
    )

    if len(optimal_combo) == num_outputs:
        selected_ranges: List[SourceRangeV1] = []
        for cand in optimal_combo:
            reason = (
                f"[{cand.provenance}] Score: {cand.composite_score:.1f}/10. "
                f"Criteria: {cand.criteria_summary}. "
                f"Confidence: {cand.confidence}. Editorial: NOT_ASSESSED."
            )
            selected_ranges.append(SourceRangeV1(
                asset_id=asset_id,
                start_seconds=cand.start_seconds,
                end_seconds=cand.end_seconds,
                duration_seconds=cand.duration_seconds,
                editorial_reason=reason,
                relevance_score=cand.composite_score,
            ))
        selected_ranges.sort(key=lambda r: r.start_seconds)
        return selected_ranges, None

    # Fallback if step-based candidate search did not yield N distinct windows:
    # Partition timeline into N equitable zones and find best window per zone
    zone_len = total_duration / num_outputs
    selected_ranges = []
    for idx, spec in enumerate(output_specs):
        z_start = idx * zone_len
        z_end = min(total_duration, (idx + 1) * zone_len)
        available = z_end - z_start

        seg_len = min(spec.seconds, available)
        s = round(z_start + max(0.0, (available - seg_len) / 2.0), 2)
        e = round(s + seg_len, 2)
        dur = round(e - s, 2)

        if dur < 1.0:
            blocker = BlockerV1(
                code="INSUFFICIENT_COHERENT_FOOTAGE",
                precise_reason=f"Could not allocate sufficient coherent footage for clip {idx + 1}.",
                next_action="Provide longer source media.",
            )
            return [], blocker

        selected_ranges.append(SourceRangeV1(
            asset_id=asset_id,
            start_seconds=s,
            end_seconds=e,
            duration_seconds=dur,
            editorial_reason=(
                f"[HEURISTIC_TEMPORAL_FALLBACK] Zone {idx + 1} placement ({s:.1f}s-{e:.1f}s). "
                "Confidence: LOW. Editorial: NOT_ASSESSED."
            ),
            relevance_score=5.0,
        ))

    selected_ranges.sort(key=lambda r: r.start_seconds)
    return selected_ranges, None
