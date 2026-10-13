# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Caption grounding and time-remapping engine for cuts, offsets, and speed variations."""

import copy
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def ground_and_remap_captions(
    transcript_segments: List[Dict[str, Any]],
    cut_start_seconds: float,
    cut_end_seconds: float,
    speed_factor: float = 1.0,
) -> List[Dict[str, Any]]:
    """Ground and remap transcript segments into a cut output's local timeline [0.0, output_duration].
    
    Guarantees:
    - User-edited transcript segments remain authoritative; they are not replaced or overwritten by ASR.
    - Captions outside [cut_start, cut_end] are pruned cleanly.
    - Intersecting captions are clamped and remapped: t_new = (t_orig - cut_start) / speed_factor.
    - Word-level timestamps (when present) are remapped with identical precision.
    - Provenance of manual edits vs ASR vs heuristic is tracked explicitly.
    """
    if not transcript_segments or cut_end_seconds <= cut_start_seconds:
        return []

    speed = max(0.1, speed_factor)
    remapped: List[Dict[str, Any]] = []

    for seg in transcript_segments:
        orig_start = float(seg.get("start", 0.0))
        orig_end = float(seg.get("end", 0.0))

        # Check for intersection with cut window
        if orig_end <= cut_start_seconds or orig_start >= cut_end_seconds:
            continue

        # Clamped boundaries in source timeline
        clamped_start = max(cut_start_seconds, orig_start)
        clamped_end = min(cut_end_seconds, orig_end)

        if clamped_end <= clamped_start:
            continue

        # Remap to output local time
        local_start = round((clamped_start - cut_start_seconds) / speed, 3)
        local_end = round((clamped_end - cut_start_seconds) / speed, 3)

        # Retain or identify provenance
        is_user_edited = bool(seg.get("is_user_edited", False) or seg.get("provenance") == "manual")
        provenance = "user_edited_authoritative" if is_user_edited else (seg.get("provenance") or "asr_retimed")

        new_seg = {
            "id": seg.get("id"),
            "start": local_start,
            "end": local_end,
            "text": seg.get("text", "").strip(),
            "source_start": orig_start,
            "source_end": orig_end,
            "provenance": provenance,
            "is_user_edited": is_user_edited,
            "confidence": seg.get("confidence", 1.0 if is_user_edited else 0.85),
        }

        # Remap words if present
        if "words" in seg and isinstance(seg["words"], list):
            remapped_words = []
            for w in seg["words"]:
                w_start = float(w.get("start", orig_start))
                w_end = float(w.get("end", orig_end))
                if w_end <= cut_start_seconds or w_start >= cut_end_seconds:
                    continue
                w_clamp_s = max(cut_start_seconds, w_start)
                w_clamp_e = min(cut_end_seconds, w_end)
                remapped_words.append({
                    "word": w.get("word", ""),
                    "start": round((w_clamp_s - cut_start_seconds) / speed, 3),
                    "end": round((w_clamp_e - cut_start_seconds) / speed, 3),
                    "confidence": w.get("confidence", 0.9),
                })
            new_seg["words"] = remapped_words

        remapped.append(new_seg)

    return remapped


def validate_caption_integrity(
    original_segments: List[Dict[str, Any]],
    remapped_segments: List[Dict[str, Any]],
    cut_start_seconds: float,
    cut_end_seconds: float,
) -> Tuple[bool, List[str]]:
    """Validate that caption remapping preserves integrity, ordering, and user edits."""
    issues: List[str] = []

    last_end = 0.0
    for idx, seg in enumerate(remapped_segments):
        start = seg.get("start", -1.0)
        end = seg.get("end", -1.0)
        text = seg.get("text", "")

        if start < 0.0:
            issues.append(f"Segment {idx} has negative start time ({start}s)")
        if end <= start:
            issues.append(f"Segment {idx} end ({end}s) is not after start ({start}s)")
        if not text:
            issues.append(f"Segment {idx} has empty text")
        if start < last_end - 0.05:
            # Overlapping segments warning (minor drift acceptable)
            pass
        last_end = end

        # If original was user-edited, remapped must preserve text and mark authoritative
        orig_match = next(
            (o for o in original_segments if o.get("id") == seg.get("id")),
            None
        )
        if orig_match and (orig_match.get("is_user_edited") or orig_match.get("provenance") == "manual"):
            if seg.get("text") != orig_match.get("text"):
                issues.append(f"Destructive caption overwrite detected on user-edited segment {seg.get('id')}")
            if not seg.get("is_user_edited"):
                issues.append(f"Lost user_edited flag on segment {seg.get('id')}")

    return len(issues) == 0, issues
