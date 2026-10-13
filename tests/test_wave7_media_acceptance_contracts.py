# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 7 Acceptance Tests: Real Media Contracts and Acceptance Truth.

Verifies:
- Physical MediaProbeService (magic bytes, SHA256 deduplication, synthetic filler detection).
- V2 Multi-Source Orchestrator (GT-07): 5 authorized sources -> 10 distinct outputs (9:16, 45-65s).
- V3 Long-Form Orchestrator (GT-06): 1 authentic ~60-min recording -> 8-10 min 16:9 narrative cut list.
- Negative mechanics: corrupt files, unauthorized rights, duplicate hashes, synthetic filler.
- Truth guards: strictly returns NOT_TESTED in absence of authentic human media.
- Master proposal mapping: GT-05 (V1), GT-06 (V3), GT-07 (V2).
"""
import os
import tempfile
from pathlib import Path
import pytest

from backend.production_acceptance.contracts import (
    MediaProbeMetadata,
    OrchestrationContractStatus,
    RightsVerificationStatus,
    SourceMediaAsset,
    V3NarrativeCut,
)
from backend.production_acceptance.probe import MediaProbeService
from backend.production_acceptance.orchestration import (
    V2MultiSourceOrchestrator,
    V3LongFormOrchestrator,
)
from backend.production_acceptance.registry import ProductionAcceptanceRegistry
from backend.release_acceptance.validator import (
    AcceptanceGateStatus,
    ReleaseAcceptanceAuditor,
    V2MultiOutputValidator,
    V3LongFormNarrativeValidator,
)


def _create_dummy_mp4_header(path: Path, extra_payload: bytes = b"valid_media_content"):
    """Creates a tiny valid MP4 ftyp container header with payload."""
    # 4 bytes size, b'ftyp', b'isom', 4 bytes minor, compatible brands
    header = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41"
    path.write_bytes(header + extra_payload)


def _create_dummy_wav_header(path: Path, extra_payload: bytes = b"valid_audio_pcm"):
    """Creates a tiny valid RIFF WAV header."""
    header = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x02\x00\x44\xac\x00\x00"
    path.write_bytes(header + extra_payload)


class TestMediaProbeService:
    """Verifies physical media probing, container checks, and filler detection."""

    def test_probe_mp4_magic_bytes(self, tmp_path: Path):
        file_path = tmp_path / "sample.mp4"
        _create_dummy_mp4_header(file_path, b"audio_and_video_stream_mock")

        meta = MediaProbeService.probe_file(file_path)
        assert meta.magic_bytes_valid is True
        assert meta.container_format.startswith("mp4")
        assert len(meta.sha256_hash) == 64
        assert meta.file_size_bytes > 0

    def test_probe_wav_magic_bytes(self, tmp_path: Path):
        file_path = tmp_path / "sample.wav"
        _create_dummy_wav_header(file_path, b"speech_narration_payload")

        meta = MediaProbeService.probe_file(file_path)
        assert meta.magic_bytes_valid is True
        assert meta.container_format == "wav"
        assert meta.has_audio_stream is True

    def test_probe_corrupt_or_empty_file(self, tmp_path: Path):
        empty_file = tmp_path / "empty.mp4"
        empty_file.write_bytes(b"")

        meta = MediaProbeService.probe_file(empty_file)
        assert meta.magic_bytes_valid is False
        assert meta.synthetic_filler_detected is True
        assert "Zero-byte" in meta.synthetic_filler_reason

    def test_detect_synthetic_filler_markers(self, tmp_path: Path):
        filler_file = tmp_path / "clip_anullsrc_filler.mp4"
        _create_dummy_mp4_header(filler_file, b"filler_payload")

        meta = MediaProbeService.probe_file(filler_file)
        assert meta.synthetic_filler_detected is True
        assert "synthetic filler indicator" in meta.synthetic_filler_reason.lower()

    def test_detect_null_byte_block_filler(self, tmp_path: Path):
        null_file = tmp_path / "nulls.mp4"
        header = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41"
        # 4000 zero bytes
        null_file.write_bytes(header + (b"\x00" * 4000))

        meta = MediaProbeService.probe_file(null_file)
        assert meta.synthetic_filler_detected is True
        assert "null-byte density" in meta.synthetic_filler_reason.lower()


class TestV2MultiSourceOrchestrator:
    """Verifies GT-07 (V2 Mode): 5 distinct sources -> 10 editable/rendered outputs."""

    def test_contract_generation_with_five_valid_sources(self, tmp_path: Path):
        sources = []
        for i in range(5):
            src_path = tmp_path / f"source_{i+1}.mp4"
            _create_dummy_mp4_header(src_path, f"source_distinct_content_{i+1}".encode())
            asset = SourceMediaAsset(
                source_id=f"src_{i+1}",
                file_path=str(src_path),
                rights_status=RightsVerificationStatus.AUTHORIZED_USER_MEDIA,
                permitted_uses=["creator_edit", "social_distribution"],
            )
            sources.append(asset)

        orchestrator = V2MultiSourceOrchestrator(project_id="test_proj_v2")
        contract = orchestrator.build_contract(sources, is_real_user_media=False)

        assert contract.gate_id == "GT-07"
        assert contract.status == OrchestrationContractStatus.CONTRACT_PREPARED
        assert len(contract.expected_outputs) == 10

        # Check expected outputs structure
        for out in contract.expected_outputs:
            assert out.target_aspect_ratio == "9:16"
            assert 45.0 <= out.target_duration_min_sec <= out.target_duration_max_sec <= 65.0
            assert out.motion_review_url.startswith("/motion?output_id=")
            assert f"project_id=test_proj_v2" in out.motion_review_url

    def test_rejects_fewer_than_five_sources(self, tmp_path: Path):
        sources = []
        for i in range(4):  # only 4 sources
            src_path = tmp_path / f"source_{i+1}.mp4"
            _create_dummy_mp4_header(src_path, f"src_content_{i}".encode())
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

    def test_rejects_duplicate_source_hashes(self, tmp_path: Path):
        sources = []
        # Create identical content for sources 1 and 2
        for i in range(5):
            src_path = tmp_path / f"source_{i+1}.mp4"
            content = b"identical_content" if i < 2 else f"distinct_{i}".encode()
            _create_dummy_mp4_header(src_path, content)
            asset = SourceMediaAsset(
                source_id=f"src_{i+1}",
                file_path=str(src_path),
                rights_status=RightsVerificationStatus.COMMERCIAL_CREATOR_LICENSE,
            )
            sources.append(asset)

        orchestrator = V2MultiSourceOrchestrator()
        contract = orchestrator.build_contract(sources)
        assert contract.status == OrchestrationContractStatus.REJECTED
        assert any("Duplicate source detected" in issue for issue in contract.issues)

    def test_rejects_unauthorized_rights(self, tmp_path: Path):
        sources = []
        for i in range(5):
            src_path = tmp_path / f"source_{i+1}.mp4"
            _create_dummy_mp4_header(src_path, f"src_content_{i}".encode())
            rights = (
                RightsVerificationStatus.AUTHORIZED_USER_MEDIA
                if i != 3
                else RightsVerificationStatus.MALICIOUS_UNAUTHORIZED
            )
            asset = SourceMediaAsset(
                source_id=f"src_{i+1}",
                file_path=str(src_path),
                rights_status=rights,
            )
            sources.append(asset)

        orchestrator = V2MultiSourceOrchestrator()
        contract = orchestrator.build_contract(sources)
        assert contract.status == OrchestrationContractStatus.REJECTED
        assert any("MALICIOUS_UNAUTHORIZED" in issue for issue in contract.issues)

    def test_acceptance_evaluation_truth_guard(self, tmp_path: Path):
        sources = []
        for i in range(5):
            src_path = tmp_path / f"source_{i+1}.mp4"
            _create_dummy_mp4_header(src_path, f"src_unique_{i}".encode())
            asset = SourceMediaAsset(
                source_id=f"src_{i+1}",
                file_path=str(src_path),
                rights_status=RightsVerificationStatus.AUTHORIZED_USER_MEDIA,
            )
            sources.append(asset)

        orchestrator = V2MultiSourceOrchestrator()
        contract = orchestrator.build_contract(sources, is_real_user_media=False)
        result = orchestrator.evaluate_acceptance(contract, rendered_output_paths=None)

        # Must report NOT_TESTED without authentic user media
        assert result.gate_id == "GT-07"
        assert result.status == "NOT_TESTED"
        assert len(result.missing_evidence) > 0


class TestV3LongFormOrchestrator:
    """Verifies GT-06 (V3 Mode): 1 authentic ~60-min recording -> 8-10 min 16:9 narrative cut list."""

    def test_contract_generation_with_valid_recording(self, tmp_path: Path):
        src_path = tmp_path / "longform_60m.mp4"
        _create_dummy_mp4_header(src_path, b"authentic_longform_recording_mock")

        source = SourceMediaAsset(
            source_id="src_longform_01",
            file_path=str(src_path),
            rights_status=RightsVerificationStatus.COMMERCIAL_CREATOR_LICENSE,
        )

        orchestrator = V3LongFormOrchestrator(project_id="test_proj_v3")
        contract = orchestrator.build_contract(source, is_real_user_media=False)

        assert contract.gate_id == "GT-06"
        assert contract.status == OrchestrationContractStatus.CONTRACT_PREPARED
        assert contract.target_aspect_ratio == "16:9"
        assert contract.target_duration_min_sec == 480.0
        assert contract.target_duration_max_sec == 600.0
        assert len(contract.narrative_cut_list) >= 3

        total_cut_duration = sum(c.duration_sec for c in contract.narrative_cut_list)
        assert 480.0 <= total_cut_duration <= 600.0
        assert contract.motion_review_url.startswith("/motion?output_id=")

    def test_rejects_unauthorized_source_rights(self, tmp_path: Path):
        src_path = tmp_path / "podcast.mp4"
        _create_dummy_mp4_header(src_path, b"unauthorized_podcast")

        source = SourceMediaAsset(
            source_id="src_podcast",
            file_path=str(src_path),
            rights_status=RightsVerificationStatus.UNVERIFIED_THIRD_PARTY,
        )

        orchestrator = V3LongFormOrchestrator()
        contract = orchestrator.build_contract(source)
        assert contract.status == OrchestrationContractStatus.REJECTED
        assert any("UNVERIFIED_THIRD_PARTY" in issue for issue in contract.issues)

    def test_rejects_out_of_bounds_narrative_cut_list(self, tmp_path: Path):
        src_path = tmp_path / "longform.mp4"
        _create_dummy_mp4_header(src_path, b"audio_recording")

        source = SourceMediaAsset(
            source_id="src_valid",
            file_path=str(src_path),
            rights_status=RightsVerificationStatus.AUTHORIZED_USER_MEDIA,
        )

        # Cuts summing to only 120s (2 minutes), violating 8-10 min requirement
        short_cuts = [
            V3NarrativeCut(
                cut_id="c1",
                source_start_sec=0.0,
                source_end_sec=120.0,
                duration_sec=120.0,
                scene_name="Too Short",
            )
        ]

        orchestrator = V3LongFormOrchestrator()
        contract = orchestrator.build_contract(source, narrative_cut_list=short_cuts)
        assert contract.status == OrchestrationContractStatus.REJECTED
        assert any("outside 8-10 minutes" in issue for issue in contract.issues)

    def test_acceptance_evaluation_truth_guard(self, tmp_path: Path):
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
        assert len(result.missing_evidence) > 0


class TestMasterProposalReleaseTruth:
    """Verifies that release audits accurately preserve Master Proposal gate mapping and truth states."""

    def test_auditor_all_gates_mapping_and_truth(self):
        audit = ReleaseAcceptanceAuditor.audit_all()

        assert audit["PHASE10_11_RELEASE_READY"] == "NO"
        assert audit["LIVE_PUBLISHING_VERIFIED"] == "NO"
        assert audit["LIVE_ANALYTICS_VERIFIED"] == "NO"

        details = audit["details"]
        # GT-05: 1 gameplay -> 3 vertical shorts (V1)
        assert details["GT-05"]["status"] == "NOT_TESTED"
        assert "V1" in details["GT-05"]["name"]

        # GT-06: 60 min -> 8-10 min 16:9 narrative (V3)
        assert details["GT-06"]["status"] == "NOT_TESTED"
        assert "V3" in details["GT-06"]["name"]

        # GT-07: 5 sources -> 10 outputs (V2)
        assert details["GT-07"]["status"] == "NOT_TESTED"
        assert "V2" in details["GT-07"]["name"]

        # GT-28: Live social media publishing
        assert details["GT-28"]["status"] == "BLOCKED"

    def test_production_acceptance_registry_statuses(self):
        statuses = ProductionAcceptanceRegistry.get_all_gate_statuses()
        assert statuses["GT-05"]["status"] == "NOT_TESTED"
        assert statuses["GT-06"]["status"] == "NOT_TESTED"
        assert statuses["GT-07"]["status"] == "NOT_TESTED"
        assert "protocol" in statuses
        assert "GT-05" in statuses["protocol"]["gates"]
        assert "GT-06" in statuses["protocol"]["gates"]
        assert "GT-07" in statuses["protocol"]["gates"]
