# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Primary Integration Adapter for Source-Backed Video Editing (Agent 3 -> Agent 5 Contract).

Exposes clean, typed interfaces for:
- Intent classification (EDIT_EXISTING_VIDEO vs GENERATE_NEW_VIDEO)
- Media acquisition & local asset resolution
- End-to-end execution of native source-backed video edits
- Deterministic source lineage verification
"""

from __future__ import annotations

import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from backend.config import settings
from backend.oaas_chat_ingestion.ingestion_service import AgentUrlIngestionService
from backend.oaas_chat_ingestion.models import (
    IngestionBlockerCode,
    UrlIngestionRequest,
    UrlIngestionResult,
)
from .analyzer import SourceMediaAnalyzer
from .editor import NativeMediaEditor
from .models import (
    EditExecutionResult,
    EditExistingMediaContract,
    EditIntentType,
    SourceLineageVerification,
    SourceMediaAnalysis,
)
from .project_adapter import SafeProjectEditAdapter
from .verifier import SourceLineageVerifier

logger = logging.getLogger(__name__)

URL_REGEX = re.compile(r'https?://[^\s<>"]+|www\.[^\s<>"]+', re.IGNORECASE)
EDIT_KEYWORDS = {
    "analise", "edite", "edit", "corte", "cut", "clip", "clips",
    "reframe", "reframe_vertical", "vertical", "legendas", "caption",
    "captions", "translate", "ingles", "english", "video", "source", "footage"
}


class EditExistingMediaAdapter:
    """Primary adapter coordinating source-backed video edit operations."""

    @classmethod
    def classify_intent(cls, message: str, found_urls: Optional[List[str]] = None) -> Tuple[bool, EditIntentType]:
        """
        Classify whether a user utterance constitutes an EDIT_EXISTING_VIDEO request.
        A message containing a URL + edit directives MUST NOT be reinterpreted as GENERATE_NEW_VIDEO.
        """
        urls = found_urls if found_urls is not None else URL_REGEX.findall(message)
        msg_lower = message.lower()

        has_url = bool(urls)
        has_edit_directive = any(kw in msg_lower for kw in EDIT_KEYWORDS)

        if has_url and has_edit_directive:
            return True, EditIntentType.EDIT_EXISTING_VIDEO
        elif has_url:
            # URL present without explicit keywords is still treated as source-backed edit/repurpose
            return True, EditIntentType.EDIT_EXISTING_VIDEO

        return False, EditIntentType.GENERATE_NEW_VIDEO

    @classmethod
    async def ingest_or_resolve_source(
        cls,
        source_target: str,
        user_id: str = "local",
        max_duration_sec: float = 14400.0,
        max_bytes: int = 2 * 1024 * 1024 * 1024,
    ) -> Tuple[bool, Optional[Path], Optional[str], Optional[str]]:
        """
        Acquire or resolve source media:
        - If source_target is an existing local file: inspects and validates locally without network.
        - If source_target is a remote URL: executes secure agent ingestion.
        Returns: (is_success, resolved_path, blocker_code, blocker_reason).
        """
        # Case A: Local file path
        local_p = Path(source_target)
        if local_p.exists() and local_p.is_file():
            if local_p.stat().st_size == 0:
                return False, None, "MEDIA_EMPTY", f"Local file is empty: {local_p}"
            return True, local_p.resolve(), None, None

        # Case B: Remote URL ingestion
        req = UrlIngestionRequest(
            url=source_target,
            user_id=user_id,
            max_duration_sec=max_duration_sec,
            max_bytes=max_bytes,
        )
        res: UrlIngestionResult = await AgentUrlIngestionService.ingest_url(req)

        if not res.is_allowed or not res.file_path:
            b_code = res.blocker_code.value if res.blocker_code else "BLOCKED_FETCH_FAILED"
            b_reason = res.blocker_reason or "Source video acquisition failed."
            return False, None, b_code, b_reason

        target_file = Path(res.file_path)
        if not target_file.exists():
            return False, None, "BLOCKED_FETCH_FAILED", f"Downloaded media file missing at {target_file}"

        return True, target_file.resolve(), None, None

    @classmethod
    def prepare_contract(
        cls,
        original_url: str,
        file_path: Path,
        analysis: SourceMediaAnalysis,
        requested_duration: Optional[float] = None,
        target_aspect_ratio: str = "9:16",
        target_language: str = "en",
        project_id: Optional[str] = None,
        user_id: str = "local",
        run_id: Optional[str] = None,
    ) -> EditExistingMediaContract:
        """Construct a validated, typed EditExistingMediaContract from analyzed source."""
        spans = SourceMediaAnalyzer.select_edit_spans(analysis, requested_duration=requested_duration)
        trim_start, trim_end = spans[0]
        actual_target_dur = round(trim_end - trim_start, 3)

        # Generate contextual caption directives aligned with requested language
        is_english = target_language.lower() in ("en", "english", "ingles")
        captions: List[Dict[str, Any]] = []

        if is_english:
            captions = [
                {"start": 0.0, "end": min(2.5, actual_target_dur * 0.45), "text": "Source footage analyzed & reframed in English"},
                {"start": min(2.5, actual_target_dur * 0.45), "end": actual_target_dur, "text": "Key moments edited for vertical delivery"},
            ]
        else:
            captions = [
                {"start": 0.0, "end": min(2.5, actual_target_dur * 0.45), "text": "Highlights editados da fonte"},
                {"start": min(2.5, actual_target_dur * 0.45), "end": actual_target_dur, "text": "Momentos principais em formato vertical"},
            ]

        return EditExistingMediaContract(
            original_url=original_url,
            asset_id=f"asset_{file_path.stem[:12]}",
            file_path=str(file_path),
            source_sha256=analysis.sha256_hash,
            source_duration=analysis.duration_sec,
            source_resolution=analysis.resolution,
            source_fps=analysis.fps,
            has_audio=analysis.has_audio,
            audio_codec=analysis.audio_codec,
            source_intervals=spans,
            target_duration=actual_target_dur,
            target_aspect_ratio=target_aspect_ratio,
            target_language=target_language,
            reframe_mode="vertical_blur_fill" if target_aspect_ratio == "9:16" else "fit",
            caption_timings=captions,
            project_id=project_id,
            user_id=user_id,
            run_id=run_id or f"run-{uuid4().hex[:8]}",
        )

    @classmethod
    async def execute_edit(
        cls,
        contract: EditExistingMediaContract,
        output_file: Optional[Path] = None,
    ) -> EditExecutionResult:
        """
        Execute full end-to-end source-backed edit:
        1. Ensure canonical Project exists
        2. Analyze source media forensic integrity
        3. Apply timeline mutations (add_asset, add_clip, set_aspect_ratio, set_captions)
        4. Render physical MP4 deliverable
        5. Verify source lineage mathematically and visually
        """
        source_path = Path(contract.file_path)
        if not source_path.exists():
            return EditExecutionResult(
                success=False,
                project_id=contract.project_id or "none",
                revision_id=1,
                asset_id=contract.asset_id,
                clip_id="none",
                blocker_code="SOURCE_FILE_NOT_FOUND",
                blocker_reason=f"Source video file not found at {source_path}",
            )

        # 1. Forensic Analysis of Source Video
        try:
            analysis = SourceMediaAnalyzer.analyze_file(source_path)
        except Exception as ex:
            logger.error("Source analysis failed for %s: %s", source_path, ex)
            return EditExecutionResult(
                success=False,
                project_id=contract.project_id or "none",
                revision_id=1,
                asset_id=contract.asset_id,
                clip_id="none",
                blocker_code="MEDIA_UNREADABLE",
                blocker_reason=f"Source media is unreadable: {ex}",
            )

        # 2. Project Resolution & Mutation via SafeProjectEditAdapter
        project_title = f"Edit: {source_path.stem[:30]} ({contract.target_aspect_ratio})"
        project, current_rev = await SafeProjectEditAdapter.get_or_create_project(
            project_id=contract.project_id,
            user_id=contract.user_id,
            title=project_title,
            aspect_ratio=contract.target_aspect_ratio,
        )

        final_rev, asset_id, clip_id = await SafeProjectEditAdapter.apply_source_edit_operations(
            project_id=project.id,
            expected_revision=current_rev,
            contract=contract,
            analysis=analysis,
        )

        # 3. Physical Render Execution
        try:
            rendered_path, rendered_sha, rendered_dur, rendered_dims = NativeMediaEditor.render_source_edit(
                contract=contract,
                output_file=output_file,
            )
        except Exception as ex:
            logger.error("FFmpeg render failed: %s", ex)
            return EditExecutionResult(
                success=False,
                project_id=project.id,
                revision_id=final_rev,
                asset_id=asset_id,
                clip_id=clip_id,
                blocker_code="RENDER_FAILED",
                blocker_reason=f"FFmpeg execution failed: {ex}",
            )

        # 4. Deterministic Source Lineage Verification
        verification = await SourceLineageVerifier.verify_source_lineage(
            project_id=project.id,
            revision_id=final_rev,
            rendered_mp4=rendered_path,
            expected_source_sha=analysis.sha256_hash,
            expected_duration=contract.target_duration,
            source_path=source_path,
        )

        if not verification.is_verified:
            logger.warning("Lineage verification failed for project %s: %s", project.id, verification.rejection_reason)
            return EditExecutionResult(
                success=False,
                project_id=project.id,
                revision_id=final_rev,
                asset_id=asset_id,
                clip_id=clip_id,
                rendered_mp4_path=str(rendered_path),
                rendered_sha256=rendered_sha,
                rendered_duration_sec=rendered_dur,
                rendered_resolution=rendered_dims,
                source_intervals=contract.source_intervals,
                target_aspect_ratio=contract.target_aspect_ratio,
                lineage_verified=False,
                lineage_verification=verification,
                blocker_code="LINEAGE_VERIFICATION_FAILED",
                blocker_reason=verification.rejection_reason or "Output failed source lineage verification.",
            )

        return EditExecutionResult(
            success=True,
            project_id=project.id,
            revision_id=final_rev,
            asset_id=asset_id,
            clip_id=clip_id,
            rendered_mp4_path=str(rendered_path),
            rendered_sha256=rendered_sha,
            rendered_duration_sec=rendered_dur,
            rendered_resolution=rendered_dims,
            source_intervals=contract.source_intervals,
            target_aspect_ratio=contract.target_aspect_ratio,
            lineage_verified=True,
            lineage_verification=verification,
        )

    @classmethod
    async def verify_source_lineage(
        cls,
        project_id: str,
        revision_id: int,
        rendered_mp4: Path,
        expected_source_sha: str,
        expected_duration: float,
        source_path: Optional[Path] = None,
        tolerance_sec: float = 0.5,
    ) -> SourceLineageVerification:
        """Deterministic public API for Agent 5 to invoke before setting VIDEO_VERIFIED."""
        return await SourceLineageVerifier.verify_source_lineage(
            project_id=project_id,
            revision_id=revision_id,
            rendered_mp4=rendered_mp4,
            expected_source_sha=expected_source_sha,
            expected_duration=expected_duration,
            source_path=source_path,
            tolerance_sec=tolerance_sec,
        )
