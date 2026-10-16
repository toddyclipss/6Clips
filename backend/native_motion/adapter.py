# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Project Revision CAS Adapter for Native Motion.

Performs optimistic-concurrency revision mutations and fine-grained element/caption
patching via 6Clips ProjectService without destructive regenerations.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from backend.core.exceptions import ProjectError, RevisionConflictError
from backend.native_motion.compiler import NativeMotionCompiler
from backend.native_motion.schema import NativeMotionSpec
from backend.services.project_service import ProjectService

logger = logging.getLogger(__name__)


class NativeMotionRevisionAdapter:
    """Adapter bridging NativeMotionSpec with ProjectService CAS and revision logs."""

    @classmethod
    async def apply_native_motion_spec(
        cls,
        project_id: str,
        expected_revision: int,
        spec: NativeMotionSpec,
        idempotency_key: Optional[str] = None,
        author: str = "agent",
    ) -> Dict[str, Any]:
        """Apply a full NativeMotionSpec to a project via ProjectService with optimistic concurrency."""
        import copy

        compiled_doc = NativeMotionCompiler.compile_to_project_document(spec)
        ProjectService.migrate_project_document(compiled_doc)
        ProjectService._recalculate_timeline_duration(compiled_doc)

        payload = {
            "patch": copy.deepcopy(compiled_doc)
        }

        result = await ProjectService.apply_operation(
            project_id=project_id,
            expected_revision=expected_revision,
            operation_type="patch_document",
            payload=payload,
            idempotency_key=idempotency_key,
            author=author,
        )
        return result

    @classmethod
    async def patch_motion_element(
        cls,
        project_id: str,
        expected_revision: int,
        element_id: str,
        property_patches: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        author: str = "agent",
    ) -> Dict[str, Any]:
        """Apply a fine-grained, non-destructive mutation to a single motion element."""
        project = await ProjectService.get_project(project_id)
        doc = json.loads(project.document_json)

        # Find the spec in code.files
        files = doc.get("code", {}).get("files", [])
        spec_file = next((f for f in files if f.get("path") == "native_motion/spec.json"), None)
        if not spec_file:
            raise ProjectError(f"Project '{project_id}' does not contain 'native_motion/spec.json'")

        spec_data = json.loads(spec_file["content"])
        spec = NativeMotionSpec.model_validate(spec_data)

        # Mutate the targeted element in-place
        target_found = False
        for scene in spec.scenes:
            for elem in scene.elements:
                if elem.id == element_id:
                    target_found = True
                    for k, v in property_patches.items():
                        if k == "transform" and isinstance(v, dict):
                            for tk, tv in v.items():
                                setattr(elem.transform, tk, tv)
                        elif k == "text_content" and elem.text_config:
                            elem.text_config.content = str(v)
                        elif k == "font_size" and elem.text_config:
                            elem.text_config.typography.font_size = float(v)
                        elif k == "fill" and elem.text_config:
                            elem.text_config.typography.fill = str(v)
                        elif k == "opacity":
                            elem.transform.opacity = float(v)
                    break
            if target_found:
                break

        if not target_found:
            raise ProjectError(f"Element '{element_id}' not found in NativeMotionSpec for project '{project_id}'")

        # Update spec file content
        spec_file["content"] = spec.model_dump_json(indent=2)

        # Apply updated document with CAS
        payload = {"patch": {"code": doc.get("code")}}
        return await ProjectService.apply_operation(
            project_id=project_id,
            expected_revision=expected_revision,
            operation_type="patch_document",
            payload=payload,
            idempotency_key=idempotency_key,
            author=author,
        )

    @classmethod
    async def patch_caption_word(
        cls,
        project_id: str,
        expected_revision: int,
        word_index: int,
        new_word: Optional[str] = None,
        color_override: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        author: str = "agent",
    ) -> Dict[str, Any]:
        """Fine-grained word-level edit without full project or video regeneration."""
        project = await ProjectService.get_project(project_id)
        doc = json.loads(project.document_json)

        files = doc.get("code", {}).get("files", [])
        spec_file = next((f for f in files if f.get("path") == "native_motion/spec.json"), None)
        if not spec_file:
            raise ProjectError(f"Project '{project_id}' does not contain 'native_motion/spec.json'")

        spec_data = json.loads(spec_file["content"])
        spec = NativeMotionSpec.model_validate(spec_data)

        caption_elem = None
        for scene in spec.scenes:
            for elem in scene.elements:
                if elem.type == "captions" and elem.captions_config:
                    caption_elem = elem
                    break
            if caption_elem:
                break

        if not caption_elem or not caption_elem.captions_config:
            raise ProjectError(f"No captions component found in project '{project_id}'")

        words = caption_elem.captions_config.words
        if word_index < 0 or word_index >= len(words):
            raise ProjectError(f"Word index {word_index} out of bounds (total: {len(words)})")

        target_word = words[word_index]
        if new_word:
            target_word.word = new_word
        if color_override:
            target_word.color_override = color_override

        spec_file["content"] = spec.model_dump_json(indent=2)
        payload = {"patch": {"code": doc.get("code")}}

        return await ProjectService.apply_operation(
            project_id=project_id,
            expected_revision=expected_revision,
            operation_type="patch_document",
            payload=payload,
            idempotency_key=idempotency_key,
            author=author,
        )
