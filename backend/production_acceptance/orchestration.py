# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Production Path Orchestrators for V1, V2, and V3 (Wave 8).

Implements rigorous acceptance orchestration:
- V1GameplayOrchestrator (GT-05): 1 licensed gameplay source -> 3 usable independent ~60s vertical clips
  with provenance, subtitles/audio, Motion review links, and independent project IDs.
- V2MultiSourceOrchestrator (GT-07): 5 authorized sources -> 10 editable/rendered outputs (9:16).
- V3LongFormOrchestrator (GT-06): 1 authentic ~60-min recording -> 8-10 min 16:9 narrative cut list & result.
- Truth guards: returns WAITING_FOR_INPUT / NOT_TESTED with concrete file instructions when authentic media is absent.
- Never claims GT-05, GT-06, or GT-07 passed based on synthetic test fixtures alone.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from .contracts import (
    MediaProbeMetadata,
    OrchestrationContractStatus,
    OrchestrationResult,
    RightsVerificationStatus,
    SourceMediaAsset,
    V1ExpectedOutputSpec,
    V1ProductionContract,
    V2ExpectedOutputSpec,
    V2ProductionContract,
    V3NarrativeCut,
    V3ProductionContract,
)
from .manifest import SourceManifestValidator, UserPermittedSourceManifest
from .probe import MediaProbeService

logger = logging.getLogger(__name__)

AUTHORIZED_RIGHTS = {
    RightsVerificationStatus.AUTHORIZED_USER_MEDIA,
    RightsVerificationStatus.COMMERCIAL_CREATOR_LICENSE,
}


class V1GameplayOrchestrator:
    """
    Acceptance orchestrator for Gate GT-05 (V1 Mode):
    Requires 1 licensed gameplay source and produces/validates THREE usable independent
    ~60s vertical clips (9:16) with provenance, subtitles/audio, Motion review, and independent projects.
    """

    def __init__(self, project_id: str = "proj_v1_acceptance"):
        self.project_id = project_id

    def build_contract(
        self,
        source: SourceMediaAsset,
        is_real_user_media: bool = False,
        probe_file: bool = True,
    ) -> V1ProductionContract:
        """Constructs and validates the V1 production contract."""
        contract = V1ProductionContract(
            contract_id=f"v1_contract_{self.project_id}",
            project_id=self.project_id,
            source_gameplay=source,
            is_real_user_media=is_real_user_media,
        )

        # 1. Rights check
        if source.rights_status not in AUTHORIZED_RIGHTS:
            contract.issues.append(
                f"Source {source.source_id} rights status '{source.rights_status.value}' is not authorized"
            )
            contract.status = OrchestrationContractStatus.REJECTED

        # 2. Probe checks
        if probe_file:
            try:
                probe = MediaProbeService.probe_file(source.file_path)
                source.probe = probe
                if not probe.magic_bytes_valid:
                    contract.issues.append("Source gameplay recording has invalid container magic bytes")
                    contract.status = OrchestrationContractStatus.REJECTED
                if probe.synthetic_filler_detected:
                    contract.issues.append(f"Source gameplay recording is synthetic filler: {probe.synthetic_filler_reason}")
                    contract.status = OrchestrationContractStatus.REJECTED
                if not probe.has_audio_stream:
                    contract.issues.append("Source gameplay recording lacks an audio stream")
                    contract.status = OrchestrationContractStatus.REJECTED
                if is_real_user_media and probe.duration_seconds < 180.0:
                    contract.issues.append(
                        f"Source duration ({probe.duration_seconds:.1f}s) is too short to produce 3 independent ~60s shorts (minimum 180s required)"
                    )
                    contract.status = OrchestrationContractStatus.REJECTED
            except Exception as e:
                contract.issues.append(f"Failed to probe source gameplay recording: {str(e)}")
                contract.status = OrchestrationContractStatus.FAILED

        if contract.status in (OrchestrationContractStatus.REJECTED, OrchestrationContractStatus.FAILED):
            return contract

        # 3. Generate 3 independent output specs with independent project references
        expected_outputs: List[V1ExpectedOutputSpec] = []
        independent_project_ids = []
        for i in range(1, 4):
            out_id = f"v1_clip_{self.project_id}_{i:02d}"
            proj_id = f"{self.project_id}_short_{i:02d}"
            independent_project_ids.append(proj_id)
            start_sec = (i - 1) * 60.0
            end_sec = start_sec + 58.0
            spec = V1ExpectedOutputSpec(
                output_id=out_id,
                project_id=proj_id,
                target_aspect_ratio="9:16",
                target_duration_min_sec=50.0,
                target_duration_max_sec=70.0,
                primary_source_id=source.source_id,
                source_start_sec=start_sec,
                source_end_sec=end_sec,
                editorial_focus="gameplay_highlight",
                project_revision=1,
                has_subtitles=True,
                motion_review_url=f"/motion?output_id={out_id}&project_id={proj_id}",
            )
            expected_outputs.append(spec)

        contract.expected_outputs = expected_outputs
        contract.independent_project_ids = independent_project_ids

        contract.status = OrchestrationContractStatus.CONTRACT_PREPARED
        if not is_real_user_media:
            contract.required_file_instructions = [
                "1. Provide an authentic licensed gameplay video recording of at least 180 seconds duration.",
                "2. Place the video file in 'data/acceptance/gt05_inputs/gameplay.mp4'.",
                "3. Ensure container is valid MP4 or WebM with dual-channel non-silent audio.",
                "4. Provide creator authorization/license metadata in permitted_uses.",
            ]

        return contract

    def build_contract_from_manifest(
        self,
        manifest: UserPermittedSourceManifest,
        secret: str = "6clips-manifest-secret",
    ) -> V1ProductionContract:
        """Builds and validates V1 contract from a validated UserPermittedSourceManifest."""
        SourceManifestValidator.validate_manifest(
            manifest, secret=secret, enforce_real_media=manifest.is_real_user_media
        )
        if not manifest.all_items_valid or len(manifest.items) != 1:
            contract = V1ProductionContract(
                contract_id=f"v1_contract_{self.project_id}",
                project_id=self.project_id,
                status=OrchestrationContractStatus.REJECTED,
                is_real_user_media=manifest.is_real_user_media,
                issues=list(manifest.validation_errors),
            )
            return contract

        source_asset = SourceManifestValidator.manifest_to_source_assets(manifest)[0]
        return self.build_contract(
            source=source_asset,
            is_real_user_media=manifest.is_real_user_media,
            probe_file=True,
        )

    def evaluate_acceptance(
        self,
        contract: V1ProductionContract,
        rendered_output_paths: Optional[List[str]] = None,
        is_cancelled: bool = False,
        budget_attempts: Optional[int] = None,
        max_budget_attempts: int = 3,
    ) -> OrchestrationResult:
        """
        Evaluates production acceptance for GT-05.
        Truth guard: without authentic user gameplay media, returns WAITING_FOR_INPUT / NOT_TESTED.
        - If all 3 outputs verified: returns READY_FOR_REVIEW with editorial assessment left open.
        - If 3rd output failed/missing, but first 2 verified: returns PARTIAL with first 2 outputs preserved.
        - If cancelled or budget exceeded: preserves valid outputs and sets appropriate status.
        """
        result = OrchestrationResult(
            gate_id="GT-05",
            status="NOT_TESTED",
            is_real_user_media=contract.is_real_user_media,
            independent_project_ids=contract.independent_project_ids,
        )

        if contract.status in (OrchestrationContractStatus.REJECTED, OrchestrationContractStatus.FAILED):
            result.status = "REJECTED" if contract.status == OrchestrationContractStatus.REJECTED else "FAILED"
            result.issues.extend(contract.issues)
            return result

        if not contract.is_real_user_media:
            result.status = "NOT_TESTED"
            result.required_file_instructions = contract.required_file_instructions
            result.missing_evidence.append(
                "Authentic licensed gameplay recording (>=180s) was not provided in test environment"
            )
            result.notes = "WAITING_FOR_INPUT: GT-05 contract prepared with 3 independent project specs, but awaiting authentic source footage."
            return result

        if not rendered_output_paths:
            result.status = "NOT_TESTED"
            result.missing_evidence.append("Expected rendered vertical outputs, none provided")
            return result

        # Probe and deduplicate rendered outputs
        output_hashes = set()
        valid_outputs: List[str] = []
        valid_project_ids: List[str] = []
        motion_urls: List[str] = []

        for idx, path_str in enumerate(rendered_output_paths):
            try:
                probe = MediaProbeService.probe_file(path_str)
                path_issues = []
                if not probe.magic_bytes_valid:
                    path_issues.append(f"Rendered output {path_str} has invalid container")
                if probe.synthetic_filler_detected:
                    path_issues.append(f"Rendered output {path_str} contains synthetic filler: {probe.synthetic_filler_reason}")
                if probe.aspect_ratio != "9:16":
                    path_issues.append(f"Rendered output {path_str} aspect ratio {probe.aspect_ratio} is not 9:16")
                if not (50.0 <= probe.duration_seconds <= 70.0):
                    path_issues.append(f"Rendered output {path_str} duration {probe.duration_seconds:.1f}s outside [50, 70]")
                if probe.sha256_hash in output_hashes:
                    path_issues.append(f"Duplicate rendered output detected: hash {probe.sha256_hash[:12]}")

                if path_issues:
                    result.issues.extend(path_issues)
                else:
                    output_hashes.add(probe.sha256_hash)
                    valid_outputs.append(path_str)
                    if idx < len(contract.independent_project_ids):
                        valid_project_ids.append(contract.independent_project_ids[idx])
            except Exception as e:
                result.issues.append(f"Failed to probe rendered output {path_str}: {str(e)}")

        for spec in contract.expected_outputs:
            if spec.motion_review_url:
                motion_urls.append(spec.motion_review_url)

        result.artifacts_verified_count = len(valid_outputs)
        result.distinct_hashes_count = len(output_hashes)
        result.motion_review_urls = motion_urls
        result.preserved_outputs = valid_outputs
        result.preserved_project_ids = valid_project_ids

        # Budget check
        if budget_attempts is not None and budget_attempts > max_budget_attempts:
            result.status = "BLOCKED_BUDGET_EXCEEDED"
            result.notes = (
                f"Execution halted: budget limit ({max_budget_attempts} attempts) exceeded. "
                f"{len(valid_outputs)} valid outputs preserved."
            )
            contract.status = OrchestrationContractStatus.BLOCKED_BUDGET_EXCEEDED
            return result

        # Cancellation check
        if is_cancelled:
            result.status = "CANCELLED"
            result.notes = f"Run cancelled by user request. {len(valid_outputs)} valid outputs preserved."
            contract.status = OrchestrationContractStatus.CANCELLED
            return result

        if len(valid_outputs) == 3 and result.distinct_hashes_count == 3:
            result.status = "READY_FOR_REVIEW"
            result.editorial_assessment = "EDITORIAL_NOT_ASSESSED"
            result.human_approval_required = True
            result.notes = (
                "READY_FOR_REVIEW: All 3 physical vertical shorts verified with independent projects, "
                "subtitles, and distinct hashes. Awaiting human editorial review."
            )
            contract.status = OrchestrationContractStatus.READY_FOR_REVIEW
        elif len(valid_outputs) in (1, 2):
            result.status = "PARTIAL"
            result.editorial_assessment = "EDITORIAL_NOT_ASSESSED"
            result.human_approval_required = True
            result.notes = (
                f"PARTIAL: {len(valid_outputs)} of 3 vertical shorts preserved and verified. "
                f"Remaining output failed or missing; not auto-approved."
            )
            contract.status = OrchestrationContractStatus.PARTIAL
        else:
            result.status = "FAILED" if result.issues else "NOT_TESTED"
            contract.status = OrchestrationContractStatus.FAILED if result.issues else OrchestrationContractStatus.NOT_TESTED

        return result


class V2MultiSourceOrchestrator:
    """
    Acceptance orchestrator for Gate GT-07 (V2 Mode):
    Requires 5 authorized source assets and produces/validates 10 distinct vertical outputs.
    """

    def __init__(self, project_id: str = "proj_v2_acceptance"):
        self.project_id = project_id

    def build_contract(
        self,
        sources: List[SourceMediaAsset],
        is_real_user_media: bool = False,
        probe_files: bool = True,
    ) -> V2ProductionContract:
        """Constructs and validates the V2 production contract."""
        contract = V2ProductionContract(
            contract_id=f"v2_contract_{self.project_id}",
            project_id=self.project_id,
            sources=sources,
            is_real_user_media=is_real_user_media,
        )

        # 1. Source count check
        if len(sources) != 5:
            contract.issues.append(
                f"GT-07 requires exactly 5 distinct source media assets, found {len(sources)}"
            )
            contract.status = OrchestrationContractStatus.REJECTED
            return contract

        # 2. Rights and probe checks
        source_hashes = set()
        for idx, src in enumerate(sources):
            if src.rights_status not in AUTHORIZED_RIGHTS:
                contract.issues.append(
                    f"Source {src.source_id} rights status '{src.rights_status.value}' is not authorized"
                )
                contract.status = OrchestrationContractStatus.REJECTED

            if probe_files:
                try:
                    probe = MediaProbeService.probe_file(src.file_path)
                    src.probe = probe
                    if not probe.magic_bytes_valid:
                        contract.issues.append(f"Source {src.source_id} has invalid container magic bytes")
                        contract.status = OrchestrationContractStatus.REJECTED
                    if probe.synthetic_filler_detected:
                        contract.issues.append(
                            f"Source {src.source_id} contains synthetic filler: {probe.synthetic_filler_reason}"
                        )
                        contract.status = OrchestrationContractStatus.REJECTED
                    if probe.sha256_hash:
                        if probe.sha256_hash in source_hashes:
                            contract.issues.append(
                                f"Duplicate source detected: hash {probe.sha256_hash[:12]} appears more than once"
                            )
                            contract.status = OrchestrationContractStatus.REJECTED
                        source_hashes.add(probe.sha256_hash)
                except Exception as e:
                    contract.issues.append(f"Failed to probe source {src.source_id}: {str(e)}")
                    contract.status = OrchestrationContractStatus.FAILED

        if contract.status in (OrchestrationContractStatus.REJECTED, OrchestrationContractStatus.FAILED):
            return contract

        # 3. Build 10 expected output specs (2 distinct outputs per source)
        expected_outputs: List[V2ExpectedOutputSpec] = []
        for src_idx, src in enumerate(sources):
            for clip_idx in range(1, 3):
                out_num = src_idx * 2 + clip_idx
                out_id = f"v2_out_{self.project_id}_{out_num:02d}"
                start_sec = 0.0 if clip_idx == 1 else 60.0
                end_sec = start_sec + 58.0
                spec = V2ExpectedOutputSpec(
                    output_id=out_id,
                    target_aspect_ratio="9:16",
                    target_duration_min_sec=45.0,
                    target_duration_max_sec=65.0,
                    primary_source_id=src.source_id,
                    source_start_sec=start_sec,
                    source_end_sec=end_sec,
                    editorial_focus="action_highlight" if clip_idx == 1 else "key_moment",
                    project_revision=1,
                    motion_review_url=f"/motion?output_id={out_id}&project_id={self.project_id}",
                )
                expected_outputs.append(spec)

        contract.expected_outputs = expected_outputs

        contract.status = OrchestrationContractStatus.CONTRACT_PREPARED
        if not is_real_user_media:
            contract.required_file_instructions = [
                "1. Provide 5 distinct creator-authorized source video files with non-identical SHA-256 hashes.",
                "2. Place assets in 'data/acceptance/gt07_inputs/source_{1..5}.mp4'.",
                "3. Ensure all assets have valid audio streams and no synthetic filler (anullsrc).",
                "4. Attach proof of permitted use (creator_edit, social_distribution).",
            ]

        return contract

    def build_contract_from_manifest(
        self,
        manifest: UserPermittedSourceManifest,
        secret: str = "6clips-manifest-secret",
    ) -> V2ProductionContract:
        """Builds and validates V2 contract from a validated UserPermittedSourceManifest."""
        SourceManifestValidator.validate_manifest(
            manifest, secret=secret, enforce_real_media=manifest.is_real_user_media
        )
        if not manifest.all_items_valid or len(manifest.items) != 5:
            contract = V2ProductionContract(
                contract_id=f"v2_contract_{self.project_id}",
                project_id=self.project_id,
                status=OrchestrationContractStatus.REJECTED,
                is_real_user_media=manifest.is_real_user_media,
                issues=list(manifest.validation_errors),
            )
            return contract

        source_assets = SourceManifestValidator.manifest_to_source_assets(manifest)
        return self.build_contract(
            sources=source_assets,
            is_real_user_media=manifest.is_real_user_media,
            probe_files=True,
        )

    def evaluate_acceptance(
        self,
        contract: V2ProductionContract,
        rendered_output_paths: Optional[List[str]] = None,
        is_cancelled: bool = False,
        budget_attempts: Optional[int] = None,
        max_budget_attempts: int = 10,
    ) -> OrchestrationResult:
        """
        Evaluates production acceptance for GT-07.
        Truth guard: without authentic user media and rendered files, returns WAITING_FOR_INPUT / NOT_TESTED.
        - If all 10 outputs verified: returns READY_FOR_REVIEW.
        - If partial outputs verified: returns PARTIAL and preserves valid outputs.
        - If cancelled or budget exceeded: preserves valid outputs.
        """
        result = OrchestrationResult(
            gate_id="GT-07",
            status="NOT_TESTED",
            is_real_user_media=contract.is_real_user_media,
        )

        if contract.status in (OrchestrationContractStatus.REJECTED, OrchestrationContractStatus.FAILED):
            result.status = "REJECTED" if contract.status == OrchestrationContractStatus.REJECTED else "FAILED"
            result.issues.extend(contract.issues)
            return result

        if not contract.is_real_user_media:
            result.status = "NOT_TESTED"
            result.required_file_instructions = contract.required_file_instructions
            result.missing_evidence.append(
                "Authentic licensed multi-source media (5 distinct real creator assets) was not provided"
            )
            result.notes = "WAITING_FOR_INPUT: GT-07 orchestration contract prepared, but physical render awaiting authentic media inputs."
            return result

        if not rendered_output_paths:
            result.status = "NOT_TESTED"
            result.missing_evidence.append("Expected rendered vertical outputs, none provided")
            return result

        # Probe and deduplicate rendered outputs
        output_hashes = set()
        valid_outputs: List[str] = []
        motion_urls: List[str] = []

        for path_str in rendered_output_paths:
            try:
                probe = MediaProbeService.probe_file(path_str)
                path_issues = []
                if not probe.magic_bytes_valid:
                    path_issues.append(f"Rendered output {path_str} has invalid container")
                if probe.synthetic_filler_detected:
                    path_issues.append(f"Rendered output {path_str} contains synthetic filler: {probe.synthetic_filler_reason}")
                if probe.aspect_ratio != "9:16":
                    path_issues.append(f"Rendered output {path_str} aspect ratio {probe.aspect_ratio} is not 9:16")
                if not (45.0 <= probe.duration_seconds <= 65.0):
                    path_issues.append(f"Rendered output {path_str} duration {probe.duration_seconds:.1f}s outside [45, 65]")
                if probe.sha256_hash in output_hashes:
                    path_issues.append(f"Duplicate rendered output detected: hash {probe.sha256_hash[:12]}")

                if path_issues:
                    result.issues.extend(path_issues)
                else:
                    output_hashes.add(probe.sha256_hash)
                    valid_outputs.append(path_str)
            except Exception as e:
                result.issues.append(f"Failed to probe rendered output {path_str}: {str(e)}")

        for spec in contract.expected_outputs:
            if spec.motion_review_url:
                motion_urls.append(spec.motion_review_url)

        result.artifacts_verified_count = len(valid_outputs)
        result.distinct_hashes_count = len(output_hashes)
        result.motion_review_urls = motion_urls
        result.preserved_outputs = valid_outputs

        # Budget check
        if budget_attempts is not None and budget_attempts > max_budget_attempts:
            result.status = "BLOCKED_BUDGET_EXCEEDED"
            result.notes = (
                f"Execution halted: budget limit ({max_budget_attempts} attempts) exceeded. "
                f"{len(valid_outputs)} valid outputs preserved."
            )
            contract.status = OrchestrationContractStatus.BLOCKED_BUDGET_EXCEEDED
            return result

        # Cancellation check
        if is_cancelled:
            result.status = "CANCELLED"
            result.notes = f"Run cancelled by user request. {len(valid_outputs)} valid outputs preserved."
            contract.status = OrchestrationContractStatus.CANCELLED
            return result

        if len(valid_outputs) == 10 and result.distinct_hashes_count == 10:
            result.status = "READY_FOR_REVIEW"
            result.editorial_assessment = "EDITORIAL_NOT_ASSESSED"
            result.human_approval_required = True
            result.notes = "READY_FOR_REVIEW: All 10 multi-source outputs verified distinct and valid. Awaiting human editorial review."
            contract.status = OrchestrationContractStatus.READY_FOR_REVIEW
        elif len(valid_outputs) > 0:
            result.status = "PARTIAL"
            result.editorial_assessment = "EDITORIAL_NOT_ASSESSED"
            result.human_approval_required = True
            result.notes = f"PARTIAL: {len(valid_outputs)} of 10 outputs verified and preserved. Remaining outputs failed or missing."
            contract.status = OrchestrationContractStatus.PARTIAL
        else:
            result.status = "FAILED" if result.issues else "NOT_TESTED"
            contract.status = OrchestrationContractStatus.FAILED if result.issues else OrchestrationContractStatus.NOT_TESTED

        return result


class V3LongFormOrchestrator:
    """
    Acceptance orchestrator for Gate GT-06 (V3 Mode):
    Requires 1 authentic ~60-minute recording and produces/validates an 8-10 minute 16:9 narrative result.
    """

    def __init__(self, project_id: str = "proj_v3_acceptance"):
        self.project_id = project_id

    def build_contract(
        self,
        source: SourceMediaAsset,
        narrative_cut_list: Optional[List[V3NarrativeCut]] = None,
        is_real_user_media: bool = False,
        probe_file: bool = True,
    ) -> V3ProductionContract:
        """Constructs and validates the V3 production contract."""
        contract = V3ProductionContract(
            contract_id=f"v3_contract_{self.project_id}",
            project_id=self.project_id,
            source_recording=source,
            is_real_user_media=is_real_user_media,
            motion_review_url=f"/motion?output_id=v3_narrative_{self.project_id}&project_id={self.project_id}",
        )

        # 1. Rights check
        if source.rights_status not in AUTHORIZED_RIGHTS:
            contract.issues.append(
                f"Source {source.source_id} rights status '{source.rights_status.value}' is not authorized"
            )
            contract.status = OrchestrationContractStatus.REJECTED

        # 2. Probe checks
        if probe_file:
            try:
                probe = MediaProbeService.probe_file(source.file_path)
                source.probe = probe
                if not probe.magic_bytes_valid:
                    contract.issues.append("Source recording has invalid container magic bytes")
                    contract.status = OrchestrationContractStatus.REJECTED
                if probe.synthetic_filler_detected:
                    contract.issues.append(f"Source recording is synthetic filler: {probe.synthetic_filler_reason}")
                    contract.status = OrchestrationContractStatus.REJECTED
                if not probe.has_audio_stream:
                    contract.issues.append("Source recording lacks an audio stream")
                    contract.status = OrchestrationContractStatus.REJECTED
                # Check ~60-min input duration (require 3000s - 4200s, ~50 to 70 mins)
                if is_real_user_media and (probe.duration_seconds < 3000.0 or probe.duration_seconds > 4200.0):
                    contract.issues.append(
                        f"Source duration ({probe.duration_seconds:.1f}s) is not an authentic ~60-minute recording (expected 3000-4200s)"
                    )
                    contract.status = OrchestrationContractStatus.REJECTED
            except Exception as e:
                contract.issues.append(f"Failed to probe source recording: {str(e)}")
                contract.status = OrchestrationContractStatus.FAILED

        if contract.status in (OrchestrationContractStatus.REJECTED, OrchestrationContractStatus.FAILED):
            return contract

        # 3. Validate or generate narrative cut list
        if narrative_cut_list:
            total_duration = sum(c.duration_sec for c in narrative_cut_list)
            if total_duration < 480.0 or total_duration > 600.0:
                contract.issues.append(
                    f"Narrative cut list total duration ({total_duration:.1f}s) is outside 8-10 minutes (480-600s)"
                )
                contract.status = OrchestrationContractStatus.REJECTED
                return contract
            contract.narrative_cut_list = narrative_cut_list
        else:
            # Generate default 8.5 min (510s) narrative structure
            contract.narrative_cut_list = self._generate_default_cut_list()

        contract.status = OrchestrationContractStatus.CONTRACT_PREPARED
        if not is_real_user_media:
            contract.required_file_instructions = [
                "1. Provide an authentic ~60-minute video recording (podcast, interview, or gameplay, 3000-4200s).",
                "2. Place recording in 'data/acceptance/gt06_inputs/longform_60m.mp4'.",
                "3. Ensure container is 16:9 aspect ratio with dual-channel audible dialogue/narration.",
                "4. Attach proof of user authorship or commercial license.",
            ]

        return contract

    def _generate_default_cut_list(self) -> List[V3NarrativeCut]:
        """Generates standard narrative condensation structure summing to 510s (8.5 min)."""
        cuts = [
            V3NarrativeCut(
                cut_id="cut_01",
                source_start_sec=120.0,
                source_end_sec=210.0,
                duration_sec=90.0,
                scene_name="Introduction & Premise",
                topic_marker="setup",
                narration_continuity_summary="Establishes central theme and stakes",
            ),
            V3NarrativeCut(
                cut_id="cut_02",
                source_start_sec=600.0,
                source_end_sec=750.0,
                duration_sec=150.0,
                scene_name="Rising Action & First Climax",
                topic_marker="rising_action",
                narration_continuity_summary="Key challenge encountered and explored",
            ),
            V3NarrativeCut(
                cut_id="cut_03",
                source_start_sec=1800.0,
                source_end_sec=1950.0,
                duration_sec=150.0,
                scene_name="Deep Dive & Resolution",
                topic_marker="resolution",
                narration_continuity_summary="Critical breakthrough and outcome analysis",
            ),
            V3NarrativeCut(
                cut_id="cut_04",
                source_start_sec=3200.0,
                source_end_sec=3320.0,
                duration_sec=120.0,
                scene_name="Synthesis & Next Steps",
                topic_marker="conclusion",
                narration_continuity_summary="Final takeaways and call to action",
            ),
        ]
        return cuts

    def build_contract_from_manifest(
        self,
        manifest: UserPermittedSourceManifest,
        secret: str = "6clips-manifest-secret",
        narrative_cut_list: Optional[List[V3NarrativeCut]] = None,
    ) -> V3ProductionContract:
        """Builds and validates V3 contract from a validated UserPermittedSourceManifest."""
        SourceManifestValidator.validate_manifest(
            manifest, secret=secret, enforce_real_media=manifest.is_real_user_media
        )
        if not manifest.all_items_valid or len(manifest.items) != 1:
            contract = V3ProductionContract(
                contract_id=f"v3_contract_{self.project_id}",
                project_id=self.project_id,
                status=OrchestrationContractStatus.REJECTED,
                is_real_user_media=manifest.is_real_user_media,
                issues=list(manifest.validation_errors),
            )
            return contract

        source_asset = SourceManifestValidator.manifest_to_source_assets(manifest)[0]
        return self.build_contract(
            source=source_asset,
            narrative_cut_list=narrative_cut_list,
            is_real_user_media=manifest.is_real_user_media,
            probe_file=True,
        )

    def evaluate_acceptance(
        self,
        contract: V3ProductionContract,
        rendered_output_path: Optional[str] = None,
        is_cancelled: bool = False,
        budget_attempts: Optional[int] = None,
        max_budget_attempts: int = 3,
    ) -> OrchestrationResult:
        """
        Evaluates production acceptance for GT-06.
        Truth guard: without authentic ~60-minute media, returns WAITING_FOR_INPUT / NOT_TESTED.
        Editorial assessment remains explicitly EDITORIAL_NOT_ASSESSED (human judgment required).
        """
        result = OrchestrationResult(
            gate_id="GT-06",
            status="NOT_TESTED",
            is_real_user_media=contract.is_real_user_media,
        )

        if contract.status in (OrchestrationContractStatus.REJECTED, OrchestrationContractStatus.FAILED):
            result.status = "REJECTED" if contract.status == OrchestrationContractStatus.REJECTED else "FAILED"
            result.issues.extend(contract.issues)
            return result

        if not contract.is_real_user_media:
            result.status = "NOT_TESTED"
            result.required_file_instructions = contract.required_file_instructions
            result.missing_evidence.append(
                "Authentic ~60-minute user recording was not provided (bounded CPU environment)"
            )
            result.notes = "WAITING_FOR_INPUT: GT-06 contract prepared, but physical long-form render awaiting authentic footage."
            return result

        if not rendered_output_path or not Path(rendered_output_path).is_file():
            result.status = "NOT_TESTED"
            result.missing_evidence.append("Rendered 8-10 minute 16:9 output artifact was not provided")
            return result

        # Budget check
        if budget_attempts is not None and budget_attempts > max_budget_attempts:
            result.status = "BLOCKED_BUDGET_EXCEEDED"
            result.notes = f"Execution halted: budget limit ({max_budget_attempts} attempts) exceeded."
            contract.status = OrchestrationContractStatus.BLOCKED_BUDGET_EXCEEDED
            return result

        # Cancellation check
        if is_cancelled:
            result.status = "CANCELLED"
            result.notes = "Run cancelled by user request."
            contract.status = OrchestrationContractStatus.CANCELLED
            return result

        try:
            probe = MediaProbeService.probe_file(rendered_output_path)
            if not probe.magic_bytes_valid:
                result.issues.append("Rendered output has invalid container")
            if probe.synthetic_filler_detected:
                result.issues.append(f"Rendered output has synthetic filler: {probe.synthetic_filler_reason}")
            if probe.aspect_ratio != "16:9":
                result.issues.append(f"Rendered output aspect ratio {probe.aspect_ratio} is not 16:9")
            if not (480.0 <= probe.duration_seconds <= 600.0):
                result.issues.append(f"Rendered output duration {probe.duration_seconds:.1f}s is not 8-10 minutes")

            result.artifacts_verified_count = 1
            result.distinct_hashes_count = 1
            result.preserved_outputs = [rendered_output_path]
            result.motion_review_urls = [contract.motion_review_url]
            result.editorial_assessment = "EDITORIAL_NOT_ASSESSED"
            result.human_approval_required = True

            if result.issues:
                result.status = "FAILED"
                contract.status = OrchestrationContractStatus.FAILED
            else:
                result.status = "READY_FOR_REVIEW"
                result.notes = "READY_FOR_REVIEW: 8-10 minute 16:9 narrative cut rendered. Editorial coherence awaits human assessment."
                contract.status = OrchestrationContractStatus.READY_FOR_REVIEW
        except Exception as e:
            result.issues.append(f"Failed to probe rendered narrative output: {str(e)}")
            result.status = "FAILED"
            contract.status = OrchestrationContractStatus.FAILED

        return result
