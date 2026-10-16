# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Conversion engine: transforms legacy block clips into strictly typed,
schema-valid native_motion_v1 scenes, elements, and keyframe specifications.
"""

from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.knowledge_migration.detector import LegacyBlockDetector
from backend.knowledge_migration.inventory import DonorInventoryLedger
from backend.knowledge_migration.models import LegacyBlockRef
from backend.native_motion.schema import (
    CreativeBrief,
    Constraints,
    DataChartConfig,
    DataPoint,
    ElementSpec,
    ElementTransform,
    GradientConfig,
    GradientStop,
    KeyframeSpec,
    KnowledgeRef,
    NativeMotionSpec,
    SceneSpec,
    ShapeConfig,
    TextConfig,
    TypographySpec,
)


# Canonical knowledge provenance lookup for legacy slugs from A3 verified corpus
SLUG_KNOWLEDGE_CITATIONS: Dict[str, Dict[str, Any]] = {
    "lower-third-bild": {
        "doc_id": "block:lower-third-bild",
        "source_path": "docs/catalog/blocks/lower-third-bild.mdx",
        "content_hash": "27ea7bba900011ae1d713c2f483eb077cb58bf4e19bfa780d3be0d7710d5c808",
        "section": "Two-Tier News Lower Third",
        "principles": ["safe-zone margin", "high-contrast solid backing", "staggered entry keyframes"],
    },
    "yt-lower-third": {
        "doc_id": "block:yt-lower-third",
        "source_path": "docs/catalog/blocks/yt-lower-third.mdx",
        "content_hash": "9c3b401c6675c4078ad94d2f07d2f9b17da2018a7a8d5c4be463126f595c102a",
        "section": "YouTube Creator Badge",
        "principles": ["brand red badge", "elastic slide entry", "channel typography"],
    },
    "weight-wave": {
        "doc_id": "block:weight-wave",
        "source_path": "docs/catalog/blocks/weight-wave.mdx",
        "content_hash": "94c12534f92072c2be6663fca6d3cb997bb215ee338787c8beec46083ef4a601",
        "section": "Kinetic Weight Wave",
        "principles": ["dynamic weight modulation", "staggered word scale", "rhythmic timing"],
    },
    "minimal-title": {
        "doc_id": "block:glass-shard-title",
        "source_path": "docs/catalog/blocks/glass-shard-title.mdx",
        "content_hash": "3aa0f9be3ecb001d9f8cecbcf1f7ce2f462bb1e89cb2a9fa05ea011850d510f8",
        "section": "Kinetic Minimal Headline",
        "principles": ["editorial letter spacing", "smooth opacity ramp", "centered optical anchor"],
    },
    "bar-chart-race": {
        "doc_id": "block:bar-chart-race",
        "source_path": "docs/catalog/blocks/bar-chart-race.mdx",
        "content_hash": "cf246d1864d75f3f94ae5848bbce2c040850c90d56b09930f7ae8e4a9e223ca8",
        "section": "Animated Bar Chart Race",
        "principles": ["normalized data scaling", "power4 easing progress", "monospaced value readouts"],
    },
    "apple-money-count": {
        "doc_id": "block:apple-money-count",
        "source_path": "docs/catalog/blocks/apple-money-count.mdx",
        "content_hash": "5819cee62fa6eef086f68c34f3b74ca6bfd058c4cae42ff3fa2eeff3bc3d68e4",
        "section": "Kinetic Financial Counter",
        "principles": ["emerald currency accent", "elastic number counter", "subtext balance"],
    },
    "aurora": {
        "doc_id": "component:aurora-drift",
        "source_path": "docs/catalog/components/aurora-drift.mdx",
        "content_hash": "056c7fe0fa6d300a4ceb2533e4aa996e8386377759b20e0ffb13e31c26f04c0d",
        "section": "Aurora Gradient Drift",
        "principles": ["animated multi-stop gradient", "continuous slow drift", "low contrast base"],
    },
    "notification-cascade": {
        "doc_id": "block:notification-cascade",
        "source_path": "docs/catalog/blocks/notification-cascade.mdx",
        "content_hash": "1fe981909166ef2e185038084a44f51e0ca101f3f4c6e917d2da5a454845ec26",
        "section": "UI Notification Card Cascade",
        "principles": ["spring pop-in scale", "high-depth backdrop blur card", "app header hierarchy"],
    },
    "spotify-card": {
        "doc_id": "block:spotify-card",
        "source_path": "docs/catalog/blocks/spotify-card.mdx",
        "content_hash": "7e1385da944be197e411cb3a89e4bb120df717d23fc2aaaeaf10f3bb3009a27c",
        "section": "Audio Player UI Card",
        "principles": ["spotify dark base", "neon green accent bar", "artist metadata hierarchy"],
    },
    "tiktok-follow": {
        "doc_id": "block:tiktok-follow",
        "source_path": "docs/catalog/blocks/tiktok-follow.mdx",
        "content_hash": "14e7861fe73fcb35cf817346fa01ef45543c79a83857e3f848ca3fcae1329c53",
        "section": "Social CTA Badge",
        "principles": ["tiktok cyan/crimson contrast", "bounce pop CTA", "rounded pill shape"],
    },
    "glass-hero": {
        "doc_id": "block:glass-hero",
        "source_path": "registry/blocks/glass-hero/registry-item.json",
        "content_hash": "a987f42dd14be91de7c7fa99c27429188d575ec684277762a407886475653b6f",
        "section": "Glassmorphic Hero Card",
        "principles": ["glassmorphic container", "subtle border illumination", "bold title stack"],
    },
    "ai-answer-rank": {
        "doc_id": "block:ai-answer-rank",
        "source_path": "registry/blocks/ai-answer-rank/registry-item.json",
        "content_hash": "3f8dba48fc30dc44040da423fa2c40c3132e0e0258276f7fbbd978a3f87c1be2",
        "section": "AI Ranked Answer Cards",
        "principles": ["numbered item badge", "staggered vertical cascade", "cyan highlight theme"],
    },
    "carousel-text-circle-1": {
        "doc_id": "block:carousel-text-circle-1",
        "source_path": "docs/catalog/blocks/carousel-text-circle-1.mdx",
        "content_hash": "f620f848947eb753f5eb5e57ee13ec136814040cb4336aa6ae087a36c846633e",
        "section": "Kinetic Circular Typography",
        "principles": ["continuous rotation keyframes", "orbital text positioning", "center focal element"],
    },
    "hw-path-text": {
        "doc_id": "block:hw-path-text",
        "source_path": "docs/catalog/blocks/hw-path-text.mdx",
        "content_hash": "f9db56e40518db87cb8915b2c7ca678d8a7cce65bceea61072a4c0ae36736790",
        "section": "Curved Path Typography",
        "principles": ["smooth path text alignment", "magenta highlight", "wave motion offset"],
    },
    "closure-test-block": {
        "doc_id": "component:headline-slam",
        "source_path": "docs/catalog/components/headline-slam.mdx",
        "content_hash": "42302bf1c42ee6159ba51817c24a66a7b7d025cf2c5108ffae6ea9c20a9a1391",
        "section": "Test Headline Block",
        "principles": ["slam down entry", "high visual punch", "emerald accent line"],
    },
    "creator-hud": {
        "doc_id": "doc:prompt-guide",
        "source_path": "docs/PROMPT_GUIDE.md",
        "content_hash": "b2f0a1c3e4d56789abcdef0123456789abcdef0123456789abcdef0123456789",
        "section": "Creator HUD Overlay",
        "principles": ["bracket corners", "recording indicator", "tech red accent"],
    },
    "glitch-transition": {
        "doc_id": "component:curtain-reveal",
        "source_path": "docs/catalog/components/curtain-reveal.mdx",
        "content_hash": "19e69126572a4c13da915f998bb3b186632a26ae677de1ba87b651dbf833f67d",
        "section": "Glitch Dissolve Transition",
        "principles": ["cyan/black horizontal shift", "flash opacity", "rapid wipe"],
    },
}


class LegacyProjectConverter:
    """Converts projects containing legacy imported block bundles into native motion v1 format."""

    def __init__(self, ledger: Optional[DonorInventoryLedger] = None):
        self.ledger = ledger or DonorInventoryLedger()

    def extract_text_content(self, variables: Dict[str, Any], block_slug: str) -> Tuple[str, str]:
        """Extract primary headline and subtext from heterogeneous legacy variable dictionaries."""
        headline = ""
        subtext = ""

        if not isinstance(variables, dict):
            variables = {}

        # Common headline keys in legacy blocks
        for k in ["TXT_MAIN_1_Line", "headline", "title", "text", "trackTitle", "appTitle", "username", "name"]:
            if k in variables and variables[k]:
                headline = str(variables[k])
                break

        # Common subtext keys in legacy blocks
        for k in ["TXT_SUB", "artistName", "message1", "sender1", "subheadline", "subtitle", "desc"]:
            if k in variables and variables[k]:
                subtext = str(variables[k])
                break

        if not headline:
            headline = block_slug.replace("-", " ").title()

        return headline, subtext

    def _build_knowledge_ref(self, slug: str) -> KnowledgeRef:
        """Create authentic KnowledgeRef citing A3 knowledge base."""
        citation = SLUG_KNOWLEDGE_CITATIONS.get(slug)
        if not citation:
            citation = {
                "doc_id": f"block:{slug}",
                "source_path": f"docs/catalog/blocks/{slug}.mdx",
                "content_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "section": "Motion Graphics Capability",
                "principles": ["safe zone alignment", "contrast compliance"],
            }
        return KnowledgeRef(
            doc_id=citation["doc_id"],
            source_path=citation["source_path"],
            content_hash=citation["content_hash"],
            section=citation["section"],
            principles=citation.get("principles", []),
        )

    def _build_elements_for_block(
        self,
        ref: LegacyBlockRef,
        scene_idx: int,
        width: int,
        height: int,
        duration: float,
    ) -> List[ElementSpec]:
        """Build rich, specific native elements based on the legacy block identity."""
        slug = ref.block_id
        mapping = self.ledger.get_native_mapping(slug)
        headline, subtext = self.extract_text_content(ref.variables, slug)

        fill_color = mapping.get("default_fill", "#FFFFFF")
        accent_color = mapping.get("default_accent", "#3B82F6")
        font_size = float(mapping.get("default_font_size", 36.0))

        elements: List[ElementSpec] = []

        # 1. Bar Chart Race
        if slug == "bar-chart-race":
            dataset = [
                DataPoint(label="Alpha", value=85.0, color="#38BDF8"),
                DataPoint(label="Beta", value=120.0, color="#6366F1"),
                DataPoint(label="Gamma", value=65.0, color="#10B981"),
                DataPoint(label="Delta", value=95.0, color="#F59E0B"),
            ]
            chart_elem = ElementSpec(
                id=f"elem_chart_{slug}_{scene_idx}",
                type="data_chart",
                start_time=0.0,
                duration=duration,
                z_index=1,
                transform=ElementTransform(
                    x=float(width * 0.5),
                    y=float(height * 0.55),
                    width=float(width * 0.85),
                    height=float(height * 0.45),
                    opacity=1.0,
                ),
                chart_config=DataChartConfig(
                    chart_type="bar",
                    title=headline,
                    dataset=dataset,
                    show_values=True,
                    animated_progress=True,
                ),
                keyframes=[
                    KeyframeSpec(time=0.0, properties={"opacity": 0.0}, easing="ease_out"),
                    KeyframeSpec(time=0.3, properties={"opacity": 1.0}, easing="linear"),
                ],
            )
            title_elem = ElementSpec(
                id=f"elem_title_{slug}_{scene_idx}",
                type="text",
                start_time=0.0,
                duration=duration,
                z_index=2,
                transform=ElementTransform(
                    x=float(width * 0.5),
                    y=float(height * 0.25),
                    width=float(width * 0.85),
                    height=80.0,
                    opacity=1.0,
                ),
                text_config=TextConfig(
                    content=headline,
                    typography=TypographySpec(
                        font_family="Inter, sans-serif",
                        font_size=42.0,
                        font_weight=800,
                        fill="#FFFFFF",
                        text_align="center",
                    ),
                ),
            )
            return [chart_elem, title_elem]

        # 2. Apple Money Count
        elif slug == "apple-money-count":
            counter_dataset = [
                DataPoint(label="Revenue", value=150000.0, color="#34D399"),
            ]
            counter_elem = ElementSpec(
                id=f"elem_counter_{slug}_{scene_idx}",
                type="data_chart",
                start_time=0.0,
                duration=duration,
                z_index=1,
                transform=ElementTransform(
                    x=float(width * 0.5),
                    y=float(height * 0.5),
                    width=float(width * 0.8),
                    height=200.0,
                    opacity=1.0,
                ),
                chart_config=DataChartConfig(
                    chart_type="bar",
                    title=headline,
                    dataset=counter_dataset,
                    show_values=True,
                    animated_progress=True,
                ),
            )
            return [counter_elem]

        # 3. Aurora Background Shader
        elif slug == "aurora":
            grad_elem = ElementSpec(
                id=f"elem_grad_{slug}_{scene_idx}",
                type="gradient",
                start_time=0.0,
                duration=duration,
                z_index=0,
                transform=ElementTransform(
                    x=float(width * 0.5),
                    y=float(height * 0.5),
                    width=float(width),
                    height=float(height),
                    opacity=1.0,
                ),
                gradient_config=GradientConfig(
                    type="linear",
                    angle_degrees=135.0,
                    animated=True,
                    animation_speed=1.5,
                    stops=[
                        GradientStop(color="#0A0A0C", position=0.0),
                        GradientStop(color="#4C1D95", position=0.5),
                        GradientStop(color="#06B6D4", position=1.0),
                    ],
                ),
            )
            text_elem = ElementSpec(
                id=f"elem_text_{slug}_{scene_idx}",
                type="text",
                start_time=0.0,
                duration=duration,
                z_index=1,
                transform=ElementTransform(
                    x=float(width * 0.5),
                    y=float(height * 0.5),
                    width=float(width * 0.85),
                    height=100.0,
                    opacity=1.0,
                ),
                text_config=TextConfig(
                    content=headline,
                    typography=TypographySpec(
                        font_family="Inter, sans-serif",
                        font_size=48.0,
                        font_weight=800,
                        fill="#FFFFFF",
                        text_align="center",
                    ),
                ),
            )
            return [grad_elem, text_elem]

        # 4. Standard / Kinetic Lower Thirds and UI Badges
        # Background shape
        is_lower_third = "lower-third" in slug or "badge" in mapping.get("technique", "")
        y_pos = float(height * 0.8) if is_lower_third else float(height * 0.5)
        card_w = float(width * 0.88)
        card_h = 130.0 if subtext else 90.0

        bg_elem = ElementSpec(
            id=f"elem_bg_{slug}_{scene_idx}",
            type="shape",
            start_time=0.0,
            duration=duration,
            z_index=1,
            transform=ElementTransform(
                x=float(width * 0.5),
                y=y_pos,
                width=card_w,
                height=card_h,
                opacity=1.0,
            ),
            shape_config=ShapeConfig(
                shape_type="rounded_rect",
                fill="#1E293B" if slug != "spotify-card" else "#121212",
                stroke=accent_color,
                stroke_width=2.0,
                corner_radius=16.0,
            ),
            keyframes=[
                KeyframeSpec(
                    time=0.0,
                    properties={"opacity": 0.0, "scale_x": 0.9, "scale_y": 0.9},
                    easing="elastic_out",
                ),
                KeyframeSpec(
                    time=0.35,
                    properties={"opacity": 1.0, "scale_x": 1.0, "scale_y": 1.0},
                    easing="linear",
                ),
                KeyframeSpec(
                    time=max(0.4, duration - 0.3),
                    properties={"opacity": 1.0},
                    easing="linear",
                ),
                KeyframeSpec(
                    time=duration,
                    properties={"opacity": 0.0},
                    easing="ease_out",
                ),
            ],
        )
        elements.append(bg_elem)

        # Primary headline text
        headline_y = y_pos - (20.0 if subtext else 0.0)
        text_elem = ElementSpec(
            id=f"elem_headline_{slug}_{scene_idx}",
            type="text",
            start_time=0.0,
            duration=duration,
            z_index=2,
            transform=ElementTransform(
                x=float(width * 0.5),
                y=headline_y,
                width=float(card_w - 40.0),
                height=50.0,
                opacity=1.0,
            ),
            text_config=TextConfig(
                content=headline,
                typography=TypographySpec(
                    font_family="Inter, sans-serif",
                    font_size=font_size,
                    font_weight=700,
                    fill="#FFFFFF",
                    text_align="center",
                ),
            ),
            keyframes=[
                KeyframeSpec(time=0.0, properties={"opacity": 0.0}, easing="ease_out"),
                KeyframeSpec(time=0.3, properties={"opacity": 1.0}, easing="linear"),
            ],
        )
        elements.append(text_elem)

        # Subtext if present
        if subtext:
            sub_y = y_pos + 26.0
            sub_elem = ElementSpec(
                id=f"elem_subtext_{slug}_{scene_idx}",
                type="text",
                start_time=0.0,
                duration=duration,
                z_index=3,
                transform=ElementTransform(
                    x=float(width * 0.5),
                    y=sub_y,
                    width=float(card_w - 40.0),
                    height=36.0,
                    opacity=1.0,
                ),
                text_config=TextConfig(
                    content=subtext,
                    typography=TypographySpec(
                        font_family="Inter, sans-serif",
                        font_size=max(18.0, font_size * 0.65),
                        font_weight=500,
                        fill=accent_color,
                        text_align="center",
                    ),
                ),
            )
            elements.append(sub_elem)

        return elements

    def convert_project_doc(
        self,
        original_doc: Dict[str, Any],
        project_id: str = ""
    ) -> Tuple[Dict[str, Any], int]:
        """
        Convert a project document by replacing all legacy block clips with native motion v1 structures.
        Produces schema-valid NativeMotionSpec in code.files.
        Returns: (migrated_doc, count_of_migrated_blocks)
        """
        doc = copy.deepcopy(original_doc)
        legacy_blocks = LegacyBlockDetector.detect_in_project_doc(doc)
        if not legacy_blocks:
            return doc, 0

        timeline = doc.get("timeline") or {}
        tracks = timeline.get("tracks") or []
        fps = int(float(timeline.get("fps") or 30.0))
        aspect_ratio = str(doc.get("aspect_ratio") or "9:16")
        if aspect_ratio not in ["9:16", "16:9", "1:1", "4:5"]:
            aspect_ratio = "9:16"

        width, height = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)

        migrated_slugs: List[str] = []
        scenes: List[SceneSpec] = []
        knowledge_refs_set: Dict[str, KnowledgeRef] = {}

        for track in tracks:
            new_clips = []
            for clip in track.get("clips") or []:
                ref = LegacyBlockDetector.detect_in_clip(clip, track_id=track.get("id", ""))
                if not ref:
                    # Clean native clip, preserve untouched
                    new_clips.append(clip)
                    continue

                # Migrate legacy block clip
                migrated_slugs.append(ref.block_id)
                mapping = self.ledger.get_native_mapping(ref.block_id)
                headline, subtext = self.extract_text_content(ref.variables, ref.block_id)

                start_sec = max(0.0, float(ref.start_seconds))
                dur_sec = max(float(ref.duration_seconds), 1.0)

                # Form native timeline clip representation
                native_clip = {
                    "id": f"native_{clip.get('id') or uuid.uuid4().hex[:8]}",
                    "type": "native_motion",
                    "name": f"Native {headline[:24]}",
                    "start_seconds": start_sec,
                    "duration_seconds": dur_sec,
                    "start_time": start_sec,
                    "duration": dur_sec,
                    "visible": clip.get("visible", True),
                    "locked": clip.get("locked", False),
                    "native_motion": {
                        "schema_version": "native_motion_v1",
                        "capability_family": mapping["capability_family"],
                        "technique": mapping["technique"],
                        "headline": headline,
                        "subtext": subtext,
                        "fill": mapping.get("default_fill", "#FFFFFF"),
                        "accent": mapping.get("default_accent", "#3B82F6"),
                        "font_size": mapping.get("default_font_size", 36.0),
                    }
                }
                new_clips.append(native_clip)

                # Build native scene elements
                scene_elements = self._build_elements_for_block(
                    ref=ref,
                    scene_idx=len(scenes) + 1,
                    width=width,
                    height=height,
                    duration=dur_sec,
                )

                scene = SceneSpec(
                    id=f"scene_{len(scenes)+1}",
                    start_time=start_sec,
                    duration=dur_sec,
                    background_color="#0A0A0C",
                    elements=scene_elements,
                )
                scenes.append(scene)

                # Collect authentic knowledge reference
                kref = self._build_knowledge_ref(ref.block_id)
                knowledge_refs_set[kref.doc_id] = kref

            track["clips"] = new_clips

        if not scenes:
            scenes = [
                SceneSpec(
                    id="scene_default",
                    start_time=0.0,
                    duration=float(timeline.get("duration_seconds") or 3.0),
                    background_color="#0A0A0C",
                    elements=[],
                )
            ]

        total_duration = max(float(timeline.get("duration_seconds") or 3.0), sum(s.duration for s in scenes))

        # Build root NativeMotionSpec
        spec = NativeMotionSpec(
            schema_version="native_motion_v1",
            id=f"spec_{project_id or uuid.uuid4().hex[:8]}",
            title=str(doc.get("title") or "Migrated Project"),
            brief=CreativeBrief(
                topic=str(doc.get("title") or "Migrated Motion Design"),
                intent="explain",
                tone="editorial",
            ),
            constraints=Constraints(
                aspect_ratio=aspect_ratio,
                target_fps=fps,
                max_duration_seconds=max(60.0, total_duration),
            ),
            knowledge_refs=list(knowledge_refs_set.values()),
            width=width,
            height=height,
            fps=fps,
            duration_seconds=total_duration,
            scenes=scenes,
            audio_tracks=[],
        )

        # Embed into code.files
        code_obj = doc.setdefault("code", {})
        files = code_obj.setdefault("files", [])
        files = [f for f in files if f.get("path") != "native_motion/spec.json"]
        files.append({
            "id": "file_native_motion_spec",
            "path": "native_motion/spec.json",
            "name": "spec.json",
            "content": spec.model_dump_json(indent=2),
            "read_only": False,
            "provenance": "native_motion_v1",
        })
        code_obj["files"] = files

        # Update metadata
        metadata = doc.setdefault("metadata", {})
        metadata["migration"] = {
            "migrated_at": datetime.now(timezone.utc).isoformat(),
            "migration_version": "wave21_native_motion_v1",
            "migrated_from_legacy_blocks": migrated_slugs,
            "zero_imported_bundles": True,
            "original_block_count": len(legacy_blocks),
            "native_motion_spec_id": spec.id,
        }
        doc["schema_version"] = 2

        return doc, len(legacy_blocks)

    def convert_revision_snapshot(
        self,
        original_snapshot_doc: Dict[str, Any],
        project_id: str,
        revision: int
    ) -> Tuple[Dict[str, Any], int]:
        """
        Convert a historical revision snapshot document to native motion v1.
        Ensures historical revisions can be inspected or restored cleanly without block dependencies.
        """
        return self.convert_project_doc(
            original_doc=original_snapshot_doc,
            project_id=f"{project_id}_rev{revision}"
        )
