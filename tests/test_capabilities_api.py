# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for Capabilities API and unified suggest_clips execution."""
import pytest
from httpx import AsyncClient, ASGITransport
import subprocess
from pathlib import Path
from uuid import uuid4

from backend.main import app
from backend.database import init_db, AsyncSessionLocal
from backend.models.downloaded_video import DownloadedVideo
from backend.config import settings


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_capabilities_api_list():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/capabilities")
        assert res.status_code == 200
        data = res.json()
        names = [c["name"] for c in data["capabilities"]]
        assert "suggest_clips" in names
        assert "project_operation" in names
        assert "ingest_trend" in names


@pytest.mark.asyncio
async def test_capabilities_api_execute_suggest_clips(tmp_path):
    await init_db()

    # Generate a dummy test video
    test_video = tmp_path / "test_sugg_source.mp4"
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=10:size=640x360:rate=30",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "10",
        "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p",
        str(test_video)
    ]
    subprocess.run(cmd, capture_output=True, check=True)

    dv_id = f"test_dv_{uuid4().hex[:8]}"
    async with AsyncSessionLocal() as db:
        dv = DownloadedVideo(
            id=dv_id,
            user_id="local",
            title="Video for Suggestion",
            video_path=str(test_video),
            duration_seconds=10,
        )
        db.add(dv)
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/capabilities/suggest_clips/execute",
            json={
                "video_id": dv_id,
                "max_clips": 3,
                "min_duration": 2.0,
                "max_duration": 4.0,
            }
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["status"] == "success"
        assert data["verification"]["ok"] is True
        assert "suggestions" in data["output"]
        assert len(data["output"]["suggestions"]) == 3
        suggs = data["output"]["suggestions"]
        assert suggs[0]["start"] == 0.0
        assert suggs[0]["end"] > 0.0
