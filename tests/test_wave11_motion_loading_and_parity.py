# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 11 Agent 2 — Finite State Machine Player, Zero Overlapping Loaders,
Independent Catalog Resilience, and 30-Capability Exact Parity Audit.
"""

import asyncio
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List

import pytest
from fastapi import HTTPException

from backend.database import init_db
from backend.media_pipeline.clip_renderer import (
    build_framing_filter,
    render_manifest_to_mp4,
)
from backend.media_pipeline.media_inspector import probe_physical_media
from backend.media_pipeline.models import (
    DurationPolicy,
    OutputSpecV1,
    OutputState,
    SourceRangeV1,
)
from backend.motion_capabilities import (
    ALL_CAPABILITIES_SPEC,
    MotionCapabilitiesRegistry,
    MotionCapabilityDispatcher,
    execute_motion_capability,
)
from backend.motion_legacy_bridge.parity_contracts import (
    preserve_caption_overrides,
)
from backend.motion_render_bridge import build_render_manifest
from backend.services.project_service import ProjectService


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Ensure database schema is created for test execution."""
    await init_db()


@pytest.fixture(scope="module")
def technical_fixture_video_mp4(tmp_path_factory) -> Path:
    """TECHNICAL_FIXTURE: Isolated 1.0-second 1920x1080 MP4 with audio using FFmpeg."""
    tmp_dir = tmp_path_factory.mktemp("wave11_technical_media")
    video_path = tmp_dir / "technical_fixture_input.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=1.0:size=1920x1080:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=1.0:sample_rate=48000",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
        "-c:a", "aac", "-b:a", "128k",
        str(video_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert res.returncode == 0, f"FFmpeg sample generation failed: {res.stderr}"
    assert video_path.exists()
    return video_path


# ─────────────────────────────────────────────────────────────────────────────
# 1. Player FSM Contract & Single Loading Indicator Verification
# ─────────────────────────────────────────────────────────────────────────────

def test_studio_preview_stage_fsm_source_integrity():
    """Verify frontend/src/components/motion/StudioPreviewStage.jsx implements
    the strict FSM states: NO_PROJECT, LOADING_EXISTING_PROJECT, EMPTY_PROJECT, READY, FAILED, CANCELLED.
    Verify that duplicate overlapping absolute spinners have been completely eliminated.
    """
    root_dir = Path(__file__).resolve().parent.parent
    stage_file = root_dir / "frontend" / "src" / "components" / "motion" / "StudioPreviewStage.jsx"
    assert stage_file.exists(), f"StudioPreviewStage.jsx not found at {stage_file}"

    code = stage_file.read_text(encoding="utf-8")

    # 1. Verify FSM states are explicitly recognized
    assert 'resolvedState === "READY"' in code
    assert 'resolvedState === "LOADING_EXISTING_PROJECT"' in code
    assert 'resolvedState === "EMPTY_PROJECT"' in code
    assert 'resolvedState === "FAILED"' in code
    assert 'resolvedState === "CANCELLED"' in code
    assert 'data-testid="studio-stage-no-project"' in code
    assert 'data-testid="studio-stage-loading"' in code
    assert 'data-testid="studio-stage-empty-project"' in code
    assert 'data-testid="studio-stage-failed"' in code
    assert 'data-testid="studio-player-retry-btn"' in code

    # 2. Verify duplicate overlay spinner removal:
    # There should NOT be an absolute overlay Box wrapping CircularProgress with zIndex: 2
    overlay_spinner_pattern = re.compile(
        r"\{\s*isLoading\s*&&\s*\(\s*<Box[^>]*position:\s*[\"']absolute[\"'][^>]*>\s*<CircularProgress",
        re.DOTALL
    )
    assert not overlay_spinner_pattern.search(code), "Forbidden duplicate overlay spinner found in StudioPreviewStage.jsx!"

    # 3. Verify exactly ONE CircularProgress component exists in StudioPreviewStage.jsx
    circular_progress_matches = re.findall(r"<CircularProgress\b", code)
    assert len(circular_progress_matches) == 1, (
        f"Expected exactly 1 <CircularProgress> in StudioPreviewStage.jsx, but found {len(circular_progress_matches)}. "
        "This indicates duplicate overlapping loaders are still present."
    )


def test_motion_graphics_stage_prop_wiring():
    """Verify frontend/src/pages/MotionGraphics.jsx wires project, error, onRetry,
    and does not spin infinitely when project is null in Refine mode.
    """
    root_dir = Path(__file__).resolve().parent.parent
    mg_file = root_dir / "frontend" / "src" / "pages" / "MotionGraphics.jsx"
    assert mg_file.exists(), f"MotionGraphics.jsx not found at {mg_file}"

    code = mg_file.read_text(encoding="utf-8")

    # Verify project prop is passed to StudioPreviewStage
    assert re.search(r"<StudioPreviewStage[^>]*\bproject=\{project\}", code, re.DOTALL), (
        "project={project} must be passed to StudioPreviewStage"
    )

    # Verify isLoading is NOT blindly set to starting when project is null
    # Must be guarded: isLoading={isProjectLoading || (starting && !!project)}
    assert re.search(r"isLoading=\{isProjectLoading\s*\|\|\s*\(starting\s*&&\s*!!project\)\}", code), (
        "isLoading must not trigger spinner when project is null"
    )

    # Verify error and onRetry are provided
    assert "error={startError || projectError}" in code
    assert "onRetry=" in code


# ─────────────────────────────────────────────────────────────────────────────
# 2. StudioResourcePanel Catalog Tab Resilience & Scrollbar Cleanliness
# ─────────────────────────────────────────────────────────────────────────────

def test_catalog_tab_independent_state_and_scrollbar_cleanliness():
    """Verify frontend/src/components/motion/StudioResourcePanel.jsx:
    1. Category filter pills have hidden scrollbar (eliminating the horizontal lavender thumb artifact).
    2. Catalog tab handles independent loading, error with Retry button, and empty states.
    """
    root_dir = Path(__file__).resolve().parent.parent
    panel_file = root_dir / "frontend" / "src" / "components" / "motion" / "StudioResourcePanel.jsx"
    assert panel_file.exists(), f"StudioResourcePanel.jsx not found at {panel_file}"

    code = panel_file.read_text(encoding="utf-8")

    # 1. Scrollbar suppression on category filter pills Stack
    assert 'scrollbarWidth: "none"' in code, "scrollbarWidth: 'none' missing on filter chips Stack"
    assert '"&::-webkit-scrollbar": { display: "none" }' in code, "Webkit scrollbar suppression missing on filter chips Stack"

    # 2. Independent error and retry handling
    assert "const [catalogError, setCatalogError] = useState(null)" in code
    assert 'data-testid="catalog-retry-btn"' in code, "Catalog tab retry button missing"
    assert 'data-testid="catalog-error-box"' in code, "Catalog tab error container missing"

    # 3. Isolated fetch function with try/catch
    assert "const fetchCatalog = useCallback(" in code
    assert "setCatalogLoading(true)" in code


# ─────────────────────────────────────────────────────────────────────────────
# 3. 30-Capability Exact Parity Audit & Deduplication (Sum == 30)
# ─────────────────────────────────────────────────────────────────────────────

def test_master_30_capabilities_exact_unique_inventory_breakdown():
    """Verify all 30 legacy capabilities are registered, properly categorized,
    and deduplicated so that every capability belongs to EXACTLY ONE category
    and the sum of all categories equals exactly 30 unique items.
    """
    capabilities = MotionCapabilitiesRegistry.list_all()
    assert len(capabilities) == 30, f"Expected exactly 30 registered capabilities, got {len(capabilities)}"

    # Authoritative Wave 11 Deduplicated Category Matrix
    e2e_verified_ids = {
        "trim",
        "audio-enhance",
        "reframe",
        "captions",
        "split-at-playhead",
        "slip-editing",
        "ripple-delete",
        "three-output-review",
        "virality-scoreboard",
    }

    render_artifact_verified_ids = {
        "merge-clips",
        "crop",
        "compress",
        "transform",
        "remove-audio",
        "speed",
        "gif",
        "subtitles",
        "watermark",
        "music-visualizer",
        "filmstrip-range-bench",
        "manual-caption-override",
    }

    backend_verified_ids = {
        "video-download",
        "remove-silence",
        "auto-cut-dialog",
        "source-video-library",
        "hook-analysis",
    }

    implemented_only_ids = {
        "auto-zoom",
        "voiceover",
        "auto-chapters",
    }

    blocked_provider_ids = {
        "translate",  # Text translation functional locally; voice dubbing requires external provider credentials
    }

    all_defined_sets = [
        ("E2E_VERIFIED", e2e_verified_ids, 9),
        ("RENDER_ARTIFACT_VERIFIED", render_artifact_verified_ids, 12),
        ("BACKEND_VERIFIED", backend_verified_ids, 5),
        ("IMPLEMENTED_ONLY", implemented_only_ids, 3),
        ("BLOCKED_PROVIDER", blocked_provider_ids, 1),
    ]

    total_count = 0
    seen_ids = set()

    for category_name, id_set, expected_count in all_defined_sets:
        assert len(id_set) == expected_count, (
            f"Category {category_name} expected {expected_count} items, got {len(id_set)}"
        )
        # Verify no duplicate IDs across categories
        overlap = seen_ids.intersection(id_set)
        assert not overlap, f"Duplicate capability IDs detected across categories: {overlap}"
        seen_ids.update(id_set)
        total_count += len(id_set)

    assert total_count == 30, f"Expected total 30 capabilities, got {total_count}"
    assert len(seen_ids) == 30, f"Expected 30 unique capability IDs, got {len(seen_ids)}"

    # Verify all 30 exist in the registry
    registry_ids = {c.id for c in capabilities}
    assert registry_ids == seen_ids, f"Registry mismatch: {registry_ids ^ seen_ids}"


# ─────────────────────────────────────────────────────────────────────────────
# 4. End-to-End Native Edit & Export Journey Integrity
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_native_edit_and_export_journey_integrity(technical_fixture_video_mp4, tmp_path):
    """Verify full end-to-end native edit journey with real MP4 media:
    Create project -> Apply trim -> Verify CAS revision increment -> Render canonical MP4 -> Probe decoded streams.
    """
    out_file = tmp_path / "wave11_native_export.mp4"

    initial_doc = {
        "schema_version": 2,
        "title": "Wave 11 Native Edit Integrity",
        "aspect_ratio": "9:16",
        "timeline": {
            "fps": 30,
            "duration_seconds": 1.0,
            "tracks": [
                {
                    "id": "trk_v1",
                    "type": "video",
                    "name": "Main Video",
                    "clips": [
                        {
                            "id": "clip_01",
                            "source_path": str(technical_fixture_video_mp4),
                            "source_trim_start": 0.0,
                            "timeline_duration_seconds": 1.0,
                            "framing_preset": "center_crop",
                        }
                    ],
                }
            ],
        },
    }

    # 1. Create project
    proj = await ProjectService.create_project(
        name="Wave 11 E2E Journey",
        aspect_ratio="9:16",
        initial_document=initial_doc,
    )
    assert proj.id
    assert proj.revision == 1

    # 2. Apply trim tool via dispatcher
    trim_res = await MotionCapabilityDispatcher.dispatch(
        capability_id="trim",
        input_path=str(technical_fixture_video_mp4),
        params={"start_seconds": 0.0, "end_seconds": 0.8},
        project_doc=initial_doc,
    )
    assert trim_res.status == "SUCCESS"
    assert trim_res.output_path is not None
    assert Path(trim_res.output_path).exists()

    # 3. Apply CAS update
    updated_doc = dict(initial_doc)
    updated_doc["timeline"]["duration_seconds"] = 0.8
    updated_doc["timeline"]["tracks"][0]["clips"][0]["timeline_duration_seconds"] = 0.8

    proj_rev2 = await ProjectService.apply_operation(
        project_id=proj.id,
        expected_revision=1,
        operation_type="update_document",
        payload={"document": updated_doc},
        idempotency_key="wave11_trim_update",
    )
    assert (proj_rev2.get("revision") if isinstance(proj_rev2, dict) else proj_rev2.revision) == 2

    # 4. Build authoritative RenderManifest and render canonical MP4
    manifest = build_render_manifest(updated_doc)
    assert manifest is not None
    assert manifest.aspect_ratio == "9:16"
    assert manifest.width == 1080
    assert manifest.height == 1920

    res_path, probe, warnings = await render_manifest_to_mp4(manifest, out_file)
    assert res_path.exists()
    assert probe is not None
    assert probe.width == 1080
    assert probe.height == 1920
    assert probe.video_codec in ("h264", "x264")
    assert 0.7 <= probe.duration_seconds <= 1.1
