# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Conversion engine: transforms legacy block clips into native_motion_v1 scenes and elements."""

from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.knowledge_migration.detector import LegacyBlockDetector
from backend.knowledge_migration.inventory import DonorInventoryLedger
from backend.knowledge_migration.models import LegacyBlockRef


class LegacyProjectConverter:
    """Converts projects containing legacy imported block bundles into native motion v1 format."""

    def __init__(self, ledger: Optional[DonorInventoryLedger] = None):
        self.ledger = ledger or DonorInventoryLedger()

    def extract_text_content(self, variables: Dict[str, Any], block_slug: str) -> Tuple[str, str]:
        """Extract primary headline and subtext from heterogeneous legacy variable dictionaries."""
        headline = ""
        subtext = ""

        # Common headline keys
        for k in ["TXT_MAIN_1_Line", "headline", "title", "text", "trackTitle", "appTitle", "username"]:
            if k in variables and variables[k]:
                headline = str(variables[k])
                break

        # Common subtext keys
        for k in ["TXT_SUB", "artistName", "message1", "sender1", "subheadline", "subtitle"]:
            if k in variables and variables[k]:
                subtext = str(variables[k])
                break

        if not headline:
            headline = block_slug.replace("-", " ").title()

        return headline, subtext

    def convert_project_doc(
        self,
        original_doc: Dict[str, Any],
        project_id: str = ""
    ) -> Tuple[Dict[str, Any], int]:
        """
        Convert a project document by replacing all legacy block clips with native motion v1 structures.
        Returns: (migrated_doc, count_of_migrated_blocks)
        """
        doc = copy.deepcopy(original_doc)
        legacy_blocks = LegacyBlockDetector.detect_in_project_doc(doc)
        if not legacy_blocks:
            return doc, 0

        timeline = doc.get("timeline") or {}
        tracks = timeline.get("tracks") or []
        fps = float(timeline.get("fps") or 30.0)
        aspect_ratio = str(doc.get("aspect_ratio") or "9:16")

        width, height = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)

        migrated_slugs: List[str] = []
        scenes: List[Dict[str, Any]] = []

        for track in tracks:
            new_clips = []
            for clip in track.get("clips") or []:
                ref = LegacyBlockDetector.detect_in_clip(clip, track_id=track.get("id", ""))
                if not ref:
                    # Clean native clip, keep unchanged
                    new_clips.append(clip)
                    continue

                # Migrate this legacy block clip!
                migrated_slugs.append(ref.block_id)
                mapping = self.ledger.get_native_mapping(ref.block_id)
                headline, subtext = self.extract_text_content(ref.variables, ref.block_id)

                start_sec = ref.start_seconds
                dur_sec = max(ref.duration_seconds, 1.0)

                # Form native timeline clip
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

                # Build native_motion_v1 scene element
                elements = [
                    {
                        "id": f"elem_bg_{ref.block_id}_{len(scenes)}",
                        "type": "shape",
                        "layer": 1,
                        "shape_config": {
                            "shape_type": "rectangle",
                            "width": float(width * 0.85),
                            "height": 120.0,
                            "corner_radius": 16.0,
                            "fill": mapping.get("default_fill", "#1E293B"),
                            "opacity": 0.85,
                        },
                        "transform": {
                            "x": float(width * 0.5),
                            "y": float(height * 0.8),
                            "opacity": 1.0,
                            "scale": 1.0,
                        }
                    },
                    {
                        "id": f"elem_text_{ref.block_id}_{len(scenes)}",
                        "type": "text",
                        "layer": 2,
                        "text_config": {
                            "content": headline,
                            "typography": {
                                "font_family": "Inter, Roboto, sans-serif",
                                "font_size": float(mapping.get("default_font_size", 36.0)),
                                "font_weight": "bold",
                                "fill": "#FFFFFF",
                                "text_align": "center",
                            }
                        },
                        "transform": {
                            "x": float(width * 0.5),
                            "y": float(height * 0.8),
                            "opacity": 1.0,
                            "scale": 1.0,
                        }
                    }
                ]

                scene = {
                    "id": f"scene_migrated_{len(scenes)+1}",
                    "start_time": start_sec,
                    "duration": dur_sec,
                    "background_color": "#0A0A0C",
                    "elements": elements
                }
                scenes.append(scene)

            track["clips"] = new_clips

        # Create or update code.files with native_motion/spec.json
        if not scenes:
            scenes = [
                {
                    "id": "scene_default",
                    "start_time": 0.0,
                    "duration": float(timeline.get("duration_seconds") or 3.0),
                    "background_color": "#0A0A0C",
                    "elements": []
                }
            ]

        native_spec = {
            "schema_version": "native_motion_v1",
            "id": f"spec_{project_id or uuid.uuid4().hex[:8]}",
            "title": str(doc.get("title") or "Migrated Project"),
            "width": width,
            "height": height,
            "fps": int(fps),
            "duration_seconds": float(timeline.get("duration_seconds") or 3.0),
            "constraints": {
                "aspect_ratio": aspect_ratio,
                "fps": int(fps),
                "safe_zone": {"top": 0.1, "bottom": 0.15, "left": 0.08, "right": 0.08}
            },
            "scenes": scenes,
            "audio_tracks": []
        }

        code_obj = doc.setdefault("code", {})
        files = code_obj.setdefault("files", [])
        # Remove old spec if present
        files = [f for f in files if f.get("path") != "native_motion/spec.json"]
        files.append({
            "id": f"file_native_motion_spec",
            "path": "native_motion/spec.json",
            "content": json.dumps(native_spec, indent=2)
        })
        code_obj["files"] = files

        # Update metadata
        metadata = doc.setdefault("metadata", {})
        metadata["migration"] = {
            "migrated_at": datetime.now(timezone.utc).isoformat(),
            "migration_version": "wave20_native_motion_v1",
            "migrated_from_legacy_blocks": migrated_slugs,
            "zero_imported_bundles": True,
            "original_block_count": len(legacy_blocks)
        }
        doc["schema_version"] = 2

        return doc, len(legacy_blocks)
