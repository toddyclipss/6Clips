# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for Automated Quality Control & Adversarial Self-Repair (Wave 21 Agent 4)."""

import pytest
from backend.native_motion.schema import (
    CreativeBrief,
    ElementSpec,
    ElementTransform,
    NativeMotionSpec,
    SceneSpec,
    TextConfig,
    TypographySpec,
    WordTimestampSpec,
    CaptionsConfig,
)
from backend.native_motion.self_repair import NativeSelfRepair, RepairBudgetExhaustedError


def test_self_repair_recovers_multiscene_duration_misalignment():
    """Verify self-repair synchronizes root duration to match scene duration sum."""
    s1 = SceneSpec(id="s1", start_time=0.0, duration=10.0, background_color="#0A0F1D")
    s2 = SceneSpec(id="s2", start_time=10.0, duration=15.0, background_color="#0A0F1D")
    # Intentional misalignment: root duration says 20.0 but scenes sum to 25.0
    spec = NativeMotionSpec(
        id="nm_test_dur_sync",
        title="Duration Sync Test",
        brief=CreativeBrief(topic="Duration Test", intent="explain", tone="tech"),
        duration_seconds=20.0,
        scenes=[s1, s2],
    )
    # Manually desync root duration to test repair
    spec.duration_seconds = 20.0

    repaired = NativeSelfRepair.audit_and_repair(spec)
    assert abs(repaired.duration_seconds - 25.0) < 0.001
    assert any(log.issue_type == "timing_sync" for log in repaired.repair_log)


def test_self_repair_bounded_retries_fail_closed():
    """Verify unresolvable flaws fail closed with RepairBudgetExhaustedError."""
    # Unresolvable flaw: impossible negative start time or corrupted word timestamps
    corrupted_words = [
        WordTimestampSpec(word="One", start=0.0, end=5.0),
        WordTimestampSpec(word="Two", start=1.0, end=2.0),
    ]
    scene = SceneSpec(
        id="s_corrupt",
        start_time=0.0,
        duration=5.0,
        background_color="#0A0F1D",
        elements=[
            ElementSpec(
                id="c_corrupt",
                type="captions",
                start_time=0.0,
                duration=5.0,
                captions_config=CaptionsConfig(words=corrupted_words),
            )
        ],
    )
    spec = NativeMotionSpec(
        id="nm_test_budget",
        title="Budget Test",
        brief=CreativeBrief(topic="Corrupt Test", intent="explain", tone="tech"),
        duration_seconds=5.0,
        scenes=[scene],
    )
    # With max_retries=0, cannot resolve and fails closed
    with pytest.raises(RepairBudgetExhaustedError):
        NativeSelfRepair.audit_and_repair(spec, max_retries=0)
