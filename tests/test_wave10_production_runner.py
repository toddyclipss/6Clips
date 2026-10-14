# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 10 Tests: Physical Production Media Pipeline Runner & Ground-Truth Verification.

Verifies:
- ProductionMediaPipelineRunner executing real physical FFmpeg transcoding:
  - Generates real H.264/AAC MP4 files with 9:16 vertical reframe.
  - Probes duration, container, audio streams, and calculates distinct SHA-256 hashes.
  - Verifies decoded frames cleanly pass through null sink without bitstream corruptions.
- Idempotency & Partial Recovery:
  - Already-rendered verified outputs are skipped on subsequent runs.
  - Simulated failure on 3rd output preserves 1st and 2nd outputs as valid.
  - Retry only re-renders the incomplete 3rd output.
- Ground-truth guards:
  - Technical fixture renders verify mechanical pipeline, but are marked physical technical fixtures.
  - Master gate status strictly remains NOT_TESTED / WAITING_FOR_INPUT when authentic creator media is absent.
"""
from pathlib import Path
import subprocess
import pytest

from backend.production_acceptance.contracts import (
    MediaProbeMetadata,
    OrchestrationContractStatus,
    RightsVerificationStatus,
    SourceMediaAsset,
    V1ExpectedOutputSpec,
    V1ProductionContract,
    V2ExpectedOutputSpec,
    V2ProductionContract,
    V3ProductionContract,
)
from backend.production_acceptance.orchestration import (
    V1GameplayOrchestrator,
    V2MultiSourceOrchestrator,
    V3LongFormOrchestrator,
)
from backend.production_acceptance.probe import MediaProbeService
from backend.production_acceptance.runner import (
    PipelineRunnerError,
    ProductionMediaPipelineRunner,
    RenderedOutputResult,
)


def _generate_synthetic_test_video(path: Path, duration_sec: int = 4):
    """
    Creates a physical playable MP4 video with real H.264 video and AAC audio
    using local FFmpeg for mechanical testing of transcoding and frame decoders.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", f"testsrc=duration={duration_sec}:size=1920x1080:rate=30",
        "-f", "lavfi",
        "-i", f"sine=frequency=1000:duration={duration_sec}",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "2",
        str(path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


class TestWave10PhysicalRunnerTranscoding:
    """Verifies physical FFmpeg execution and verification routines."""

    def test_ffmpeg_available_on_system(self):
        runner = ProductionMediaPipelineRunner()
        assert runner.is_ffmpeg_available() is True

    @pytest.mark.asyncio
    async def test_physical_ffmpeg_v1_transcode_and_decoded_frames(self, tmp_path: Path):
        """
        Creates a short test video fixture and executes ProductionMediaPipelineRunner with allow_direct_ffmpeg=True.
        Proves physical MP4 outputs are generated, have 9:16 aspect ratio, valid audio, and clean decoded frames.
        """
        src_path = tmp_path / "gameplay_fixture.mp4"
        _generate_synthetic_test_video(src_path, duration_sec=6)

        source = SourceMediaAsset(
            source_id="src_gameplay_fixture",
            file_path=str(src_path),
            rights_status=RightsVerificationStatus.COMMERCIAL_CREATOR_LICENSE,
        )

        orchestrator = V1GameplayOrchestrator(project_id="proj_wave10_phys")
        # Build contract with technical fixture (is_real_user_media=False)
        contract = orchestrator.build_contract(source, is_real_user_media=False, probe_file=False)
        # Override output duration bounds for fast test execution
        for spec in contract.expected_outputs:
            spec.source_start_sec = 0.0
            spec.source_end_sec = 1.5

        out_dir = tmp_path / "v1_renders"
        runner = ProductionMediaPipelineRunner(allow_direct_ffmpeg=True)

        results = await runner.render_v1_shorts(contract, out_dir)

        assert len(results) == 3
        hashes = set()
        for r in results:
            assert r.success is True
            assert Path(r.file_path).is_file()
            assert Path(r.file_path).stat().st_size > 0
            assert r.aspect_ratio == "9:16"
            assert r.has_audio is True
            assert r.decoded_frames_verified is True
            assert len(r.sha256_hash) == 64
            hashes.add(r.sha256_hash)

        # Proves decoder frames verification directly
        for r in results:
            assert ProductionMediaPipelineRunner.verify_decoded_frames(r.file_path) is True

    @pytest.mark.asyncio
    async def test_partial_failure_preservation_and_idempotent_retry(self, tmp_path: Path):
        """
        GT-26 requirement:
        1. 3rd output transcode fails -> 1st and 2nd outputs are preserved.
        2. Retry skips 1st and 2nd outputs (idempotency) and only transcodes the incomplete 3rd output.
        """
        src_path = tmp_path / "gameplay_partial.mp4"
        _generate_synthetic_test_video(src_path, duration_sec=5)

        source = SourceMediaAsset(
            source_id="src_gameplay_partial",
            file_path=str(src_path),
            rights_status=RightsVerificationStatus.COMMERCIAL_CREATOR_LICENSE,
        )

        orchestrator = V1GameplayOrchestrator(project_id="proj_wave10_partial")
        contract = orchestrator.build_contract(source, is_real_user_media=False, probe_file=False)
        for spec in contract.expected_outputs:
            spec.source_start_sec = 0.0
            spec.source_end_sec = 1.0

        out_dir = tmp_path / "v1_partial_renders"

        # Step 1: Run with simulated failure on 3rd output (index 2)
        failing_runner = ProductionMediaPipelineRunner(
            allow_direct_ffmpeg=True,
            simulate_failure_on_output_index=2,
        )
        first_attempt = await failing_runner.render_v1_shorts(contract, out_dir)

        assert len(first_attempt) == 3
        assert first_attempt[0].success is True
        assert first_attempt[1].success is True
        assert first_attempt[2].success is False
        assert "Simulated physical transcode timeout/failure" in first_attempt[2].error_message

        # Verify physical files for 1st and 2nd exist on disk
        assert Path(first_attempt[0].file_path).is_file()
        assert Path(first_attempt[1].file_path).is_file()
        output1_mtime = Path(first_attempt[0].file_path).stat().st_mtime

        # Step 2: Retry with working runner (simulate_failure_on_output_index=None)
        recovering_runner = ProductionMediaPipelineRunner(allow_direct_ffmpeg=True)
        second_attempt = await recovering_runner.render_v1_shorts(contract, out_dir)

        assert len(second_attempt) == 3
        assert second_attempt[0].success is True
        assert second_attempt[1].success is True
        assert second_attempt[2].success is True

        # Idempotency check: 1st output file was NOT re-rendered or modified
        assert Path(second_attempt[0].file_path).stat().st_mtime == output1_mtime
        assert Path(second_attempt[2].file_path).is_file()
        assert second_attempt[2].decoded_frames_verified is True

    @pytest.mark.asyncio
    async def test_truth_guard_technical_fixture_does_not_claim_editorial_pass(self, tmp_path: Path):
        """
        Ground-truth requirement:
        Even though technical physical rendering succeeded, the orchestrator and validator
        strictly evaluate GT-05 as NOT_TESTED / WAITING_FOR_INPUT when is_real_user_media=False.
        """
        src_path = tmp_path / "gameplay_fixture.mp4"
        _generate_synthetic_test_video(src_path, duration_sec=4)

        source = SourceMediaAsset(
            source_id="src_gameplay_fixture",
            file_path=str(src_path),
            rights_status=RightsVerificationStatus.COMMERCIAL_CREATOR_LICENSE,
        )

        orchestrator = V1GameplayOrchestrator(project_id="proj_gt05_guard")
        contract = orchestrator.build_contract(source, is_real_user_media=False, probe_file=False)

        # Evaluate acceptance with rendered paths
        eval_result = orchestrator.evaluate_acceptance(
            contract,
            rendered_output_paths=[str(tmp_path / "out1.mp4"), str(tmp_path / "out2.mp4")],
        )

        assert eval_result.gate_id == "GT-05"
        assert eval_result.status == "NOT_TESTED"
        assert eval_result.is_real_user_media is False
        assert "Authentic licensed gameplay recording" in eval_result.missing_evidence[0]
        assert "WAITING_FOR_INPUT" in eval_result.notes
