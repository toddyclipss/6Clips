# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Acceptance test suite for gaming-first Outcomes-as-a-Service real video creation workflow.

Validates the full vertical slice:
inspect_media -> create_project -> suggest_clips -> catalog intro block -> generate_captions -> project_render
with CAS revision tracking, audio muxing, and zero writes to the production database.
"""
import asyncio
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
import pytest
from sqlalchemy import select

from backend.database import AsyncSessionLocal, init_db
from backend.models.downloaded_video import DownloadedVideo
from backend.models.project import Project
from backend.models.project_revision import ProjectRevision
from backend.services.project_service import ProjectService
from backend.services.executor_service import ExecutorService
from backend.core.capabilities import CapabilityRegistry
from backend.core.verifiers import verify_video_stream, verify_media_audio
from backend.core.exceptions import RevisionConflictError
from backend.services.video_utils import probe_media_streams


PROD_DB_PATH = Path("c:/Users/toddy/Desktop/ViralMint/viralmint.db")
EXPECTED_PROD_HASH = "40973CC72CD4358CB69DBD24B6E2BE1D6924A06351F162757F49CBA1CE056DA9"


def get_file_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().upper()


@pytest.fixture(autouse=True)
def verify_production_db_isolation():
    """Ensure production database hash is identical before and after every test."""
    assert PROD_DB_PATH.exists(), "Production DB must exist"
    pre_hash = get_file_sha256(PROD_DB_PATH)
    assert pre_hash == EXPECTED_PROD_HASH, f"Production DB modified before test! Expected {EXPECTED_PROD_HASH}, got {pre_hash}"
    yield
    post_hash = get_file_sha256(PROD_DB_PATH)
    assert post_hash == EXPECTED_PROD_HASH, f"Production DB modified during test! Expected {EXPECTED_PROD_HASH}, got {post_hash}"


@pytest.mark.asyncio
async def test_gaming_first_oaas_full_vertical_slice(tmp_path):
    """Execute end-to-end gaming highlight OaaS workflow on technical fixture."""
    # 1. Setup isolated database and directories
    await init_db()

    fixture_video = Path("c:/Users/toddy/Desktop/ViralMint/tmp_isolated_test/storage/downloads/technical_gaming_fixture.mp4")
    assert fixture_video.exists(), "Technical fixture must exist"

    # Register technical fixture in isolated DB
    fixture_id = "apex_clutch_40s"
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(DownloadedVideo).where(DownloadedVideo.id == fixture_id))
        dv = res.scalar_one_or_none()
        if not dv:
            dv = DownloadedVideo(
                id=fixture_id,
                user_id="local",
                platform="local",
                title="[TECHNICAL_FIXTURE_PENDING_USER_MEDIA] Apex Legends Clutch Play",
                video_path=str(fixture_video),
                duration_seconds=35,
            )
            db.add(dv)
            await db.commit()

    # 2. Step 1: inspect_media
    inspect_run = await ExecutorService.create_run(
        objective="Inspect gaming media assets",
        user_id="local",
    )
    inspect_step = await ExecutorService.execute_step(
        run_id=inspect_run.id,
        step_name="Inspect Media",
        capability_name="inspect_media",
        payload={"video_id": f"dl:{fixture_id}"},
        user_id="local",
        authorized=True,
    )
    await ExecutorService.complete_run(inspect_run.id, status="completed")

    assert inspect_step["status"] == "success"
    items = inspect_step["output"]["items"]
    assert len(items) == 1
    item = items[0]
    assert item["duration"] == 35.0
    assert item["video"]["width"] == 1080
    assert item["video"]["height"] == 1920
    assert item["video"]["aspect_ratio"] == "9:16"
    assert item["has_audio"] is True

    # 3. Step 2: create_project
    proj_run = await ExecutorService.create_run(
        objective="Create canonical gaming highlight project",
        user_id="local",
    )
    proj_step = await ExecutorService.execute_step(
        run_id=proj_run.id,
        step_name="Create Project",
        capability_name="create_project",
        payload={"name": "Gaming Highlight Short", "aspect_ratio": "9:16"},
        user_id="local",
        authorized=True,
    )
    await ExecutorService.complete_run(proj_run.id, status="completed")

    assert proj_step["status"] == "success"
    project_id = proj_step["output"]["project_id"]
    revision = proj_step["output"]["revision"]
    assert revision == 1

    # 4. Step 3: suggest_clips (Whisper transcription + Virality Scoring + Timeline Binding)
    clips_run = await ExecutorService.create_run(
        objective="Analyze gameplay moments and bind top highlight",
        project_id=project_id,
        user_id="local",
    )
    clips_step = await ExecutorService.execute_step(
        run_id=clips_run.id,
        step_name="Suggest Clips",
        capability_name="suggest_clips",
        payload={
            "video_id": f"dl:{fixture_id}",
            "project_id": project_id,
            "apply_to_project": True,
            "expected_revision": revision,
            "max_clips": 1,
            "min_duration": 8.0,
            "max_duration": 25.0,
        },
        user_id="local",
        authorized=True,
    )
    await ExecutorService.complete_run(clips_run.id, status="completed")

    assert clips_step["status"] == "success"
    suggestions = clips_step["output"]["suggestions"]
    assert len(suggestions) > 0
    top_clip = suggestions[0]
    assert top_clip["virality_score"] >= 5.0
    assert "start" in top_clip and "end" in top_clip

    # Verify project has updated revision and timeline video clip
    proj_record = await ProjectService.get_project(project_id)
    assert proj_record.revision > revision
    revision = proj_record.revision
    doc = json.loads(proj_record.document_json)
    v_track = next((t for t in doc["timeline"]["tracks"] if t["type"] == "video"), None)
    assert v_track is not None
    assert len(v_track["clips"]) >= 1
    bound_clip = v_track["clips"][0]
    assert bound_clip["asset_id"] == f"dl:{fixture_id}"
    assert bound_clip["duration"] == top_clip["duration"]

    # 5. Step 4: search_catalog and add motion intro block
    catalog_run = await ExecutorService.create_run(
        objective="Discover and insert motion intro graphic",
        project_id=project_id,
        user_id="local",
    )
    cat_step = await ExecutorService.execute_step(
        run_id=catalog_run.id,
        step_name="Search Catalog",
        capability_name="search_catalog",
        payload={"query": "hud", "limit": 5},
        user_id="local",
        authorized=True,
    )
    catalog_items = cat_step["output"]["items"]
    assert len(catalog_items) > 0
    selected_block = catalog_items[0]["id"]

    # Insert motion intro block at start
    intro_step = await ExecutorService.execute_step(
        run_id=catalog_run.id,
        step_name="Add Motion Intro Block",
        capability_name="project_operation",
        payload={
            "project_id": project_id,
            "expected_revision": revision,
            "operation_type": "add_block",
            "payload": {
                "block_id": selected_block,
                "start_seconds": 0.0,
                "duration_seconds": 3.0,
                "title": "Gaming Intro",
            },
        },
        user_id="local",
        authorized=True,
    )
    await ExecutorService.complete_run(catalog_run.id, status="completed")
    revision = intro_step["output"]["revision"]

    # 6. Step 5: generate_captions
    captions_run = await ExecutorService.create_run(
        objective="Generate synchronized speech captions",
        project_id=project_id,
        user_id="local",
    )
    cap_step = await ExecutorService.execute_step(
        run_id=captions_run.id,
        step_name="Generate Captions",
        capability_name="generate_captions",
        payload={
            "project_id": project_id,
            "expected_revision": revision,
            "position": "bottom",
            "color": "#FFE600",
        },
        user_id="local",
        authorized=True,
    )
    await ExecutorService.complete_run(captions_run.id, status="completed")
    assert cap_step["status"] == "success"
    captions_count = cap_step["output"]["captions_count"]
    assert captions_count >= 1
    revision = cap_step["output"]["revision"]

    # 7. Step 6: project_render
    render_run = await ExecutorService.create_run(
        objective="Render immutable project revision to MP4 with audio muxing",
        project_id=project_id,
        user_id="local",
    )
    render_step = await ExecutorService.execute_step(
        run_id=render_run.id,
        step_name="Project Render",
        capability_name="project_render",
        payload={
            "project_id": project_id,
            "revision": revision,
            "aspect_ratio": "9:16",
        },
        user_id="local",
        authorized=True,
    )
    await ExecutorService.complete_run(render_run.id, status="completed")

    assert render_step["status"] == "success"
    rendered_file = Path(render_step["output"]["video_path"])
    assert rendered_file.exists(), f"Rendered file {rendered_file} must exist on disk"

    # Technical FFprobe verification of output
    probe = probe_media_streams(rendered_file)
    assert probe["ok"] is True
    assert probe["video"] is not None
    assert probe["video"]["aspect_ratio"] == "9:16"
    assert probe["duration_seconds"] > 2.0
    # Crucial audio verification: output must NOT be silent
    assert probe["has_audio"] is True
    assert probe["audio"] is not None
    assert probe["audio"]["channels"] >= 1

    # 8. Step 7: Optimistic Concurrency Control (CAS) Test
    # Attempting to apply an operation with a stale revision must fail with RevisionConflictError
    stale_revision = 1
    with pytest.raises(RevisionConflictError):
        await ProjectService.apply_operation(
            project_id=project_id,
            expected_revision=stale_revision,
            operation_type="set_aspect_ratio",
            payload={"aspect_ratio": "16:9"},
            author="test",
        )
