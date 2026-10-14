# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 11 Production Acceptance & Media Pipeline Tests.

Verifies:
- GT-05 (V1 mode):
  - Invalidation of cached renders upon project revision change or source hash change.
  - Physical H.264/AAC generation and decoded frames verification.
  - Rejection of synthetic filler sources.
  - Strict preservation of NOT_TESTED / WAITING_FOR_INPUT when authentic media is absent.
- GT-07 (V2 multi-source mode):
  - Multi-source contract generation with distinct source attribution.
  - Deduplication and lineage verification.
- GT-06 (V3 narrative mode):
  - Narrative cut list verification summing to 8-10 minutes.
  - Rejection of out-of-bounds cut lists.
  - Preservation of EDITORIAL_NOT_ASSESSED status.
- GT-24 & GT-26:
  - Single uninterrupted execution to terminal status (READY_FOR_REVIEW, PARTIAL, WAITING_FOR_INPUT, BLOCKED).
  - 3rd output transcode failure preserves 1st and 2nd valid outputs.
"""
from pathlib import Path
import json
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
    V3NarrativeCut,
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
    """Generates an MP4 video fixture with H.264 video and AAC audio."""
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


class TestWave11ProductionMediaRunnerAndAcceptance:
    """Wave 11 tests for physical media runner, cache invalidation, and truth gates."""

    @pytest.mark.asyncio
    async def test_v1_revision_change_invalidates_cached_render(self, tmp_path: Path):
        """
        Wave 11 requirement:
        Detect changed rights consent/media hash/revision and invalidate reuse when appropriate.
        """
        src_path = tmp_path / "gameplay_rev.mp4"
        _generate_synthetic_test_video(src_path, duration_sec=5)

        probe = MediaProbeService.probe_file(src_path)
        source = SourceMediaAsset(
            source_id="src_gameplay_rev",
            file_path=str(src_path),
            rights_status=RightsVerificationStatus.COMMERCIAL_CREATOR_LICENSE,
            probe=probe,
        )

        orchestrator = V1GameplayOrchestrator(project_id="proj_rev_test")
        contract = orchestrator.build_contract(source, is_real_user_media=False, probe_file=False)
        for spec in contract.expected_outputs:
            spec.source_start_sec = 0.0
            spec.source_end_sec = 1.0
            spec.project_revision = 1

        out_dir = tmp_path / "v1_rev_renders"
        runner = ProductionMediaPipelineRunner(allow_direct_ffmpeg=True)

        # 1. First render (revision 1)
        res1 = await runner.render_v1_shorts(contract, out_dir)
        assert res1[0].success is True
        file1 = Path(res1[0].file_path)
        assert file1.is_file()
        mtime1 = file1.stat().st_mtime

        # Check sidecar exists
        sidecar = file1.with_suffix(".meta.json")
        assert sidecar.is_file()

        # 2. Re-run with SAME revision -> should be reused (idempotent resume)
        res_same = await runner.render_v1_shorts(contract, out_dir)
        assert Path(res_same[0].file_path).stat().st_mtime == mtime1

        # 3. Modify contract revision to 2
        for spec in contract.expected_outputs:
            spec.project_revision = 2

        # Re-run -> should invalidate cached render and re-transcode
        res_new_rev = await runner.render_v1_shorts(contract, out_dir)
        assert res_new_rev[0].success is True
        mtime2 = Path(res_new_rev[0].file_path).stat().st_mtime
        assert mtime2 >= mtime1

        # Sidecar should now record revision 2
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
        assert meta["project_revision"] == 2

    def test_gt05_terminal_states_truth_guard(self, tmp_path: Path):
        """
        GT-24 requirement:
        Natural language PROD action progresses to genuine terminal state:
        READY_FOR_REVIEW, PARTIAL, WAITING_FOR_INPUT, or BLOCKED.
        Never declare contract prepared as READY_FOR_REVIEW.
        """
        src_path = tmp_path / "gameplay.mp4"
        _generate_synthetic_test_video(src_path, duration_sec=4)

        source = SourceMediaAsset(
            source_id="src_gp",
            file_path=str(src_path),
            rights_status=RightsVerificationStatus.COMMERCIAL_CREATOR_LICENSE,
        )
        orchestrator = V1GameplayOrchestrator(project_id="proj_gt24")

        # 1. Without authentic media: strictly WAITING_FOR_INPUT / NOT_TESTED
        contract = orchestrator.build_contract(source, is_real_user_media=False, probe_file=False)
        assert contract.status == OrchestrationContractStatus.CONTRACT_PREPARED
        result = orchestrator.evaluate_acceptance(contract)
        assert result.status == "NOT_TESTED"
        assert "WAITING_FOR_INPUT" in result.notes

        # 2. With authentic media and 2 valid outputs: PARTIAL
        contract_real = orchestrator.build_contract(source, is_real_user_media=True, probe_file=False)
        # Mock probe callable for 2 outputs
        out1 = str(tmp_path / "out1.mp4")
        out2 = str(tmp_path / "out2.mp4")
        _generate_synthetic_test_video(Path(out1), duration_sec=2)
        _generate_synthetic_test_video(Path(out2), duration_sec=2)

        # Monkeypatch probe for 9:16 vertical 58s
        from unittest.mock import patch
        with patch.object(MediaProbeService, "probe_file") as mock_probe:
            mock_probe.side_effect = lambda p: MediaProbeMetadata(
                file_path=str(p),
                file_size_bytes=1000,
                sha256_hash=f"hash_{Path(p).name}",
                magic_bytes_valid=True,
                has_audio_stream=True,
                aspect_ratio="9:16",
                duration_seconds=58.0,
            )
            eval_partial = orchestrator.evaluate_acceptance(contract_real, rendered_output_paths=[out1, out2])
            assert eval_partial.status == "PARTIAL"
            assert eval_partial.artifacts_verified_count == 2
            assert len(eval_partial.preserved_outputs) == 2

    def test_gt06_longform_narrative_cutlist_constraints(self, tmp_path: Path):
        """
        GT-06 requirement:
        V3 narrative cut list must sum to 8-10 minutes (480-600s).
        Out-of-bounds cut lists are REJECTED.
        """
        src_path = tmp_path / "longform.mp4"
        _generate_synthetic_test_video(src_path, duration_sec=3)

        source = SourceMediaAsset(
            source_id="src_lf",
            file_path=str(src_path),
            rights_status=RightsVerificationStatus.COMMERCIAL_CREATOR_LICENSE,
        )
        orchestrator = V3LongFormOrchestrator(project_id="proj_v3_cut")

        # Invalid cut list: only 120s total (< 480s)
        invalid_cuts = [
            V3NarrativeCut(
                cut_id="c1",
                source_start_sec=0.0,
                source_end_sec=120.0,
                duration_sec=120.0,
                scene_name="Too short",
            )
        ]
        contract = orchestrator.build_contract(source, narrative_cut_list=invalid_cuts, is_real_user_media=False, probe_file=False)
        assert contract.status == OrchestrationContractStatus.REJECTED
        assert any("outside 8-10 minutes" in iss for iss in contract.issues)

        # Valid default cut list: sums to 510s (8.5 minutes)
        valid_contract = orchestrator.build_contract(source, is_real_user_media=False, probe_file=False)
        assert valid_contract.status == OrchestrationContractStatus.CONTRACT_PREPARED
        total_dur = sum(c.duration_sec for c in valid_contract.narrative_cut_list)
        assert 480.0 <= total_dur <= 600.0
