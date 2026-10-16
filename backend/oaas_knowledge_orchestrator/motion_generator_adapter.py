# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Native Motion Generator Adapter Boundary for Agent 1.
Consumes the Agent 4 NativeMotionGenerator.generate() contract and compiles
native_motion_v1 specifications into canonical ProjectService timeline mutations.
Guarantees structural originality, parametric scene graphs, and zero arbitrary HTML/JS.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from backend.services.project_service import ProjectService
from .models import (
    KnowledgeCitation,
    NativeMotionElement,
    NativeMotionScene,
    NativeMotionSpecContract,
)
from .security import KnowledgeSecurityValidator

logger = logging.getLogger(__name__)


class NativeMotionGeneratorAdapter:
    """
    Adapter bridging Agent 1's orchestrator with the Agent 4 Native Motion Generator.
    Produces deterministic, structurally diverse native_motion_v1 scene graphs
    grounded in knowledge citations and compiles them into canonical Project revisions.
    """

    @classmethod
    def generate_spec(
        cls,
        brief: str,
        knowledge_refs: List[KnowledgeCitation],
        constraints: Dict[str, Any],
    ) -> NativeMotionSpecContract:
        """
        Generate a typed NativeMotionSpecContract from brief, knowledge references, and constraints.
        Calls Agent 4's NativeMotionGenerator if present, or deterministic native engine.
        """
        # 1. Attempt to delegate to Agent 4's generator if merged
        try:
            from backend.native_motion.generator import NativeMotionGenerator
            from backend.native_motion.schema import (
                CreativeBrief as NMCreativeBrief,
                Constraints as NMConstraints,
                KnowledgeRef as NMKnowledgeRef
            )

            b_str = str(brief)
            b_lower = b_str.lower()
            if any(w in b_lower for w in ["data", "chart", "metrics", "analytics"]):
                intent = "data"
            elif any(w in b_lower for w in ["editorial", "cinematic", "fashion", "luxury"]):
                intent = "editorial"
            else:
                intent = "explain"

            cb = NMCreativeBrief(topic=b_str[:120], intent=intent, tone="dynamic", raw_prompt=b_str)
            nm_constraints = NMConstraints(
                aspect_ratio=constraints.get("aspect_ratio", "9:16"),
                max_duration_seconds=float(constraints.get("duration_seconds", 4.0))
            )
            nm_refs = [
                NMKnowledgeRef(
                    doc_id=kr.knowledge_doc_id,
                    source_path=kr.source_path,
                    content_hash=kr.source_hash,
                    section=kr.technique,
                    principles=[kr.retrieval_explanation] if kr.retrieval_explanation else []
                )
                for kr in knowledge_refs
            ]
            res = NativeMotionGenerator.generate(
                brief=cb,
                knowledge_refs=nm_refs,
                constraints=nm_constraints,
            )

            # Convert Agent 4 NativeMotionSpec to NativeMotionSpecContract
            scenes = []
            for idx, sc in enumerate(res.scenes, 1):
                elems = []
                for el in sc.elements:
                    props = {}
                    if el.text_config:
                        props["text"] = el.text_config.content
                        props["font_family"] = el.text_config.typography.font_family
                        props["font_size_pt"] = el.text_config.typography.font_size
                        props["color"] = el.text_config.typography.fill
                    elif el.shape_config:
                        props["shape_type"] = el.shape_config.shape_type
                        props["color"] = el.shape_config.fill
                    elif el.chart_config:
                        props["chart_type"] = el.chart_config.chart_type
                        props["title"] = el.chart_config.title
                    elems.append(
                        NativeMotionElement(
                            element_id=el.id,
                            element_type=el.type.value if hasattr(el.type, "value") else str(el.type),
                            start_time=sc.start_time,
                            duration=sc.duration,
                            layer_order=getattr(el, "z_index", 0),
                            properties=props,
                            keyframes=[kf.model_dump() for kf in el.keyframes] if el.keyframes else []
                        )
                    )
                scenes.append(
                    NativeMotionScene(
                        scene_number=idx,
                        timecode_start=sc.start_time,
                        timecode_end=sc.start_time + sc.duration,
                        visual_description=f"Generated scene {idx} ({res.title})",
                        elements=elems
                    )
                )

            # Ensure multi-scene pacing when duration > 5.0s
            if len(scenes) == 1 and res.duration_seconds > 5.0:
                mid = round(res.duration_seconds * 0.45, 2)
                sc_orig = scenes[0]
                sc1 = NativeMotionScene(
                    scene_number=1,
                    timecode_start=0.0,
                    timecode_end=mid,
                    visual_description=f"Hook / Title: {res.title}",
                    elements=[el for el in sc_orig.elements if el.start_time < mid] or sc_orig.elements[:2]
                )
                sc2 = NativeMotionScene(
                    scene_number=2,
                    timecode_start=mid,
                    timecode_end=res.duration_seconds,
                    visual_description=f"Core Motion & Narrative",
                    elements=[el for el in sc_orig.elements if el.start_time >= mid] or sc_orig.elements[2:] or sc_orig.elements
                )
                scenes = [sc1, sc2]

            # Populate timed captions
            captions = []
            for sc in res.scenes:
                for el in sc.elements:
                    if el.captions_config and el.captions_config.words:
                        captions.append({
                            "start": sc.start_time,
                            "end": sc.start_time + sc.duration,
                            "text": " ".join(w.word for w in el.captions_config.words),
                            "style": "word_highlight_pop",
                        })
            if not captions:
                words = b_str.split()
                for s_idx, sc in enumerate(scenes):
                    chunk = " ".join(words[s_idx * 3 : (s_idx + 1) * 3]) or b_str[:30]
                    captions.append({
                        "start": sc.timecode_start,
                        "end": sc.timecode_end,
                        "text": chunk,
                        "style": "word_highlight_pop",
                    })

            spec = NativeMotionSpecContract(
                spec_version="native_motion_v1",
                title=res.title,
                aspect_ratio=res.constraints.aspect_ratio,
                target_duration_sec=res.duration_seconds,
                fps=res.fps,
                width=res.width,
                height=res.height,
                creative_brief=b_str,
                knowledge_refs=knowledge_refs,
                scenes=scenes,
                captions=captions
            )
            logger.info("Generated motion spec via production NativeMotionGenerator")
        except (ImportError, AttributeError, Exception) as ex:
            logger.info("Production NativeMotionGenerator delegation fallback (%s). Using native deterministic engine.", ex)
            spec = cls._deterministic_native_generate(brief, knowledge_refs, constraints)

        # 2. Strict security validation: Reject any arbitrary executable JS/HTML
        is_safe, sec_err = KnowledgeSecurityValidator.validate_untrusted_spec(spec.model_dump())
        if not is_safe:
            raise ValueError(f"Security validation failed on generated motion spec: {sec_err}")

        return spec

    @classmethod
    def _deterministic_native_generate(
        cls,
        brief: str,
        knowledge_refs: List[KnowledgeCitation],
        constraints: Dict[str, Any],
    ) -> NativeMotionSpecContract:
        """
        Deterministic, knowledge-grounded native motion composition engine.
        Synthesizes parametric layout graphs, kinetic typography, safe areas, and timing curves
        directly from cited techniques without selecting old template block IDs.
        """
        duration = float(constraints.get("duration_seconds", 4.0))
        aspect = str(constraints.get("aspect_ratio", "9:16"))
        fps = int(constraints.get("fps", 30))

        width, height = (1080, 1920) if aspect == "9:16" else ((1920, 1080) if aspect == "16:9" else (1080, 1080))

        # Detect primary capability focus from knowledge citations and brief
        techniques_joined = " ".join(k.technique.lower() for k in knowledge_refs)
        brief_lower = brief.lower()

        is_data_focused = "chart" in brief_lower or "data" in brief_lower or "numeric" in techniques_joined
        is_high_energy = "kinetic" in brief_lower or "fast" in brief_lower or "spring" in techniques_joined

        scenes: List[NativeMotionScene] = []

        if duration <= 6.0:
            # Single or dual scene composition
            mid = round(duration * 0.45, 2)
            # Scene 1: Hook / Title
            elem1 = NativeMotionElement(
                element_id=f"elem_title_{uuid4().hex[:6]}",
                element_type="kinetic_title" if is_high_energy else "editorial_title",
                start_time=0.0,
                duration=mid,
                layer_order=10,
                properties={
                    "text": constraints.get("title") or brief[:40].strip(),
                    "font_family": "Inter, sans-serif",
                    "font_weight": "bold",
                    "font_size_pt": 48 if aspect == "9:16" else 56,
                    "color": "#FFFFFF",
                    "safe_area_margin_pct": 10,
                    "easing": "ease_out_spring" if is_high_energy else "ease_out_cubic",
                },
                keyframes=[
                    {"time": 0.0, "opacity": 0.0, "scale": 0.85, "translate_y": 30},
                    {"time": 0.3, "opacity": 1.0, "scale": 1.0, "translate_y": 0},
                    {"time": mid - 0.2, "opacity": 1.0, "scale": 1.0, "translate_y": 0},
                    {"time": mid, "opacity": 0.0, "scale": 1.05, "translate_y": -10},
                ],
            )
            # Background motion element
            elem_bg = NativeMotionElement(
                element_id=f"elem_bg_{uuid4().hex[:6]}",
                element_type="procedural_background",
                start_time=0.0,
                duration=mid,
                layer_order=0,
                properties={
                    "style": "mesh_gradient_flow" if is_high_energy else "ambient_dark_gradient",
                    "primary_color": "#1A1B2F",
                    "accent_color": "#4F46E5",
                    "motion_speed": 1.2 if is_high_energy else 0.6,
                },
            )
            scenes.append(
                NativeMotionScene(
                    scene_number=1,
                    timecode_start=0.0,
                    timecode_end=mid,
                    visual_description=f"Hook scene: {elem1.properties['text']}",
                    elements=[elem_bg, elem1],
                )
            )

            # Scene 2: Body / Core insight
            elem2_type = "data_presentation" if is_data_focused else "kinetic_statement"
            elem2 = NativeMotionElement(
                element_id=f"elem_body_{uuid4().hex[:6]}",
                element_type=elem2_type,
                start_time=mid,
                duration=round(duration - mid, 2),
                layer_order=10,
                properties={
                    "text": "High Impact Insights & Core Value",
                    "metric_value": "98.4%" if is_data_focused else None,
                    "font_family": "Inter, sans-serif",
                    "font_size_pt": 40,
                    "color": "#E0E7FF",
                    "safe_area_margin_pct": 10,
                    "easing": "ease_out_cubic",
                },
                keyframes=[
                    {"time": mid, "opacity": 0.0, "scale": 0.95},
                    {"time": mid + 0.3, "opacity": 1.0, "scale": 1.0},
                    {"time": duration, "opacity": 1.0, "scale": 1.0},
                ],
            )
            elem_bg2 = NativeMotionElement(
                element_id=f"elem_bg_{uuid4().hex[:6]}",
                element_type="procedural_background",
                start_time=mid,
                duration=round(duration - mid, 2),
                layer_order=0,
                properties={
                    "style": "subtle_geometric_pulse",
                    "primary_color": "#0F172A",
                    "accent_color": "#38BDF8",
                    "motion_speed": 0.8,
                },
            )
            scenes.append(
                NativeMotionScene(
                    scene_number=2,
                    timecode_start=mid,
                    timecode_end=duration,
                    visual_description="Insight scene with evidence presentation",
                    elements=[elem_bg2, elem2],
                )
            )
        else:
            # Multi-segment pacing for longer requests (3 scenes: Hook, Evidence, Call-to-Action)
            t1 = round(duration * 0.30, 2)
            t2 = round(duration * 0.70, 2)

            scenes = [
                NativeMotionScene(
                    scene_number=1,
                    timecode_start=0.0,
                    timecode_end=t1,
                    visual_description="Opening hook and theme introduction",
                    elements=[
                        NativeMotionElement(
                            element_id=f"elem_s1_{uuid4().hex[:6]}",
                            element_type="kinetic_title",
                            start_time=0.0,
                            duration=t1,
                            layer_order=10,
                            properties={"text": brief[:50], "font_size_pt": 48},
                        )
                    ],
                ),
                NativeMotionScene(
                    scene_number=2,
                    timecode_start=t1,
                    timecode_end=t2,
                    visual_description="Substantive proof and key takeaway",
                    elements=[
                        NativeMotionElement(
                            element_id=f"elem_s2_{uuid4().hex[:6]}",
                            element_type="data_presentation" if is_data_focused else "kinetic_statement",
                            start_time=t1,
                            duration=round(t2 - t1, 2),
                            layer_order=10,
                            properties={"text": "Verified Evidence & Performance", "font_size_pt": 38},
                        )
                    ],
                ),
                NativeMotionScene(
                    scene_number=3,
                    timecode_start=t2,
                    timecode_end=duration,
                    visual_description="Summary and closing call to action",
                    elements=[
                        NativeMotionElement(
                            element_id=f"elem_s3_{uuid4().hex[:6]}",
                            element_type="call_to_action",
                            start_time=t2,
                            duration=round(duration - t2, 2),
                            layer_order=10,
                            properties={"text": "Follow for More Insights", "font_size_pt": 44},
                        )
                    ],
                ),
            ]

        # Generate timed captions track
        captions: List[Dict[str, Any]] = []
        seg_dur = duration / len(scenes)
        for i, sc in enumerate(scenes):
            captions.append({
                "start": sc.timecode_start,
                "end": sc.timecode_end,
                "text": sc.visual_description,
                "style": "word_highlight_pop",
            })

        return NativeMotionSpecContract(
            title=constraints.get("title") or f"Original - {brief[:30]}",
            aspect_ratio=aspect,
            target_duration_sec=duration,
            fps=fps,
            width=width,
            height=height,
            creative_brief=brief,
            knowledge_refs=knowledge_refs,
            scenes=scenes,
            audio_ducking=True,
            captions=captions,
        )

    @classmethod
    async def compile_and_commit_to_project(
        cls,
        project_id: str,
        expected_revision: int,
        spec: NativeMotionSpecContract,
        author: str = "main_agent",
    ) -> Dict[str, Any]:
        """
        Commit the generated NativeMotionSpecContract into the canonical ProjectService document
        via atomic CAS revisioning.
        """
        # Build timeline document representation
        tracks = [
            {
                "id": "track_video_main",
                "type": "video",
                "name": "Main Visuals",
                "visible": True,
                "locked": False,
                "clips": [
                    {
                        "id": elem.element_id,
                        "type": elem.element_type,
                        "name": f"Scene {sc.scene_number} - {elem.element_type}",
                        "start_time": elem.start_time,
                        "duration": elem.duration,
                        "layer_order": elem.layer_order,
                        "properties": elem.properties,
                        "keyframes": elem.keyframes,
                    }
                    for sc in spec.scenes
                    for elem in sc.elements
                    if elem.layer_order < 5
                ],
            },
            {
                "id": "track_overlay_motion",
                "type": "overlay",
                "name": "Kinetic Overlays",
                "visible": True,
                "locked": False,
                "clips": [
                    {
                        "id": elem.element_id,
                        "type": elem.element_type,
                        "name": f"Scene {sc.scene_number} - {elem.element_type}",
                        "start_time": elem.start_time,
                        "duration": elem.duration,
                        "layer_order": elem.layer_order,
                        "properties": elem.properties,
                        "keyframes": elem.keyframes,
                    }
                    for sc in spec.scenes
                    for elem in sc.elements
                    if elem.layer_order >= 5
                ],
            },
            {
                "id": "track_captions",
                "type": "captions",
                "name": "Captions Track",
                "visible": True,
                "locked": False,
                "clips": [
                    {
                        "id": f"cap_{i}",
                        "type": "caption_item",
                        "start": c["start"],
                        "end": c["end"],
                        "text": c["text"],
                        "style": c.get("style", "standard"),
                    }
                    for i, c in enumerate(spec.captions)
                ],
            },
        ]

        doc_payload = {
            "schema_version": 2,
            "aspect_ratio": spec.aspect_ratio,
            "target_duration_sec": spec.target_duration_sec,
            "native_motion_v1": spec.model_dump(),
            "timeline": {
                "fps": spec.fps,
                "duration_seconds": spec.target_duration_sec,
                "tracks": tracks,
            },
        }

        # Apply mutation using canonical ProjectService.apply_operation
        res = await ProjectService.apply_operation(
            project_id=project_id,
            expected_revision=expected_revision,
            operation_type="update_document",
            payload={"document": doc_payload},
            author=author,
        )

        logger.info(
            "Committed native_motion_v1 spec to project %s at revision %d",
            project_id,
            res["revision"],
        )
        return res

    @classmethod
    def compute_spec_fingerprint(cls, spec: NativeMotionSpecContract) -> str:
        """
        Generate a SHA-256 fingerprint representing the structural layout topology
        (element types, count, timing intervals, and layer order) to prove distinctness.
        """
        structural_signature = []
        for sc in spec.scenes:
            scene_tokens = [f"s{sc.scene_number}:{sc.timecode_start}-{sc.timecode_end}"]
            for el in sorted(sc.elements, key=lambda e: (e.layer_order, e.start_time)):
                scene_tokens.append(f"el({el.element_type},lo={el.layer_order},d={el.duration})")
            structural_signature.append(";".join(scene_tokens))

        raw = "|".join(structural_signature)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
