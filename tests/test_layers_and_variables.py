# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Focused tests for Layers + Variables (Phase 8).
Verifies:
- canonical timeline.tracks[].clips[] projection (no parallel layers[] document)
- stable clip IDs
- durable visibility and lock enforcement
- reorder, group, ungroup, rename
- CAS conflict rejection on stale reorder and variable writes
- variable validation (numeric bounds, boolean, enum)
- instance isolation between identical blocks
- backward compatibility with existing schema_version 2 projects
"""
import copy
import pytest
from backend.database import init_db
from backend.services.project_service import ProjectService
from backend.services.hyperframes_adapter import HyperFramesAdapter
from backend.core.exceptions import RevisionConflictError, ProjectError


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.mark.asyncio
async def test_layers_projection_and_stable_identity():
    """Verify Layers projects directly from timeline.tracks[].clips[] with stable IDs."""
    p = await ProjectService.create_project(name="Layers Identity Test")
    
    # 1. Add video clip
    res1 = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=1,
        operation_type="add_clip",
        payload={
            "track_id": "track_video_main",
            "clip": {"id": "elem_video_1", "start_seconds": 0.0, "duration_seconds": 5.0, "title": "Main Video"}
        }
    )
    assert res1["applied"] is True
    assert res1["revision"] == 2
    
    # 2. Add HyperFrames block
    res2 = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=2,
        operation_type="add_block",
        payload={
            "block_id": "lower-third-modern",
            "instance_id": "elem_block_1",
            "title": "Lower Third Modern",
            "start_seconds": 1.0,
            "duration_seconds": 4.0,
            "variables": {"name": "Alice", "title": "Lead Engineer"}
        }
    )
    assert res2["applied"] is True
    assert res2["revision"] == 3

    doc = res2["document"]
    # Verify no parallel 'layers' key was created (Architectural Invariant)
    assert "layers" not in doc

    clips = [c for t in doc["timeline"]["tracks"] for c in t.get("clips", [])]
    assert len(clips) == 2
    
    c_vid = next(c for c in clips if c["id"] == "elem_video_1")
    c_blk = next(c for c in clips if c["id"] == "elem_block_1")
    
    # Check stable fields and defaults
    assert c_vid["visible"] is True
    assert c_vid["locked"] is False
    assert c_vid["parent_id"] is None
    assert c_vid["layer_order"] == 0

    assert c_blk["visible"] is True
    assert c_blk["locked"] is False
    assert c_blk["parent_id"] is None
    assert c_blk["layer_order"] == 1


@pytest.mark.asyncio
async def test_visibility_persistence_and_render_projection():
    """Verify durable visibility toggles and its effect on HyperFrames HTML preview/render."""
    p = await ProjectService.create_project(name="Visibility Test")
    await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=1,
        operation_type="add_clip",
        payload={"track_id": "track_video_main", "clip": {"id": "c_vis_1", "title": "Hero Video", "duration_seconds": 5.0}}
    )
    
    # Check visible in HTML
    doc_rev2 = await ProjectService.get_revision_snapshot(p.id, 2)
    html_rev2 = HyperFramesAdapter.project_doc_to_html(doc_rev2)
    assert 'id="c_vis_1"' in html_rev2
    assert 'data-hf-id="c_vis_1"' in html_rev2

    # Hide element via typed operation
    res_hide = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=2,
        operation_type="set_element_visibility",
        payload={"clip_id": "c_vis_1", "visible": False}
    )
    assert res_hide["revision"] == 3
    doc_rev3 = res_hide["document"]
    clip_doc = next(c for t in doc_rev3["timeline"]["tracks"] for c in t["clips"] if c["id"] == "c_vis_1")
    assert clip_doc["visible"] is False

    # Check hidden element is absent from HTML preview/render
    html_rev3 = HyperFramesAdapter.project_doc_to_html(doc_rev3)
    assert 'id="c_vis_1"' not in html_rev3
    assert 'data-hf-id="c_vis_1"' not in html_rev3

    # Show element again
    res_show = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=3,
        operation_type="set_element_visibility",
        payload={"clip_id": "c_vis_1", "visible": True}
    )
    assert res_show["revision"] == 4
    html_rev4 = HyperFramesAdapter.project_doc_to_html(res_show["document"])
    assert 'id="c_vis_1"' in html_rev4


@pytest.mark.asyncio
async def test_lock_enforcement_backend():
    """Verify ProjectService rejects mutations to locked elements."""
    p = await ProjectService.create_project(name="Lock Test")
    await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=1,
        operation_type="add_block",
        payload={
            "block_id": "lower-third-modern",
            "instance_id": "blk_lock_1",
            "variables": {"name": "Bob"}
        }
    )
    
    # Lock element
    res_lock = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=2,
        operation_type="set_element_lock",
        payload={"clip_id": "blk_lock_1", "locked": True}
    )
    assert res_lock["revision"] == 3
    locked_clip = next(c for t in res_lock["document"]["timeline"]["tracks"] for c in t["clips"] if c["id"] == "blk_lock_1")
    assert locked_clip["locked"] is True

    # Attempt forbidden mutations while locked:
    # 1. Update variables -> rejected
    with pytest.raises(ProjectError) as exc_v:
        await ProjectService.apply_operation(
            project_id=p.id,
            expected_revision=3,
            operation_type="update_block_variables",
            payload={"clip_id": "blk_lock_1", "variables": {"name": "Charlie"}}
        )
    assert "locked element" in str(exc_v.value).lower()

    # 2. Rename -> rejected
    with pytest.raises(ProjectError) as exc_r:
        await ProjectService.apply_operation(
            project_id=p.id,
            expected_revision=3,
            operation_type="rename_element",
            payload={"clip_id": "blk_lock_1", "name": "New Name"}
        )
    assert "locked element" in str(exc_r.value).lower()

    # 3. Reorder -> rejected
    with pytest.raises(ProjectError) as exc_o:
        await ProjectService.apply_operation(
            project_id=p.id,
            expected_revision=3,
            operation_type="reorder_layer",
            payload={"clip_id": "blk_lock_1", "layer_order": 99}
        )
    assert "locked element" in str(exc_o.value).lower()

    # 4. Remove -> rejected
    with pytest.raises(ProjectError) as exc_d:
        await ProjectService.apply_operation(
            project_id=p.id,
            expected_revision=3,
            operation_type="remove_clip",
            payload={"clip_id": "blk_lock_1"}
        )
    assert "locked element" in str(exc_d.value).lower()

    # Unlock element
    res_unlock = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=3,
        operation_type="set_element_lock",
        payload={"clip_id": "blk_lock_1", "locked": False}
    )
    assert res_unlock["revision"] == 4
    
    # Now mutation succeeds
    res_mutate = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=4,
        operation_type="rename_element",
        payload={"clip_id": "blk_lock_1", "name": "Unlocked Bob"}
    )
    assert res_mutate["revision"] == 5
    renamed = next(c for t in res_mutate["document"]["timeline"]["tracks"] for c in t["clips"] if c["id"] == "blk_lock_1")
    assert renamed["name"] == "Unlocked Bob"


@pytest.mark.asyncio
async def test_reorder_group_and_ungroup():
    """Verify layer reordering, grouping into structural container, and ungrouping."""
    p = await ProjectService.create_project(name="Hierarchy Test")
    
    # Add 3 elements
    await ProjectService.apply_operation(
        project_id=p.id, expected_revision=1, operation_type="add_clip",
        payload={"track_id": "t1", "clip": {"id": "c1", "title": "Base", "duration_seconds": 5.0}}
    )
    await ProjectService.apply_operation(
        project_id=p.id, expected_revision=2, operation_type="add_clip",
        payload={"track_id": "t1", "clip": {"id": "c2", "title": "Mid", "duration_seconds": 5.0}}
    )
    await ProjectService.apply_operation(
        project_id=p.id, expected_revision=3, operation_type="add_clip",
        payload={"track_id": "t1", "clip": {"id": "c3", "title": "Top", "duration_seconds": 5.0}}
    )

    # Reorder c1 to top (layer_order 10)
    res_reorder = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=4,
        operation_type="reorder_layer",
        payload={"clip_id": "c1", "layer_order": 10}
    )
    assert res_reorder["revision"] == 5
    clips = [c for t in res_reorder["document"]["timeline"]["tracks"] for c in t["clips"]]
    c1 = next(c for c in clips if c["id"] == "c1")
    assert c1["layer_order"] == 10

    # Group c2 and c3 into "Overlay Group"
    res_group = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=5,
        operation_type="group_elements",
        payload={"clip_ids": ["c2", "c3"], "group_name": "Overlay Group", "group_id": "grp_overlay"}
    )
    assert res_group["revision"] == 6
    doc_grp = res_group["document"]
    all_clips = [c for t in doc_grp["timeline"]["tracks"] for c in t["clips"]]
    
    grp = next((c for c in all_clips if c["id"] == "grp_overlay"), None)
    assert grp is not None
    assert grp["type"] == "group"
    assert grp["title"] == "Overlay Group"

    c2 = next(c for c in all_clips if c["id"] == "c2")
    c3 = next(c for c in all_clips if c["id"] == "c3")
    assert c2["parent_id"] == "grp_overlay"
    assert c3["parent_id"] == "grp_overlay"

    # HTML verification: group structural container does not produce DOM element, but children are ordered
    html = HyperFramesAdapter.project_doc_to_html(doc_grp)
    assert 'id="grp_overlay"' not in html
    assert 'id="c2"' in html
    assert 'id="c3"' in html

    # Ungroup Overlay Group
    res_ungroup = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=6,
        operation_type="ungroup_elements",
        payload={"group_id": "grp_overlay"}
    )
    assert res_ungroup["revision"] == 7
    doc_ungrp = res_ungroup["document"]
    remaining_clips = [c for t in doc_ungrp["timeline"]["tracks"] for c in t["clips"]]
    assert not any(c["id"] == "grp_overlay" for c in remaining_clips)
    
    # Children survived with parent_id cleared to None
    c2_after = next(c for c in remaining_clips if c["id"] == "c2")
    c3_after = next(c for c in remaining_clips if c["id"] == "c3")
    assert c2_after["parent_id"] is None
    assert c3_after["parent_id"] is None


@pytest.mark.asyncio
async def test_cas_conflict_rejection_on_stale_reorder_and_variables():
    """Verify optimistic CAS concurrency prevents dirty writes on layers reorder and variables."""
    p = await ProjectService.create_project(name="CAS Layers Conflict Test")
    await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=1,
        operation_type="add_block",
        payload={"block_id": "lower-third-modern", "instance_id": "b1", "variables": {"name": "Initial"}}
    )
    
    # Concurrently advance project to revision 3
    await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=2,
        operation_type="rename_element",
        payload={"clip_id": "b1", "name": "Concurrent Edit"}
    )

    # Attempt reorder with stale expected_revision=2 -> 409 Conflict
    with pytest.raises(RevisionConflictError) as exc_reorder:
        await ProjectService.apply_operation(
            project_id=p.id,
            expected_revision=2,
            operation_type="reorder_layer",
            payload={"clip_id": "b1", "layer_order": 5}
        )
    assert exc_reorder.value.current_revision == 3
    assert exc_reorder.value.expected_revision == 2

    # Attempt variable update with stale expected_revision=2 -> 409 Conflict
    with pytest.raises(RevisionConflictError) as exc_var:
        await ProjectService.apply_operation(
            project_id=p.id,
            expected_revision=2,
            operation_type="update_block_variables",
            payload={"clip_id": "b1", "variables": {"name": "Stale Write"}}
        )
    assert exc_var.value.current_revision == 3
    assert exc_var.value.expected_revision == 2


@pytest.mark.asyncio
async def test_variable_validation_and_instance_isolation():
    """Verify typed variable validation and isolation between multiple instances of the same block."""
    p = await ProjectService.create_project(name="Variables Isolation Test")
    
    # Add Instance A
    await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=1,
        operation_type="add_block",
        payload={
            "block_id": "lower-third-modern",
            "instance_id": "inst_A",
            "variables": {"name": "ALICE", "title": "Developer"}
        }
    )
    
    # Add Instance B (same block_id)
    await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=2,
        operation_type="add_block",
        payload={
            "block_id": "lower-third-modern",
            "instance_id": "inst_B",
            "variables": {"name": "BOB", "title": "Designer"}
        }
    )

    # Mutate Instance A variables
    res_a = await ProjectService.apply_operation(
        project_id=p.id,
        expected_revision=3,
        operation_type="update_block_variables",
        payload={"clip_id": "inst_A", "variables": {"name": "ALICE UPDATED"}}
    )
    assert res_a["revision"] == 4
    
    clips = [c for t in res_a["document"]["timeline"]["tracks"] for c in t["clips"]]
    clip_a = next(c for c in clips if c["id"] == "inst_A")
    clip_b = next(c for c in clips if c["id"] == "inst_B")

    # Instance A has new name, Instance B remains strictly unchanged
    assert clip_a["variables"]["name"] == "ALICE UPDATED"
    assert clip_b["variables"]["name"] == "BOB"
    assert clip_b["variables"]["title"] == "Designer"


@pytest.mark.asyncio
async def test_backward_compatibility_schema_version_2():
    """Verify legacy schema_version 2 projects without layer metadata receive safe defaults on migration."""
    legacy_doc = {
        "schema_version": 2,
        "timeline": {
            "fps": 30,
            "duration_seconds": 10.0,
            "tracks": [
                {
                    "id": "track_video_main",
                    "type": "video",
                    "clips": [
                        {"id": "legacy_c1", "duration_seconds": 5.0},
                        {"id": "legacy_c2", "duration_seconds": 5.0},
                    ]
                }
            ]
        }
    }
    migrated = ProjectService.migrate_project_document(copy.deepcopy(legacy_doc))
    clips = migrated["timeline"]["tracks"][0]["clips"]
    
    assert clips[0]["visible"] is True
    assert clips[0]["locked"] is False
    assert clips[0]["parent_id"] is None
    assert clips[0]["layer_order"] == 0

    assert clips[1]["visible"] is True
    assert clips[1]["locked"] is False
    assert clips[1]["parent_id"] is None
    assert clips[1]["layer_order"] == 1


@pytest.mark.asyncio
async def test_variable_schema_validation_numeric_bounds_and_enum(monkeypatch):
    """Verify typed variable validation catches invalid bounds, non-numbers, and invalid enums."""
    from backend.services.registry_adapter import RegistryAdapter

    mock_item = {
        "id": "mock-test-block",
        "variables": [
            {"id": "font_size", "type": "number", "min": 12, "max": 72, "default": 24},
            {"id": "show_badge", "type": "boolean", "default": True},
            {"id": "theme", "type": "enum", "options": ["dark", "light", "neon"], "default": "dark"},
        ]
    }
    monkeypatch.setattr(RegistryAdapter, "get_catalog_item", lambda block_id: mock_item if block_id == "mock-test-block" else None)

    # Valid values pass
    ProjectService.validate_block_variables("mock-test-block", {
        "font_size": 32,
        "show_badge": False,
        "theme": "neon",
    })

    # Numeric below min -> ProjectError
    with pytest.raises(ProjectError) as exc_min:
        ProjectService.validate_block_variables("mock-test-block", {"font_size": 8})
    assert "below minimum" in str(exc_min.value)

    # Numeric above max -> ProjectError
    with pytest.raises(ProjectError) as exc_max:
        ProjectService.validate_block_variables("mock-test-block", {"font_size": 120})
    assert "above maximum" in str(exc_max.value)

    # Non-numeric string -> ProjectError
    with pytest.raises(ProjectError) as exc_num:
        ProjectService.validate_block_variables("mock-test-block", {"font_size": "not_a_number"})
    assert "must be numeric" in str(exc_num.value)

    # Invalid enum option -> ProjectError
    with pytest.raises(ProjectError) as exc_enum:
        ProjectService.validate_block_variables("mock-test-block", {"theme": "invalid_theme"})
    assert "not in options" in str(exc_enum.value)

    # Invalid boolean -> ProjectError
    with pytest.raises(ProjectError) as exc_bool:
        ProjectService.validate_block_variables("mock-test-block", {"show_badge": "invalid_bool_val"})
    assert "must be boolean" in str(exc_bool.value)

