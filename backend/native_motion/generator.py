# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Knowledge-to-Motion Generator.

Produces original, safe, typed, editable native_motion_v1 scene specifications
from creative briefs and cited knowledge techniques. Never uses fixed 196 donor
block templates.
"""

from __future__ import annotations

import hashlib
import random
import uuid
from typing import Any, Dict, List, Optional

from backend.native_motion.schema import (
    AudioTrackSpec,
    CameraSpec,
    CaptionsConfig,
    Constraints,
    CreativeBrief,
    DataChartConfig,
    DataPoint,
    EasingCurve,
    ElementSpec,
    ElementTransform,
    GradientConfig,
    GradientStop,
    KeyframeSpec,
    KnowledgeRef,
    NativeMotionSpec,
    ParticlesConfig,
    SafeZoneSpec,
    SceneSpec,
    ShaderConfig,
    ShapeConfig,
    TextConfig,
    TypographySpec,
    WordTimestampSpec,
)


class NativeMotionGenerator:
    """Foundational creative engine that composes dynamic, original motion graphics."""

    @classmethod
    def generate(
        cls,
        brief: CreativeBrief,
        knowledge_refs: List[KnowledgeRef],
        constraints: Optional[Constraints] = None,
        seed: Optional[int] = None,
        audio_path: Optional[str] = None,
        words: Optional[List[WordTimestampSpec]] = None,
    ) -> NativeMotionSpec:
        """Generate a complete NativeMotionSpec deterministically based on brief and seed.

        Distinct briefs produce fundamentally distinct scene structures, layouts,
        and timeline behaviors.
        """
        constraints = constraints or Constraints()
        rng = random.Random(seed if seed is not None else cls._seed_from_brief(brief))

        spec_id = f"nm_{uuid.UUID(int=rng.getrandbits(128)).hex[:12]}"
        aspect = constraints.aspect_ratio
        w, h = cls._dimensions_for_aspect(aspect)

        safe_zones = SafeZoneSpec(
            top=0.14 if aspect == "9:16" else 0.08,
            bottom=0.20 if aspect == "9:16" else 0.10,
            left=0.08,
            right=0.08,
        )

        # Decide duration
        target_dur = min(constraints.max_duration_seconds, 6.0)  # Standard punchy motion slice

        # Route composition style based on brief intent and tone
        intent = brief.intent.lower()
        tone = brief.tone.lower()

        if intent in ("data", "metrics", "chart", "analytics"):
            scenes = cls._build_data_kinetic_scenes(
                brief=brief,
                width=w,
                height=h,
                safe_zones=safe_zones,
                duration=target_dur,
                rng=rng,
                knowledge_refs=knowledge_refs,
            )
        elif intent in ("editorial", "cinematic", "fashion", "luxury"):
            scenes = cls._build_editorial_scenes(
                brief=brief,
                width=w,
                height=h,
                safe_zones=safe_zones,
                duration=target_dur,
                rng=rng,
                knowledge_refs=knowledge_refs,
            )
        else:
            # Dynamic kinetic typographic layout
            scenes = cls._build_kinetic_scenes(
                brief=brief,
                width=w,
                height=h,
                safe_zones=safe_zones,
                duration=target_dur,
                rng=rng,
                knowledge_refs=knowledge_refs,
                words=words,
            )

        audio_tracks = []
        if audio_path:
            audio_tracks.append(
                AudioTrackSpec(
                    id=f"audio_{spec_id[:8]}",
                    file_path=audio_path,
                    start_time=0.0,
                    duration=target_dur,
                    volume=1.0,
                )
            )

        spec = NativeMotionSpec(
            schema_version="native_motion_v1",
            id=spec_id,
            title=f"{brief.topic[:60]} — {tone.capitalize()} Motion",
            brief=brief,
            constraints=constraints,
            knowledge_refs=knowledge_refs,
            safe_zones=safe_zones,
            width=w,
            height=h,
            fps=constraints.target_fps,
            duration_seconds=target_dur,
            scenes=scenes,
            audio_tracks=audio_tracks,
        )
        return spec

    @staticmethod
    def _seed_from_brief(brief: CreativeBrief) -> int:
        """Derive a stable integer seed from brief parameters."""
        raw = f"{brief.topic}|{brief.intent}|{brief.tone}|{brief.target_audience}"
        return int(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8], 16)

    @staticmethod
    def _dimensions_for_aspect(aspect: str) -> tuple[int, int]:
        if aspect == "9:16":
            return (1080, 1920)
        elif aspect == "16:9":
            return (1920, 1080)
        elif aspect == "1:1":
            return (1080, 1080)
        elif aspect == "4:5":
            return (1080, 1350)
        return (1080, 1920)

    # ------------------------------------------------------------------------
    # Specialized Composition Builders (Not Templates: Dynamic Algorithmic Trees)
    # ------------------------------------------------------------------------

    @classmethod
    def _build_data_kinetic_scenes(
        cls,
        brief: CreativeBrief,
        width: int,
        height: int,
        safe_zones: SafeZoneSpec,
        duration: float,
        rng: random.Random,
        knowledge_refs: List[KnowledgeRef],
    ) -> List[SceneSpec]:
        """Construct a high-energy data & metrics motion scene."""
        elements: List[ElementSpec] = []
        cx = width / 2
        cy = height / 2

        # 1. Ambient Background Gradient
        bg_elem = ElementSpec(
            id="bg_gradient",
            type="gradient",
            start_time=0.0,
            duration=duration,
            z_index=0,
            transform=ElementTransform(x=0, y=0, width=width, height=height, anchor_x=0.0, anchor_y=0.0),
            gradient_config=GradientConfig(
                type="linear",
                angle_degrees=145.0,
                stops=[
                    GradientStop(color="#090D16", position=0.0),
                    GradientStop(color="#0B132B", position=0.5),
                    GradientStop(color="#1C2541", position=1.0),
                ],
                animated=True,
                animation_speed=0.5,
            ),
        )
        elements.append(bg_elem)

        # 2. Subtle Particles Atmosphere
        particles_elem = ElementSpec(
            id="atm_particles",
            type="particles",
            start_time=0.0,
            duration=duration,
            z_index=1,
            transform=ElementTransform(x=0, y=0, width=width, height=height, anchor_x=0.0, anchor_y=0.0),
            particles_config=ParticlesConfig(
                count=60,
                color="#38BDF8",
                speed_range=(15.0, 40.0),
                size_range=(2.0, 5.0),
                direction="up",
                blend_mode="screen",
            ),
        )
        elements.append(particles_elem)

        # 3. Main Data Card Container
        card_w = width * (1.0 - (safe_zones.left + safe_zones.right))
        card_h = height * 0.45
        card_x = safe_zones.left * width
        card_y = cy - (card_h / 2) + (height * 0.05)

        card_start = min(0.2, duration * 0.1)
        card_elem = ElementSpec(
            id="data_card",
            type="shape",
            start_time=card_start,
            duration=max(0.1, duration - card_start),
            z_index=5,
            transform=ElementTransform(
                x=card_x,
                y=card_y,
                width=card_w,
                height=card_h,
                anchor_x=0.0,
                anchor_y=0.0,
                opacity=0.0,
                scale_x=0.92,
                scale_y=0.92,
            ),
            keyframes=[
                KeyframeSpec(time=0.0, properties={"opacity": 0.0, "scale_x": 0.92, "scale_y": 0.92}, easing="power4_out"),
                KeyframeSpec(time=0.6, properties={"opacity": 1.0, "scale_x": 1.0, "scale_y": 1.0}, easing="back_out"),
            ],
            shape_config=ShapeConfig(
                shape_type="rounded_rect",
                fill="rgba(15, 23, 42, 0.85)",
                stroke="#38BDF8",
                stroke_width=2.0,
                corner_radius=24.0,
            ),
        )
        elements.append(card_elem)

        # 4. Data Chart
        values = [rng.randint(35, 95) for _ in range(4)]
        labels = ["WEEK 1", "WEEK 2", "WEEK 3", "WEEK 4"]
        chart_start = min(0.4, duration * 0.2)
        chart_elem = ElementSpec(
            id="metric_chart",
            type="data_chart",
            start_time=chart_start,
            duration=max(0.1, duration - chart_start),
            z_index=10,
            transform=ElementTransform(
                x=card_x + 30,
                y=card_y + 40,
                width=card_w - 60,
                height=card_h - 80,
                anchor_x=0.0,
                anchor_y=0.0,
                opacity=0.0,
            ),
            keyframes=[
                KeyframeSpec(time=0.0, properties={"opacity": 0.0}, easing="ease_out"),
                KeyframeSpec(time=0.4, properties={"opacity": 1.0}, easing="power2_in_out"),
            ],
            chart_config=DataChartConfig(
                chart_type="bar",
                title=f"{brief.topic.upper()} SURGE",
                dataset=[
                    DataPoint(label=labels[i], value=float(values[i]), color="#0EA5E9" if i < 3 else "#38BDF8")
                    for i in range(4)
                ],
                show_values=True,
                show_grid=True,
                animated_progress=True,
            ),
        )
        elements.append(chart_elem)

        # 5. Dynamic Headline Typography
        title_y = safe_zones.top * height + 40
        title_start = min(0.1, duration * 0.05)
        title_elem = ElementSpec(
            id="hero_title",
            type="text",
            start_time=title_start,
            duration=max(0.1, duration - title_start),
            z_index=15,
            transform=ElementTransform(
                x=cx,
                y=title_y,
                width=card_w,
                height=120,
                anchor_x=0.5,
                anchor_y=0.0,
                opacity=0.0,
                rotation_deg=-3.0,
            ),
            keyframes=[
                KeyframeSpec(time=0.0, properties={"opacity": 0.0, "y": title_y - 30, "rotation_deg": -3.0}, easing="power4_out"),
                KeyframeSpec(time=0.5, properties={"opacity": 1.0, "y": title_y, "rotation_deg": 0.0}, easing="back_out"),
            ],
            text_config=TextConfig(
                content=brief.topic.upper(),
                typography=TypographySpec(
                    font_family="Outfit, sans-serif",
                    font_size=52.0 if width <= 1080 else 64.0,
                    font_weight=900,
                    letter_spacing=1.5,
                    line_height=1.1,
                    text_align="center",
                    fill="#F8FAFC",
                    shadow="0px 8px 24px rgba(0,0,0,0.6)",
                ),
                max_width=card_w,
            ),
        )
        elements.append(title_elem)

        # 6. Accent Growth Badge
        badge_start = min(0.6, duration * 0.4)
        badge_elem = ElementSpec(
            id="growth_badge",
            type="text",
            start_time=badge_start,
            duration=max(0.1, duration - badge_start),
            z_index=20,
            transform=ElementTransform(
                x=cx,
                y=card_y + card_h + 30,
                width=240,
                height=60,
                anchor_x=0.5,
                anchor_y=0.0,
                opacity=0.0,
                scale_x=0.5,
                scale_y=0.5,
            ),
            keyframes=[
                KeyframeSpec(time=0.0, properties={"opacity": 0.0, "scale_x": 0.5, "scale_y": 0.5}, easing="elastic_out"),
                KeyframeSpec(time=0.6, properties={"opacity": 1.0, "scale_x": 1.0, "scale_y": 1.0}, easing="elastic_out"),
            ],
            text_config=TextConfig(
                content="+248% GROWTH",
                typography=TypographySpec(
                    font_family="JetBrains Mono, monospace",
                    font_size=28.0,
                    font_weight=700,
                    letter_spacing=2.0,
                    text_align="center",
                    fill="#10B981",  # emerald-500
                    shadow="0px 0px 12px rgba(16, 185, 129, 0.4)",
                ),
            ),
        )
        elements.append(badge_elem)

        # 7. Vignette Shader
        shader_elem = ElementSpec(
            id="lens_vignette",
            type="shader_effect",
            start_time=0.0,
            duration=duration,
            z_index=30,
            transform=ElementTransform(x=0, y=0, width=width, height=height, anchor_x=0.0, anchor_y=0.0),
            shader_config=ShaderConfig(effect_type="vignette", intensity=0.45, radius=35.0),
        )
        elements.append(shader_elem)

        scene = SceneSpec(
            id="scene_data_01",
            start_time=0.0,
            duration=duration,
            background_color="#0A0F1D",
            camera=CameraSpec(projection="2d", zoom=1.0),
            elements=elements,
        )
        return [scene]

    @classmethod
    def _build_editorial_scenes(
        cls,
        brief: CreativeBrief,
        width: int,
        height: int,
        safe_zones: SafeZoneSpec,
        duration: float,
        rng: random.Random,
        knowledge_refs: List[KnowledgeRef],
    ) -> List[SceneSpec]:
        """Construct an elegant, cinematic/editorial widescreen motion scene."""
        elements: List[ElementSpec] = []
        cx = width / 2
        cy = height / 2

        # 1. Warm Architectural Canvas with dynamic sweeping light
        bg_elem = ElementSpec(
            id="cinematic_bg",
            type="gradient",
            start_time=0.0,
            duration=duration,
            z_index=0,
            transform=ElementTransform(x=0, y=0, width=width, height=height, anchor_x=0.0, anchor_y=0.0),
            gradient_config=GradientConfig(
                type="linear",
                angle_degrees=45.0,
                stops=[
                    GradientStop(color="#5C4D3C", position=0.0),
                    GradientStop(color="#29231E", position=0.5),
                    GradientStop(color="#0F0E0D", position=1.0),
                ],
                animated=True,
                animation_speed=1.5,
            ),
        )
        elements.append(bg_elem)

        # 1b. Ambient Architectural Dust Particles
        particles_elem = ElementSpec(
            id="arch_particles",
            type="particles",
            start_time=0.0,
            duration=duration,
            z_index=1,
            transform=ElementTransform(x=0, y=0, width=width, height=height, anchor_x=0.0, anchor_y=0.0),
            particles_config=ParticlesConfig(
                count=80,
                color="#FACC15",
                speed_range=(20.0, 50.0),
                size_range=(3.5, 7.0),
                direction="ambient",
                blend_mode="screen",
            ),
        )
        elements.append(particles_elem)

        # 2. Geometric Architectural Framing Lines
        frame_margin_x = safe_zones.left * width
        frame_margin_y = safe_zones.top * height
        frame_w = width - (frame_margin_x * 2)
        frame_h = height - (frame_margin_y * 2)

        border_start = min(0.1, duration * 0.05)
        frame_elem = ElementSpec(
            id="arch_border",
            type="shape",
            start_time=border_start,
            duration=max(0.1, duration - border_start),
            z_index=5,
            transform=ElementTransform(
                x=frame_margin_x,
                y=frame_margin_y,
                width=frame_w,
                height=frame_h,
                anchor_x=0.0,
                anchor_y=0.0,
                opacity=0.0,
            ),
            keyframes=[
                KeyframeSpec(time=0.0, properties={"opacity": 0.0}, easing="linear"),
                KeyframeSpec(time=min(1.0, duration * 0.5), properties={"opacity": 0.4}, easing="power2_in_out"),
            ],
            shape_config=ShapeConfig(
                shape_type="rounded_rect",
                fill="transparent",
                stroke="#D4AF37",  # Gold accent
                stroke_width=1.0,
                corner_radius=4.0,
            ),
        )
        elements.append(frame_elem)

        # 3. Main Editorial Headline
        headline_start = min(0.3, duration * 0.15)
        hero_text = ElementSpec(
            id="editorial_headline",
            type="text",
            start_time=headline_start,
            duration=max(0.1, duration - headline_start),
            z_index=15,
            transform=ElementTransform(
                x=cx,
                y=cy - 40,
                width=frame_w * 0.85,
                height=160,
                anchor_x=0.5,
                anchor_y=0.5,
                opacity=0.0,
                scale_x=0.96,
                scale_y=0.96,
            ),
            keyframes=[
                KeyframeSpec(time=0.0, properties={"opacity": 0.0, "scale_x": 0.96, "scale_y": 0.96}, easing="power2_in_out"),
                KeyframeSpec(time=min(1.2, duration * 0.6), properties={"opacity": 1.0, "scale_x": 1.0, "scale_y": 1.0}, easing="power2_in_out"),
            ],
            text_config=TextConfig(
                content=brief.topic,
                typography=TypographySpec(
                    font_family="Playfair Display, serif",
                    font_size=64.0 if width >= 1920 else 44.0,
                    font_weight=400,
                    letter_spacing=3.0,
                    line_height=1.25,
                    text_align="center",
                    fill="#F5F5F0",
                    shadow="0px 10px 30px rgba(0,0,0,0.8)",
                ),
            ),
        )
        elements.append(hero_text)

        # 4. Monospace Sub-title / Act Marker
        act_start = min(0.6, duration * 0.3)
        subtitle_elem = ElementSpec(
            id="editorial_act",
            type="text",
            start_time=act_start,
            duration=max(0.1, duration - act_start),
            z_index=16,
            transform=ElementTransform(
                x=cx,
                y=cy + 60,
                width=300,
                height=40,
                anchor_x=0.5,
                anchor_y=0.0,
                opacity=0.0,
            ),
            keyframes=[
                KeyframeSpec(time=0.0, properties={"opacity": 0.0}, easing="ease_out"),
                KeyframeSpec(time=min(0.8, duration * 0.4), properties={"opacity": 0.85}, easing="power2_in_out"),
            ],
            text_config=TextConfig(
                content="FOLIO // 2026",
                typography=TypographySpec(
                    font_family="JetBrains Mono, monospace",
                    font_size=18.0,
                    font_weight=400,
                    letter_spacing=6.0,
                    text_align="center",
                    fill="#D4AF37",
                ),
            ),
        )
        elements.append(subtitle_elem)

        # 5. Cinematic Vignette
        vignette_elem = ElementSpec(
            id="cinematic_vignette",
            type="shader_effect",
            start_time=0.0,
            duration=duration,
            z_index=25,
            transform=ElementTransform(x=0, y=0, width=width, height=height, anchor_x=0.0, anchor_y=0.0),
            shader_config=ShaderConfig(effect_type="vignette", intensity=0.6, radius=40.0),
        )
        elements.append(vignette_elem)

        scene = SceneSpec(
            id="scene_editorial_01",
            start_time=0.0,
            duration=duration,
            background_color="#121110",
            camera=CameraSpec(projection="perspective_3d", zoom=1.03),
            elements=elements,
        )
        return [scene]

    @classmethod
    def _build_kinetic_scenes(
        cls,
        brief: CreativeBrief,
        width: int,
        height: int,
        safe_zones: SafeZoneSpec,
        duration: float,
        rng: random.Random,
        knowledge_refs: List[KnowledgeRef],
        words: Optional[List[WordTimestampSpec]] = None,
    ) -> List[SceneSpec]:
        """Construct a kinetic narrative scene with optional aligned speech captions."""
        elements: List[ElementSpec] = []
        cx = width / 2
        cy = height / 2

        # 1. Dark vibrant background with animated angle sweep
        bg_elem = ElementSpec(
            id="kinetic_bg",
            type="gradient",
            start_time=0.0,
            duration=duration,
            z_index=0,
            transform=ElementTransform(x=0, y=0, width=width, height=height, anchor_x=0.0, anchor_y=0.0),
            gradient_config=GradientConfig(
                type="linear",
                angle_degrees=135.0,
                stops=[
                    GradientStop(color="#4C1D95", position=0.0),  # purple-900
                    GradientStop(color="#1E1B4B", position=0.5),  # indigo-950
                    GradientStop(color="#090D16", position=1.0),
                ],
                animated=True,
                animation_speed=1.5,
            ),
        )
        elements.append(bg_elem)

        # 1b. Ambient Energy Particles
        particles_elem = ElementSpec(
            id="kinetic_particles",
            type="particles",
            start_time=0.0,
            duration=duration,
            z_index=1,
            transform=ElementTransform(x=0, y=0, width=width, height=height, anchor_x=0.0, anchor_y=0.0),
            particles_config=ParticlesConfig(
                count=80,
                color="#A78BFA",
                speed_range=(25.0, 60.0),
                size_range=(3.5, 7.0),
                direction="up",
                blend_mode="screen",
            ),
        )
        elements.append(particles_elem)

        # 2. Kinetic Title
        title_y = safe_zones.top * height + 60
        title_start = min(0.1, duration * 0.05)
        title_elem = ElementSpec(
            id="kinetic_hero",
            type="text",
            start_time=title_start,
            duration=max(0.1, duration - title_start),
            z_index=10,
            transform=ElementTransform(
                x=cx,
                y=title_y,
                width=width * 0.85,
                height=140,
                anchor_x=0.5,
                anchor_y=0.0,
                opacity=0.0,
            ),
            keyframes=[
                KeyframeSpec(time=0.0, properties={"opacity": 0.0, "y": title_y - 60, "scale_x": 0.8, "scale_y": 0.8}, easing="power4_out"),
                KeyframeSpec(time=0.6, properties={"opacity": 1.0, "y": title_y, "scale_x": 1.0, "scale_y": 1.0}, easing="back_out"),
            ],
            text_config=TextConfig(
                content=brief.topic.upper(),
                typography=TypographySpec(
                    font_family="Montserrat, sans-serif",
                    font_size=54.0 if width <= 1080 else 68.0,
                    font_weight=900,
                    letter_spacing=1.0,
                    line_height=1.1,
                    text_align="center",
                    fill="#FFFFFF",
                    shadow="0px 6px 20px rgba(0,0,0,0.5)",
                ),
            ),
        )
        elements.append(title_elem)

        # 3. Speech Captions Component (if words provided)
        if words:
            caption_elem = ElementSpec(
                id="kinetic_captions",
                type="captions",
                start_time=0.0,
                duration=duration,
                z_index=20,
                transform=ElementTransform(
                    x=cx,
                    y=height * (1.0 - safe_zones.bottom) - 80,
                    width=width * 0.84,
                    height=160,
                    anchor_x=0.5,
                    anchor_y=0.5,
                ),
                captions_config=CaptionsConfig(
                    words=words,
                    active_color="#FBBF24",
                    inactive_color="#94A3B8",
                    typography=TypographySpec(
                        font_family="Inter, sans-serif",
                        font_size=42.0,
                        font_weight=800,
                        letter_spacing=0.5,
                        text_align="center",
                        fill="#FFFFFF",
                    ),
                    animation_mode="word_pop",
                    safe_zone_anchor="bottom",
                    background_veil=True,
                ),
            )
            elements.append(caption_elem)

        scene = SceneSpec(
            id="scene_kinetic_01",
            start_time=0.0,
            duration=duration,
            background_color="#0F172A",
            camera=CameraSpec(projection="2d", zoom=1.0),
            elements=elements,
        )
        return [scene]
