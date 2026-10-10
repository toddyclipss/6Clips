# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
import pytest
from backend.database import init_db
from backend.services.project_service import ProjectService
from backend.services.hyperframes_adapter import HyperFramesAdapter
from backend.services.studio_service import StudioService


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.mark.asyncio
async def test_hyperframes_adapter_doc_to_html_contract():
    doc = {
        "title": "HyperFrames Test",
        "aspect_ratio": "9:16",
        "timeline": {
            "duration_seconds": 12.0,
            "tracks": [
                {
                    "id": "track_captions",
                    "type": "captions",
                    "clips": [
                        {"id": "cap_1", "start_seconds": 0.0, "duration_seconds": 5.0, "caption_text": "HOOK OF THE VIDEO"}
                    ]
                }
            ]
        }
    }
    html = HyperFramesAdapter.project_doc_to_html(doc)
    assert "data-composition-id" in html
    assert "__timelines" in html
    assert "HOOK OF THE VIDEO" in html

    # Verify that StudioService cheap checks pass on this HTML
    issues = StudioService._composition_issues(html)
    assert issues == [], f"Expected no composition issues, got: {issues}"


@pytest.mark.asyncio
async def test_sync_project_to_studio():
    p = await ProjectService.create_project(name="Sync Test", aspect_ratio="16:9")
    sync_res = await HyperFramesAdapter.sync_project_to_studio(p.id)
    assert sync_res["project_id"] == p.id
    assert sync_res["revision"] == 1

    proj_dir = StudioService.project_dir()
    assert (proj_dir / "index.html").is_file()
    assert (proj_dir / "project_meta.json").is_file()
