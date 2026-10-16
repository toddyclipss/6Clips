# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for NativeSelfRepair: automated technical self-repair, contrast, overlap, and bounded retries."""

import pytest
from backend.native_motion.schema import (
    Constraints,
    CreativeBrief,
    ElementSpec,
    ElementTransform,
    NativeMotionSpec,
    SceneSpec,
    TextConfig,
    TypographySpec,
    WordTimestampSpec,
)
from backend.native_motion.self_repair import (
    NativeSelfRepair,
    RepairBudgetExhaustedError,
)


def test_self_repair_recovers_word_timestamp_overlap():
    words = [
        WordTimestampSpec(word="Word1", start=0.0, end=1.5),  # Overlaps Word2!
        WordTimestampSpec(word="Word2", start=1.0, end=2.0),
    ]
    brief = CreativeBrief(topic="Word Sync", intent="explain", tone="punchy")
    scene = SceneSpec(
        id="s1",
        start_time=0.0,
        duration=3.0,
        elements=[
            ElementSpec(
                id="captions_1",
                type="captions",
                start_time=0.0,
                duration=3.0,
                captions_config={"words": words},
            )
        ],
    )
    spec = NativeMotionSpec(
        id="nm_sync_test",
        title="Sync Test",
        brief=brief,
        duration_seconds=3.0,
        scenes=[scene],
    )

    repaired_spec = NativeSelfRepair.audit_and_repair(spec)

    repaired_words = repaired_spec.scenes[0].elements[0].captions_config.words
    assert repaired_words[0].end == repaired_words[1].start  # Clamped to 1.0s
    assert len(repaired_spec.repair_log) >= 1
    assert repaired_spec.repair_log[0].issue_type == "timing_sync"


def test_self_repair_recovers_safe_zone_overflow():
    brief = CreativeBrief(topic="Safe Zone Test", intent="data", tone="tech")
    scene = SceneSpec(
        id="s1",
        start_time=0.0,
        duration=3.0,
        elements=[
            ElementSpec(
                id="overflow_text",
                type="text",
                start_time=0.0,
                duration=3.0,
                transform=ElementTransform(x=10, y=1900, width=400, height=100, anchor_x=0.5, anchor_y=0.5),
                text_config=TextConfig(content="Exceeds bottom safe margin"),
            )
        ],
    )
    spec = NativeMotionSpec(
        id="nm_overflow_test",
        title="Overflow Test",
        brief=brief,
        duration_seconds=3.0,
        scenes=[scene],
    )

    repaired_spec = NativeSelfRepair.audit_and_repair(spec)
    # Bottom margin is 0.18 -> max_y = 1920 * 0.82 = 1574.4
    elem_prop = repaired_spec.scenes[0].elements[0].transform
    assert elem_prop.y + (elem_prop.height * (1.0 - elem_prop.anchor_y)) <= (1.0 - spec.safe_zones.bottom) * spec.height
    assert any(log.issue_type == "safe_zone_overflow" for log in repaired_spec.repair_log)


def test_self_repair_recovers_wcag_contrast_violation():
    brief = CreativeBrief(topic="Contrast Test", intent="editorial", tone="minimal")
    scene = SceneSpec(
        id="s1",
        start_time=0.0,
        duration=3.0,
        background_color="#121212",  # Near black
        elements=[
            ElementSpec(
                id="low_contrast_text",
                type="text",
                start_time=0.0,
                duration=3.0,
                text_config=TextConfig(
                    content="Invisible Dark Text",
                    typography=TypographySpec(fill="#1A1A1A"),  # Almost identical to background!
                ),
            )
        ],
    )
    spec = NativeMotionSpec(
        id="nm_contrast_test",
        title="Contrast Test",
        brief=brief,
        duration_seconds=3.0,
        scenes=[scene],
    )

    repaired_spec = NativeSelfRepair.audit_and_repair(spec)
    new_fill = repaired_spec.scenes[0].elements[0].text_config.typography.fill
    assert new_fill == "#FFFFFF"  # Automatically repaired to high-contrast white
    assert any(log.issue_type == "wcag_contrast" for log in repaired_spec.repair_log)
