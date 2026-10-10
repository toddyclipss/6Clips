# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Integration test: Real TrendResult -> ingest -> Project Asset -> Preview pipeline."""
import pytest
import subprocess
import shutil
from pathlib import Path
from uuid import uuid4
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.database import init_db, AsyncSessionLocal
from backend.models.trends_result import TrendsResult
from backend.services.project_service import ProjectService
from backend.services.executor_service import ExecutorService
from backend.services.hyperframes_adapter import HyperFramesAdapter
from backend.services.studio_service import StudioService
from backend.services.video_utils import probe_media, probe_duration
from backend.core.verifiers import verify_video_stream


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_real_trend_ingest_to_preview_pipeline(tmp_path):
    await init_db()

    # 1. Create a real media MP4 using ffmpeg
    media_file = tmp_path / "real_trend_source.mp4"
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=3:size=720x1280:rate=30",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "3",
        "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p",
        str(media_file)
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    assert media_file.exists() and media_file.stat().st_size > 1000

    # 2. Insert a real TrendsResult row pointing to this media
    trend_id = f"trend_test_{uuid4().hex[:8]}"
    async with AsyncSessionLocal() as db:
        tr = TrendsResult(
            id=trend_id,
            user_id="local",
            platform="youtube",
            video_id=f"vid_{trend_id}",
            title="Viral AI Dance Craze",
            video_url=str(media_file),
            views=1500000,
            author="Trending Channel",
            duration_seconds=3,
            is_downloaded=False,
        )
        db.add(tr)
        await db.commit()

    # 3. Create a Project (Revision 1)
    project = await ProjectService.create_project(
        name="Trend Ingest Composition",
        aspect_ratio="9:16",
    )
    assert project.revision == 1

    # 4. Ingest Trend into Project via ExecutorService (Capability: ingest_trend)
    run = await ExecutorService.create_run(
        objective=f"Ingest trend {trend_id} into project {project.id}",
        project_id=project.id,
    )
    res_step = await ExecutorService.execute_step(
        run_id=run.id,
        step_name="Ingest trend into project",
        capability_name="ingest_trend",
        payload={
            "trend_result_id": trend_id,
            "project_id": project.id,
            "expected_revision": 1,
        },
        authorized=True,
    )
    assert res_step["status"] == "success"
    assert res_step["verification"]["ok"] is True
    assert res_step["verification"]["new_revision"] == 2

    # Verify project document now has the asset in DB
    p_updated = await ProjectService.get_project(project.id)
    assert p_updated.revision == 2
    import json
    doc = json.loads(p_updated.document_json)
    assets = doc.get("assets", [])
    assert len(assets) == 1
    asset_id = assets[0]["id"]
    assert asset_id.startswith("dl:")
    assert assets[0]["source_trend_id"] == trend_id

    # 5. Add a timeline clip referencing this ingested asset (Revision 2 -> 3)
    clip_id = f"clip_{uuid4().hex[:8]}"
    res_clip = await ProjectService.apply_operation(
        project_id=project.id,
        expected_revision=2,
        operation_type="add_clip",
        payload={
            "track_id": "track_video_main",
            "clip": {
                "id": clip_id,
                "asset_id": asset_id,
                "title": "Viral Trend Highlight",
                "start_seconds": 0.0,
                "duration_seconds": 3.0,
            }
        },
    )
    assert res_clip["revision"] == 3

    # 6. Synchronize project to studio preview stage
    sync_res = await HyperFramesAdapter.sync_project_to_studio(project.id)
    html_file = Path(sync_res["html_path"])
    assert html_file.exists()

    # 7. Test read-only Preview HTTP endpoint
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        prev_res = await client.get(f"/api/projects/{project.id}/preview")
        assert prev_res.status_code == 200
        preview_html = prev_res.text
        assert "Viral Trend Highlight" in preview_html or clip_id in preview_html
        assert f"/api/projects/{project.id}/preview/assets/" in preview_html

        # Extract video asset filename from preview HTML (filter for .mp4)
        import re
        m = re.search(rf'/api/projects/{project.id}/preview/assets/([^"\'>\s]+\.mp4)', preview_html)
        assert m is not None, "Staged video asset URL not found in preview HTML"
        asset_filename = m.group(1)

        # 8. Test staged preview asset HTTP delivery
        asset_res = await client.get(f"/api/projects/{project.id}/preview/assets/{asset_filename}")
        assert asset_res.status_code == 200
        assert len(asset_res.content) > 1000

        # 9. Verify the staged asset on disk with ffprobe
        staged_path = StudioService.project_dir() / "assets" / asset_filename
        assert staged_path.exists()
        v_res = verify_video_stream(staged_path, min_duration=0.5)
        assert v_res["ok"] is True, f"Verification failed: {v_res}"
        w, h, dur = probe_media(staged_path)
        assert w == 720
        assert h == 1280
        assert dur >= 2.5
