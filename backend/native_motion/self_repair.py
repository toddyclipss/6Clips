# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Automatic Technical Self-Repair with Bounded Retries for Native Motion.

Validates, sanitizes, and repairs WCAG contrast violations, bounding box overlaps,
safe-zone overflow, and word timestamp desynchronization. Preserves provenance
and logs all patches with fail-closed bounds.
"""

from __future__ import annotations

import datetime
import logging
import math
import re
from typing import Any, Dict, List, Optional, Tuple

from backend.core.exceptions import ViralMintError
from backend.native_motion.schema import (
    ElementSpec,
    NativeMotionSpec,
    RepairLogEntry,
    WordTimestampSpec,
)

logger = logging.getLogger(__name__)


class RepairBudgetExhaustedError(ViralMintError):
    """Raised when self-repair cannot resolve all flaws within bounded retries."""
    def __init__(self, message: str = "Self-repair budget exhausted (3 retries). Fails closed."):
        super().__init__(message)


class NativeSelfRepair:
    """Automated repair subsystem for native motion specifications."""

    MAX_RETRIES = 3

    @classmethod
    def audit_and_repair(
        cls,
        spec: NativeMotionSpec,
        max_retries: int = MAX_RETRIES,
    ) -> NativeMotionSpec:
        """Inspect and iteratively patch spec flaws up to max_retries."""
        for retry_idx in range(1, max_retries + 1):
            flaws_found = False

            # 1. Word timestamp monotonicity & overlap check
            flaws_found |= cls._repair_word_timestamps(spec, retry_idx)

            # 2. Safe zone margin boundary overflow check
            flaws_found |= cls._repair_safe_zone_overflow(spec, retry_idx)

            # 3. Text overlap collision check
            flaws_found |= cls._repair_text_overlaps(spec, retry_idx)

            # 4. WCAG contrast check (text vs background)
            flaws_found |= cls._repair_contrast(spec, retry_idx)

            # 5. Multi-scene duration synchronization check
            flaws_found |= cls._repair_duration_and_scenes(spec, retry_idx)

            if not flaws_found:
                # All checks passed cleanly
                return spec

        # If after max_retries flaws are still unresolved, fail closed
        if cls.has_critical_flaws(spec):
            raise RepairBudgetExhaustedError(
                f"Spec '{spec.id}' has unresolvable flaws after {max_retries} self-repair retries."
            )

        return spec

    @classmethod
    def has_critical_flaws(cls, spec: NativeMotionSpec) -> bool:
        """Evaluate if any critical layout or timing violations remain."""
        for scene in spec.scenes:
            for elem in scene.elements:
                if elem.type == "captions" and elem.captions_config:
                    words = elem.captions_config.words
                    for i in range(len(words) - 1):
                        if words[i].end > words[i + 1].start + 0.05:
                            return True
        return False

    # ------------------------------------------------------------------------
    # Specific Repair Algorithms
    # ------------------------------------------------------------------------

    @classmethod
    def _repair_word_timestamps(cls, spec: NativeMotionSpec, retry_idx: int) -> bool:
        repaired = False
        now_str = datetime.datetime.utcnow().isoformat()

        for scene in spec.scenes:
            for elem in scene.elements:
                if elem.type == "captions" and elem.captions_config:
                    words = elem.captions_config.words
                    for i in range(len(words) - 1):
                        curr_w = words[i]
                        next_w = words[i + 1]
                        if curr_w.end > next_w.start:
                            # Clamp current word end to next word start
                            old_end = curr_w.end
                            curr_w.end = next_w.start
                            spec.repair_log.append(
                                RepairLogEntry(
                                    timestamp=now_str,
                                    issue_type="timing_sync",
                                    details=f"Word '{curr_w.word}' end ({old_end}s) overlapped with '{next_w.word}' start ({next_w.start}s)",
                                    patch_applied={"word": curr_w.word, "old_end": old_end, "new_end": curr_w.end},
                                    retry_index=retry_idx,
                                    resolved=True,
                                )
                            )
                            repaired = True
        return repaired

    @classmethod
    def _repair_safe_zone_overflow(cls, spec: NativeMotionSpec, retry_idx: int) -> bool:
        repaired = False
        now_str = datetime.datetime.utcnow().isoformat()
        w = spec.width
        h = spec.height
        sz = spec.safe_zones

        min_x = sz.left * w
        max_x = (1.0 - sz.right) * w
        min_y = sz.top * h
        max_y = (1.0 - sz.bottom) * h

        for scene in spec.scenes:
            for elem in scene.elements:
                if elem.type in ("text", "captions"):
                    props = elem.transform
                    left_edge = props.x - (props.width * props.anchor_x)
                    right_edge = props.x + (props.width * (1.0 - props.anchor_x))
                    top_edge = props.y - (props.height * props.anchor_y)
                    bottom_edge = props.y + (props.height * (1.0 - props.anchor_y))

                    patch = {}
                    if left_edge < min_x:
                        shift = min_x - left_edge
                        props.x += shift
                        patch["shift_x"] = shift
                    elif right_edge > max_x:
                        shift = right_edge - max_x
                        props.x -= shift
                        patch["shift_x"] = -shift

                    if bottom_edge > max_y:
                        shift = bottom_edge - max_y
                        props.y -= shift
                        patch["shift_y"] = -shift
                    elif top_edge < min_y:
                        shift = min_y - top_edge
                        props.y += shift
                        patch["shift_y"] = shift

                    if patch:
                        spec.repair_log.append(
                            RepairLogEntry(
                                timestamp=now_str,
                                issue_type="safe_zone_overflow",
                                details=f"Element '{elem.id}' exceeded safe zones (boundaries: x=[{min_x}, {max_x}], y=[{min_y}, {max_y}])",
                                patch_applied=patch,
                                retry_index=retry_idx,
                                resolved=True,
                            )
                        )
                        repaired = True
        return repaired

    @classmethod
    def _repair_text_overlaps(cls, spec: NativeMotionSpec, retry_idx: int) -> bool:
        repaired = False
        now_str = datetime.datetime.utcnow().isoformat()

        for scene in spec.scenes:
            text_elems = [e for e in scene.elements if e.type == "text" and e.text_config]
            for i in range(len(text_elems)):
                for j in range(i + 1, len(text_elems)):
                    e1 = text_elems[i]
                    e2 = text_elems[j]
                    # Check temporal overlap
                    e1_end = e1.start_time + e1.duration
                    e2_end = e2.start_time + e2.duration
                    time_overlap = max(e1.start_time, e2.start_time) < min(e1_end, e2_end)
                    if not time_overlap:
                        continue

                    # Check bounding box collision
                    t1 = e1.transform
                    t2 = e2.transform
                    b1_top = t1.y - (t1.height * t1.anchor_y)
                    b1_bottom = t1.y + (t1.height * (1.0 - t1.anchor_y))
                    b2_top = t2.y - (t2.height * t2.anchor_y)
                    b2_bottom = t2.y + (t2.height * (1.0 - t2.anchor_y))

                    # If vertical overlap occurs
                    if max(b1_top, b2_top) < min(b1_bottom, b2_bottom):
                        # Shift e2 below e1 with padding
                        gap = 24.0
                        new_y = b1_bottom + (t2.height * t2.anchor_y) + gap
                        shift = new_y - t2.y
                        t2.y = new_y

                        spec.repair_log.append(
                            RepairLogEntry(
                                timestamp=now_str,
                                issue_type="text_overlap",
                                details=f"Text elements '{e1.id}' and '{e2.id}' collided vertically.",
                                patch_applied={"shifted_element": e2.id, "y_shift": shift},
                                retry_index=retry_idx,
                                resolved=True,
                            )
                        )
                        repaired = True
        return repaired

    @classmethod
    def _repair_contrast(cls, spec: NativeMotionSpec, retry_idx: int) -> bool:
        repaired = False
        now_str = datetime.datetime.utcnow().isoformat()

        # Parse approximate luminance for hex colors
        def hex_luminance(c: str) -> float:
            c = c.lstrip("#")
            if len(c) == 3:
                c = "".join([x * 2 for x in c])
            if len(c) >= 6:
                r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
                return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
            return 0.5

        for scene in spec.scenes:
            bg_lum = hex_luminance(scene.background_color)
            for elem in scene.elements:
                if elem.type == "text" and elem.text_config:
                    fill = elem.text_config.typography.fill
                    if fill.startswith("#"):
                        text_lum = hex_luminance(fill)
                        contrast = (max(text_lum, bg_lum) + 0.05) / (min(text_lum, bg_lum) + 0.05)
                        if contrast < 4.5:  # WCAG AA threshold
                            # Low contrast: enforce white text on dark background or dark on light
                            new_fill = "#FFFFFF" if bg_lum < 0.5 else "#000000"
                            elem.text_config.typography.fill = new_fill
                            spec.repair_log.append(
                                RepairLogEntry(
                                    timestamp=now_str,
                                    issue_type="wcag_contrast",
                                    details=f"Element '{elem.id}' contrast ratio was {round(contrast, 2)}:1 (< 4.5:1).",
                                    patch_applied={"old_fill": fill, "new_fill": new_fill},
                                    retry_index=retry_idx,
                                    resolved=True,
                                )
                            )
                            repaired = True

        return repaired

    @classmethod
    def _repair_duration_and_scenes(cls, spec: NativeMotionSpec, retry_idx: int) -> bool:
        repaired = False
        now_str = datetime.datetime.utcnow().isoformat()

        if not spec.scenes:
            return False

        # Ensure scene start times are monotonic and aligned
        cur_t = 0.0
        for i, s in enumerate(spec.scenes):
            if abs(s.start_time - cur_t) > 0.001:
                old_st = s.start_time
                s.start_time = round(cur_t, 3)
                spec.repair_log.append(
                    RepairLogEntry(
                        timestamp=now_str,
                        issue_type="timing_sync",
                        details=f"Scene '{s.id}' start time shifted from {old_st}s to {s.start_time}s to preserve timeline continuity.",
                        patch_applied={"scene_id": s.id, "old_start": old_st, "new_start": s.start_time},
                        retry_index=retry_idx,
                        resolved=True,
                    )
                )
                repaired = True
            cur_t += s.duration

        total_scenes_dur = round(sum(s.duration for s in spec.scenes), 3)
        if abs(spec.duration_seconds - total_scenes_dur) > 0.001:
            old_dur = spec.duration_seconds
            spec.duration_seconds = total_scenes_dur
            spec.repair_log.append(
                RepairLogEntry(
                    timestamp=now_str,
                    issue_type="timing_sync",
                    details=f"Root duration_seconds synchronized from {old_dur}s to {total_scenes_dur}s matching scene duration sum.",
                    patch_applied={"old_duration": old_dur, "new_duration": total_scenes_dur},
                    retry_index=retry_idx,
                    resolved=True,
                )
            )
            repaired = True

        return repaired
