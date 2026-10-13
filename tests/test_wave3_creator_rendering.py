# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Tests for Physical Original Video Rendering (Wave 3 Role 5).

Verifies:
- Authentic FFmpeg MP4 generation in an isolated temp directory.
- 9:16 vertical (1080x1920) and 16:9 widescreen (1920x1080) aspect rendering.
- ffprobe validation of physical video duration, dimensions, audio streams, and file size.
- Multi-scene stitching and audio-visual multiplexing.
- No false claims: ensures physical file exists and is greater than 1KB.
"""
import asyncio
from pathlib import Path
import shutil
import tempfile
import pytest

from backend.original_creation.models import (
    EvidenceLedger,
    EvidenceLedgerEntry,
    OriginalCompositionSpec,
    OriginalCreationStatus,
    ShotListEntry,
    TeleprompterScript,
    VoiceInputRequirement,
)
from backend.original_creation.renderer import (
    OriginalVideoRenderer,
    generate_procedural_scene_card,
    render_scene_clip,
    synthesize_narration_audio,
)
from backend.services.video_utils import probe_media, probe_duration


@pytest.fixture
def isolated_tmp_dir():
    """Create isolated temporary directory for test renders."""
    tmp = Path(tempfile.mkdtemp(prefix="viralmint_test_render_"))
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.mark.asyncio
async def test_procedural_scene_card_generation(isolated_tmp_dir):
    """Verify offline generation of high-res typography cards."""
    out_png = isolated_tmp_dir / "test_card.png"
    generate_procedural_scene_card(
        title="JAMES WEBB DISCOVERY",
        subtitle="Unprecedented Infrared Atmospheric Signals",
        output_png=out_png,
        width=1080,
        height=1920,
    )

    assert out_png.exists()
    assert out_png.stat().st_size > 1000
    w, h, _ = probe_media(out_png)
    assert w == 1080
    assert h == 1920


@pytest.mark.asyncio
async def test_single_scene_clip_rendering(isolated_tmp_dir):
    """Verify physical MP4 generation of an individual motion scene."""
    scene = ShotListEntry(
        scene_number=1,
        timecode_start_sec=0.0,
        timecode_end_sec=2.0,
        visual_description="Opening hook establishing science topic",
        overlay_text="COSMIC BREAKTHROUGH",
    )
    out_mp4 = isolated_tmp_dir / "scene_1.mp4"
    tmp_sub = isolated_tmp_dir / "tmp"

    clip = await render_scene_clip(
        scene=scene,
        target_width=1080,
        target_height=1920,
        output_mp4=out_mp4,
        tmp_dir=tmp_sub,
    )

    assert clip.exists()
    assert clip.stat().st_size > 2000
    w, h, dur = probe_media(clip)
    assert w == 1080
    assert h == 1920
    assert 1.8 <= dur <= 2.2


@pytest.mark.asyncio
async def test_full_original_video_rendering_9_16(isolated_tmp_dir):
    """
    Verify full end-to-end physical MP4 composition in 9:16 vertical aspect.
    Includes procedural voice synthesis and multi-scene stitching.
    """
    spec = OriginalCompositionSpec(
        title="Original Astronomy Dispatch",
        topic="James Webb Space Telescope",
        target_duration_sec=6,
        aspect_ratio="9:16",
        evidence_ledger=EvidenceLedger(
            topic="James Webb Space Telescope",
            entries=[
                EvidenceLedgerEntry(
                    claim_text="Spectroscopic data confirms high-redshift galaxy composition.",
                    source_title="NASA STScI Release",
                    citation="Science Brief 2026",
                )
            ],
        ),
        spoken_script=TeleprompterScript(
            spoken_text="Did you see the new James Webb telescope findings? Early cosmic signatures were confirmed.",
            word_count=15,
            estimated_read_time_seconds=6.0,
        ),
        shot_list=[
            ShotListEntry(
                scene_number=1,
                timecode_start_sec=0.0,
                timecode_end_sec=3.0,
                visual_description="Deep space infrared hook",
                overlay_text="NEW JWST DISCOVERY",
            ),
            ShotListEntry(
                scene_number=2,
                timecode_start_sec=3.0,
                timecode_end_sec=6.0,
                visual_description="Atmospheric spectrum analysis",
                overlay_text="MOLECULAR SIGNATURES",
            ),
        ],
        voice_requirement=VoiceInputRequirement.PROCEDURAL_SYNTHESIS_ALLOWED,
        status=OriginalCreationStatus.READY_FOR_COMPOSITION,
    )

    rendered_spec = await OriginalVideoRenderer.render_composition(
        spec=spec,
        output_dir=isolated_tmp_dir,
    )

    assert rendered_spec.status == OriginalCreationStatus.RENDERED
    assert rendered_spec.rendered_result is not None
    final_path = Path(rendered_spec.rendered_result.video_path)
    assert final_path.exists()
    assert final_path.stat().st_size > 5000

    probe = rendered_spec.rendered_result.probe_stats
    assert probe.width == 1080
    assert probe.height == 1920
    assert probe.aspect_ratio == "9:16"
    assert probe.has_audio is True
    assert probe.duration_seconds > 2.0


@pytest.mark.asyncio
async def test_original_video_rendering_16_9_widescreen(isolated_tmp_dir):
    """
    Verify physical MP4 composition in 16:9 horizontal widescreen aspect.
    """
    spec = OriginalCompositionSpec(
        title="Culinary Chemistry",
        topic="Coffee Bean Roasting",
        target_duration_sec=4,
        aspect_ratio="16:9",
        evidence_ledger=EvidenceLedger(
            topic="Coffee Bean Roasting",
            entries=[
                EvidenceLedgerEntry(
                    claim_text="Maillard reactions govern caramelization and acidity.",
                    source_title="SCA Roasting Science",
                    citation="SCA Whitepaper",
                )
            ],
        ),
        spoken_script=TeleprompterScript(
            spoken_text="The Maillard reaction is the secret behind balanced coffee acidity.",
            word_count=10,
            estimated_read_time_seconds=4.0,
        ),
        shot_list=[
            ShotListEntry(
                scene_number=1,
                timecode_start_sec=0.0,
                timecode_end_sec=4.0,
                visual_description="Roasting process breakdown",
                overlay_text="MAILLARD REACTION",
            ),
        ],
        voice_requirement=VoiceInputRequirement.PROCEDURAL_SYNTHESIS_ALLOWED,
        status=OriginalCreationStatus.READY_FOR_COMPOSITION,
    )

    rendered_spec = await OriginalVideoRenderer.render_composition(
        spec=spec,
        output_dir=isolated_tmp_dir,
    )

    assert rendered_spec.status == OriginalCreationStatus.RENDERED
    assert rendered_spec.rendered_result is not None
    probe = rendered_spec.rendered_result.probe_stats
    assert probe.width == 1920
    assert probe.height == 1080
    assert probe.aspect_ratio == "16:9"
    assert probe.has_audio is True
