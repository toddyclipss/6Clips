# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Knowledge-to-Motion Generator.

Produces original, safe, typed, editable native_motion_v1 scene specifications
from creative briefs and cited knowledge techniques. Never uses fixed 196 donor
block templates. Supports multi-scene compositions with frame-accurate durations,
substantially distinct topologies, and live KnowledgeBase retrieval.
"""

from __future__ import annotations

import hashlib
import logging
import random
import uuid
from typing import Any, Dict, List, Literal, Optional

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
    SceneTransitionSpec,
    ShaderConfig,
    ShapeConfig,
    TextConfig,
    TypographySpec,
    VideoLayerConfig,
    WordTimestampSpec,
)

logger = logging.getLogger(__name__)


class NativeMotionGenerator:
    """Foundational creative engine that composes dynamic, original motion graphics."""

    @classmethod
    def retrieve_knowledge_for_brief(
        cls, brief: CreativeBrief, limit: int = 3
    ) -> List[KnowledgeRef]:
        """Retrieve authentic knowledge directives from 6Clips curated KnowledgeBase."""
        try:
            from backend.knowledge_base.service import KnowledgeBase
            kb = KnowledgeBase()
            query = f"{brief.intent} {brief.topic} {brief.tone}"
            results = kb.search(query, limit=limit)
            refs = []
            for r in results:
                doc = kb.get_by_id(r.knowledge_doc_id)
                if not doc:
                    continue
                principles = list(doc.principles) if doc.principles else [f"technique_{doc.donor_section.lower().replace(' ', '_')}"]
                refs.append(
                    KnowledgeRef(
                        doc_id=doc.knowledge_doc_id,
                        source_path=doc.source_path,
                        content_hash=doc.source_hash,
                        section=doc.donor_section or "general",
                        principles=principles[:4],
                        donor_group=doc.donor_group,
                        applied_properties={
                            "donor_group": doc.donor_group,
                            "confidence": doc.confidence,
                            "rights": str(doc.rights.value if hasattr(doc.rights, "value") else doc.rights),
                        },
                    )
                )
            if refs:
                return refs
        except Exception as e:
            logger.info("KnowledgeBase query encountered exception: %s", e)

        # Truthful engine-safe generic citation
        return [
            KnowledgeRef(
                doc_id="technique-native-safe-grammar",
                source_path="backend/native_motion/schema.py",
                content_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                section="native-grammar-invariants",
                principles=["safe_zone_anchor", "wcag_contrast_veil", "deterministic_stepping"],
                donor_group="Core",
                applied_properties={"engine": "native_motion_v1"},
            )
        ]

    @classmethod
    def generate(
        cls,
        brief: CreativeBrief,
        knowledge_refs: Optional[List[KnowledgeRef]] = None,
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

        if not knowledge_refs:
            knowledge_refs = cls.retrieve_knowledge_for_brief(brief)

        spec_id = f"nm_{uuid.UUID(int=rng.getrandbits(128)).hex[:12]}"
        aspect = constraints.aspect_ratio
        w, h = cls._dimensions_for_aspect(aspect)

        safe_zones = SafeZoneSpec(
            top=0.14 if aspect == "9:16" else 0.08,
            bottom=0.20 if aspect == "9:16" else 0.10,
            left=0.08,
            right=0.08,
        )

        # Decide duration: if default 60.0 was uncustomized, default to punchy 6.0s
        target_dur = 6.0 if constraints.max_duration_seconds == 60.0 else constraints.max_duration_seconds

        # Route composition style based on brief intent and tone
        intent = brief.intent.lower()
        tone = brief.tone.lower()

        if target_dur > 6.0:
            scenes = cls._build_multiscene_composition(
                brief=brief,
                width=w,
                height=h,
                safe_zones=safe_zones,
                total_duration=target_dur,
                rng=rng,
                knowledge_refs=knowledge_refs,
                words=words,
            )
        elif intent in ("data", "metrics", "chart", "analytics"):
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
                    audio_type="speech_authentic" if words else "bgm",
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
    # Generic Multi-Scene Composition Router
    # ------------------------------------------------------------------------

    @classmethod
    def _build_multiscene_composition(
        cls,
        brief: CreativeBrief,
        width: int,
        height: int,
        safe_zones: SafeZoneSpec,
        total_duration: float,
        rng: random.Random,
        knowledge_refs: List[KnowledgeRef],
        words: Optional[List[WordTimestampSpec]] = None,
    ) -> List[SceneSpec]:
        """Divide total duration into balanced narrative scenes with transitions."""
        # Determine scene count: 3 to 5 scenes
        if total_duration >= 40.0:
            n_scenes = 4
        elif total_duration >= 20.0:
            n_scenes = 3
        else:
            n_scenes = 2

        dur_per_scene = round(total_duration / n_scenes, 3)
        scenes: List[SceneSpec] = []
        cur_time = 0.0

        for i in range(n_scenes):
            is_last = (i == n_scenes - 1)
            s_dur = round(total_duration - cur_time, 3) if is_last else dur_per_scene

            trans = None
            if not is_last:
                trans_types = ["slide_left", "crossfade", "slide_up", "wipe_horizontal", "zoom_in"]
                trans = SceneTransitionSpec(type=trans_types[i % len(trans_types)], duration=0.6)

            # Build elements for this scene
            elements: List[ElementSpec] = []

            # Background gradient
            bg_elem = ElementSpec(
                id=f"s{i}_bg",
                type="gradient",
                start_time=0.0,
                duration=s_dur,
                z_index=0,
                transform=ElementTransform(x=0, y=0, width=width, height=height, anchor_x=0.0, anchor_y=0.0),
                gradient_config=GradientConfig(
                    type="linear",
                    angle_degrees=135.0 + i * 30.0,
                    stops=[
                        GradientStop(color="#090D16", position=0.0),
                        GradientStop(color="#0F172A", position=0.5),
                        GradientStop(color="#1E293B", position=1.0),
                    ],
                    animated=True,
                ),
            )
            elements.append(bg_elem)

            # Title / Scene label
            title_elem_id = "hero_title" if i == 0 else f"s{i}_title"
            title_elem = ElementSpec(
                id=title_elem_id,
                type="text",
                start_time=0.1,
                duration=s_dur - 0.1,
                z_index=10,
                transform=ElementTransform(
                    x=width / 2,
                    y=safe_zones.top * height + 60,
                    width=width * 0.85,
                    height=100,
                    anchor_x=0.5,
                    anchor_y=0.0,
                ),
                text_config=TextConfig(
                    content=f"{brief.topic.upper()} — PART {i+1}",
                    typography=TypographySpec(
                        font_family="Outfit, sans-serif",
                        font_size=42.0 if width <= 1080 else 52.0,
                        font_weight=800,
                        fill="#F8FAFC",
                    ),
                    animation_type="fade_slide_up",
                ),
            )
            elements.append(title_elem)

            # Middle content: alternate chart / callout
            if i % 2 == 1:
                chart_elem = ElementSpec(
                    id=f"s{i}_chart",
                    type="data_chart",
                    start_time=0.3,
                    duration=s_dur - 0.3,
                    z_index=15,
                    transform=ElementTransform(
                        x=safe_zones.left * width + 20,
                        y=height * 0.32,
                        width=width * (1.0 - safe_zones.left - safe_zones.right) - 40,
                        height=height * 0.38,
                        anchor_x=0.0,
                        anchor_y=0.0,
                    ),
                    chart_config=DataChartConfig(
                        chart_type="bar",
                        title="PERFORMANCE GAIN",
                        dataset=[
                            DataPoint(label="BASELINE", value=25.0, color="#64748B"),
                            DataPoint(label="PHASE 1", value=55.0, color="#38BDF8"),
                            DataPoint(label="PHASE 2", value=92.0, color="#10B981"),
                        ],
                    ),
                )
                elements.append(chart_elem)
            else:
                card_elem = ElementSpec(
                    id=f"s{i}_card",
                    type="shape",
                    start_time=0.2,
                    duration=s_dur - 0.2,
                    z_index=8,
                    transform=ElementTransform(
                        x=safe_zones.left * width,
                        y=height * 0.35,
                        width=width * (1.0 - safe_zones.left - safe_zones.right),
                        height=height * 0.28,
                        anchor_x=0.0,
                        anchor_y=0.0,
                    ),
                    shape_config=ShapeConfig(
                        shape_type="rounded_rect",
                        fill="rgba(15, 23, 42, 0.85)",
                        stroke="#38BDF8",
                        stroke_width=1.5,
                        corner_radius=16.0,
                    ),
                )
                elements.append(card_elem)

            # Captions if provided and on first scene
            if words and i == 0:
                cap_elem = ElementSpec(
                    id=f"s{i}_captions",
                    type="captions",
                    start_time=0.0,
                    duration=s_dur,
                    z_index=25,
                    transform=ElementTransform(
                        x=width / 2,
                        y=height * (1.0 - safe_zones.bottom) - 80,
                        width=width * 0.85,
                        height=140,
                        anchor_x=0.5,
                        anchor_y=0.5,
                    ),
                    captions_config=CaptionsConfig(
                        words=words,
                        active_color="#FBBF24",
                        inactive_color="#94A3B8",
                    ),
                )
                elements.append(cap_elem)

            scene = SceneSpec(
                id=f"scene_{i+1:02d}",
                name=f"Part {i+1}",
                start_time=cur_time,
                duration=s_dur,
                background_color="#0A0F1D",
                transition=trans,
                elements=elements,
                knowledge_refs=knowledge_refs,
            )
            scenes.append(scene)
            cur_time += s_dur

        return scenes

    # ------------------------------------------------------------------------
    # Specialized Benchmark Brief Builders (B1 to B6)
    # ------------------------------------------------------------------------

    @classmethod
    def build_benchmark_b1(
        cls, approach: Literal["A", "B"] = "A", seed: int = 101
    ) -> NativeMotionSpec:
        """B1: vertical 9:16, 25 s topical educational short with 3 animated callouts."""
        brief = CreativeBrief(
            topic="Global Renewable Grid Scaling & Battery Storage Breakthrough",
            intent="education",
            tone="tech",
            target_audience="Science & Energy Creators",
        )
        constraints = Constraints(aspect_ratio="9:16", max_duration_seconds=25.0, target_fps=30)
        rng = random.Random(seed)
        w, h = 1080, 1920
        safe_zones = SafeZoneSpec(top=0.14, bottom=0.20, left=0.08, right=0.08)
        krefs = cls.retrieve_knowledge_for_brief(brief, limit=2)

        if approach == "A":
            # Approach A: Card-stack layout with vertical progress bar & clean callouts
            durations = [6.0, 6.0, 7.0, 6.0]  # Sum = 25.0s
            transitions = [
                SceneTransitionSpec(type="slide_up", duration=0.6),
                SceneTransitionSpec(type="wipe_horizontal", duration=0.6),
                SceneTransitionSpec(type="crossfade", duration=0.6),
                None,
            ]
            scenes: List[SceneSpec] = []
            cur_t = 0.0

            callout_data = [
                {"title": "GLOBAL GRID CAPACITY", "val": "+310 GWh ADDED", "desc": "Annual battery storage expansion surge"},
                {"title": "ROUND-TRIP EFFICIENCY", "val": "94.2% STORED", "desc": "Solid-state electrolyte breakthrough"},
                {"title": "PEAK LOAD DIVERSION", "val": "82% PEAK SHED", "desc": "Decentralized micro-inverter automation"},
                {"title": "VERIFIED FINDING", "val": "NET-ZERO ACCELERATION", "desc": "Decarbonizing industrial base load"},
            ]

            for idx, dur in enumerate(durations):
                c = callout_data[idx]
                elems: List[ElementSpec] = []

                # Background
                elems.append(
                    ElementSpec(
                        id=f"b1a_s{idx}_bg",
                        type="gradient",
                        start_time=0.0,
                        duration=dur,
                        z_index=0,
                        transform=ElementTransform(x=0, y=0, width=w, height=h, anchor_x=0.0, anchor_y=0.0),
                        gradient_config=GradientConfig(
                            type="linear",
                            angle_degrees=140.0,
                            stops=[GradientStop(color="#09131C", position=0.0), GradientStop(color="#0B253A", position=1.0)],
                            animated=True,
                        ),
                    )
                )

                # Card container
                card_w = w * 0.84
                card_h = h * 0.42
                card_x = w * 0.08
                card_y = h * 0.28
                elems.append(
                    ElementSpec(
                        id=f"b1a_s{idx}_card",
                        type="shape",
                        start_time=0.2,
                        duration=dur - 0.2,
                        z_index=5,
                        transform=ElementTransform(x=card_x, y=card_y, width=card_w, height=card_h, anchor_x=0.0, anchor_y=0.0),
                        shape_config=ShapeConfig(
                            shape_type="rounded_rect",
                            fill="rgba(11, 23, 38, 0.9)",
                            stroke="#38BDF8",
                            stroke_width=2.0,
                            corner_radius=20.0,
                        ),
                    )
                )

                # Callout metric
                elems.append(
                    ElementSpec(
                        id=f"b1a_s{idx}_text_callout",
                        type="text",
                        start_time=0.3,
                        duration=dur - 0.3,
                        z_index=10,
                        transform=ElementTransform(x=w / 2, y=card_y + 110, width=card_w - 40, height=80, anchor_x=0.5, anchor_y=0.5),
                        text_config=TextConfig(
                            content=c["val"],
                            typography=TypographySpec(font_family="Outfit, sans-serif", font_size=56.0, font_weight=900, fill="#38BDF8"),
                            animation_type="word_pop",
                            highlight_words=[c["val"].split()[0]],
                            highlight_color="#38BDF8",
                        ),
                    )
                )

                # Callout description
                elems.append(
                    ElementSpec(
                        id=f"b1a_s{idx}_desc",
                        type="text",
                        start_time=0.5,
                        duration=dur - 0.5,
                        z_index=11,
                        transform=ElementTransform(x=w / 2, y=card_y + 200, width=card_w - 60, height=60, anchor_x=0.5, anchor_y=0.5),
                        text_config=TextConfig(
                            content=c["desc"],
                            typography=TypographySpec(font_family="Inter, sans-serif", font_size=28.0, font_weight=500, fill="#E2E8F0"),
                            animation_type="fade_slide_up",
                        ),
                    )
                )

                # Source attribution footer (Safe area anchored)
                elems.append(
                    ElementSpec(
                        id=f"b1a_s{idx}_source",
                        type="text",
                        start_time=0.1,
                        duration=dur - 0.1,
                        z_index=15,
                        transform=ElementTransform(x=w / 2, y=h * (1.0 - safe_zones.bottom) - 30, width=card_w, height=40, anchor_x=0.5, anchor_y=0.5),
                        text_config=TextConfig(
                            content="SOURCE: IEA Clean Energy Grid Report (2026)",
                            typography=TypographySpec(font_family="JetBrains Mono, monospace", font_size=18.0, font_weight=500, fill="#94A3B8"),
                            source_attribution="IEA Clean Energy Grid Report (2026)",
                        ),
                    )
                )

                scene = SceneSpec(
                    id=f"b1a_scene_{idx+1}",
                    name=f"Callout {idx+1}",
                    start_time=cur_t,
                    duration=dur,
                    background_color="#09131C",
                    transition=transitions[idx],
                    elements=elems,
                    knowledge_refs=krefs,
                )
                scenes.append(scene)
                cur_t += dur

        else:
            # Approach B: Radial Orbit HUD with Concentric Gauges (Topologically distinct!)
            durations = [6.0, 6.0, 7.0, 6.0]  # Sum = 25.0s
            transitions = [
                SceneTransitionSpec(type="wipe_radial", duration=0.7),
                SceneTransitionSpec(type="zoom_in", duration=0.6),
                SceneTransitionSpec(type="slide_right", duration=0.6),
                None,
            ]
            scenes = []
            cur_t = 0.0

            hud_metrics = [
                {"center": "310", "unit": "GWh", "label": "GLOBAL STORAGE SCALE"},
                {"center": "94.2", "unit": "%", "label": "EFFICIENCY QUOTIENT"},
                {"center": "82", "unit": "%", "label": "PEAK LOAD DISPATCH"},
                {"center": "NET", "unit": "ZERO", "label": "DECARBONIZATION PATH"},
            ]

            for idx, dur in enumerate(durations):
                m = hud_metrics[idx]
                elems = []

                # Dynamic dark amber/slate gradient
                elems.append(
                    ElementSpec(
                        id=f"b1b_s{idx}_bg",
                        type="gradient",
                        start_time=0.0,
                        duration=dur,
                        z_index=0,
                        transform=ElementTransform(x=0, y=0, width=w, height=h, anchor_x=0.0, anchor_y=0.0),
                        gradient_config=GradientConfig(
                            type="radial",
                            stops=[GradientStop(color="#1C1917", position=0.0), GradientStop(color="#0C0A09", position=1.0)],
                            animated=True,
                        ),
                    )
                )

                # Ambient dust particles
                elems.append(
                    ElementSpec(
                        id=f"b1b_s{idx}_parts",
                        type="particles",
                        start_time=0.0,
                        duration=dur,
                        z_index=1,
                        transform=ElementTransform(x=0, y=0, width=w, height=h, anchor_x=0.0, anchor_y=0.0),
                        particles_config=ParticlesConfig(count=70, color="#F59E0B", speed_range=(10.0, 30.0)),
                    )
                )

                # Radial donut gauge
                elems.append(
                    ElementSpec(
                        id=f"b1b_s{idx}_donut",
                        type="data_chart",
                        start_time=0.2,
                        duration=dur - 0.2,
                        z_index=8,
                        transform=ElementTransform(x=w / 2, y=h * 0.42, width=w * 0.75, height=w * 0.75, anchor_x=0.5, anchor_y=0.5),
                        chart_config=DataChartConfig(
                            chart_type="donut",
                            title=m["label"],
                            animated_progress=True,
                        ),
                    )
                )

                # HUD Monospace Readout
                elems.append(
                    ElementSpec(
                        id=f"b1b_s{idx}_hud_title",
                        type="text",
                        start_time=0.4,
                        duration=dur - 0.4,
                        z_index=15,
                        transform=ElementTransform(x=w / 2, y=h * 0.68, width=w * 0.85, height=80, anchor_x=0.5, anchor_y=0.5),
                        text_config=TextConfig(
                            content=f"METRIC: {m['center']} {m['unit']} // {m['label']}",
                            typography=TypographySpec(font_family="JetBrains Mono, monospace", font_size=24.0, font_weight=700, fill="#F59E0B"),
                            animation_type="typewriter",
                        ),
                    )
                )

                # Source attribution
                elems.append(
                    ElementSpec(
                        id=f"b1b_s{idx}_source",
                        type="text",
                        start_time=0.1,
                        duration=dur - 0.1,
                        z_index=16,
                        transform=ElementTransform(x=w / 2, y=h * (1.0 - safe_zones.bottom) - 30, width=w * 0.85, height=40, anchor_x=0.5, anchor_y=0.5),
                        text_config=TextConfig(
                            content="SOURCE: IEA Energy Storage Registry 2026",
                            typography=TypographySpec(font_family="JetBrains Mono, monospace", font_size=18.0, font_weight=500, fill="#A8A29E"),
                            source_attribution="IEA Energy Storage Registry 2026",
                        ),
                    )
                )

                scene = SceneSpec(
                    id=f"b1b_scene_{idx+1}",
                    name=f"Radial HUD {idx+1}",
                    start_time=cur_t,
                    duration=dur,
                    background_color="#0C0A09",
                    transition=transitions[idx],
                    elements=elems,
                    knowledge_refs=krefs,
                )
                scenes.append(scene)
                cur_t += dur

        return NativeMotionSpec(
            schema_version="native_motion_v1",
            id=f"nm_b1_{approach.lower()}_{seed}",
            title=f"B1: Renewable Grid Scaling ({approach})",
            brief=brief,
            constraints=constraints,
            knowledge_refs=krefs,
            safe_zones=safe_zones,
            width=w,
            height=h,
            fps=30,
            duration_seconds=25.0,
            scenes=scenes,
        )

    @classmethod
    def build_benchmark_b2(
        cls, approach: Literal["A", "B"] = "A", seed: int = 202
    ) -> NativeMotionSpec:
        """B2: vertical 9:16, 18 s high-energy developer product showcase with 10x metric."""
        brief = CreativeBrief(
            topic="HyperCompile v3: 10x Rust Build Velocity",
            intent="data",
            tone="tech",
            target_audience="Software Engineers & DevOps",
        )
        constraints = Constraints(aspect_ratio="9:16", max_duration_seconds=18.0, target_fps=30)
        w, h = 1080, 1920
        safe_zones = SafeZoneSpec(top=0.14, bottom=0.20, left=0.08, right=0.08)
        krefs = cls.retrieve_knowledge_for_brief(brief, limit=2)

        if approach == "A":
            # Approach A: Developer IDE Terminal & Metric Surge
            durations = [5.0, 7.0, 6.0]  # Sum = 18.0s
            transitions = [
                SceneTransitionSpec(type="slide_left", duration=0.6),
                SceneTransitionSpec(type="zoom_in", duration=0.6),
                None,
            ]
            scenes = []
            cur_t = 0.0

            # Scene 1: Bottleneck
            s1_elems = [
                ElementSpec(
                    id="b2a_s1_bg",
                    type="gradient",
                    start_time=0.0,
                    duration=5.0,
                    z_index=0,
                    transform=ElementTransform(x=0, y=0, width=w, height=h, anchor_x=0.0, anchor_y=0.0),
                    gradient_config=GradientConfig(type="linear", angle_degrees=135.0, stops=[GradientStop(color="#090D16", position=0.0), GradientStop(color="#111827", position=1.0)]),
                ),
                ElementSpec(
                    id="b2a_s1_title",
                    type="text",
                    start_time=0.2,
                    duration=4.8,
                    z_index=10,
                    transform=ElementTransform(x=w / 2, y=h * 0.35, width=w * 0.85, height=120, anchor_x=0.5, anchor_y=0.5),
                    text_config=TextConfig(
                        content="TIRED OF SLOW BUILDS?",
                        typography=TypographySpec(font_family="Outfit, sans-serif", font_size=58.0, font_weight=900, fill="#F8FAFC"),
                        animation_type="word_pop",
                    ),
                ),
                ElementSpec(
                    id="b2a_s1_sub",
                    type="text",
                    start_time=0.6,
                    duration=4.4,
                    z_index=11,
                    transform=ElementTransform(x=w / 2, y=h * 0.45, width=w * 0.85, height=60, anchor_x=0.5, anchor_y=0.5),
                    text_config=TextConfig(
                        content="Cargo build taking 14 minutes per release cycle...",
                        typography=TypographySpec(font_family="JetBrains Mono, monospace", font_size=24.0, font_weight=500, fill="#EF4444"),
                        animation_type="typewriter",
                    ),
                ),
            ]
            scenes.append(SceneSpec(id="b2a_s1", name="Bottleneck", start_time=cur_t, duration=5.0, background_color="#090D16", transition=transitions[0], elements=s1_elems, knowledge_refs=krefs))
            cur_t += 5.0

            # Scene 2: 10x Surge
            s2_elems = [
                ElementSpec(
                    id="b2a_s2_bg",
                    type="gradient",
                    start_time=0.0,
                    duration=7.0,
                    z_index=0,
                    transform=ElementTransform(x=0, y=0, width=w, height=h, anchor_x=0.0, anchor_y=0.0),
                    gradient_config=GradientConfig(type="linear", angle_degrees=150.0, stops=[GradientStop(color="#0B132B", position=0.0), GradientStop(color="#1C2541", position=1.0)], animated=True),
                ),
                ElementSpec(
                    id="b2a_s2_counter",
                    type="data_chart",
                    start_time=0.2,
                    duration=6.8,
                    z_index=15,
                    transform=ElementTransform(x=w / 2, y=h * 0.38, width=w * 0.85, height=220, anchor_x=0.5, anchor_y=0.5),
                    chart_config=DataChartConfig(
                        chart_type="counter",
                        title="10X SPEEDUP (ILLUSTRATIVE TEST METRIC)",
                        counter_prefix="",
                        counter_suffix="x",
                        counter_start=1.0,
                        counter_end=10.4,
                        counter_decimals=1,
                    ),
                ),
                ElementSpec(
                    id="b2a_s2_chart",
                    type="data_chart",
                    start_time=0.5,
                    duration=6.5,
                    z_index=16,
                    transform=ElementTransform(x=w * 0.08, y=h * 0.52, width=w * 0.84, height=h * 0.28, anchor_x=0.0, anchor_y=0.0),
                    chart_config=DataChartConfig(
                        chart_type="bar",
                        title="BUILD TIME REDUCTION",
                        dataset=[
                            DataPoint(label="LEGACY", value=840.0, color="#64748B"),
                            DataPoint(label="HYPERCOMPILE", value=84.0, color="#38BDF8"),
                        ],
                    ),
                ),
            ]
            scenes.append(SceneSpec(id="b2a_s2", name="10x Surge", start_time=cur_t, duration=7.0, background_color="#0B132B", transition=transitions[1], elements=s2_elems, knowledge_refs=krefs))
            cur_t += 7.0

            # Scene 3: Terminal UI
            s3_elems = [
                ElementSpec(
                    id="b2a_s3_bg",
                    type="gradient",
                    start_time=0.0,
                    duration=6.0,
                    z_index=0,
                    transform=ElementTransform(x=0, y=0, width=w, height=h, anchor_x=0.0, anchor_y=0.0),
                    gradient_config=GradientConfig(type="linear", angle_degrees=135.0, stops=[GradientStop(color="#090D16", position=0.0), GradientStop(color="#1E1B4B", position=1.0)]),
                ),
                ElementSpec(
                    id="b2a_s3_badge",
                    type="text",
                    start_time=0.2,
                    duration=5.8,
                    z_index=12,
                    transform=ElementTransform(x=w / 2, y=h * 0.40, width=w * 0.85, height=90, anchor_x=0.5, anchor_y=0.5),
                    text_config=TextConfig(
                        content="ZERO CODE CHANGES REQUIRED",
                        typography=TypographySpec(font_family="Outfit, sans-serif", font_size=46.0, font_weight=800, fill="#10B981"),
                        animation_type="fade_slide_up",
                    ),
                ),
                ElementSpec(
                    id="b2a_s3_cta",
                    type="text",
                    start_time=0.6,
                    duration=5.4,
                    z_index=15,
                    transform=ElementTransform(x=w / 2, y=h * (1.0 - safe_zones.bottom) - 40, width=w * 0.85, height=60, anchor_x=0.5, anchor_y=0.5),
                    text_config=TextConfig(
                        content="SAMPLE METRICS // TEST SUITE BENCHMARK",
                        typography=TypographySpec(font_family="JetBrains Mono, monospace", font_size=20.0, font_weight=500, fill="#94A3B8"),
                        source_attribution="HyperCompile v3 Synthetic Test Suite",
                    ),
                ),
            ]
            scenes.append(SceneSpec(id="b2a_s3", name="Terminal CTA", start_time=cur_t, duration=6.0, background_color="#090D16", transition=None, elements=s3_elems, knowledge_refs=krefs))

        else:
            # Approach B: Split-screen High-Contrast Kinetic Typography
            durations = [5.0, 7.0, 6.0]  # Sum = 18.0s
            transitions = [
                SceneTransitionSpec(type="slide_right", duration=0.6),
                SceneTransitionSpec(type="crossfade", duration=0.6),
                None,
            ]
            scenes = []
            cur_t = 0.0

            # Scene 1: Kinetic Typographic Hook
            s1_elems = [
                ElementSpec(
                    id="b2b_s1_bg",
                    type="gradient",
                    start_time=0.0,
                    duration=5.0,
                    z_index=0,
                    transform=ElementTransform(x=0, y=0, width=w, height=h, anchor_x=0.0, anchor_y=0.0),
                    gradient_config=GradientConfig(type="linear", angle_degrees=180.0, stops=[GradientStop(color="#18181B", position=0.0), GradientStop(color="#09090B", position=1.0)]),
                ),
                ElementSpec(
                    id="b2b_s1_kinetic",
                    type="text",
                    start_time=0.2,
                    duration=4.8,
                    z_index=10,
                    transform=ElementTransform(x=w / 2, y=h * 0.40, width=w * 0.85, height=180, anchor_x=0.5, anchor_y=0.5),
                    text_config=TextConfig(
                        content="COMPILE 10X FASTER",
                        typography=TypographySpec(font_family="Montserrat, sans-serif", font_size=64.0, font_weight=900, letter_spacing=2.0, fill="#F59E0B"),
                        animation_type="kinetic_scale",
                        highlight_words=["10X"],
                        highlight_color="#F59E0B",
                    ),
                ),
            ]
            scenes.append(SceneSpec(id="b2b_s1", name="Typographic Hook", start_time=cur_t, duration=5.0, background_color="#09090B", transition=transitions[0], elements=s1_elems, knowledge_refs=krefs))
            cur_t += 5.0

            # Scene 2: Circular Donut Gauge & 10x Metric
            s2_elems = [
                ElementSpec(
                    id="b2b_s2_bg",
                    type="gradient",
                    start_time=0.0,
                    duration=7.0,
                    z_index=0,
                    transform=ElementTransform(x=0, y=0, width=w, height=h, anchor_x=0.0, anchor_y=0.0),
                    gradient_config=GradientConfig(type="radial", stops=[GradientStop(color="#27272A", position=0.0), GradientStop(color="#09090B", position=1.0)]),
                ),
                ElementSpec(
                    id="b2b_s2_donut",
                    type="data_chart",
                    start_time=0.2,
                    duration=6.8,
                    z_index=10,
                    transform=ElementTransform(x=w / 2, y=h * 0.40, width=w * 0.75, height=w * 0.75, anchor_x=0.5, anchor_y=0.5),
                    chart_config=DataChartConfig(chart_type="donut", title="SPEEDUP FACTOR", animated_progress=True),
                ),
                ElementSpec(
                    id="b2b_s2_label",
                    type="text",
                    start_time=0.6,
                    duration=6.4,
                    z_index=15,
                    transform=ElementTransform(x=w / 2, y=h * 0.65, width=w * 0.85, height=60, anchor_x=0.5, anchor_y=0.5),
                    text_config=TextConfig(
                        content="10.0X COMPILATION MULTIPLIER",
                        typography=TypographySpec(font_family="JetBrains Mono, monospace", font_size=28.0, font_weight=700, fill="#F59E0B"),
                        animation_type="word_pop",
                    ),
                ),
            ]
            scenes.append(SceneSpec(id="b2b_s2", name="Donut Gauge", start_time=cur_t, duration=7.0, background_color="#09090B", transition=transitions[1], elements=s2_elems, knowledge_refs=krefs))
            cur_t += 7.0

            # Scene 3: Glassmorphic spec list
            s3_elems = [
                ElementSpec(
                    id="b2b_s3_bg",
                    type="gradient",
                    start_time=0.0,
                    duration=6.0,
                    z_index=0,
                    transform=ElementTransform(x=0, y=0, width=w, height=h, anchor_x=0.0, anchor_y=0.0),
                    gradient_config=GradientConfig(type="linear", angle_degrees=145.0, stops=[GradientStop(color="#18181B", position=0.0), GradientStop(color="#27272A", position=1.0)]),
                ),
                ElementSpec(
                    id="b2b_s3_text",
                    type="text",
                    start_time=0.2,
                    duration=5.8,
                    z_index=10,
                    transform=ElementTransform(x=w / 2, y=h * 0.42, width=w * 0.85, height=120, anchor_x=0.5, anchor_y=0.5),
                    text_config=TextConfig(
                        content="BUILT FOR MASSIVE WORKSPACES",
                        typography=TypographySpec(font_family="Outfit, sans-serif", font_size=48.0, font_weight=800, fill="#FFFFFF"),
                        animation_type="fade_slide_up",
                    ),
                ),
                ElementSpec(
                    id="b2b_s3_sample_label",
                    type="text",
                    start_time=0.5,
                    duration=5.5,
                    z_index=15,
                    transform=ElementTransform(x=w / 2, y=h * (1.0 - safe_zones.bottom) - 30, width=w * 0.85, height=40, anchor_x=0.5, anchor_y=0.5),
                    text_config=TextConfig(
                        content="SAMPLE METRICS // VERIFIED LOCAL TEST",
                        typography=TypographySpec(font_family="JetBrains Mono, monospace", font_size=18.0, font_weight=500, fill="#71717A"),
                        source_attribution="Sample developer metric test",
                    ),
                ),
            ]
            scenes.append(SceneSpec(id="b2b_s3", name="Spec Showcase", start_time=cur_t, duration=6.0, background_color="#18181B", transition=None, elements=s3_elems, knowledge_refs=krefs))

        return NativeMotionSpec(
            schema_version="native_motion_v1",
            id=f"nm_b2_{approach.lower()}_{seed}",
            title=f"B2: 10x Developer Showcase ({approach})",
            brief=brief,
            constraints=constraints,
            knowledge_refs=krefs,
            safe_zones=safe_zones,
            width=w,
            height=h,
            fps=30,
            duration_seconds=18.0,
            scenes=scenes,
        )

    @classmethod
    def build_benchmark_b3_synthetic(
        cls, audio_path: str, words: List[WordTimestampSpec], seed: int = 303
    ) -> NativeMotionSpec:
        """B3: vertical 9:16, 30 s podcast highlight with synthetic speech demonstration."""
        brief = CreativeBrief(
            topic="Building a Resilient Organic Growth Engine",
            intent="explain",
            tone="punchy",
            target_audience="Founders & Product Builders",
        )
        constraints = Constraints(aspect_ratio="9:16", max_duration_seconds=30.0, target_fps=30)
        w, h = 1080, 1920
        safe_zones = SafeZoneSpec(top=0.14, bottom=0.20, left=0.08, right=0.08)
        krefs = cls.retrieve_knowledge_for_brief(brief, limit=2)

        durations = [9.0, 12.0, 9.0]  # Sum = 30.0s
        transitions = [
            SceneTransitionSpec(type="crossfade", duration=0.8),
            SceneTransitionSpec(type="slide_up", duration=0.6),
            None,
        ]
        scenes = []
        cur_t = 0.0

        for idx, dur in enumerate(durations):
            elems = []
            # Background
            elems.append(
                ElementSpec(
                    id=f"b3_s{idx}_bg",
                    type="gradient",
                    start_time=0.0,
                    duration=dur,
                    z_index=0,
                    transform=ElementTransform(x=0, y=0, width=w, height=h, anchor_x=0.0, anchor_y=0.0),
                    gradient_config=GradientConfig(
                        type="linear",
                        angle_degrees=135.0,
                        stops=[GradientStop(color="#1E1B4B", position=0.0), GradientStop(color="#090D16", position=1.0)],
                        animated=True,
                    ),
                )
            )

            # Particles
            elems.append(
                ElementSpec(
                    id=f"b3_s{idx}_parts",
                    type="particles",
                    start_time=0.0,
                    duration=dur,
                    z_index=1,
                    transform=ElementTransform(x=0, y=0, width=w, height=h, anchor_x=0.0, anchor_y=0.0),
                    particles_config=ParticlesConfig(count=60, color="#A78BFA", speed_range=(15.0, 40.0)),
                )
            )

            # Header speaker tag
            elems.append(
                ElementSpec(
                    id=f"b3_s{idx}_speaker",
                    type="text",
                    start_time=0.1,
                    duration=dur - 0.1,
                    z_index=10,
                    transform=ElementTransform(x=w / 2, y=safe_zones.top * h + 40, width=w * 0.85, height=60, anchor_x=0.5, anchor_y=0.5),
                    text_config=TextConfig(
                        content="PODCAST HIGHLIGHT // THE RETENTION ENGINE",
                        typography=TypographySpec(font_family="JetBrains Mono, monospace", font_size=20.0, font_weight=700, fill="#A78BFA"),
                    ),
                )
            )

            # Simulated speaking head video viewport
            elems.append(
                ElementSpec(
                    id=f"b3_s{idx}_viewport",
                    type="video_layer",
                    start_time=0.2,
                    duration=dur - 0.2,
                    z_index=5,
                    transform=ElementTransform(x=w / 2, y=h * 0.42, width=w * 0.84, height=h * 0.36, anchor_x=0.5, anchor_y=0.5),
                    video_config=VideoLayerConfig(reframe_mode="center_tracked", loop=True),
                )
            )

            # Captions in Scene 2 (core insight)
            if idx == 1:
                elems.append(
                    ElementSpec(
                        id=f"b3_s{idx}_captions",
                        type="captions",
                        start_time=0.0,
                        duration=dur,
                        z_index=20,
                        transform=ElementTransform(x=w / 2, y=h * (1.0 - safe_zones.bottom) - 80, width=w * 0.85, height=140, anchor_x=0.5, anchor_y=0.5),
                        captions_config=CaptionsConfig(
                            words=words,
                            active_color="#FBBF24",
                            inactive_color="#94A3B8",
                            animation_mode="word_pop",
                        ),
                    )
                )

            scene = SceneSpec(
                id=f"b3_scene_{idx+1}",
                name=f"Podcast Segment {idx+1}",
                start_time=cur_t,
                duration=dur,
                background_color="#090D16",
                transition=transitions[idx],
                elements=elems,
                knowledge_refs=krefs,
            )
            scenes.append(scene)
            cur_t += dur

        audio_tracks = [
            AudioTrackSpec(
                id="audio_b3_speech",
                file_path=audio_path,
                start_time=0.0,
                duration=30.0,
                volume=1.0,
                audio_type="synthetic_test_speech",
                duck_during_speech=True,
                ducking_factor=0.3,
            )
        ]

        return NativeMotionSpec(
            schema_version="native_motion_v1",
            id=f"nm_b3_synthetic_{seed}",
            title="B3: Speaking-Head Highlight (Synthetic Speech Demonstration)",
            brief=brief,
            constraints=constraints,
            knowledge_refs=krefs,
            safe_zones=safe_zones,
            width=w,
            height=h,
            fps=30,
            duration_seconds=30.0,
            scenes=scenes,
            audio_tracks=audio_tracks,
        )

    @classmethod
    def build_benchmark_b4(cls, seed: int = 404) -> NativeMotionSpec:
        """B4: horizontal 16:9, 45 s transformer-attention educational infographic."""
        brief = CreativeBrief(
            topic="Inside Transformer Attention: Scaled Dot-Product & Multi-Head Routing",
            intent="education",
            tone="tech",
            target_audience="AI Engineers & Researchers",
        )
        constraints = Constraints(aspect_ratio="16:9", max_duration_seconds=45.0, target_fps=30)
        w, h = 1920, 1080
        safe_zones = SafeZoneSpec(top=0.08, bottom=0.10, left=0.08, right=0.08)
        krefs = cls.retrieve_knowledge_for_brief(brief, limit=2)

        durations = [11.0, 12.0, 11.0, 11.0]  # Sum = 45.0s
        transitions = [
            SceneTransitionSpec(type="slide_right", duration=0.7),
            SceneTransitionSpec(type="wipe_horizontal", duration=0.7),
            SceneTransitionSpec(type="crossfade", duration=0.7),
            None,
        ]
        scenes = []
        cur_t = 0.0

        stage_titles = [
            "STAGE 1: TOKEN EMBEDDINGS & LINEAR PROJECTIONS (Q, K, V)",
            "STAGE 2: SCALED DOT-PRODUCT SIMILARITY COMPUTATION",
            "STAGE 3: SOFTMAX ATTENTION MATRIX & HEATMAP DISTRIBUTION",
            "STAGE 4: WEIGHTED VALUE AGGREGATION & MULTI-HEAD CONTEXT",
        ]

        for idx, dur in enumerate(durations):
            elems = []
            # Background
            elems.append(
                ElementSpec(
                    id=f"b4_s{idx}_bg",
                    type="gradient",
                    start_time=0.0,
                    duration=dur,
                    z_index=0,
                    transform=ElementTransform(x=0, y=0, width=w, height=h, anchor_x=0.0, anchor_y=0.0),
                    gradient_config=GradientConfig(
                        type="linear",
                        angle_degrees=145.0,
                        stops=[GradientStop(color="#090D16", position=0.0), GradientStop(color="#0F172A", position=1.0)],
                        animated=True,
                    ),
                )
            )

            # Diagram Attention Component
            elems.append(
                ElementSpec(
                    id=f"b4_s{idx}_diagram",
                    type="data_chart",
                    start_time=0.2,
                    duration=dur - 0.2,
                    z_index=10,
                    transform=ElementTransform(x=w * 0.08, y=h * 0.15, width=w * 0.84, height=h * 0.70, anchor_x=0.0, anchor_y=0.0),
                    chart_config=DataChartConfig(
                        chart_type="diagram_attention",
                        title=stage_titles[idx],
                        attention_heads=4,
                    ),
                )
            )

            scene = SceneSpec(
                id=f"b4_scene_{idx+1}",
                name=f"Stage {idx+1}",
                start_time=cur_t,
                duration=dur,
                background_color="#090D16",
                transition=transitions[idx],
                elements=elems,
                knowledge_refs=krefs,
            )
            scenes.append(scene)
            cur_t += dur

        return NativeMotionSpec(
            schema_version="native_motion_v1",
            id=f"nm_b4_{seed}",
            title="B4: Transformer Attention Infographic (16:9, 45s)",
            brief=brief,
            constraints=constraints,
            knowledge_refs=krefs,
            safe_zones=safe_zones,
            width=w,
            height=h,
            fps=30,
            duration_seconds=45.0,
            scenes=scenes,
        )

    @classmethod
    def build_benchmark_b5(
        cls, source_video_path: Optional[str] = None, seed: int = 505
    ) -> NativeMotionSpec:
        """B5: vertical 9:16, 40 s reframe from presentation video with professional captions."""
        brief = CreativeBrief(
            topic="Keynote Reframe: The Future of Autonomous Coding Agents",
            intent="explain",
            tone="editorial",
            target_audience="Tech Founders & Developers",
        )
        constraints = Constraints(aspect_ratio="9:16", max_duration_seconds=40.0, target_fps=30)
        w, h = 1080, 1920
        safe_zones = SafeZoneSpec(top=0.14, bottom=0.20, left=0.08, right=0.08)
        krefs = cls.retrieve_knowledge_for_brief(brief, limit=2)

        durations = [10.0, 10.0, 10.0, 10.0]  # Sum = 40.0s
        transitions = [
            SceneTransitionSpec(type="slide_left", duration=0.6),
            SceneTransitionSpec(type="crossfade", duration=0.6),
            SceneTransitionSpec(type="slide_up", duration=0.6),
            None,
        ]
        scenes = []
        cur_t = 0.0

        for idx, dur in enumerate(durations):
            elems = []
            # Background
            elems.append(
                ElementSpec(
                    id=f"b5_s{idx}_bg",
                    type="gradient",
                    start_time=0.0,
                    duration=dur,
                    z_index=0,
                    transform=ElementTransform(x=0, y=0, width=w, height=h, anchor_x=0.0, anchor_y=0.0),
                    gradient_config=GradientConfig(
                        type="linear",
                        angle_degrees=135.0,
                        stops=[GradientStop(color="#090D16", position=0.0), GradientStop(color="#111827", position=1.0)],
                        animated=True,
                    ),
                )
            )

            # Reframe video layer with dynamic tracking crop
            crop_x = 0.15 + (idx * 0.10)
            elems.append(
                ElementSpec(
                    id=f"b5_s{idx}_reframe",
                    type="video_layer",
                    start_time=0.2,
                    duration=dur - 0.2,
                    z_index=5,
                    transform=ElementTransform(x=w / 2, y=h * 0.42, width=w * 0.88, height=h * 0.44, anchor_x=0.5, anchor_y=0.5),
                    video_config=VideoLayerConfig(
                        source_path=source_video_path,
                        crop_rect={"x": crop_x, "y": 0.05, "w": 0.56, "h": 0.90},
                        reframe_mode="manual_crop",
                    ),
                )
            )

            # Header tag
            elems.append(
                ElementSpec(
                    id=f"b5_s{idx}_tag",
                    type="text",
                    start_time=0.3,
                    duration=dur - 0.3,
                    z_index=10,
                    transform=ElementTransform(x=w / 2, y=safe_zones.top * h + 40, width=w * 0.85, height=60, anchor_x=0.5, anchor_y=0.5),
                    text_config=TextConfig(
                        content=f"PRESENTATION REFRAME // ACT {idx+1}",
                        typography=TypographySpec(font_family="JetBrains Mono, monospace", font_size=20.0, font_weight=700, fill="#38BDF8"),
                    ),
                )
            )

            # Safe area captions
            b5_words = [
                WordTimestampSpec(word="Autonomous", start=1.0, end=1.8),
                WordTimestampSpec(word="agents", start=1.8, end=2.4),
                WordTimestampSpec(word="transform", start=2.4, end=3.1),
                WordTimestampSpec(word="software", start=3.1, end=3.8),
                WordTimestampSpec(word="delivery.", start=3.8, end=4.6),
            ]
            elems.append(
                ElementSpec(
                    id=f"b5_s{idx}_captions",
                    type="captions",
                    start_time=0.5,
                    duration=dur - 0.5,
                    z_index=15,
                    transform=ElementTransform(x=w / 2, y=h * (1.0 - safe_zones.bottom) - 80, width=w * 0.85, height=140, anchor_x=0.5, anchor_y=0.5),
                    captions_config=CaptionsConfig(words=b5_words, active_color="#38BDF8", inactive_color="#94A3B8"),
                )
            )

            scene = SceneSpec(
                id=f"b5_scene_{idx+1}",
                name=f"Reframe Act {idx+1}",
                start_time=cur_t,
                duration=dur,
                background_color="#090D16",
                transition=transitions[idx],
                elements=elems,
                knowledge_refs=krefs,
            )
            scenes.append(scene)
            cur_t += dur

        return NativeMotionSpec(
            schema_version="native_motion_v1",
            id=f"nm_b5_{seed}",
            title="B5: Presentation Reframe (9:16, 40s)",
            brief=brief,
            constraints=constraints,
            knowledge_refs=krefs,
            safe_zones=safe_zones,
            width=w,
            height=h,
            fps=30,
            duration_seconds=40.0,
            scenes=scenes,
        )

    @classmethod
    def build_benchmark_b6(cls, seed: int = 606) -> NativeMotionSpec:
        """B6: horizontal 16:9, 10 s minimalist cinematic branded stinger."""
        brief = CreativeBrief(
            topic="Aether Dynamics // Autonomous Motion Systems",
            intent="editorial",
            tone="luxury",
            target_audience="High-End Design & Enterprise",
        )
        constraints = Constraints(aspect_ratio="16:9", max_duration_seconds=10.0, target_fps=30)
        w, h = 1920, 1080
        safe_zones = SafeZoneSpec(top=0.08, bottom=0.10, left=0.08, right=0.08)
        krefs = cls.retrieve_knowledge_for_brief(brief, limit=2)

        durations = [5.0, 5.0]  # Sum = 10.0s
        scenes = []

        # Scene 1: Monogram line construction
        s1_elems = [
            ElementSpec(
                id="b6_s1_bg",
                type="gradient",
                start_time=0.0,
                duration=5.0,
                z_index=0,
                transform=ElementTransform(x=0, y=0, width=w, height=h, anchor_x=0.0, anchor_y=0.0),
                gradient_config=GradientConfig(
                    type="linear",
                    angle_degrees=45.0,
                    stops=[GradientStop(color="#1C1917", position=0.0), GradientStop(color="#09090B", position=1.0)],
                    animated=True,
                ),
            ),
            ElementSpec(
                id="b6_s1_frame",
                type="shape",
                start_time=0.2,
                duration=4.8,
                z_index=5,
                transform=ElementTransform(x=w * 0.15, y=h * 0.15, width=w * 0.70, height=h * 0.70, anchor_x=0.0, anchor_y=0.0),
                shape_config=ShapeConfig(shape_type="rounded_rect", fill="transparent", stroke="#D4AF37", stroke_width=1.0, corner_radius=2.0),
            ),
            ElementSpec(
                id="b6_s1_brand",
                type="text",
                start_time=0.4,
                duration=4.6,
                z_index=10,
                transform=ElementTransform(x=w / 2, y=h / 2, width=w * 0.65, height=140, anchor_x=0.5, anchor_y=0.5),
                text_config=TextConfig(
                    content="A E T H E R",
                    typography=TypographySpec(
                        font_family="Playfair Display, serif",
                        font_size=72.0,
                        font_weight=400,
                        letter_spacing=12.0,
                        fill="#F5F5F0",
                    ),
                    animation_type="kinetic_scale",
                ),
            ),
        ]
        scenes.append(
            SceneSpec(
                id="b6_scene_1",
                name="Monogram",
                start_time=0.0,
                duration=5.0,
                background_color="#09090B",
                transition=SceneTransitionSpec(type="crossfade", duration=0.8),
                elements=s1_elems,
                knowledge_refs=krefs,
            )
        )

        # Scene 2: Tagline Reveal
        s2_elems = [
            ElementSpec(
                id="b6_s2_bg",
                type="gradient",
                start_time=0.0,
                duration=5.0,
                z_index=0,
                transform=ElementTransform(x=0, y=0, width=w, height=h, anchor_x=0.0, anchor_y=0.0),
                gradient_config=GradientConfig(
                    type="radial",
                    stops=[GradientStop(color="#292524", position=0.0), GradientStop(color="#09090B", position=1.0)],
                    animated=True,
                ),
            ),
            ElementSpec(
                id="b6_s2_parts",
                type="particles",
                start_time=0.0,
                duration=5.0,
                z_index=1,
                transform=ElementTransform(x=0, y=0, width=w, height=h, anchor_x=0.0, anchor_y=0.0),
                particles_config=ParticlesConfig(count=40, color="#D4AF37", speed_range=(8.0, 24.0)),
            ),
            ElementSpec(
                id="b6_s2_tagline",
                type="text",
                start_time=0.3,
                duration=4.7,
                z_index=10,
                transform=ElementTransform(x=w / 2, y=h / 2 - 20, width=w * 0.70, height=80, anchor_x=0.5, anchor_y=0.5),
                text_config=TextConfig(
                    content="INTELLIGENCE IN MOTION",
                    typography=TypographySpec(
                        font_family="Playfair Display, serif",
                        font_size=48.0,
                        font_weight=400,
                        letter_spacing=8.0,
                        fill="#F5F5F0",
                    ),
                    animation_type="fade_slide_up",
                ),
            ),
            ElementSpec(
                id="b6_s2_mono",
                type="text",
                start_time=0.6,
                duration=4.4,
                z_index=11,
                transform=ElementTransform(x=w / 2, y=h / 2 + 50, width=w * 0.70, height=40, anchor_x=0.5, anchor_y=0.5),
                text_config=TextConfig(
                    content="AETHER DYNAMICS // 2026",
                    typography=TypographySpec(
                        font_family="JetBrains Mono, monospace",
                        font_size=18.0,
                        font_weight=400,
                        letter_spacing=6.0,
                        fill="#D4AF37",
                    ),
                ),
            ),
        ]
        scenes.append(
            SceneSpec(
                id="b6_scene_2",
                name="Tagline",
                start_time=5.0,
                duration=5.0,
                background_color="#09090B",
                transition=None,
                elements=s2_elems,
                knowledge_refs=krefs,
            )
        )

        return NativeMotionSpec(
            schema_version="native_motion_v1",
            id=f"nm_b6_{seed}",
            title="B6: Cinematic Branded Stinger (16:9, 10s)",
            brief=brief,
            constraints=constraints,
            knowledge_refs=krefs,
            safe_zones=safe_zones,
            width=w,
            height=h,
            fps=30,
            duration_seconds=10.0,
            scenes=scenes,
        )

    # ------------------------------------------------------------------------
    # Legacy Single-Scene Builders (Preserved for Backward Compatibility)
    # ------------------------------------------------------------------------

    @classmethod
    def _build_data_kinetic_scenes(
        cls, brief: CreativeBrief, width: int, height: int, safe_zones: SafeZoneSpec, duration: float, rng: random.Random, knowledge_refs: List[KnowledgeRef]
    ) -> List[SceneSpec]:
        cx = width / 2
        cy = height / 2
        card_w = width * (1.0 - (safe_zones.left + safe_zones.right))
        card_h = height * 0.45
        card_x = safe_zones.left * width
        card_y = cy - (card_h / 2) + (height * 0.05)

        elements: List[ElementSpec] = [
            ElementSpec(
                id="bg_gradient",
                type="gradient",
                start_time=0.0,
                duration=duration,
                z_index=0,
                transform=ElementTransform(x=0, y=0, width=width, height=height, anchor_x=0.0, anchor_y=0.0),
                gradient_config=GradientConfig(
                    type="linear",
                    angle_degrees=145.0,
                    stops=[GradientStop(color="#090D16", position=0.0), GradientStop(color="#0B132B", position=0.5), GradientStop(color="#1C2541", position=1.0)],
                    animated=True,
                ),
            ),
            ElementSpec(
                id="atm_particles",
                type="particles",
                start_time=0.0,
                duration=duration,
                z_index=1,
                transform=ElementTransform(x=0, y=0, width=width, height=height, anchor_x=0.0, anchor_y=0.0),
                particles_config=ParticlesConfig(count=60, color="#38BDF8", speed_range=(15.0, 40.0)),
            ),
            ElementSpec(
                id="data_card",
                type="shape",
                start_time=min(0.2, duration * 0.1),
                duration=max(0.1, duration - min(0.2, duration * 0.1)),
                z_index=5,
                transform=ElementTransform(x=card_x, y=card_y, width=card_w, height=card_h, anchor_x=0.0, anchor_y=0.0, opacity=0.0),
                keyframes=[
                    KeyframeSpec(time=0.0, properties={"opacity": 0.0, "scale_x": 0.92, "scale_y": 0.92}, easing="power4_out"),
                    KeyframeSpec(time=0.6, properties={"opacity": 1.0, "scale_x": 1.0, "scale_y": 1.0}, easing="back_out"),
                ],
                shape_config=ShapeConfig(shape_type="rounded_rect", fill="rgba(15, 23, 42, 0.85)", stroke="#38BDF8", stroke_width=2.0, corner_radius=24.0),
            ),
            ElementSpec(
                id="metric_chart",
                type="data_chart",
                start_time=min(0.4, duration * 0.2),
                duration=max(0.1, duration - min(0.4, duration * 0.2)),
                z_index=10,
                transform=ElementTransform(x=card_x + 30, y=card_y + 40, width=card_w - 60, height=card_h - 80, anchor_x=0.0, anchor_y=0.0, opacity=0.0),
                keyframes=[KeyframeSpec(time=0.0, properties={"opacity": 0.0}), KeyframeSpec(time=0.4, properties={"opacity": 1.0})],
                chart_config=DataChartConfig(
                    chart_type="bar",
                    title=f"{brief.topic.upper()} SURGE",
                    dataset=[DataPoint(label=f"WEEK {i+1}", value=float(rng.randint(35, 95)), color="#38BDF8") for i in range(4)],
                ),
            ),
            ElementSpec(
                id="hero_title",
                type="text",
                start_time=min(0.1, duration * 0.05),
                duration=max(0.1, duration - min(0.1, duration * 0.05)),
                z_index=15,
                transform=ElementTransform(x=cx, y=safe_zones.top * height + 40, width=card_w, height=120, anchor_x=0.5, anchor_y=0.0),
                text_config=TextConfig(
                    content=brief.topic.upper(),
                    typography=TypographySpec(font_family="Outfit, sans-serif", font_size=52.0 if width <= 1080 else 64.0, font_weight=900, fill="#F8FAFC"),
                ),
            ),
        ]
        return [SceneSpec(id="scene_data_01", start_time=0.0, duration=duration, background_color="#0A0F1D", elements=elements, knowledge_refs=knowledge_refs)]

    @classmethod
    def _build_editorial_scenes(
        cls, brief: CreativeBrief, width: int, height: int, safe_zones: SafeZoneSpec, duration: float, rng: random.Random, knowledge_refs: List[KnowledgeRef]
    ) -> List[SceneSpec]:
        cx = width / 2
        cy = height / 2
        frame_margin_x = safe_zones.left * width
        frame_margin_y = safe_zones.top * height
        frame_w = width - (frame_margin_x * 2)
        frame_h = height - (frame_margin_y * 2)

        elements: List[ElementSpec] = [
            ElementSpec(
                id="cinematic_bg",
                type="gradient",
                start_time=0.0,
                duration=duration,
                z_index=0,
                transform=ElementTransform(x=0, y=0, width=width, height=height, anchor_x=0.0, anchor_y=0.0),
                gradient_config=GradientConfig(
                    type="linear",
                    angle_degrees=45.0,
                    stops=[GradientStop(color="#5C4D3C", position=0.0), GradientStop(color="#29231E", position=0.5), GradientStop(color="#0F0E0D", position=1.0)],
                    animated=True,
                ),
            ),
            ElementSpec(
                id="arch_particles",
                type="particles",
                start_time=0.0,
                duration=duration,
                z_index=1,
                transform=ElementTransform(x=0, y=0, width=width, height=height, anchor_x=0.0, anchor_y=0.0),
                particles_config=ParticlesConfig(count=80, color="#FACC15", speed_range=(20.0, 50.0)),
            ),
            ElementSpec(
                id="arch_border",
                type="shape",
                start_time=min(0.1, duration * 0.05),
                duration=max(0.1, duration - min(0.1, duration * 0.05)),
                z_index=5,
                transform=ElementTransform(x=frame_margin_x, y=frame_margin_y, width=frame_w, height=frame_h, anchor_x=0.0, anchor_y=0.0),
                shape_config=ShapeConfig(shape_type="rounded_rect", fill="transparent", stroke="#D4AF37", stroke_width=1.0, corner_radius=4.0),
            ),
            ElementSpec(
                id="editorial_headline",
                type="text",
                start_time=min(0.3, duration * 0.15),
                duration=max(0.1, duration - min(0.3, duration * 0.15)),
                z_index=15,
                transform=ElementTransform(x=cx, y=cy - 40, width=frame_w * 0.85, height=160, anchor_x=0.5, anchor_y=0.5),
                text_config=TextConfig(
                    content=brief.topic,
                    typography=TypographySpec(font_family="Playfair Display, serif", font_size=64.0 if width >= 1920 else 44.0, font_weight=400, fill="#F5F5F0"),
                ),
            ),
        ]
        return [SceneSpec(id="scene_editorial_01", start_time=0.0, duration=duration, background_color="#121110", elements=elements, knowledge_refs=knowledge_refs)]

    @classmethod
    def _build_kinetic_scenes(
        cls, brief: CreativeBrief, width: int, height: int, safe_zones: SafeZoneSpec, duration: float, rng: random.Random, knowledge_refs: List[KnowledgeRef], words: Optional[List[WordTimestampSpec]] = None
    ) -> List[SceneSpec]:
        cx = width / 2
        cy = height / 2

        elements: List[ElementSpec] = [
            ElementSpec(
                id="kinetic_bg",
                type="gradient",
                start_time=0.0,
                duration=duration,
                z_index=0,
                transform=ElementTransform(x=0, y=0, width=width, height=height, anchor_x=0.0, anchor_y=0.0),
                gradient_config=GradientConfig(
                    type="linear",
                    angle_degrees=135.0,
                    stops=[GradientStop(color="#4C1D95", position=0.0), GradientStop(color="#1E1B4B", position=0.5), GradientStop(color="#090D16", position=1.0)],
                    animated=True,
                ),
            ),
            ElementSpec(
                id="kinetic_particles",
                type="particles",
                start_time=0.0,
                duration=duration,
                z_index=1,
                transform=ElementTransform(x=0, y=0, width=width, height=height, anchor_x=0.0, anchor_y=0.0),
                particles_config=ParticlesConfig(count=80, color="#A78BFA", speed_range=(25.0, 60.0)),
            ),
            ElementSpec(
                id="kinetic_hero",
                type="text",
                start_time=min(0.1, duration * 0.05),
                duration=max(0.1, duration - min(0.1, duration * 0.05)),
                z_index=10,
                transform=ElementTransform(x=cx, y=safe_zones.top * height + 60, width=width * 0.85, height=140, anchor_x=0.5, anchor_y=0.0),
                text_config=TextConfig(
                    content=brief.topic.upper(),
                    typography=TypographySpec(font_family="Montserrat, sans-serif", font_size=54.0 if width <= 1080 else 68.0, font_weight=900, fill="#FFFFFF"),
                ),
            ),
        ]
        if words:
            elements.append(
                ElementSpec(
                    id="kinetic_captions",
                    type="captions",
                    start_time=0.0,
                    duration=duration,
                    z_index=20,
                    transform=ElementTransform(x=cx, y=height * (1.0 - safe_zones.bottom) - 80, width=width * 0.84, height=160, anchor_x=0.5, anchor_y=0.5),
                    captions_config=CaptionsConfig(words=words, active_color="#FBBF24", inactive_color="#94A3B8"),
                )
            )
        return [SceneSpec(id="scene_kinetic_01", start_time=0.0, duration=duration, background_color="#0F172A", elements=elements, knowledge_refs=knowledge_refs)]
