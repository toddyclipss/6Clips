# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for Native Creative Grammar & Versatile Primitives (Wave 21 Agent 4)."""

import pytest
from backend.native_motion.compiler import NativeMotionCompiler
from backend.native_motion.generator import NativeMotionGenerator
from backend.native_motion.schema import (
    Constraints,
    CreativeBrief,
    DataChartConfig,
    DataPoint,
    ElementSpec,
    ElementTransform,
    NativeMotionSpec,
    SceneSpec,
    TextConfig,
    TypographySpec,
    VideoLayerConfig,
)


def test_text_per_word_and_typewriter_grammar():
    """Verify text primitive supports typewriter, word_pop, highlight words, and attribution."""
    cfg = TextConfig(
        content="Global Renewable Energy Expansion Added 310 GWh",
        animation_type="word_pop",
        stagger_delay=0.06,
        highlight_words=["310", "GWh"],
        highlight_color="#38BDF8",
        source_attribution="IEA Clean Energy Grid Report 2026",
    )
    assert cfg.animation_type == "word_pop"
    assert "310" in cfg.highlight_words
    assert cfg.source_attribution is not None

    scene = SceneSpec(
        id="scene_text_test",
        start_time=0.0,
        duration=5.0,
        elements=[
            ElementSpec(
                id="text_1",
                type="text",
                start_time=0.0,
                duration=5.0,
                transform=ElementTransform(x=540, y=960, width=900, height=200),
                text_config=cfg,
            )
        ],
    )
    spec = NativeMotionSpec(
        id="nm_test_text",
        title="Text Grammar Test",
        brief=CreativeBrief(topic="Renewable Energy", intent="education", tone="tech"),
        duration_seconds=5.0,
        scenes=[scene],
    )
    html = NativeMotionCompiler.compile_to_html(spec)
    assert "word_pop" in html
    assert "SOURCE:" in html
    assert "highlight_words" in html or "isHighlight" in html


def test_data_chart_counter_and_attention_diagram():
    """Verify data chart primitive supports numeric counters and transformer attention diagrams."""
    counter_cfg = DataChartConfig(
        chart_type="counter",
        title="10X ACCELERATION",
        counter_prefix="+",
        counter_suffix="x",
        counter_start=1.0,
        counter_end=10.4,
        counter_decimals=1,
    )
    assert counter_cfg.chart_type == "counter"
    assert counter_cfg.counter_end == 10.4

    attention_cfg = DataChartConfig(
        chart_type="diagram_attention",
        title="MULTI-HEAD ATTENTION PROJECTION",
        attention_heads=4,
        attention_matrix=[
            [0.8, 0.1, 0.05, 0.05],
            [0.1, 0.7, 0.15, 0.05],
            [0.05, 0.15, 0.7, 0.1],
            [0.05, 0.05, 0.1, 0.8],
        ],
    )
    assert attention_cfg.chart_type == "diagram_attention"
    assert len(attention_cfg.attention_matrix) == 4

    scene = SceneSpec(
        id="scene_chart_test",
        start_time=0.0,
        duration=5.0,
        elements=[
            ElementSpec(
                id="chart_1",
                type="data_chart",
                start_time=0.0,
                duration=5.0,
                chart_config=attention_cfg,
            )
        ],
    )
    spec = NativeMotionSpec(
        id="nm_test_chart",
        title="Chart Grammar Test",
        brief=CreativeBrief(topic="Attention Mechanism", intent="education", tone="tech"),
        duration_seconds=5.0,
        scenes=[scene],
    )
    html = NativeMotionCompiler.compile_to_html(spec)
    assert "renderAttentionDiagram" in html
    assert "TRANSFORMER ATTENTION MECHANISM" in html


def test_video_layer_reframe_primitive():
    """Verify video layer primitive supports reframe crop box and tracking viewport."""
    v_cfg = VideoLayerConfig(
        source_path="media/test_keynote.mp4",
        crop_rect={"x": 0.25, "y": 0.05, "w": 0.56, "h": 0.90},
        reframe_mode="manual_crop",
        volume=1.0,
    )
    assert v_cfg.reframe_mode == "manual_crop"
    assert v_cfg.crop_rect["w"] == 0.56

    elem = ElementSpec(
        id="v_layer_1",
        type="video_layer",
        start_time=0.0,
        duration=6.0,
        transform=ElementTransform(x=540, y=960, width=900, height=800),
        video_config=v_cfg,
    )
    assert elem.type == "video_layer"
    assert elem.video_config.source_path == "media/test_keynote.mp4"
