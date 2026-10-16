# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for native_motion_v1 schema validation, security sanitization, and attack rejection."""

import pytest
from pydantic import ValidationError

from backend.native_motion.schema import (
    Constraints,
    CreativeBrief,
    ElementSpec,
    ElementTransform,
    KeyframeSpec,
    KnowledgeRef,
    NativeMotionSpec,
    SceneSpec,
    TextConfig,
    TypographySpec,
    WordTimestampSpec,
)


def test_creative_brief_rejects_script_tag():
    with pytest.raises(ValidationError) as exc:
        CreativeBrief(topic="<script>alert('xss')</script>")
    assert "Unsafe executable pattern detected" in str(exc.value)


def test_creative_brief_rejects_eval_and_exec():
    with pytest.raises(ValidationError):
        CreativeBrief(topic="Valid Topic", raw_prompt="eval(process.exit())")

    with pytest.raises(ValidationError):
        CreativeBrief(topic="Valid Topic", intent="exec(sh)")


def test_typography_spec_font_fallback():
    # Valid safe font passes
    t1 = TypographySpec(font_family="Playfair Display, serif")
    assert "Playfair Display" in t1.font_family

    # Unsafe/unlicensed arbitrary font falls back to safe Inter stack
    t2 = TypographySpec(font_family="MaliciousCommercialFont, custom")
    assert t2.font_family == "Inter, sans-serif"


def test_color_sanitization_and_validation():
    # Valid colors pass
    t1 = TypographySpec(fill="#F8FAFC", stroke="rgba(15, 23, 42, 0.8)")
    assert t1.fill == "#F8FAFC"

    # Unsafe or invalid color string rejected
    with pytest.raises(ValidationError):
        TypographySpec(fill="javascript:alert(1)")


def test_word_timestamp_monotonicity_validation():
    # Valid timestamps pass
    w1 = WordTimestampSpec(word="Hello", start=0.0, end=0.5)
    assert w1.end >= w1.start

    # Negative end time before start rejected
    with pytest.raises(ValidationError):
        WordTimestampSpec(word="Reversed", start=1.5, end=0.8)


def test_scene_spec_rejects_negative_duration():
    with pytest.raises(ValidationError):
        SceneSpec(id="scene_01", start_time=0.0, duration=-1.5)


def test_native_motion_spec_auto_dimension_sync():
    brief = CreativeBrief(topic="Auto Aspect", intent="data", tone="tech")
    scene = SceneSpec(id="s1", start_time=0.0, duration=3.0)

    # 9:16 auto-corrects to 1080x1920
    spec_916 = NativeMotionSpec(
        id="nm_test_1",
        title="Test 9:16",
        brief=brief,
        constraints=Constraints(aspect_ratio="9:16"),
        duration_seconds=3.0,
        scenes=[scene],
    )
    assert (spec_916.width, spec_916.height) == (1080, 1920)

    # 16:9 auto-corrects to 1920x1080
    spec_169 = NativeMotionSpec(
        id="nm_test_2",
        title="Test 16:9",
        brief=brief,
        constraints=Constraints(aspect_ratio="16:9"),
        duration_seconds=3.0,
        scenes=[scene],
    )
    assert (spec_169.width, spec_169.height) == (1920, 1080)
