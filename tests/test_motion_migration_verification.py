import asyncio
import json
import pytest
from pathlib import Path
from starlette.testclient import TestClient

from backend.main import create_app
from backend.database import init_db, AsyncSessionLocal
from backend.services.project_service import ProjectService
from backend.services.executor_service import ExecutorService
from backend.core.capabilities import CapabilityRegistry
from backend.services.library_index import lineage, families
from backend.models.downloaded_video import DownloadedVideo
from backend.models.generated_video import GeneratedVideo
from backend.models.project import Project
from backend.models.project_revision import ProjectRevision
from backend.core.exceptions import (
    RevisionConflictError,
    ProjectNotFoundError,
    AuthorizationRequiredError,
    CapabilityExecutionError,
)
from sqlalchemy import select


@pytest.fixture(autouse=True)
async def setup_database():
    await init_db()


@pytest.mark.asyncio
async def test_save_draft_update_document_operation():
    """Verify that update_document operation works without 400 and increments revision."""
    p = await ProjectService.create_project(name="Draft Project", aspect_ratio="9:16")
    assert p.revision == 1

    new_doc = {
        "title": "Updated Draft",
        "aspect_ratio": "9:16",
        "timeline": {
            "duration_seconds": 12.0,
            "tracks": [
                {
                    "id": "track_video_main",
                    "type": "video",
                    "clips": [
                        {"id": "clip_1", "start_seconds": 0.0, "duration_seconds": 12.0}
                    ]
                }
            ]
        }
    }

    # Test via ProjectService
    res = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=1,
        operation_type="update_document",
        payload={"document": new_doc},
        author="user",
    )

    assert res["applied"] is True
    assert res["revision"] == 2
    assert res["document"]["title"] == "Updated Draft"
    assert res["document"]["timeline"]["duration_seconds"] == 12.0


@pytest.mark.asyncio
async def test_concurrency_race_prevention_no_duplicates():
    """
    Verify that simultaneous edits expecting revision 1 cannot both succeed or
    create duplicate revision 2 snapshots.
    """
    p = await ProjectService.create_project(name="Concurrent Race Test", aspect_ratio="9:16")
    project_id = p.id

    doc_a = {"title": "Doc A", "timeline": {"duration_seconds": 5.0, "tracks": []}}
    doc_b = {"title": "Doc B", "timeline": {"duration_seconds": 10.0, "tracks": []}}

    # Attempt two concurrent operations both expecting revision 1
    task1 = asyncio.create_task(
        ProjectService.apply_operation(
            project_id=project_id,
            expected_revision=1,
            operation_type="update_document",
            payload={"document": doc_a},
        )
    )
    task2 = asyncio.create_task(
        ProjectService.apply_operation(
            project_id=project_id,
            expected_revision=1,
            operation_type="update_document",
            payload={"document": doc_b},
        )
    )

    results = await asyncio.gather(task1, task2, return_exceptions=True)

    successes = [r for r in results if isinstance(r, dict) and r.get("applied")]
    conflicts = [r for r in results if isinstance(r, RevisionConflictError)]

    # Exactly one must succeed, and one must fail with RevisionConflictError
    assert len(successes) == 1, f"Expected 1 success, got {len(successes)}"
    assert len(conflicts) == 1, f"Expected 1 conflict, got {len(conflicts)}"
    assert successes[0]["revision"] == 2

    # Check database: only one revision 2 should exist
    async with AsyncSessionLocal() as db:
        rev_rows = (await db.execute(
            select(ProjectRevision)
            .where(ProjectRevision.project_id == project_id)
            .where(ProjectRevision.revision == 2)
        )).scalars().all()
        assert len(rev_rows) == 1, f"Duplicate revision 2 found in DB: {len(rev_rows)}"


def test_api_save_draft_and_render_dispatch(tmp_path):
    """Test REST API routes for saving draft and dispatching render."""
    app = create_app()
    with TestClient(app) as client:
        # 1. Create project
        create_res = client.post("/api/projects", json={"name": "API Test", "aspect_ratio": "9:16"})
        assert create_res.status_code == 200
        p_data = create_res.json()
        pid = p_data["id"]
        rev = p_data["revision"]

        # 2. Save Draft via operations endpoint with update_document
        draft_doc = {
            "title": "API Draft Saved",
            "aspect_ratio": "9:16",
            "timeline": {
                "tracks": [
                    {
                        "id": "track_video_main",
                        "type": "video",
                        "clips": [{"id": "c1", "duration_seconds": 6.0}]
                    }
                ]
            }
        }
        op_res = client.post(f"/api/projects/{pid}/operations", json={
            "expected_revision": rev,
            "operation_type": "update_document",
            "payload": {"document": draft_doc},
            "author": "user"
        })
        assert op_res.status_code == 200, f"Failed with {op_res.text}"
        assert op_res.json()["revision"] == 2

        # 3. Render project (frozen revision render dispatch)
        render_res = client.post(f"/api/projects/{pid}/render", json={"revision": 2})
        assert render_res.status_code == 200, f"Render failed: {render_res.text}"
        assert render_res.json()["frozen_revision"] == 2
        assert "job_id" in render_res.json()


def test_tools_from_asset_api(tmp_path):
    """Test /api/tools/{tool}/from-asset endpoint with real video file on disk."""
    app = create_app()
    with TestClient(app) as client:
        # Create dummy video file
        dummy_file = tmp_path / "source_video.mp4"
        dummy_file.write_bytes(b"\x00" * 2048)

        # Seed DownloadedVideo
        async def _seed_video():
            async with AsyncSessionLocal() as db:
                dv = DownloadedVideo(
                    user_id="local",
                    title="Source Asset",
                    video_path=str(dummy_file),
                    duration_seconds=10,
                )
                db.add(dv)
                await db.commit()
                await db.refresh(dv)
                return dv.id

        video_id = asyncio.run(_seed_video())

        # Test tool dispatch via from-asset
        for tool_name, params in [
            ("trim", {"start_seconds": 1.0, "end_seconds": 4.0}),
            ("speed", {"speed": 1.5, "keep_pitch": True}),
            ("reframe", {"aspect_ratio": "9:16"}),
            ("compress", {"resolution": "original", "level": "high"}),
        ]:
            res = client.post(f"/api/tools/{tool_name}/from-asset", json={
                "video_id": video_id,
                **params
            })
            assert res.status_code == 200, f"Tool {tool_name} failed: {res.text}"
            data = res.json()
            assert "job_id" in data
            assert data["status"] == "queued"


@pytest.mark.asyncio
async def test_executor_service_no_fake_pass_and_auth():
    """Verify ExecutorService fails on missing project and requires authorization."""
    run = await ExecutorService.create_run(objective="Test Verification")

    # 1. Non-existent project for project_render must RAISE ProjectNotFoundError
    with pytest.raises(ProjectNotFoundError):
        await ExecutorService.execute_step(
            run_id=run.id,
            step_name="Render non-existent",
            capability_name="project_render",
            payload={"project_id": "non_existent_project_id_123"},
        )

    # 2. Unhandled capability must RAISE CapabilityExecutionError, NOT generic_pass
    from backend.core.capabilities import Capability
    CapabilityRegistry.register(
        Capability(
            name="unhandled_mock_capability",
            description="Test unhandled capability",
            surface="common",
            required_params=["query"],
        )
    )
    with pytest.raises(CapabilityExecutionError):
        await ExecutorService.execute_step(
            run_id=run.id,
            step_name="Search trends unhandled",
            capability_name="unhandled_mock_capability",
            payload={"query": "ai news"},
        )

    # 3. Authorization required capability without authorized=True must fail
    with pytest.raises(AuthorizationRequiredError):
        await ExecutorService.execute_step(
            run_id=run.id,
            step_name="Upload YouTube unauthorized",
            capability_name="upload_youtube",
            payload={"video_id": "vid_123"},
            authorized=False,
        )


@pytest.mark.asyncio
async def test_multi_parent_lineage(tmp_path):
    """Verify multi-parent lineage traversal across parent_keys."""
    file_p1 = tmp_path / "p1.mp4"
    file_p2 = tmp_path / "p2.mp4"
    file_child = tmp_path / "child.mp4"
    file_p1.write_bytes(b"\x00" * 1024)
    file_p2.write_bytes(b"\x00" * 1024)
    file_child.write_bytes(b"\x00" * 1024)

    async with AsyncSessionLocal() as db:
        dv1 = DownloadedVideo(user_id="local", title="Parent 1", video_path=str(file_p1), duration_seconds=5)
        dv2 = DownloadedVideo(user_id="local", title="Parent 2", video_path=str(file_p2), duration_seconds=5)
        db.add_all([dv1, dv2])
        await db.commit()
        await db.refresh(dv1)
        await db.refresh(dv2)

        gv_child = GeneratedVideo(
            user_id="local",
            title="Composite Child",
            video_path=str(file_child),
            duration_seconds=10,
            status="ready",
            source_type="motion_graphics",
            parent_asset_ids_json=json.dumps([f"downloaded:{dv1.id}", f"downloaded:{dv2.id}"]),
        )
        db.add(gv_child)
        await db.commit()
        await db.refresh(gv_child)

        child_key = f"gv:{gv_child.id}"
        lin = await lineage(db, child_key)
        assert lin is not None
        ancestor_keys = [a["key"] for a in lin["ancestors"]]
        assert f"dl:{dv1.id}" in ancestor_keys
        assert f"dl:{dv2.id}" in ancestor_keys

        # Check families: child should be in families of parent 1
        fam = await families(db)
        p1_family = next((f for f in fam.get("families", []) if f["root"]["key"] == f"dl:{dv1.id}"), None)
        assert p1_family is not None
        child_keys = [c["item"]["key"] for c in p1_family.get("children", [])]
        assert child_key in child_keys


@pytest.mark.asyncio
async def test_isolated_render_staging_no_cross_contamination(tmp_path):
    """
    Verify that staging project A and project B generates separate directories
    and does not mutate or contaminate global StudioService.project_dir().
    """
    from backend.services.hyperframes_adapter import HyperFramesAdapter
    from backend.services.studio_service import StudioService
    import shutil

    # Create dummy real assets
    p1_file = tmp_path / "asset1.mp4"
    p2_file = tmp_path / "asset2.mp4"
    p1_file.write_bytes(b"\x00" * 512)
    p2_file.write_bytes(b"\x00" * 512)

    async with AsyncSessionLocal() as db:
        dv1 = DownloadedVideo(user_id="local", title="Asset 1", video_path=str(p1_file), duration_seconds=5)
        dv2 = DownloadedVideo(user_id="local", title="Asset 2", video_path=str(p2_file), duration_seconds=8)
        db.add_all([dv1, dv2])
        await db.commit()
        await db.refresh(dv1)
        await db.refresh(dv2)

    proj_a = await ProjectService.create_project(name="Project Alpha", aspect_ratio="9:16")
    proj_b = await ProjectService.create_project(name="Project Beta", aspect_ratio="16:9")

    doc_a = {
        "title": "Alpha Comp",
        "aspect_ratio": "9:16",
        "timeline": {
            "duration_seconds": 5.0,
            "tracks": [{"type": "video", "clips": [{"id": "c1", "asset_id": f"dl:{dv1.id}", "file": "asset1.mp4", "duration_seconds": 5.0}]}]
        }
    }
    doc_b = {
        "title": "Beta Comp",
        "aspect_ratio": "16:9",
        "timeline": {
            "duration_seconds": 8.0,
            "tracks": [{"type": "video", "clips": [{"id": "c2", "asset_id": f"dl:{dv2.id}", "file": "asset2.mp4", "duration_seconds": 8.0}]}]
        }
    }

    await ProjectService.apply_operation(proj_a.id, 1, "update_document", {"document": doc_a})
    await ProjectService.apply_operation(proj_b.id, 1, "update_document", {"document": doc_b})

    # Stage both projects for render
    rev_a, dir_a = await HyperFramesAdapter.stage_project_for_render(proj_a.id, revision=2)
    rev_b, dir_b = await HyperFramesAdapter.stage_project_for_render(proj_b.id, revision=2)

    try:
        assert dir_a != dir_b, "Staging directories must be completely distinct"
        assert dir_a != StudioService.project_dir(), "Staging must not use global studio dir"
        assert dir_b != StudioService.project_dir()

        html_a = (dir_a / "index.html").read_text(encoding="utf-8")
        html_b = (dir_b / "index.html").read_text(encoding="utf-8")

        # HTML isolation
        assert "Alpha Comp" in html_a
        assert "Beta Comp" not in html_a
        assert "Beta Comp" in html_b
        assert "Alpha Comp" not in html_b

        # Meta isolation
        meta_a = json.loads((dir_a / "project_meta.json").read_text(encoding="utf-8"))
        meta_b = json.loads((dir_b / "project_meta.json").read_text(encoding="utf-8"))
        assert meta_a["project_id"] == proj_a.id
        assert meta_a["aspect_ratio"] == "9:16"
        assert meta_b["project_id"] == proj_b.id
        assert meta_b["aspect_ratio"] == "16:9"

        # Assets isolation
        assert any("asset1.mp4" in f.name for f in (dir_a / "assets").iterdir())
        assert not any("asset2.mp4" in f.name for f in (dir_a / "assets").iterdir())
        assert any("asset2.mp4" in f.name for f in (dir_b / "assets").iterdir())
        assert not any("asset1.mp4" in f.name for f in (dir_b / "assets").iterdir())
    finally:
        shutil.rmtree(dir_a, ignore_errors=True)
        shutil.rmtree(dir_b, ignore_errors=True)


@pytest.mark.asyncio
async def test_universal_asset_resolver(tmp_path):
    """
    Verify universal asset resolution across prefixes (dl:, gv:, downloaded:, generated:)
    and raw UUIDs, including disk verification and clean errors.
    """
    from backend.services.asset_resolver import resolve_asset_record_and_path, AssetNotFoundError

    test_file_dl = tmp_path / "dl_video.mp4"
    test_file_gv = tmp_path / "gv_video.mp4"
    test_file_dl.write_bytes(b"\x00" * 256)
    test_file_gv.write_bytes(b"\x00" * 256)

    async with AsyncSessionLocal() as db:
        dv = DownloadedVideo(user_id="local", title="Downloaded Asset", video_path=str(test_file_dl), duration_seconds=4)
        gv = GeneratedVideo(user_id="local", title="Generated Asset", video_path=str(test_file_gv), duration_seconds=6)
        db.add_all([dv, gv])
        await db.commit()
        await db.refresh(dv)
        await db.refresh(gv)

    # 1. dl: prefix
    key, path, meta = await resolve_asset_record_and_path(f"dl:{dv.id}")
    assert key == f"dl:{dv.id}"
    assert path == test_file_dl
    assert meta["type"] == "downloaded"

    # 2. downloaded: alias
    key, path, meta = await resolve_asset_record_and_path(f"downloaded:{dv.id}")
    assert key == f"dl:{dv.id}"

    # 3. raw UUID for downloaded
    key, path, meta = await resolve_asset_record_and_path(str(dv.id))
    assert key == f"dl:{dv.id}"

    # 4. gv: prefix
    key, path, meta = await resolve_asset_record_and_path(f"gv:{gv.id}")
    assert key == f"gv:{gv.id}"
    assert path == test_file_gv
    assert meta["type"] == "generated"

    # 5. generated: alias
    key, path, meta = await resolve_asset_record_and_path(f"generated:{gv.id}")
    assert key == f"gv:{gv.id}"

    # 6. raw UUID for generated
    key, path, meta = await resolve_asset_record_and_path(str(gv.id))
    assert key == f"gv:{gv.id}"

    # 7. Non-existent asset ID raises AssetNotFoundError
    with pytest.raises(AssetNotFoundError):
        await resolve_asset_record_and_path("dl:non_existent_uuid_9999")

    # 8. Asset whose file is missing from disk raises AssetNotFoundError
    test_file_dl.unlink()
    with pytest.raises(AssetNotFoundError):
        await resolve_asset_record_and_path(f"dl:{dv.id}", must_exist=True)


@pytest.mark.asyncio
async def test_aspect_ratio_synchronization_and_derivation():
    """
    Verify that updating aspect_ratio in document synchronizes Project.aspect_ratio,
    frozen revisions, and generates corresponding composition dimensions.
    """
    from backend.services.hyperframes_adapter import HyperFramesAdapter
    from backend.services.motion_render_service import _composition_aspect
    import tempfile
    import shutil

    p = await ProjectService.create_project(name="Aspect Sync Test", aspect_ratio="9:16")
    assert p.aspect_ratio == "9:16"

    # Update document to 16:9
    doc = {
        "title": "Landscape Comp",
        "aspect_ratio": "16:9",
        "timeline": {"duration_seconds": 10.0, "tracks": []}
    }
    await ProjectService.apply_operation(p.id, 1, "update_document", {"document": doc})

    # 1. DB project aspect_ratio must be synchronized to 16:9
    refreshed = await ProjectService.get_project(p.id)
    assert refreshed.aspect_ratio == "16:9"

    # 2. Frozen revision snapshot has 16:9
    rev, snap = await ProjectService.freeze_for_render(p.id)
    assert snap.get("aspect_ratio") == "16:9"

    # 3. HTML generated has width=1920 height=1080 and correct data attributes
    html = HyperFramesAdapter.project_doc_to_html(snap)
    assert 'data-width="1920"' in html
    assert 'data-height="1080"' in html

    # 4. Composition aspect helper derives 16:9 from HTML
    tmp_dir = Path(tempfile.mkdtemp(prefix="test_aspect_"))
    try:
        (tmp_dir / "index.html").write_text(html, encoding="utf-8")
        derived = _composition_aspect(tmp_dir, requested="9:16")
        assert derived == "16:9", f"Expected 16:9 derived from HTML, got {derived}"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_missing_asset_staging_fails_cleanly():
    """Verify that stage_project_for_render fails with AssetNotFoundError on missing asset."""
    from backend.services.hyperframes_adapter import HyperFramesAdapter
    from backend.services.asset_resolver import AssetNotFoundError

    p = await ProjectService.create_project(name="Missing Asset Test", aspect_ratio="9:16")
    bad_doc = {
        "title": "Bad Comp",
        "timeline": {
            "duration_seconds": 5.0,
            "tracks": [{"type": "video", "clips": [{"id": "c1", "asset_id": "dl:non_existent_asset_id"}]}]
        }
    }
    await ProjectService.apply_operation(p.id, 1, "update_document", {"document": bad_doc})

    with pytest.raises(AssetNotFoundError):
        await HyperFramesAdapter.stage_project_for_render(p.id)


def test_preview_bridge_contract_in_html():
    """Verify that composition HTML contains bidirectional preview bridge and playback attributes."""
    from backend.services.hyperframes_adapter import HyperFramesAdapter

    doc = {
        "title": "Bridge Test",
        "aspect_ratio": "9:16",
        "timeline": {
            "duration_seconds": 6.0,
            "tracks": [
                {
                    "type": "video",
                    "clips": [
                        {
                            "id": "v1",
                            "file": "clip.mp4",
                            "start_seconds": 1.0,
                            "duration_seconds": 4.0,
                            "trim_start": 2.0,
                            "trim_end": 6.0,
                        }
                    ]
                },
                {
                    "type": "audio",
                    "clips": [
                        {
                            "id": "a1",
                            "file": "music.mp3",
                            "start_seconds": 0.0,
                            "duration_seconds": 6.0,
                            "trim_start": 0.5,
                        }
                    ]
                }
            ]
        }
    }
    html = HyperFramesAdapter.project_doc_to_html(doc)

    # 1. Video and Audio playback metadata
    assert 'data-playback-start="2.0"' in html
    assert 'data-trim-start="2.0"' in html
    assert 'data-media-start="2.0"' in html
    assert 'data-start="1.0"' in html
    assert 'data-duration="4.0"' in html

    assert '<audio data-hf-id="a1" id="a1"' in html
    assert 'data-playback-start="0.5"' in html

    # 2. Stage metadata
    assert 'data-composition-id="viralmint_stage"' in html
    assert 'data-width="1080"' in html
    assert 'data-height="1920"' in html

    # 3. Bidirectional postMessage bridge
    assert 'id="vm-preview-bridge"' in html
    assert 'vm-parent' in html
    assert 'vm-runtime' in html
    assert 'window.__timelines["viralmint_stage"]' in html


@pytest.mark.asyncio
async def test_real_video_asset_audiovisual_execution(tmp_path):
    """
    Verify real audiovisual execution with FFmpeg:
    Generates a genuine video with video and audio streams, stages it into a project,
    and runs deterministic tool execution with stream verification.
    """
    import subprocess
    from backend.core.verifiers import verify_video_stream
    from backend.services.video_utils import probe_duration
    from backend.core.tool_runners import run_tool_trim
    from backend.models.job import Job
    import shutil

    # 1. Synthesize real MP4 video with testsrc video + sine audio
    real_src = tmp_path / "real_test_source.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=1000:sample_rate=44100",
        "-t", "2.0",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "64k",
        str(real_src)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"FFmpeg synthesis failed: {res.stderr}"
    assert real_src.is_file()

    # 2. Verify source stream has valid video and duration ~2s
    v_check = verify_video_stream(real_src, min_duration=1.0)
    assert v_check["ok"] is True
    assert v_check["duration_seconds"] >= 1.9

    # 3. Run real deterministic trim tool on the asset
    async with AsyncSessionLocal() as db:
        dv = DownloadedVideo(
            user_id="local",
            title="Real Source Video",
            video_path=str(real_src),
            duration_seconds=2,
        )
        db.add(dv)
        await db.commit()
        await db.refresh(dv)

        job = Job(id=f"job_trim_test_{tmp_path.name[:6]}", user_id="local", job_type="tool:trim", status="pending")
        db.add(job)
        await db.commit()

    in_copy = tmp_path / "in_to_trim.mp4"
    shutil.copyfile(real_src, in_copy)

    # Trim 0.5s to 1.5s (resulting in 1.0s video)
    await run_tool_trim(
        job_id=job.id,
        in_path=in_copy,
        start_seconds=0.5,
        end_seconds=1.5,
        user_id="local",
    )

    # 4. Check job status and output video
    async with AsyncSessionLocal() as db:
        j_fresh = await db.get(Job, job.id)
        assert j_fresh.status == "success"
        out_data = json.loads(j_fresh.output_json) if j_fresh.output_json else {}
        out_file = out_data.get("file") or out_data.get("video_path")
        if not out_file:
            from backend.api.tools import tool_out_path
            out_file = str(tool_out_path(job.id, ".mp4"))
        assert Path(out_file).is_file()

        # 5. Verify trimmed video output stream
        trimmed_check = verify_video_stream(Path(out_file), min_duration=0.8)
        assert trimmed_check["ok"] is True
        assert 0.8 <= trimmed_check["duration_seconds"] <= 1.2


