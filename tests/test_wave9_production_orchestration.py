# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 9 Tests: Production Path Acceptance Orchestration (V1, V2, V3).

Verifies:
- GT-05 (V1): 1 authorized gameplay recording -> 3 vertical shorts (~60s) with subtitles,
  independent project IDs, and Motion review URLs -> READY_FOR_REVIEW.
- GT-05 PARTIAL: Failed third output preserves the first two outputs as PARTIAL without
  falsely claiming completion or failing the valid outputs.
- GT-06 (V3): 1 authentic ~60-min recording -> 8-10 min 16:9 narrative condensation with
  editorial assessment strictly preserved as EDITORIAL_NOT_ASSESSED.
- GT-07 (V2): 5 authorized sources -> 10 distinct vertical outputs with lineage and dedupe.
- Cancellation and budget cap enforcement: stops execution and preserves completed outputs.
- ProductionMediaPipelineRunner protocol and isolation: unmounted production runner reports
  MEDIA_ENGINE_NOT_MOUNTED; fake test runners cannot leak into production paths.
"""
from pathlib import Path
import pytest

from backend.production_acceptance.contracts import (
    MediaProbeMetadata,
    OrchestrationContractStatus,
    RightsVerificationStatus,
    SourceMediaAsset,
    V1ExpectedOutputSpec,
    V2ExpectedOutputSpec,
    V3NarrativeCut,
)
from backend.production_acceptance.manifest import (
    SourceLicenseType,
    UserPermittedSourceItem,
    UserPermittedSourceManifest,
)
from backend.production_acceptance.orchestration import (
    V1GameplayOrchestrator,
    V2MultiSourceOrchestrator,
    V3LongFormOrchestrator,
)
from backend.production_acceptance.probe import MediaProbeService
from backend.production_acceptance.runner import (
    MediaPipelineRunnerProtocol,
    PipelineRunnerError,
    ProductionMediaPipelineRunner,
    RenderedOutputResult,
)


def _create_mock_video(path: Path, payload: bytes = b"mock_video_bytes"):
    """Helper to write a valid MP4 ftyp container with unique payload."""
    path.parent.mkdir(parents=True, exist_ok=True)
    header = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41"
    path.write_bytes(header + payload)


def _make_mock_probe_callable(aspect_ratio: str = "9:16", duration_seconds: float = 58.5):
    """Returns a mock probe callable returning specified duration and aspect ratio."""
    def mock_probe(file_path):
        p = Path(file_path)
        sha = MediaProbeService.calculate_sha256(p)
        return MediaProbeMetadata(
            file_path=str(p),
            file_size_bytes=p.stat().st_size,
            sha256_hash=sha,
            magic_bytes_valid=True,
            has_audio_stream=True,
            aspect_ratio=aspect_ratio,
            duration_seconds=duration_seconds,
        )
    return mock_probe


class FakeTestPipelineRunner(MediaPipelineRunnerProtocol):
    """Isolated test-only runner double simulating native media pipeline."""

    async def render_v1_shorts(self, contract, output_directory, budget_limit_attempts=3):
        out_dir = Path(output_directory)
        results = []
        for idx, spec in enumerate(contract.expected_outputs):
            p = out_dir / f"{spec.output_id}.mp4"
            _create_mock_video(p, f"rendered_clip_content_{idx}".encode())
            results.append(
                RenderedOutputResult(
                    output_id=spec.output_id,
                    project_id=spec.project_id,
                    file_path=str(p),
                    sha256_hash=MediaProbeService.calculate_sha256(p),
                    duration_seconds=58.5,
                    aspect_ratio="9:16",
                    has_audio=True,
                    success=True,
                    motion_review_url=spec.motion_review_url,
                )
            )
        return results

    async def render_v2_batch(self, contract, output_directory):
        out_dir = Path(output_directory)
        results = []
        for idx, spec in enumerate(contract.expected_outputs):
            p = out_dir / f"{spec.output_id}.mp4"
            _create_mock_video(p, f"v2_rendered_content_{idx}".encode())
            results.append(
                RenderedOutputResult(
                    output_id=spec.output_id,
                    project_id=contract.project_id,
                    file_path=str(p),
                    sha256_hash=MediaProbeService.calculate_sha256(p),
                    duration_seconds=55.0,
                    aspect_ratio="9:16",
                    has_audio=True,
                    success=True,
                    motion_review_url=spec.motion_review_url,
                )
            )
        return results

    async def render_v3_narrative(self, contract, output_directory):
        p = Path(output_directory) / f"v3_{contract.project_id}.mp4"
        _create_mock_video(p, b"v3_narrative_condensation_bytes")
        return RenderedOutputResult(
            output_id=f"v3_narrative_{contract.project_id}",
            project_id=contract.project_id,
            file_path=str(p),
            sha256_hash=MediaProbeService.calculate_sha256(p),
            duration_seconds=510.0,
            aspect_ratio="16:9",
            has_audio=True,
            success=True,
            motion_review_url=contract.motion_review_url,
        )


class TestV1GameplayOrchestrationWave9:
    """Verifies GT-05 V1 mode with manifest integration, READY_FOR_REVIEW, and PARTIAL."""

    def test_v1_manifest_integration_and_contract(self, tmp_path: Path, monkeypatch):
        base_dir = tmp_path / "data" / "acceptance" / "gt05_inputs"
        src_path = base_dir / "gameplay.mp4"
        _create_mock_video(src_path, b"authorized_gameplay_recording_data")

        # Mock probe duration to 240s for gameplay
        monkeypatch.setattr(MediaProbeService, "probe_file", _make_mock_probe_callable(aspect_ratio="16:9", duration_seconds=240.0))

        item = UserPermittedSourceItem(
            source_id="item_gp_01",
            file_path=str(src_path),
            rights_holder="GamerG",
            license_type=SourceLicenseType.LICENSED_GAMEPLAY,
            permitted_uses=["creator_edit", "social_distribution"],
            consent_signed_at_utc="2026-10-13T12:00:00Z",
        )
        item.consent_signature = item.compute_consent_signature()

        manifest = UserPermittedSourceManifest(
            manifest_id="mf_v1_01",
            gate_id="GT-05",
            items=[item],
            allowed_base_dirs=[str(tmp_path / "data" / "acceptance")],
            is_real_user_media=True,
        )

        orchestrator = V1GameplayOrchestrator(project_id="proj_v1_manifest")
        contract = orchestrator.build_contract_from_manifest(manifest)

        assert contract.gate_id == "GT-05"
        assert contract.is_real_user_media is True
        assert len(contract.expected_outputs) == 3
        assert len(contract.independent_project_ids) == 3
        assert contract.status == OrchestrationContractStatus.CONTRACT_PREPARED

    @pytest.mark.asyncio
    async def test_v1_three_vertical_shorts_ready_for_review(self, tmp_path: Path, monkeypatch):
        src_path = tmp_path / "data" / "acceptance" / "gameplay.mp4"
        _create_mock_video(src_path, b"gameplay_stream")

        source = SourceMediaAsset(
            source_id="src_01",
            file_path=str(src_path),
            rights_status=RightsVerificationStatus.AUTHORIZED_USER_MEDIA,
        )

        orchestrator = V1GameplayOrchestrator(project_id="proj_gt05_review")
        contract = orchestrator.build_contract(source, is_real_user_media=True, probe_file=False)

        # Render 3 outputs using fake runner
        runner = FakeTestPipelineRunner()
        results = await runner.render_v1_shorts(contract, tmp_path / "outputs")
        output_paths = [r.file_path for r in results]

        # Mock probe for vertical outputs (9:16, 58.5s)
        monkeypatch.setattr(MediaProbeService, "probe_file", _make_mock_probe_callable(aspect_ratio="9:16", duration_seconds=58.5))

        evaluated = orchestrator.evaluate_acceptance(contract, rendered_output_paths=output_paths)

        # Must report READY_FOR_REVIEW with editorial left open
        assert evaluated.gate_id == "GT-05"
        assert evaluated.status == "READY_FOR_REVIEW"
        assert evaluated.artifacts_verified_count == 3
        assert evaluated.distinct_hashes_count == 3
        assert len(evaluated.preserved_outputs) == 3
        assert evaluated.editorial_assessment == "EDITORIAL_NOT_ASSESSED"
        assert evaluated.human_approval_required is True
        assert contract.status == OrchestrationContractStatus.READY_FOR_REVIEW

    @pytest.mark.asyncio
    async def test_v1_partial_failure_preserves_first_two_outputs(self, tmp_path: Path, monkeypatch):
        """
        Wave 9 Requirement: When third output fails to render or is missing,
        first two valid outputs must be preserved with status PARTIAL.
        """
        src_path = tmp_path / "data" / "acceptance" / "gameplay.mp4"
        _create_mock_video(src_path, b"gameplay_stream")

        source = SourceMediaAsset(
            source_id="src_01",
            file_path=str(src_path),
            rights_status=RightsVerificationStatus.AUTHORIZED_USER_MEDIA,
        )

        orchestrator = V1GameplayOrchestrator(project_id="proj_gt05_partial")
        contract = orchestrator.build_contract(source, is_real_user_media=True, probe_file=False)

        # Create only 2 valid outputs (3rd output failed)
        out_dir = tmp_path / "partial_outputs"
        out_dir.mkdir(parents=True, exist_ok=True)
        clip1 = out_dir / "clip_01.mp4"
        clip2 = out_dir / "clip_02.mp4"
        _create_mock_video(clip1, b"clip_01_content")
        _create_mock_video(clip2, b"clip_02_content")

        monkeypatch.setattr(MediaProbeService, "probe_file", _make_mock_probe_callable(aspect_ratio="9:16", duration_seconds=58.5))

        # Evaluate with only the 2 valid outputs
        evaluated = orchestrator.evaluate_acceptance(
            contract, rendered_output_paths=[str(clip1), str(clip2)]
        )

        assert evaluated.gate_id == "GT-05"
        assert evaluated.status == "PARTIAL"
        assert evaluated.artifacts_verified_count == 2
        assert len(evaluated.preserved_outputs) == 2
        assert str(clip1) in evaluated.preserved_outputs
        assert str(clip2) in evaluated.preserved_outputs
        assert evaluated.preserved_project_ids == contract.independent_project_ids[:2]
        assert "PARTIAL: 2 of 3 vertical shorts preserved" in evaluated.notes
        assert contract.status == OrchestrationContractStatus.PARTIAL

    def test_v1_cancellation_and_budget_cap_enforcement(self, tmp_path: Path, monkeypatch):
        src_path = tmp_path / "data" / "acceptance" / "gameplay.mp4"
        _create_mock_video(src_path, b"gameplay_data")

        source = SourceMediaAsset(
            source_id="src_01",
            file_path=str(src_path),
            rights_status=RightsVerificationStatus.AUTHORIZED_USER_MEDIA,
        )

        orchestrator = V1GameplayOrchestrator(project_id="proj_gt05_budget")
        contract = orchestrator.build_contract(source, is_real_user_media=True, probe_file=False)

        clip1 = tmp_path / "clip_01.mp4"
        _create_mock_video(clip1, b"clip_01_bytes")

        monkeypatch.setattr(MediaProbeService, "probe_file", _make_mock_probe_callable(aspect_ratio="9:16", duration_seconds=58.5))

        # 1. Test budget cap exceeded
        eval_budget = orchestrator.evaluate_acceptance(
            contract,
            rendered_output_paths=[str(clip1)],
            budget_attempts=5,
            max_budget_attempts=3,
        )
        assert eval_budget.status == "BLOCKED_BUDGET_EXCEEDED"
        assert len(eval_budget.preserved_outputs) == 1
        assert "budget limit (3 attempts) exceeded" in eval_budget.notes

        # 2. Test user cancellation
        eval_cancel = orchestrator.evaluate_acceptance(
            contract,
            rendered_output_paths=[str(clip1)],
            is_cancelled=True,
        )
        assert eval_cancel.status == "CANCELLED"
        assert len(eval_cancel.preserved_outputs) == 1
        assert "cancelled by user request" in eval_cancel.notes


class TestV2AndV3OrchestrationWave9:
    """Verifies V2 (GT-07) and V3 (GT-06) acceptance orchestration."""

    @pytest.mark.asyncio
    async def test_v2_ten_outputs_and_partial_preservation(self, tmp_path: Path, monkeypatch):
        sources = []
        for i in range(5):
            p = tmp_path / f"src_{i+1}.mp4"
            _create_mock_video(p, f"source_{i+1}_payload".encode())
            sources.append(
                SourceMediaAsset(
                    source_id=f"src_{i+1}",
                    file_path=str(p),
                    rights_status=RightsVerificationStatus.COMMERCIAL_CREATOR_LICENSE,
                )
            )

        orchestrator = V2MultiSourceOrchestrator(project_id="proj_v2_wave9")
        contract = orchestrator.build_contract(sources, is_real_user_media=True, probe_files=False)

        runner = FakeTestPipelineRunner()
        results = await runner.render_v2_batch(contract, tmp_path / "v2_out")

        monkeypatch.setattr(MediaProbeService, "probe_file", _make_mock_probe_callable(aspect_ratio="9:16", duration_seconds=55.0))

        # 1. Full 10 outputs -> READY_FOR_REVIEW
        all_paths = [r.file_path for r in results]
        eval_full = orchestrator.evaluate_acceptance(contract, rendered_output_paths=all_paths)
        assert eval_full.status == "READY_FOR_REVIEW"
        assert eval_full.artifacts_verified_count == 10
        assert eval_full.editorial_assessment == "EDITORIAL_NOT_ASSESSED"

        # 2. Partial (8 of 10 outputs) -> PARTIAL
        partial_paths = all_paths[:8]
        eval_partial = orchestrator.evaluate_acceptance(contract, rendered_output_paths=partial_paths)
        assert eval_partial.status == "PARTIAL"
        assert eval_partial.artifacts_verified_count == 8
        assert len(eval_partial.preserved_outputs) == 8

    def test_v3_narrative_condensation_editorial_open(self, tmp_path: Path, monkeypatch):
        src_path = tmp_path / "longform_60m.mp4"
        _create_mock_video(src_path, b"authentic_longform_recording")

        source = SourceMediaAsset(
            source_id="src_long_01",
            file_path=str(src_path),
            rights_status=RightsVerificationStatus.AUTHORIZED_USER_MEDIA,
        )

        orchestrator = V3LongFormOrchestrator(project_id="proj_v3_wave9")
        contract = orchestrator.build_contract(source, is_real_user_media=True, probe_file=False)

        out_path = tmp_path / "v3_narrative.mp4"
        _create_mock_video(out_path, b"rendered_narrative_content")

        monkeypatch.setattr(MediaProbeService, "probe_file", _make_mock_probe_callable(aspect_ratio="16:9", duration_seconds=510.0))

        evaluated = orchestrator.evaluate_acceptance(contract, rendered_output_path=str(out_path))

        assert evaluated.gate_id == "GT-06"
        assert evaluated.status == "READY_FOR_REVIEW"
        assert evaluated.artifacts_verified_count == 1
        assert evaluated.editorial_assessment == "EDITORIAL_NOT_ASSESSED"
        assert evaluated.human_approval_required is True


class TestProductionRunnerProtocolIsolation:
    """Verifies that ProductionMediaPipelineRunner strictly requires native mounting."""

    @pytest.mark.asyncio
    async def test_unmounted_production_runner_raises_clean_error(self, tmp_path: Path):
        unmounted = ProductionMediaPipelineRunner(engine_callable=None)
        assert unmounted.is_engine_mounted is False

        source = SourceMediaAsset(
            source_id="src_01",
            file_path=str(tmp_path / "src.mp4"),
            rights_status=RightsVerificationStatus.AUTHORIZED_USER_MEDIA,
        )
        orchestrator = V1GameplayOrchestrator()
        contract = orchestrator.build_contract(source, is_real_user_media=False, probe_file=False)

        with pytest.raises(PipelineRunnerError) as exc_info:
            await unmounted.render_v1_shorts(contract, tmp_path / "out")

        assert exc_info.value.code == "MEDIA_ENGINE_NOT_MOUNTED"
        assert "not mounted in this worker context" in exc_info.value.message
