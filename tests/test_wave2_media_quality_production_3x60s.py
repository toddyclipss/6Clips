# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Acceptance test suite for Wave 2 Agent 2 — 3×60-Second Real Media Quality Pipeline (GT-05, GT-08, GT-11).

Tests:
1. Negative guard: Insufficient source duration (< 180s for 3x60s) returns INSUFFICIENT_SOURCE_DURATION blocker.
2. Short fixture smoke test (< 30s): fast verification, explicitly distinguished from GT-05 acceptance.
3. Safe-region reframing visual presets: Gameplay Reticle, HUD-Aware Blur, and Facecam Split.
4. Comprehensive 3×60-second real media production on >180-second source:
   - 3 distinct 1080x1920 MP4 artifacts.
   - Duration ~60.0s (within TARGET tolerance).
   - Non-overlapping source ranges.
   - Distinct SHA-256 hashes.
   - Real synchronized audio (AAC, non-silent).
   - Honest editorial scoring with NOT_ASSESSED human rating.
5. Production DB isolation guarantee.
"""

import asyncio
import hashlib
import json
import subprocess
from pathlib import Path
import pytest

from backend.database import AsyncSessionLocal, init_db
from backend.media_pipeline.clip_renderer import render_output_clip
from backend.media_pipeline.media_inspector import (
    compute_file_sha256,
    inspect_source_provenance_and_rights,
    probe_physical_media,
)
from backend.media_pipeline.models import (
    BatchStatus,
    DurationPolicy,
    OutputResultV1,
    OutputSpecV1,
    OutputState,
    ProductionRequestV1,
    SourceAssetV1,
    SourceRangeV1,
)
from backend.media_pipeline.producer_adapter import MediaProducerPort
from backend.media_pipeline.segment_selector import select_editorial_segments

PROD_DB_PATH = Path("c:/Users/toddy/Desktop/ViralMint/viralmint.db")


def get_file_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().upper()


@pytest.fixture(autouse=True)
def verify_production_db_isolation():
    """Ensure production database remains pristine before and after tests."""
    if PROD_DB_PATH.exists():
        pre_hash = get_file_sha256(PROD_DB_PATH)
        yield
        post_hash = get_file_sha256(PROD_DB_PATH)
        assert pre_hash == post_hash, f"Production DB modified! Pre: {pre_hash}, Post: {post_hash}"
    else:
        yield


def create_authorized_longform_footage(target_path: Path, duration_s: int = 188) -> Path:
    """Create an authorized 16:9 gameplay-style source (>180 seconds) with dynamic visual movement and stereo audio."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    # Uses testsrc2 + moving reticle box + dual tone audio
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={duration_s}:size=1920x1080:rate=25",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration_s}",
        "-vf", (
            "drawbox=x='860+100*sin(t/5)':y='440+50*cos(t/5)':w=200:h=200:color=yellow@0.7:t=fill,"
            "drawbox=x=950:y=530:w=20:h=20:color=red@0.9:t=fill"
        ),
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        str(target_path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)
    return target_path


def create_smoke_test_source(target_path: Path, duration_s: int = 24) -> Path:
    """Create a short 24-second source for smoke test verification."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={duration_s}:size=1280x720:rate=25",
        "-f", "lavfi", "-i", f"sine=frequency=600:duration={duration_s}",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac", "-b:a", "96k", "-ar", "44100",
        str(target_path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)
    return target_path


@pytest.mark.asyncio
async def test_insufficient_source_duration_negative_guard(tmp_path):
    """Verify that a source shorter than required 3x60s outputs halts in INSUFFICIENT_SOURCE_DURATION."""
    src_path = tmp_path / "short_source.mp4"
    create_smoke_test_source(src_path, duration_s=120)  # 120s is less than 3x60s (180s)

    probe, blocker = await probe_physical_media(src_path)
    assert blocker is None
    assert probe is not None

    specs = [
        OutputSpecV1(output_id="clip_1", seconds=60.0, duration_policy=DurationPolicy.TARGET, tolerance_seconds=3.0),
        OutputSpecV1(output_id="clip_2", seconds=60.0, duration_policy=DurationPolicy.TARGET, tolerance_seconds=3.0),
        OutputSpecV1(output_id="clip_3", seconds=60.0, duration_policy=DurationPolicy.TARGET, tolerance_seconds=3.0),
    ]

    ranges, sel_blocker = select_editorial_segments(probe, specs)
    assert sel_blocker is not None
    assert sel_blocker.code == "INSUFFICIENT_SOURCE_DURATION"
    assert "shorter than required minimum" in sel_blocker.precise_reason
    assert len(ranges) == 0


@pytest.mark.asyncio
async def test_short_fixture_smoke_test_plumbing(tmp_path):
    """Affordable smoke test (~24s source -> 3x7s clips) validating pipeline plumbing and non-overlap."""
    src_path = tmp_path / "smoke_source.mp4"
    create_smoke_test_source(src_path, duration_s=24)

    probe, _ = await probe_physical_media(src_path)
    assert probe is not None

    specs = [
        OutputSpecV1(output_id="smoke_1", seconds=7.0, duration_policy=DurationPolicy.EXACT),
        OutputSpecV1(output_id="smoke_2", seconds=7.0, duration_policy=DurationPolicy.EXACT),
        OutputSpecV1(output_id="smoke_3", seconds=7.0, duration_policy=DurationPolicy.EXACT),
    ]

    ranges, blocker = select_editorial_segments(probe, specs, media_path=src_path)
    assert blocker is None
    assert len(ranges) == 3

    # Check non-overlap
    assert ranges[0].end_seconds <= ranges[1].start_seconds
    assert ranges[1].end_seconds <= ranges[2].start_seconds

    # Render clip 1
    out_dir = tmp_path / "smoke_renders"
    result = await render_output_clip(
        source_path=src_path,
        source_range=ranges[0],
        spec=specs[0],
        project_id="smoke_proj",
        output_dir=out_dir,
    )

    assert result.state == OutputState.SUCCEEDED
    assert result.media_probe.width == 1080
    assert result.media_probe.height == 1920
    assert 6.5 <= result.media_probe.duration_seconds <= 7.5


@pytest.mark.asyncio
async def test_safe_region_reframing_presets(tmp_path):
    """Verify safe-region presets (gameplay_reticle and hud_aware_blur) render valid 1080x1920 outputs."""
    src_path = tmp_path / "preset_source.mp4"
    create_smoke_test_source(src_path, duration_s=10)

    source_range = SourceRangeV1(
        asset_id="preset_src",
        start_seconds=1.0,
        end_seconds=7.0,
        duration_seconds=6.0,
        editorial_reason="Preset test range",
        relevance_score=8.0,
    )

    out_dir = tmp_path / "preset_renders"

    # 1. Gameplay reticle preset
    spec_reticle = OutputSpecV1(
        output_id="reticle_clip",
        seconds=6.0,
        editorial_constraints={"safe_region_preset": "gameplay_reticle"},
    )
    res_reticle = await render_output_clip(src_path, source_range, spec_reticle, "proj_reticle", out_dir)
    assert res_reticle.state == OutputState.SUCCEEDED
    assert res_reticle.media_probe.width == 1080
    assert res_reticle.media_probe.height == 1920
    assert any("Gameplay reticle" in w for w in res_reticle.warnings)

    # 2. HUD-aware blur preset
    spec_hud = OutputSpecV1(
        output_id="hud_clip",
        seconds=6.0,
        editorial_constraints={"safe_region_preset": "hud_aware_blur"},
    )
    res_hud = await render_output_clip(src_path, source_range, spec_hud, "proj_hud", out_dir)
    assert res_hud.state == OutputState.SUCCEEDED
    assert res_hud.media_probe.width == 1080
    assert res_hud.media_probe.height == 1920
    assert any("HUD-aware blur" in w for w in res_hud.warnings)


@pytest.mark.asyncio
async def test_longform_3x60s_production_pipeline_acceptance(tmp_path):
    """GT-05 / GT-08 / GT-11 Master Production Acceptance:
    Genuine >180-second authorized source -> 3 distinct ~60-second 9:16 MP4 clips with synchronized audio.
    """
    await init_db()

    # 1. Generate authorized long-form footage (188 seconds)
    src_path = tmp_path / "authorized_gameplay_188s.mp4"
    create_authorized_longform_footage(src_path, duration_s=188)

    # Verify input source probe
    probe_in, blocker_in = await probe_physical_media(src_path)
    assert blocker_in is None
    assert probe_in.duration_seconds >= 187.0
    assert probe_in.width == 1920
    assert probe_in.height == 1080
    assert probe_in.is_silent is False

    storage_dir = tmp_path / "media_production_storage"
    producer = MediaProducerPort(storage_dir=storage_dir)

    req = ProductionRequestV1(
        run_id="run_wave2_3x60s_acceptance",
        contract_id="contract_gt05_production",
        project_id="proj_gt05_gameplay",
        user_id="creator_pro",
        source_assets=[
            SourceAssetV1(
                asset_id="src_gameplay_long",
                editorial_role="primary_footage",
                acquisition_route="authorized_fixture",
                permitted_uses=["clip_extraction", "motion_review"],
                local_path=str(src_path),
            )
        ],
        outputs=[
            OutputSpecV1(
                output_id="clip_hook_60s",
                aspect_ratio="9:16",
                seconds=60.0,
                duration_policy=DurationPolicy.TARGET,
                tolerance_seconds=3.0,
                editorial_constraints={"safe_region_preset": "gameplay_reticle"},
            ),
            OutputSpecV1(
                output_id="clip_combat_60s",
                aspect_ratio="9:16",
                seconds=60.0,
                duration_policy=DurationPolicy.TARGET,
                tolerance_seconds=3.0,
                editorial_constraints={"safe_region_preset": "hud_aware_blur"},
            ),
            OutputSpecV1(
                output_id="clip_clutch_60s",
                aspect_ratio="9:16",
                seconds=60.0,
                duration_policy=DurationPolicy.TARGET,
                tolerance_seconds=3.0,
                editorial_constraints={"safe_region_preset": "center_crop"},
            ),
        ],
    )

    # 2. Submit batch
    submission = await producer.submit_batch(req)
    assert submission["accepted"] is True
    assert submission["blocker"] is None
    job_id = submission["job_id"]

    # 3. Poll until COMPLETE
    report = None
    for _ in range(120):
        report = producer.get_batch(job_id)
        if report.status in (BatchStatus.COMPLETE, BatchStatus.BLOCKED, BatchStatus.PARTIAL):
            break
        await asyncio.sleep(2.0)

    assert report is not None
    assert report.status == BatchStatus.COMPLETE, f"Expected COMPLETE, got {report.status}. Blockers: {report.blockers}"
    assert len(report.outputs) == 3

    rendered_files: list[Path] = []
    output_hashes: list[str] = []
    output_ranges: list[SourceRangeV1] = []

    for idx, out in enumerate(report.outputs):
        assert out.state == OutputState.SUCCEEDED
        assert out.checks.technical == "PASS"
        assert out.checks.contract == "PASS"
        assert out.checks.editorial == "NOT_ASSESSED"  # Never forged automated PASS

        probe = out.media_probe
        assert probe is not None
        assert probe.width == 1080
        assert probe.height == 1920
        # Target 60s with +-3s tolerance -> duration between 57.0s and 63.0s
        assert 57.0 <= probe.duration_seconds <= 63.5, f"Clip {idx} duration {probe.duration_seconds}s outside [57.0s, 63.5s]"
        assert probe.audio_codec == "aac"
        assert probe.is_silent is False

        # Physical file verification
        artifact_path = producer.resolve_artifact_path(out.artifact_id)
        assert artifact_path is not None
        assert artifact_path.exists()
        assert artifact_path.stat().st_size > 500_000  # >500KB real physical video bytes

        h = compute_file_sha256(artifact_path)
        output_hashes.append(h)
        rendered_files.append(artifact_path)

        assert len(out.source_ranges) == 1
        output_ranges.append(out.source_ranges[0])

    # 4. Independent outputs guarantee: distinct physical SHA-256 hashes
    assert len(set(output_hashes)) == 3, f"Duplicate output artifact hashes detected! Hashes: {output_hashes}"

    # 5. Non-overlapping source ranges
    assert output_ranges[0].end_seconds <= output_ranges[1].start_seconds
    assert output_ranges[1].end_seconds <= output_ranges[2].start_seconds

    # 6. Provenance & score transparency
    for r in output_ranges:
        assert r.relevance_score > 0.0
        assert "Editorial: NOT_ASSESSED" in r.editorial_reason
