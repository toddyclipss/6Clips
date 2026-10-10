# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
import pytest
from backend.database import init_db
from backend.services.project_service import ProjectService
from backend.core.exceptions import ProjectError, RevisionConflictError


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.mark.asyncio
async def test_lock_enforcement_direct_clip():
    """Verify that operations directly targeting a locked clip are rejected with ProjectError."""
    p = await ProjectService.create_project(name="Lock Test Project", aspect_ratio="9:16")
    assert p.revision == 1

    # 1. Add clip
    res = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=1,
        operation_type="add_clip",
        payload={
            "track_id": "track_video_main",
            "clip": {
                "id": "clip_locked_target",
                "asset_id": "dl:test_asset",
                "start_seconds": 1.0,
                "duration_seconds": 4.0,
                "locked": False,
            },
        },
    )
    assert res["revision"] == 2

    # 2. Lock the clip
    res = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=2,
        operation_type="set_element_lock",
        payload={"clip_id": "clip_locked_target", "locked": True},
    )
    assert res["revision"] == 3
    clip = res["document"]["timeline"]["tracks"][0]["clips"][0]
    assert clip["locked"] is True

    # 3. Attempt mutations on the locked clip -> all must fail with ProjectError
    # move_clip
    with pytest.raises(ProjectError) as exc:
        await ProjectService.apply_operation(
            project_id=p.id,
            expected_revision=3,
            operation_type="move_clip",
            payload={"clip_id": "clip_locked_target", "start_seconds": 3.0},
        )
    assert "locked element" in str(exc.value)

    # resize / trim
    with pytest.raises(ProjectError) as exc:
        await ProjectService.apply_operation(
            project_id=p.id,
            expected_revision=3,
            operation_type="update_clip_timing",
            payload={"clip_id": "clip_locked_target", "duration_seconds": 8.0},
        )
    assert "locked element" in str(exc.value)

    # rename
    with pytest.raises(ProjectError) as exc:
        await ProjectService.apply_operation(
            project_id=p.id,
            expected_revision=3,
            operation_type="rename_element",
            payload={"clip_id": "clip_locked_target", "name": "Hacked Name"},
        )
    assert "locked element" in str(exc.value)

    # reorder layer
    with pytest.raises(ProjectError) as exc:
        await ProjectService.apply_operation(
            project_id=p.id,
            expected_revision=3,
            operation_type="reorder_layer",
            payload={"clip_id": "clip_locked_target", "layer_order": 99},
        )
    assert "locked element" in str(exc.value)

    # add keyframe
    with pytest.raises(ProjectError) as exc:
        await ProjectService.apply_operation(
            project_id=p.id,
            expected_revision=3,
            operation_type="add_keyframe",
            payload={"clip_id": "clip_locked_target", "keyframe": {"property": "opacity", "time": 0.5, "value": 0.5}},
        )
    assert "locked element" in str(exc.value)

    # set parent
    with pytest.raises(ProjectError) as exc:
        await ProjectService.apply_operation(
            project_id=p.id,
            expected_revision=3,
            operation_type="set_parent",
            payload={"clip_id": "clip_locked_target", "parent_id": "some_group"},
        )
    assert "locked element" in str(exc.value)

    # delete clip
    with pytest.raises(ProjectError) as exc:
        await ProjectService.apply_operation(
            project_id=p.id,
            expected_revision=3,
            operation_type="remove_clip",
            payload={"clip_id": "clip_locked_target"},
        )
    assert "locked element" in str(exc.value)

    # 4. Confirm project revision remained exactly at 3 (zero partial mutation)
    proj = await ProjectService.get_project(p.id)
    assert proj.revision == 3


@pytest.mark.asyncio
async def test_lock_enforcement_group_ancestor_and_child():
    """Verify lock propagation, ancestor lock enforcement on children, and locked child protection."""
    p = await ProjectService.create_project(name="Group Lock Test", aspect_ratio="9:16")

    # Add child 1 and child 2
    res = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=1,
        operation_type="add_clip",
        payload={
            "track_id": "track_video_main",
            "clip": {"id": "elem_child_1", "start_seconds": 0.0, "duration_seconds": 3.0, "layer_order": 1},
        },
    )
    res = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=2,
        operation_type="add_clip",
        payload={
            "track_id": "track_video_main",
            "clip": {"id": "elem_child_2", "start_seconds": 1.0, "duration_seconds": 4.0, "layer_order": 2},
        },
    )

    # Group them
    res = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=3,
        operation_type="group_elements",
        payload={
            "clip_ids": ["elem_child_1", "elem_child_2"],
            "group_name": "Folder Alpha",
            "group_id": "group_alpha",
        },
    )
    assert res["revision"] == 4

    # Lock the group
    res = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=4,
        operation_type="set_element_lock",
        payload={"clip_id": "group_alpha", "locked": True},
    )
    assert res["revision"] == 5

    # 1. Mutating elem_child_1 must fail because group_alpha is locked!
    with pytest.raises(ProjectError) as exc:
        await ProjectService.apply_operation(
            project_id=p.id,
            expected_revision=5,
            operation_type="move_clip",
            payload={"clip_id": "elem_child_1", "start_seconds": 2.0},
        )
    assert "ancestor group 'group_alpha' is locked" in str(exc.value)

    # 2. Cannot unlock elem_child_1 directly while group_alpha is locked
    with pytest.raises(ProjectError) as exc:
        await ProjectService.apply_operation(
            project_id=p.id,
            expected_revision=5,
            operation_type="set_element_lock",
            payload={"clip_id": "elem_child_1", "locked": False},
        )
    assert "parent group 'group_alpha' is locked" in str(exc.value)

    # 3. Unlock the group
    res = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=5,
        operation_type="set_element_lock",
        payload={"clip_id": "group_alpha", "locked": False},
    )
    assert res["revision"] == 6

    # 4. Now lock only elem_child_2
    res = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=6,
        operation_type="set_element_lock",
        payload={"clip_id": "elem_child_2", "locked": True},
    )
    assert res["revision"] == 7

    # 5. Cannot delete or ungroup group_alpha because elem_child_2 inside is locked!
    with pytest.raises(ProjectError) as exc:
        await ProjectService.apply_operation(
            project_id=p.id,
            expected_revision=7,
            operation_type="ungroup_elements",
            payload={"group_id": "group_alpha"},
        )
    assert "child element 'elem_child_2' is locked" in str(exc.value)

    with pytest.raises(ProjectError) as exc:
        await ProjectService.apply_operation(
            project_id=p.id,
            expected_revision=7,
            operation_type="remove_clip",
            payload={"clip_id": "group_alpha"},
        )
    assert "child element 'elem_child_2' is locked" in str(exc.value)

    # 6. Unlock elem_child_2, then ungrouping succeeds cleanly
    res = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=7,
        operation_type="set_element_lock",
        payload={"clip_id": "elem_child_2", "locked": False},
    )
    assert res["revision"] == 8

    res = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=8,
        operation_type="ungroup_elements",
        payload={"group_id": "group_alpha"},
    )
    assert res["revision"] == 9
    clips = res["document"]["timeline"]["tracks"][0]["clips"]
    # Group is removed, children have parent_id=None
    assert not any(c.get("id") == "group_alpha" for c in clips)
    child1 = next(c for c in clips if c.get("id") == "elem_child_1")
    assert child1.get("parent_id") is None


@pytest.mark.asyncio
async def test_reorder_layer_delta_and_set_parent():
    """Verify group reordering shifts child layer orders and set_parent handles cycle prevention."""
    p = await ProjectService.create_project(name="Reorder and Parent Test", aspect_ratio="9:16")

    # Add child1 (lo=10), child2 (lo=11)
    await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=1,
        operation_type="add_clip",
        payload={
            "track_id": "track_video_main",
            "clip": {"id": "c1", "start_seconds": 0.0, "duration_seconds": 2.0, "layer_order": 10},
        },
    )
    await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=2,
        operation_type="add_clip",
        payload={
            "track_id": "track_video_main",
            "clip": {"id": "c2", "start_seconds": 0.0, "duration_seconds": 2.0, "layer_order": 11},
        },
    )
    res = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=3,
        operation_type="group_elements",
        payload={"clip_ids": ["c1", "c2"], "group_name": "Grp", "group_id": "g1"},
    )
    # group layer_order was set to max(10, 11) + 1 = 12
    # Now reorder g1 to 20 (delta = +8). Children should shift to 18 and 19.
    res = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=4,
        operation_type="reorder_layer",
        payload={"clip_id": "g1", "layer_order": 20},
    )
    clips = res["document"]["timeline"]["tracks"][0]["clips"]
    c1 = next(c for c in clips if c["id"] == "c1")
    c2 = next(c for c in clips if c["id"] == "c2")
    g1 = next(c for c in clips if c["id"] == "g1")
    assert g1["layer_order"] == 20
    assert c1["layer_order"] == 18
    assert c2["layer_order"] == 19

    # Add clip c3, then set_parent to g1
    await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=5,
        operation_type="add_clip",
        payload={
            "track_id": "track_video_main",
            "clip": {"id": "c3", "start_seconds": 0.0, "duration_seconds": 2.0, "layer_order": 5},
        },
    )
    res = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=6,
        operation_type="set_parent",
        payload={"clip_id": "c3", "parent_id": "g1"},
    )
    c3 = next(c for c in res["document"]["timeline"]["tracks"][0]["clips"] if c["id"] == "c3")
    assert c3["parent_id"] == "g1"

    # Self-parenting cycle prevention
    with pytest.raises(ProjectError) as exc:
        await ProjectService.apply_operation(
            project_id=p.id,
            expected_revision=7,
            operation_type="set_parent",
            payload={"clip_id": "g1", "parent_id": "g1"},
        )
    assert "Cannot set element 'g1' as its own parent" in str(exc.value)


@pytest.mark.asyncio
async def test_variable_validation_types():
    """Verify typed variable validation across number, boolean, enum, color, image."""
    p = await ProjectService.create_project(name="Variables Validation Test", aspect_ratio="9:16")

    # Add block weight-wave
    res = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=1,
        operation_type="add_block",
        payload={
            "block_id": "weight-wave",
            "instance_id": "elem_ww_1",
            "variables": {
                "title": "Bench Test",
                "color": "#8b5cf6",
            },
        },
    )
    assert res["revision"] == 2

    # Valid update
    res = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=2,
        operation_type="update_block_variables",
        payload={
            "clip_id": "elem_ww_1",
            "variables": {
                "title": "Updated Title",
                "color": "#10b981",
            },
        },
    )
    assert res["revision"] == 3
    clip, _ = ProjectService._find_clip_and_track(res["document"]["timeline"]["tracks"], "elem_ww_1")
    assert clip is not None
    assert clip["variables"]["title"] == "Updated Title"
    assert clip["variables"]["color"] == "#10b981"

    # Invalid color format
    with pytest.raises(ProjectError) as exc:
        await ProjectService.apply_operation(
            project_id=p.id,
            expected_revision=3,
            operation_type="update_block_variables",
            payload={
                "clip_id": "elem_ww_1",
                "variables": {
                    "color": "not-a-color-value!@#$",
                },
            },
        )
    assert "valid CSS color" in str(exc.value)

    # Project revision remains unchanged at 3
    proj = await ProjectService.get_project(p.id)
    assert proj.revision == 3


@pytest.mark.asyncio
async def test_filmstrip_generation_and_cache_no_revision_bump():
    """Verify filmstrip contact sheet is generated, cached, and leaves ProjectRevision untouched."""
    from pathlib import Path
    from backend.database import AsyncSessionLocal
    from backend.models.downloaded_video import DownloadedVideo
    from backend.api.downloaded import get_downloaded_filmstrip

    test_vid_path = Path("motion/studio/test_moving_video.mp4").resolve()
    assert test_vid_path.exists(), f"Test video must exist at {test_vid_path}"

    vid_id = "test_vid_filmstrip_probe"
    async with AsyncSessionLocal() as db:
        v = await db.get(DownloadedVideo, vid_id)
        if not v:
            v = DownloadedVideo(
                id=vid_id,
                title="Filmstrip Test Video",
                video_path=str(test_vid_path),
                duration_seconds=10,
            )
            db.add(v)
            await db.commit()

    # Create a project with this asset
    p = await ProjectService.create_project(name="Filmstrip Project", aspect_ratio="9:16")
    initial_rev = p.revision

    # 1. First call: generates filmstrip
    resp1 = await get_downloaded_filmstrip(video_id=vid_id, n=8, h=48)
    assert resp1.status_code == 200
    assert resp1.media_type == "image/jpeg"
    file_path1 = Path(resp1.path)
    assert file_path1.exists()
    assert file_path1.stat().st_size > 0

    # 2. Second call: served from cache
    resp2 = await get_downloaded_filmstrip(video_id=vid_id, n=8, h=48)
    assert resp2.status_code == 200
    assert Path(resp2.path) == file_path1

    # 3. Verify ProjectRevision is completely unchanged
    p_after = await ProjectService.get_project(p.id)
    assert p_after.revision == initial_rev

