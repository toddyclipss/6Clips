# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 8 Acceptance Tests: Real Production Acceptance, Orchestration & Truth.

Verifies:
- GT-05 (V1): 1 licensed gameplay source -> 3 usable independent ~60s vertical clips
  with provenance, subtitles/audio, Motion review links, and independent project IDs.
- GT-06 (V3): 1 authentic ~60-min recording -> 8-10 min 16:9 narrative cut list & result.
- GT-07 (V2): 5 authorized sources -> 10 distinct editable/rendered outputs (9:16).
- Negative mechanics: corrupt files, unauthorized rights, duplicate hashes, synthetic filler, short durations.
- Truth guards: strictly returns WAITING_FOR_INPUT / NOT_TESTED with concrete file instructions
  when authentic human media is absent; never claims success from synthetic fixtures alone.
"""
from pathlib import Path
import pytest

from backend.production_acceptance.contracts import (
    MediaProbeMetadata,
    OrchestrationContractStatus,
    RightsVerificationStatus,
    SourceMediaAsset,
    V1ExpectedOutputSpec,
    V3NarrativeCut,
)
from backend.production_acceptance.probe import MediaProbeService
from backend.production_acceptance.orchestration import (
    V1GameplayOrchestrator,
    V2MultiSourceOrchestrator,
    V3LongFormOrchestrator,
)
from backend.production_acceptance.registry import ProductionAcceptanceRegistry
from backend.release_acceptance.validator import (
    AcceptanceGateStatus,
    ReleaseAcceptanceAuditor,
)


def _create_dummy_mp4_header(path: Path, extra_payload: bytes = b"valid_media_content"):
    """Creates a tiny valid MP4 ftyp container header with payload."""
    header = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41"
    path.write_bytes(header + extra_payload)


class TestGT05GameplayV1Orchestration:
    """Verifies GT-05 (V1 Mode): 1 licensed gameplay source -> 3 usable independent ~60s vertical clips."""

    def test_v1_contract_generation_structure(self, tmp_path: Path):
        src_path = tmp_path / "gameplay.mp4"
        _create_dummy_mp4_header(src_path, b"gameplay_video_audio_data")

        source = SourceMediaAsset(
            source_id="src_gameplay_01",
            file_path=str(src_path),
            rights_status=RightsVerificationStatus.AUTHORIZED_USER_MEDIA,
            permitted_uses=["creator_edit", "social_distribution"],
        )

        orchestrator = V1GameplayOrchestrator(project_id="proj_gt05_test")
        contract = orchestrator.build_contract(source, is_real_user_media=False)

        assert contract.gate_id == "GT-05"
        assert contract.status == OrchestrationContractStatus.CONTRACT_PREPARED
        assert len(contract.expected_outputs) == 3
        assert len(contract.independent_project_ids) == 3

        # Verify each of the 3 outputs has its own project reference, 9:16 aspect, and Motion review link
        for idx, out in enumerate(contract.expected_outputs):
            assert out.target_aspect_ratio == "9:16"
            assert 50.0 <= out.target_duration_min_sec <= out.target_duration_max_sec <= 70.0
            assert out.project_id == contract.independent_project_ids[idx]
            assert out.has_subtitles is True
            assert out.motion_review_url.startswith("/motion?output_id=")
            assert f"project_id={contract.independent_project_ids[idx]}" in out.motion_review_url

        # Verify instructions for operator
        assert len(contract.required_file_instructions) > 0
        assert any("data/acceptance/gt05_inputs/gameplay.mp4" in inst for inst in contract.required_file_instructions)

    def test_v1_rejects_unauthorized_rights(self, tmp_path: Path):
        src_path = tmp_path / "unauthorized_gameplay.mp4"
        _create_dummy_mp4_header(src_path, b"gameplay")

        source = SourceMediaAsset(
            source_id="src_bad_rights",
            file_path=str(src_path),
            rights_status=RightsVerificationStatus.MALICIOUS_UNAUTHORIZED,
        )

        orchestrator = V1GameplayOrchestrator()
        contract = orchestrator.build_contract(source)
        assert contract.status == OrchestrationContractStatus.REJECTED
        assert any("MALICIOUS_UNAUTHORIZED" in issue for issue in contract.issues)

    def test_v1_rejects_synthetic_filler_source(self, tmp_path: Path):
        src_path = tmp_path / "gameplay_anullsrc_filler.mp4"
        _create_dummy_mp4_header(src_path, b"gameplay_with_fake_audio")

        source = SourceMediaAsset(
            source_id="src_synthetic",
            file_path=str(src_path),
            rights_status=RightsVerificationStatus.AUTHORIZED_USER_MEDIA,
        )

        orchestrator = V1GameplayOrchestrator()
        contract = orchestrator.build_contract(source)
        assert contract.status == OrchestrationContractStatus.REJECTED
        assert any("synthetic filler" in issue for issue in contract.issues)

    def test_v1_acceptance_evaluation_truth_guard(self, tmp_path: Path):
        src_path = tmp_path / "gameplay.mp4"
        _create_dummy_mp4_header(src_path, b"gameplay")

        source = SourceMediaAsset(
            source_id="src_gameplay",
            file_path=str(src_path),
            rights_status=RightsVerificationStatus.AUTHORIZED_USER_MEDIA,
        )

        orchestrator = V1GameplayOrchestrator()
        contract = orchestrator.build_contract(source, is_real_user_media=False)
        result = orchestrator.evaluate_acceptance(contract, rendered_output_paths=None)

        # Must strictly report NOT_TESTED with WAITING_FOR_INPUT notes without authentic user footage
        assert result.gate_id == "GT-05"
        assert result.status == "NOT_TESTED"
        assert "WAITING_FOR_INPUT" in result.notes
        assert len(result.required_file_instructions) > 0
        assert len(result.missing_evidence) > 0


class TestGT07MultiSourceV2Orchestration:
    """Verifies GT-07 (V2 Mode): 5 authorized sources -> 10 distinct editable/rendered outputs."""

    def test_v2_contract_generation_structure(self, tmp_path: Path):
        sources = []
        for i in range(5):
            src_path = tmp_path / f"source_{i+1}.mp4"
            _create_dummy_mp4_header(src_path, f"source_payload_{i+1}".encode())
            asset = SourceMediaAsset(
                source_id=f"src_{i+1}",
                file_path=str(src_path),
                rights_status=RightsVerificationStatus.AUTHORIZED_USER_MEDIA,
            )
            sources.append(asset)

        orchestrator = V2MultiSourceOrchestrator(project_id="proj_gt07_test")
        contract = orchestrator.build_contract(sources, is_real_user_media=False)

        assert contract.gate_id == "GT-07"
        assert contract.status == OrchestrationContractStatus.CONTRACT_PREPARED
        assert len(contract.expected_outputs) == 10
        assert len(contract.required_file_instructions) > 0

    def test_v2_rejects_fewer_than_five_sources(self, tmp_path: Path):
        sources = []
        for i in range(3):
            src_path = tmp_path / f"source_{i+1}.mp4"
            _create_dummy_mp4_header(src_path, f"source_payload_{i+1}".encode())
            asset = SourceMediaAsset(
                source_id=f"src_{i+1}",
                file_path=str(src_path),
                rights_status=RightsVerificationStatus.AUTHORIZED_USER_MEDIA,
            )
            sources.append(asset)

        orchestrator = V2MultiSourceOrchestrator()
        contract = orchestrator.build_contract(sources)
        assert contract.status == OrchestrationContractStatus.REJECTED
        assert any("exactly 5 distinct source media assets" in issue for issue in contract.issues)

    def test_v2_acceptance_evaluation_truth_guard(self, tmp_path: Path):
        sources = []
        for i in range(5):
            src_path = tmp_path / f"source_{i+1}.mp4"
            _create_dummy_mp4_header(src_path, f"src_unique_{i}".encode())
            asset = SourceMediaAsset(
                source_id=f"src_{i+1}",
                file_path=str(src_path),
                rights_status=RightsVerificationStatus.COMMERCIAL_CREATOR_LICENSE,
            )
            sources.append(asset)

        orchestrator = V2MultiSourceOrchestrator()
        contract = orchestrator.build_contract(sources, is_real_user_media=False)
        result = orchestrator.evaluate_acceptance(contract, rendered_output_paths=None)

        assert result.gate_id == "GT-07"
        assert result.status == "NOT_TESTED"
        assert "WAITING_FOR_INPUT" in result.notes
        assert len(result.required_file_instructions) > 0


class TestGT06LongFormV3Orchestration:
    """Verifies GT-06 (V3 Mode): 1 authentic ~60-minute recording -> 8-10 min 16:9 narrative result."""

    def test_v3_contract_generation_structure(self, tmp_path: Path):
        src_path = tmp_path / "longform_60m.mp4"
        _create_dummy_mp4_header(src_path, b"authentic_longform_recording_mock")

        source = SourceMediaAsset(
            source_id="src_longform_01",
            file_path=str(src_path),
            rights_status=RightsVerificationStatus.COMMERCIAL_CREATOR_LICENSE,
        )

        orchestrator = V3LongFormOrchestrator(project_id="proj_gt06_test")
        contract = orchestrator.build_contract(source, is_real_user_media=False)

        assert contract.gate_id == "GT-06"
        assert contract.status == OrchestrationContractStatus.CONTRACT_PREPARED
        assert contract.target_aspect_ratio == "16:9"
        assert contract.target_duration_min_sec == 480.0
        assert contract.target_duration_max_sec == 600.0
        assert len(contract.narrative_cut_list) >= 4
        assert len(contract.required_file_instructions) > 0

    def test_v3_rejects_out_of_bounds_narrative_cut_list(self, tmp_path: Path):
        src_path = tmp_path / "longform.mp4"
        _create_dummy_mp4_header(src_path, b"audio_recording")

        source = SourceMediaAsset(
            source_id="src_valid",
            file_path=str(src_path),
            rights_status=RightsVerificationStatus.AUTHORIZED_USER_MEDIA,
        )

        # Cuts summing to 1500s (25 minutes), violating 8-10 min target
        long_cuts = [
            V3NarrativeCut(
                cut_id="c1",
                source_start_sec=0.0,
                source_end_sec=1500.0,
                duration_sec=1500.0,
                scene_name="Too Long",
            )
        ]

        orchestrator = V3LongFormOrchestrator()
        contract = orchestrator.build_contract(source, narrative_cut_list=long_cuts)
        assert contract.status == OrchestrationContractStatus.REJECTED
        assert any("outside 8-10 minutes" in issue for issue in contract.issues)

    def test_v3_acceptance_evaluation_truth_guard(self, tmp_path: Path):
        src_path = tmp_path / "longform.mp4"
        _create_dummy_mp4_header(src_path, b"audio_content")

        source = SourceMediaAsset(
            source_id="src_valid",
            file_path=str(src_path),
            rights_status=RightsVerificationStatus.AUTHORIZED_USER_MEDIA,
        )

        orchestrator = V3LongFormOrchestrator()
        contract = orchestrator.build_contract(source, is_real_user_media=False)
        result = orchestrator.evaluate_acceptance(contract, rendered_output_path=None)

        assert result.gate_id == "GT-06"
        assert result.status == "NOT_TESTED"
        assert "WAITING_FOR_INPUT" in result.notes
        assert len(result.required_file_instructions) > 0
