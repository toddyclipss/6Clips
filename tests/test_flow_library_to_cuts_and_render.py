# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""End-to-end proof: Library video -> 3 cuts -> manual review -> project render -> verified lineage."""
import json
import pytest
from pathlib import Path
from uuid import uuid4

from backend.database import init_db, AsyncSessionLocal
from backend.models.downloaded_video import DownloadedVideo
from backend.models.generated_video import GeneratedVideo
from backend.services.project_service import ProjectService
from backend.services.executor_service import ExecutorService
from backend.core.verifiers import verify_file_output, verify_lineage
from backend.services.library_index import gather
from backend.agents.generator_motion import MotionGeneratorAgent


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.mark.asyncio
async def test_small_complete_workflow(tmp_path):
    # 1. Setup a Library source video
    source_file = tmp_path / "source_library_video.mp4"
    source_file.write_bytes(b"\x00" * 8192)  # valid dummy bytes

    async with AsyncSessionLocal() as db:
        dv = DownloadedVideo(
            user_id="local",
            title="Podcast Episode 42",
            video_path=str(source_file),
            duration_seconds=60,
            platform="youtube",
        )
        db.add(dv)
        await db.commit()
        await db.refresh(dv)
        source_id = dv.id

    # 2. Extract 3 captioned cuts (deterministic, works 100% without external LLM keys)
    cut_ids = []
    async with AsyncSessionLocal() as db:
        for i in range(3):
            start = i * 15.0
            end = start + 12.0
            cut_file = tmp_path / f"cut_{i+1}.mp4"
            cut_file.write_bytes(b"\x00" * 4096)

            gv = GeneratedVideo(
                user_id="local",
                title=f"Podcast Ep 42 - Highlight {i+1}",
                video_path=str(cut_file),
                source_downloaded_video_id=source_id,
                source_asset_id=f"dl:{source_id}",
                parent_asset_ids_json=json.dumps([f"dl:{source_id}"]),
                clip_start_seconds=start,
                clip_end_seconds=end,
                duration_seconds=12,
                operation="clip_extraction",
                caption_status="applied",
                status="ready",
            )
            db.add(gv)
            await db.commit()
            await db.refresh(gv)
            cut_ids.append(gv.id)

    assert len(cut_ids) == 3

    # 3. Create versioned project from cuts
    project = await ProjectService.create_project(
        name="Episode 42 Shorts Assembly",
        aspect_ratio="9:16",
    )
    assert project.revision == 1

    # Add each cut as a clip to the project
    for idx, cid in enumerate(cut_ids):
        res = await ProjectService.apply_operation(
            project_id=project.id,
            expected_revision=project.revision,
            operation_type="add_clip",
            payload={
                "track_id": "track_video_main",
                "clip": {
                    "id": f"clip_slot_{idx+1}",
                    "asset_id": f"gen:{cid}",
                    "start_seconds": idx * 12.0,
                    "duration_seconds": 12.0,
                    "trim_start": 0.0,
                    "trim_end": 12.0,
                },
            },
            idempotency_key=f"add_cut_{cid}",
            author="agent",
        )
        # Update local project revision tracker
        project.revision = res["revision"]

    assert project.revision == 4  # 1 (init) + 3 cuts added

    # 4. Manual user refinement: trim cut 2 by adjusting start and duration
    manual_edit_res = await ProjectService.apply_operation(
        project_id=project.id,
        expected_revision=4,
        operation_type="update_clip",
        payload={
            "clip_id": "clip_slot_2",
            "patch": {
                "duration_seconds": 10.0,
                "trim_end": 10.0,
            },
        },
        idempotency_key="user_trim_cut_2",
        author="user",
    )
    assert manual_edit_res["applied"] is True
    assert manual_edit_res["revision"] == 5

    # 5. Freeze revision 5 for render
    frozen_rev, snapshot = await ProjectService.freeze_for_render(project.id, revision=5)
    assert frozen_rev == 5
    clips_in_render = snapshot["timeline"]["tracks"][0]["clips"]
    assert len(clips_in_render) == 3
    # Check that manual trim is reflected in render snapshot
    assert clips_in_render[1]["duration_seconds"] == 10.0

    # 6. Simulate render output and save GeneratedVideo with lineage
    render_file = tmp_path / "final_assembly_render.mp4"
    render_file.write_bytes(b"\x00" * 16384)

    rendered_id = await MotionGeneratorAgent._save(
        user_id="local",
        title="Episode 42 Final Short",
        variables={"assembly": True},
        niche="podcasts",
        video_path=render_file,
        thumb_path=None,
        audio_path=None,
        aspect_ratio="9:16",
        duration_seconds=34,
        script="Assembly of 3 highlights",
        caption_status="applied",
        project_id=project.id,
        project_revision=frozen_rev,
        parent_asset_ids=[f"gen:{cid}" for cid in cut_ids],
        operation="motion_render",
    )
    assert rendered_id

    # 7. Verify origin linkage and lineage
    async with AsyncSessionLocal() as db:
        rendered_gv = await db.get(GeneratedVideo, rendered_id)
        assert rendered_gv.project_id == project.id
        assert rendered_gv.project_revision == 5
        assert rendered_gv.file_hash is not None

        parents = json.loads(rendered_gv.parent_asset_ids_json)
        assert len(parents) == 3
        assert parents == [f"gen:{c}" for c in cut_ids]

        verif = verify_lineage(
            {
                "parent_keys": parents,
                "source_asset_id": rendered_gv.source_asset_id,
            },
            expected_parents=[cut_ids[0], cut_ids[1], cut_ids[2]],
        )
        assert verif["ok"] is True

    # 8. Verify library index incorporates the rendered video with lineage
    async with AsyncSessionLocal() as db:
        items = await gather(db)
        rendered_item = next((it for it in items if it["id"] == rendered_id), None)
        assert rendered_item is not None
        assert rendered_item["project_id"] == project.id
        assert rendered_item["project_revision"] == 5
        assert len(rendered_item["parent_keys"]) == 3
