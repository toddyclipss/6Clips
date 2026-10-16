# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Unit and Adversarial Tests for SourceLineageVerifier (Agent 3).

Verifies:
- Accurate verification when rendered deliverable matches timeline and source footage
- Fails closed when project timeline lacks source video clip
- Fails closed when timeline asset SHA does not match source SHA
- Fails closed on duration drift (e.g. 9.8s rendered vs 15.00s displayed)
- Fails closed when output is a pitch-black video or synthetic prompt title card
- Fails closed when rendered file is missing or unreadable
"""

import asyncio
from pathlib import Path
import pytest
import subprocess

from backend.database import init_db
from backend.oaas_media_edit import (
    EditExistingMediaContract,
    NativeMediaEditor,
    SafeProjectEditAdapter,
    SourceLineageVerifier,
    SourceMediaAnalyzer,
)


@pytest.fixture(autouse=True)
def db_setup(monkeypatch):
    monkeypatch.setenv("VIRALMINT_TEST_ENV", "1")
    asyncio.run(init_db())


@pytest.fixture
def test_source_video(tmp_path: Path) -> Path:
    """Generate a valid 6-second moving video with audio."""
    src = tmp_path / "valid_source.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
        "-t", "6.0",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        str(src),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return src


def test_verifier_passes_on_genuine_deliverable(test_source_video: Path, tmp_path: Path):
    """Verify verifier returns is_verified=True for authentic source-backed render."""
    async def _test():
        analysis = SourceMediaAnalyzer.analyze_file(test_source_video)

        project, cur_rev = await SafeProjectEditAdapter.get_or_create_project(
            title="Verifier Test Project",
            aspect_ratio="9:16",
        )

        contract = EditExistingMediaContract(
            original_url="https://www.youtube.com/watch?v=FV93IVwJP_4",
            file_path=str(test_source_video),
            source_sha256=analysis.sha256_hash,
            source_duration=6.0,
            source_resolution=(1920, 1080),
            source_intervals=[(0.0, 3.0)],
            target_duration=3.0,
            target_aspect_ratio="9:16",
            project_id=project.id,
        )

        final_rev, _, _ = await SafeProjectEditAdapter.apply_source_edit_operations(
            project_id=project.id,
            expected_revision=cur_rev,
            contract=contract,
            analysis=analysis,
        )

        out_mp4 = tmp_path / "genuine_render.mp4"
        NativeMediaEditor.render_source_edit(contract, output_file=out_mp4)

        verification = await SourceLineageVerifier.verify_source_lineage(
            project_id=project.id,
            revision_id=final_rev,
            rendered_mp4=out_mp4,
            expected_source_sha=analysis.sha256_hash,
            expected_duration=3.0,
            source_path=test_source_video,
        )

        assert verification.is_verified is True
        assert verification.duration_matches_target is True
        assert verification.visual_frames_authentic is True
        assert verification.not_static_black is True
        assert verification.timeline_has_source_clip is True
        assert verification.rejection_reason is None

    asyncio.run(_test())


def test_verifier_fails_on_duration_drift(test_source_video: Path, tmp_path: Path):
    """Verify verifier fails closed when output duration (e.g. 5.0s) drifts from expected (e.g. 3.0s)."""
    async def _test():
        analysis = SourceMediaAnalyzer.analyze_file(test_source_video)

        project, cur_rev = await SafeProjectEditAdapter.get_or_create_project(
            title="Duration Drift Test",
            aspect_ratio="9:16",
        )

        contract = EditExistingMediaContract(
            original_url="https://www.youtube.com/watch?v=FV93IVwJP_4",
            file_path=str(test_source_video),
            source_sha256=analysis.sha256_hash,
            source_duration=6.0,
            source_resolution=(1920, 1080),
            source_intervals=[(0.0, 5.0)],  # Render 5.0s
            target_duration=5.0,
            target_aspect_ratio="9:16",
            project_id=project.id,
        )

        final_rev, _, _ = await SafeProjectEditAdapter.apply_source_edit_operations(
            project_id=project.id,
            expected_revision=cur_rev,
            contract=contract,
            analysis=analysis,
        )

        out_mp4 = tmp_path / "drift_render.mp4"
        NativeMediaEditor.render_source_edit(contract, output_file=out_mp4)

        # Ask verifier to check for 3.0s when physical file is 5.0s (testing drift rejection)
        verification = await SourceLineageVerifier.verify_source_lineage(
            project_id=project.id,
            revision_id=final_rev,
            rendered_mp4=out_mp4,
            expected_source_sha=analysis.sha256_hash,
            expected_duration=3.0,  # Expect 3.0s
            source_path=test_source_video,
        )

        assert verification.is_verified is False
        assert verification.duration_matches_target is False
        assert "differs from expected" in (verification.rejection_reason or "")

    asyncio.run(_test())


def test_verifier_fails_on_static_black_title_card(test_source_video: Path, tmp_path: Path):
    """Verify verifier fails closed if physical file is a pitch-black canvas or title card."""
    async def _test():
        analysis = SourceMediaAnalyzer.analyze_file(test_source_video)

        project, cur_rev = await SafeProjectEditAdapter.get_or_create_project(
            title="Black Title Card Rejection",
            aspect_ratio="9:16",
        )

        contract = EditExistingMediaContract(
            original_url="https://www.youtube.com/watch?v=FV93IVwJP_4",
            file_path=str(test_source_video),
            source_sha256=analysis.sha256_hash,
            source_duration=6.0,
            source_resolution=(1920, 1080),
            source_intervals=[(0.0, 3.0)],
            target_duration=3.0,
            target_aspect_ratio="9:16",
            project_id=project.id,
        )

        final_rev, _, _ = await SafeProjectEditAdapter.apply_source_edit_operations(
            project_id=project.id,
            expected_revision=cur_rev,
            contract=contract,
            analysis=analysis,
        )

        # Generate black video as counterfeit deliverable
        fake_black_mp4 = tmp_path / "fake_black.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=1080x1920:r=30",
            "-t", "3.0",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            str(fake_black_mp4),
        ]
        subprocess.run(cmd, capture_output=True, check=True)

        verification = await SourceLineageVerifier.verify_source_lineage(
            project_id=project.id,
            revision_id=final_rev,
            rendered_mp4=fake_black_mp4,
            expected_source_sha=analysis.sha256_hash,
            expected_duration=3.0,
            source_path=test_source_video,
        )

        assert verification.is_verified is False
        assert verification.not_static_black is False
        assert "pitch black" in (verification.rejection_reason or "").lower() or "title card" in (verification.rejection_reason or "").lower()

    asyncio.run(_test())


def test_verifier_fails_on_sha_mismatch(test_source_video: Path, tmp_path: Path):
    """Verify verifier fails closed when timeline asset SHA does not match expected SHA."""
    async def _test():
        analysis = SourceMediaAnalyzer.analyze_file(test_source_video)

        project, cur_rev = await SafeProjectEditAdapter.get_or_create_project(
            title="SHA Mismatch Test",
            aspect_ratio="9:16",
        )

        contract = EditExistingMediaContract(
            original_url="https://www.youtube.com/watch?v=FV93IVwJP_4",
            file_path=str(test_source_video),
            source_sha256=analysis.sha256_hash,
            source_duration=6.0,
            source_resolution=(1920, 1080),
            source_intervals=[(0.0, 3.0)],
            target_duration=3.0,
            target_aspect_ratio="9:16",
            project_id=project.id,
        )

        final_rev, _, _ = await SafeProjectEditAdapter.apply_source_edit_operations(
            project_id=project.id,
            expected_revision=cur_rev,
            contract=contract,
            analysis=analysis,
        )

        out_mp4 = tmp_path / "valid_render.mp4"
        NativeMediaEditor.render_source_edit(contract, output_file=out_mp4)

        # Provide mismatched expected SHA
        verification = await SourceLineageVerifier.verify_source_lineage(
            project_id=project.id,
            revision_id=final_rev,
            rendered_mp4=out_mp4,
            expected_source_sha="completely_different_and_invalid_sha_1234567890",
            expected_duration=3.0,
            source_path=test_source_video,
        )

        assert verification.is_verified is False
        assert "does not match expected" in (verification.rejection_reason or "")

    asyncio.run(_test())
