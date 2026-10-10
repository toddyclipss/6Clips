# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Comprehensive test suite for Phase 9 Code & FileTree canonical integration."""
import pytest
from pathlib import Path
from backend.database import init_db
from backend.services.project_service import ProjectService
from backend.services.hyperframes_adapter import HyperFramesAdapter
from backend.core.exceptions import ProjectError, RevisionConflictError, IdempotencyConflictError


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.mark.asyncio
async def test_code_file_create_and_versioning():
    """Verify create_file operation persists in document and increments project revision."""
    p = await ProjectService.create_project(name="Code Project A", aspect_ratio="9:16")
    assert p.revision == 1

    # 1. Create a CSS stylesheet
    res1 = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=1,
        operation_type="create_file",
        payload={
            "path": "styles/custom.css",
            "content": ".headline { color: #8b5cf6; font-size: 64px; }",
        },
    )
    assert res1["revision"] == 2
    doc1 = res1["document"]
    files1 = doc1.get("code", {}).get("files", [])
    assert len(files1) == 1
    assert files1[0]["path"] == "styles/custom.css"
    assert ".headline" in files1[0]["content"]

    # 2. Create an HTML file
    res2 = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=2,
        operation_type="create_file",
        payload={
            "path": "components/banner.html",
            "content": '<div class="banner">PROMO LAUNCH</div>',
        },
    )
    assert res2["revision"] == 3
    doc2 = res2["document"]
    files2 = doc2.get("code", {}).get("files", [])
    assert len(files2) == 2


@pytest.mark.asyncio
async def test_code_file_update_content():
    """Verify update_file mutates file content and bumps revision."""
    p = await ProjectService.create_project(name="Code Project Update", aspect_ratio="9:16")

    res1 = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=1,
        operation_type="create_file",
        payload={
            "path": "script.js",
            "content": "console.log('v1');",
        },
    )
    fid = res1["document"]["code"]["files"][0]["id"]

    # Update content via file ID
    res2 = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=2,
        operation_type="update_file",
        payload={
            "id": fid,
            "content": "console.log('v2 updated');",
        },
    )
    assert res2["revision"] == 3
    updated_f = res2["document"]["code"]["files"][0]
    assert updated_f["content"] == "console.log('v2 updated');"


@pytest.mark.asyncio
async def test_code_file_rename_and_move():
    """Verify rename_file and move_file preserve file identity while updating path."""
    p = await ProjectService.create_project(name="Code Project Move", aspect_ratio="9:16")

    res1 = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=1,
        operation_type="create_file",
        payload={
            "path": "old_name.css",
            "content": "body { margin: 0; }",
        },
    )
    file_id = res1["document"]["code"]["files"][0]["id"]

    # Rename
    res2 = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=2,
        operation_type="rename_file",
        payload={
            "id": file_id,
            "new_path": "new_name.css",
        },
    )
    assert res2["revision"] == 3
    f2 = res2["document"]["code"]["files"][0]
    assert f2["id"] == file_id
    assert f2["path"] == "new_name.css"

    # Move to nested folder
    res3 = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=3,
        operation_type="move_file",
        payload={
            "id": file_id,
            "new_path": "themes/dark/new_name.css",
        },
    )
    assert res3["revision"] == 4
    f3 = res3["document"]["code"]["files"][0]
    assert f3["id"] == file_id
    assert f3["path"] == "themes/dark/new_name.css"


@pytest.mark.asyncio
async def test_code_file_delete_and_safety_checks():
    """Verify safe delete_file operation and active reference protection."""
    p = await ProjectService.create_project(name="Code Project Delete", aspect_ratio="9:16")

    # Add a file
    res1 = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=1,
        operation_type="create_file",
        payload={
            "path": "unused.js",
            "content": "// unused",
        },
    )
    fid = res1["document"]["code"]["files"][0]["id"]

    # Delete unused file
    res2 = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=2,
        operation_type="delete_file",
        payload={"id": fid},
    )
    assert res2["revision"] == 3
    assert len(res2["document"]["code"]["files"]) == 0

    # Add a file referenced by a clip
    res3 = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=3,
        operation_type="create_file",
        payload={
            "path": "referenced.css",
            "content": "/* ref */",
        },
    )
    fid2 = res3["document"]["code"]["files"][0]["id"]

    # Add clip referencing file path
    res4 = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=4,
        operation_type="add_clip",
        payload={
            "track_id": "track_video_main",
            "clip": {
                "id": "clip_ref",
                "type": "video",
                "file": "referenced.css",
                "start_seconds": 0.0,
                "duration_seconds": 4.0,
            },
        },
    )
    assert res4["revision"] == 5

    # Attempt to delete referenced file without force -> should raise ProjectError
    with pytest.raises(ProjectError) as exc_info:
        await ProjectService.apply_operation(
            project_id=p.id,
            expected_revision=5,
            operation_type="delete_file",
            payload={"id": fid2},
        )
    assert "referenced by active clip" in str(exc_info.value)

    # Delete with force=True -> succeeds
    res6 = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=5,
        operation_type="delete_file",
        payload={"id": fid2, "force": True},
    )
    assert res6["revision"] == 6
    assert len(res6["document"]["code"]["files"]) == 0


@pytest.mark.asyncio
async def test_code_file_path_safety_and_traversal_rejection():
    """Verify rejection of directory traversal, drive letters, and invalid path syntax."""
    p = await ProjectService.create_project(name="Path Safety", aspect_ratio="9:16")

    # Directory traversal
    with pytest.raises(ProjectError) as exc1:
        await ProjectService.apply_operation(
            project_id=p.id,
            expected_revision=1,
            operation_type="create_file",
            payload={"path": "../secret.js", "content": ""},
        )
    assert "Directory traversal" in str(exc1.value)

    # Absolute path
    with pytest.raises(ProjectError) as exc2:
        await ProjectService.apply_operation(
            project_id=p.id,
            expected_revision=1,
            operation_type="create_file",
            payload={"path": "/etc/passwd", "content": ""},
        )
    assert "Absolute paths" in str(exc2.value)

    # Drive letter path
    with pytest.raises(ProjectError) as exc3:
        await ProjectService.apply_operation(
            project_id=p.id,
            expected_revision=1,
            operation_type="create_file",
            payload={"path": "C:/Windows/cmd.exe", "content": ""},
        )
    assert "Drive letter" in str(exc3.value)


@pytest.mark.asyncio
async def test_code_file_json_validation():
    """Verify validation of JSON content on create_file and update_file."""
    p = await ProjectService.create_project(name="JSON Validation", aspect_ratio="9:16")

    # Valid JSON
    res1 = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=1,
        operation_type="create_file",
        payload={"path": "config.json", "content": '{"theme": "dark", "speed": 1.5}'},
    )
    assert res1["revision"] == 2

    # Invalid JSON on create -> rejected
    with pytest.raises(ProjectError) as exc:
        await ProjectService.apply_operation(
            project_id=p.id,
            expected_revision=2,
            operation_type="create_file",
            payload={"path": "bad.json", "content": '{ bad_json: unquoted }'},
        )
    assert "Invalid JSON content" in str(exc.value)


@pytest.mark.asyncio
async def test_code_edits_affect_preview_and_render_staging(tmp_path: Path):
    """Verify code files are compiled into preview HTML and staged in isolated render directories."""
    p = await ProjectService.create_project(name="Preview Code Render", aspect_ratio="9:16")

    # 1. Add CSS and HTML code files
    await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=1,
        operation_type="create_file",
        payload={
            "path": "styles/neon.css",
            "content": "#neon-title { color: #f43f5e; text-shadow: 0 0 10px #f43f5e; }",
        },
    )
    res2 = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=2,
        operation_type="create_file",
        payload={
            "path": "components/overlay.html",
            "content": '<div id="neon-title">VIRAL NEON FLASH</div>',
        },
    )

    doc = res2["document"]
    html = HyperFramesAdapter.project_doc_to_html(doc)

    # Assert CSS and HTML are compiled into stage
    assert "#neon-title { color: #f43f5e;" in html
    assert '<div id="neon-title">VIRAL NEON FLASH</div>' in html

    # Assert render staging copies physical files into render directory
    render_dir = tmp_path / "test_render_staging"
    rev, staged_path = await HyperFramesAdapter.stage_project_for_render(p.id, revision=3, dest_dir=render_dir)
    assert rev == 3
    assert (staged_path / "index.html").is_file()
    assert (staged_path / "styles" / "neon.css").is_file()
    assert (staged_path / "components" / "overlay.html").is_file()
    assert (staged_path / "styles" / "neon.css").read_text(encoding="utf-8") == "#neon-title { color: #f43f5e; text-shadow: 0 0 10px #f43f5e; }"


@pytest.mark.asyncio
async def test_block_instance_code_override_isolation():
    """Verify per-instance code overrides affect only the targeted block without mutating registry source."""
    from backend.services.registry_adapter import RegistryAdapter

    p = await ProjectService.create_project(name="Block Override Test", aspect_ratio="9:16")

    # Add block instance
    res1 = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=1,
        operation_type="add_block",
        payload={
            "block_id": "weight-wave",
            "start_seconds": 0.0,
            "duration_seconds": 4.0,
        },
    )
    block_clip = next(
        (c for t in res1["document"]["timeline"]["tracks"] for c in t.get("clips", []) if c.get("type") == "block"),
        None,
    )
    assert block_clip is not None
    cid = block_clip["id"]

    # Read original immutable block source
    orig_source = RegistryAdapter.read_block_source("weight-wave")
    assert orig_source["read_only"] is True
    assert "data-composition-id" in orig_source["content"]

    # Create project-owned code override targeting this block instance
    custom_override_content = """<!DOCTYPE html>
<html>
<head><title>Custom Weight Wave</title></head>
<body>
  <div data-composition-id="custom_override" id="ww-root">
    <h1 id="ww-line">CUSTOM OVERRIDE TEXT</h1>
  </div>
</body>
</html>"""

    res2 = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=2,
        operation_type="create_file",
        payload={
            "path": f"compositions/{cid}.html",
            "clip_id": cid,
            "content": custom_override_content,
        },
    )
    assert res2["revision"] == 3

    # Sync to studio and verify staged composition HTML contains the override
    sync_res = await HyperFramesAdapter.sync_project_to_studio(p.id)
    comp_file = Path(sync_res["html_path"]).parent / "compositions" / f"{cid}.html"
    assert comp_file.is_file()
    content = comp_file.read_text(encoding="utf-8")
    assert "CUSTOM OVERRIDE TEXT" in content

    # Verify original registry snapshot remains intact and unmodified
    orig_re_read = RegistryAdapter.read_block_source("weight-wave")
    assert "CUSTOM OVERRIDE TEXT" not in orig_re_read["content"]
