# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for Multi-scene Compositions and True Frame-Motion Transitions (Wave 21 Agent 4)."""

import pytest
from backend.native_motion.compiler import NativeMotionCompiler
from backend.native_motion.generator import NativeMotionGenerator
from backend.native_motion.schema import (
    Constraints,
    CreativeBrief,
    NativeMotionSpec,
    SceneSpec,
    SceneTransitionSpec,
    ShapeConfig,
    ElementSpec,
    ElementTransform,
)


def test_multiscene_duration_sum_equals_requested_duration():
    """Verify composition sum equals requested duration with zero drift."""
    for requested_dur in [10.0, 18.0, 25.0, 30.0, 40.0, 45.0]:
        brief = CreativeBrief(topic=f"Testing {requested_dur}s duration", intent="explain", tone="tech")
        spec = NativeMotionGenerator.generate(
            brief=brief,
            constraints=Constraints(aspect_ratio="9:16", max_duration_seconds=requested_dur),
            seed=42,
        )
        assert len(spec.scenes) >= 2, f"Expected multi-scene for {requested_dur}s"
        scene_sum = sum(s.duration for s in spec.scenes)
        assert abs(scene_sum - requested_dur) < 0.002, f"Drift detected: {scene_sum} != {requested_dur}"
        assert abs(spec.duration_seconds - requested_dur) < 0.002


def test_all_scene_transitions_present_in_compiled_html():
    """Verify that all transition types are cleanly compiled into the offline HTML player."""
    transitions = [
        "crossfade",
        "slide_left",
        "slide_right",
        "slide_up",
        "slide_down",
        "wipe_horizontal",
        "wipe_radial",
        "zoom_in",
        "zoom_out",
    ]
    brief = CreativeBrief(topic="Transition Suite", intent="explain", tone="tech")
    scenes = []
    t_cur = 0.0
    for idx, t_type in enumerate(transitions):
        s = SceneSpec(
            id=f"scene_trans_{idx}",
            start_time=t_cur,
            duration=3.0,
            background_color="#0A0F1D",
            transition=SceneTransitionSpec(type=t_type, duration=0.5),
            elements=[
                ElementSpec(
                    id=f"elem_{idx}",
                    type="shape",
                    start_time=0.0,
                    duration=3.0,
                    transform=ElementTransform(x=100, y=100, width=200, height=200),
                    shape_config=ShapeConfig(fill="#38BDF8"),
                )
            ],
        )
        scenes.append(s)
        t_cur += 3.0

    spec = NativeMotionSpec(
        id="nm_test_transitions",
        title="Transitions Test",
        brief=brief,
        width=1080,
        height=1920,
        fps=30,
        duration_seconds=t_cur,
        scenes=scenes,
    )

    html = NativeMotionCompiler.compile_to_html(spec)
    assert "renderTransition" in html
    assert "crossfade" in html
    assert "slide_left" in html
    assert "wipe_radial" in html
    assert "zoom_in" in html
    assert "window.__seekTime" in html
    assert "window.__seekFrame" in html
