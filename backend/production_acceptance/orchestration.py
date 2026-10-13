# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Production Path Orchestrators for V2 and V3 (Wave 7).

Implements rigorous acceptance orchestration:
- V2MultiSourceOrchestrator (GT-07): 5 authorized sources -> 10 editable/rendered outputs (9:16).
- V3LongFormOrchestrator (GT-06): 1 authentic ~60-min recording -> 8-10 min 16:9 narrative cut list & result.
- Enforces strict rights verification, physical probe metadata, hash deduplication,
  motion review URL canonical linking, and strict truth guard (NOT_TESTED without authentic media).
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
    V2ExpectedOutputSpec,
    V2ProductionContract,
    V3NarrativeCut,
    V3ProductionContract,
)
from .probe import MediaProbeService

logger = logging.getLogger(__name__)

AUTHORIZED_RIGHTS = {
    RightsVerificationStatus.AUTHORIZED_USER_MEDIA,
    RightsVerificationStatus.COMMERCIAL_CREATOR_LICENSE,
}


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

        if contract.status == OrchestrationContractStatus.REJECTED or contract.status == OrchestrationContractStatus.FAILED:
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
        return contract

    def evaluate_acceptance(
        self,
        contract: V2ProductionContract,
        rendered_output_paths: Optional[List[str]] = None,
    ) -> OrchestrationResult:
        """
        Evaluates production acceptance for GT-07.
        Truth guard: without authentic user media and rendered files, returns NOT_TESTED.
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
            result.missing_evidence.append(
                "Authentic licensed multi-source media (5 distinct real creator assets) was not provided"
            )
            result.notes = "GT-07 orchestration contract prepared, but physical render skipped due to lack of authentic media."
            return result

        if not rendered_output_paths or len(rendered_output_paths) != 10:
            result.status = "NOT_TESTED"
            result.missing_evidence.append(
                f"Expected 10 rendered outputs, found {len(rendered_output_paths or [])}"
            )
            return result

        # Probe and deduplicate rendered outputs
        output_hashes = set()
        motion_urls = []
        for path_str in rendered_output_paths:
            try:
                probe = MediaProbeService.probe_file(path_str)
                if not probe.magic_bytes_valid:
                    result.issues.append(f"Rendered output {path_str} has invalid container")
                if probe.synthetic_filler_detected:
                    result.issues.append(f"Rendered output {path_str} is synthetic filler")
                if probe.aspect_ratio != "9:16":
                    result.issues.append(f"Rendered output {path_str} aspect ratio {probe.aspect_ratio} is not 9:16")
                if not (45.0 <= probe.duration_seconds <= 65.0):
                    result.issues.append(f"Rendered output {path_str} duration {probe.duration_seconds:.1f}s outside [45, 65]")
                if probe.sha256_hash in output_hashes:
                    result.issues.append(f"Duplicate rendered output detected: hash {probe.sha256_hash[:12]}")
                output_hashes.add(probe.sha256_hash)
            except Exception as e:
                result.issues.append(f"Failed to probe rendered output {path_str}: {str(e)}")

        for spec in contract.expected_outputs:
            if spec.motion_review_url:
                motion_urls.append(spec.motion_review_url)

        result.artifacts_verified_count = len(rendered_output_paths)
        result.distinct_hashes_count = len(output_hashes)
        result.motion_review_urls = motion_urls

        if result.issues:
            result.status = "FAILED"
        elif result.distinct_hashes_count == 10 and result.artifacts_verified_count == 10:
            result.status = "PASSED"
        else:
            result.status = "NOT_TESTED"

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
            contract.narrative_cut_list = narrative_cut_list
        else:
            # Generate default 8.5 min (510s) narrative structure
            contract.narrative_cut_list = self._generate_default_cut_list()

        if contract.status != OrchestrationContractStatus.REJECTED:
            contract.status = OrchestrationContractStatus.CONTRACT_PREPARED

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

    def evaluate_acceptance(
        self,
        contract: V3ProductionContract,
        rendered_output_path: Optional[str] = None,
    ) -> OrchestrationResult:
        """
        Evaluates production acceptance for GT-06.
        Truth guard: without authentic ~60-minute media, returns NOT_TESTED.
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
            result.missing_evidence.append(
                "Authentic ~60-minute user recording was not provided (bounded CPU environment)"
            )
            result.notes = "GT-06 contract prepared, but physical long-form render skipped due to lack of authentic footage."
            return result

        if not rendered_output_path or not Path(rendered_output_path).is_file():
            result.status = "NOT_TESTED"
            result.missing_evidence.append("Rendered 8-10 minute 16:9 output artifact was not provided")
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
            result.motion_review_urls = [contract.motion_review_url]

            if result.issues:
                result.status = "FAILED"
            else:
                result.status = "PASSED"
        except Exception as e:
            result.issues.append(f"Failed to probe rendered narrative output: {str(e)}")
            result.status = "FAILED"

        return result
