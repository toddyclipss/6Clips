# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for Six Benchmark Video Briefs (B1-B6) & Structural Topology (Wave 21 Agent 4)."""

import pytest
from backend.native_motion.generator import NativeMotionGenerator


def test_benchmark_b1_topological_diversity():
    """Verify B1 (25s, 9:16) has two substantially different visual approaches with distinct topologies."""
    spec_a = NativeMotionGenerator.build_benchmark_b1(approach="A", seed=101)
    spec_b = NativeMotionGenerator.build_benchmark_b1(approach="B", seed=102)

    assert spec_a.duration_seconds == 25.0
    assert spec_b.duration_seconds == 25.0
    assert (spec_a.width, spec_a.height) == (1080, 1920)
    assert (spec_b.width, spec_b.height) == (1080, 1920)

    # Topology comparison
    topo_a = [e.type for s in spec_a.scenes for e in s.elements]
    topo_b = [e.type for s in spec_b.scenes for e in s.elements]
    assert topo_a != topo_b, "Approach A and Approach B must be topologically distinct!"

    # Approach A has card shapes and text callouts; Approach B has radial particles and donut chart
    assert any(e.type == "shape" for s in spec_a.scenes for e in s.elements)
    assert any(e.type == "data_chart" and e.chart_config.chart_type == "donut" for s in spec_b.scenes for e in s.elements)


def test_benchmark_b2_topological_diversity():
    """Verify B2 (18s, 9:16) has two substantially different visual approaches with distinct topologies."""
    spec_a = NativeMotionGenerator.build_benchmark_b2(approach="A", seed=201)
    spec_b = NativeMotionGenerator.build_benchmark_b2(approach="B", seed=202)

    assert spec_a.duration_seconds == 18.0
    assert spec_b.duration_seconds == 18.0
    assert (spec_a.width, spec_a.height) == (1080, 1920)

    topo_a = [e.type for s in spec_a.scenes for e in s.elements]
    topo_b = [e.type for s in spec_b.scenes for e in s.elements]
    assert topo_a != topo_b, "B2 Approach A and B must have distinct topologies!"

    # Approach A has numeric counter and bar chart; Approach B has donut and kinetic text
    assert any(e.chart_config and e.chart_config.chart_type == "counter" for s in spec_a.scenes for e in s.elements if e.type == "data_chart")
    assert any(e.chart_config and e.chart_config.chart_type == "donut" for s in spec_b.scenes for e in s.elements if e.type == "data_chart")


def test_benchmark_b3_speech_and_ducking_structure():
    """Verify B3 (30s, 9:16) structure has speech captions and audio track with ducking."""
    from backend.native_motion.schema import WordTimestampSpec

    words = [
        WordTimestampSpec(word="Organic", start=1.0, end=1.6),
        WordTimestampSpec(word="growth", start=1.6, end=2.2),
        WordTimestampSpec(word="compounds.", start=2.2, end=3.0),
    ]
    spec = NativeMotionGenerator.build_benchmark_b3_synthetic(audio_path="tools/wave21_a4/speech_demo.wav", words=words, seed=303)
    assert spec.duration_seconds == 30.0
    assert (spec.width, spec.height) == (1080, 1920)
    assert len(spec.audio_tracks) == 1
    assert spec.audio_tracks[0].audio_type == "synthetic_test_speech"
    assert spec.audio_tracks[0].duck_during_speech is True

    # Captions element present in scene 2
    captions_elem = next(e for s in spec.scenes for e in s.elements if e.type == "captions")
    assert captions_elem.captions_config is not None


def test_benchmark_b4_transformer_attention_diagram():
    """Verify B4 (45s, 16:9) multi-stage transformer attention infographic."""
    spec = NativeMotionGenerator.build_benchmark_b4(seed=404)
    assert spec.duration_seconds == 45.0
    assert (spec.width, spec.height) == (1920, 1080)
    assert len(spec.scenes) == 4

    # Every stage contains diagram_attention chart type
    for s in spec.scenes:
        diagram_elem = next((e for e in s.elements if e.type == "data_chart" and e.chart_config.chart_type == "diagram_attention"), None)
        assert diagram_elem is not None, f"Stage {s.id} missing diagram_attention component"


def test_benchmark_b5_presentation_reframe():
    """Verify B5 (40s, 9:16) presentation reframe highlight with video layer and crop rect."""
    spec = NativeMotionGenerator.build_benchmark_b5(seed=505)
    assert spec.duration_seconds == 40.0
    assert (spec.width, spec.height) == (1080, 1920)
    assert len(spec.scenes) == 4

    for s in spec.scenes:
        v_elem = next((e for e in s.elements if e.type == "video_layer"), None)
        assert v_elem is not None
        assert v_elem.video_config.crop_rect is not None


def test_benchmark_b6_cinematic_stinger():
    """Verify B6 (10s, 16:9) minimalist cinematic branded stinger."""
    spec = NativeMotionGenerator.build_benchmark_b6(seed=606)
    assert spec.duration_seconds == 10.0
    assert (spec.width, spec.height) == (1920, 1080)
    assert len(spec.scenes) == 2
    assert spec.scenes[0].transition.type == "crossfade"
