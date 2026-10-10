# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for professional timeline operations and GSAP keyframe projection."""
import pytest
import asyncio
from uuid import uuid4

from backend.services.project_service import ProjectService
from backend.services.hyperframes_adapter import HyperFramesAdapter
import json
from backend.database import init_db
from backend.models.project import default_empty_document


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.mark.asyncio
async def test_duplicate_clip_operation():
    """Verify duplicate_clip creates unique cloned clip with offset start time."""
    doc = json.loads(default_empty_document("Test Project"))
    clip = {
        "id": "clip_orig_123",
        "type": "video",
        "title": "Main Clip",
        "start_seconds": 2.0,
        "duration_seconds": 4.0,
        "asset_file": "sample.mp4",
        "trim_start": 0.0,
        "trim_end": 4.0,
    }
    doc["timeline"]["tracks"][0]["clips"].append(clip)

    project = await ProjectService.create_project(name="Dup Test", initial_document=doc)
    project_id = project.id
    rev = project.revision

    # Duplicate clip
    res = await ProjectService.apply_operation(
        project_id=project_id,
        expected_revision=rev,
        operation_type="duplicate_clip",
        payload={"clip_id": "clip_orig_123", "offset_seconds": 4.0},
    )
    new_doc = res["document"]
    clips = new_doc["timeline"]["tracks"][0]["clips"]
    assert len(clips) == 2
    cloned = clips[1]
    assert cloned["id"] != "clip_orig_123"
    assert cloned["id"].startswith("clip_")
    assert cloned["title"] == "Main Clip"
    assert cloned["start_seconds"] == 6.0
    assert cloned["duration_seconds"] == 4.0
    assert cloned["asset_file"] == "sample.mp4"


@pytest.mark.asyncio
async def test_split_clip_operation():
    """Verify split_clip splits clip into two continuous pieces with correct trims."""
    doc = json.loads(default_empty_document("Test Split Project"))
    clip = {
        "id": "clip_to_split",
        "type": "video",
        "title": "To Split",
        "start_seconds": 1.0,
        "duration_seconds": 6.0,
        "asset_file": "clip.mp4",
        "trim_start": 2.0,
        "trim_end": 8.0,
    }
    doc["timeline"]["tracks"][0]["clips"].append(clip)

    project = await ProjectService.create_project(name="Split Test", initial_document=doc)
    project_id = project.id
    rev = project.revision

    # Split clip at 3.0s (2.0s into the clip)
    res = await ProjectService.apply_operation(
        project_id=project_id,
        expected_revision=rev,
        operation_type="split_clip",
        payload={"clip_id": "clip_to_split", "split_time": 3.0},
    )
    new_doc = res["document"]
    clips = new_doc["timeline"]["tracks"][0]["clips"]
    assert len(clips) == 2

    part1 = next(c for c in clips if c["id"] == "clip_to_split")
    part2 = next(c for c in clips if c["id"] != "clip_to_split")

    assert part1["start_seconds"] == 1.0
    assert part1["duration_seconds"] == 2.0  # 3.0 - 1.0
    assert part1["trim_start"] == 2.0
    assert part1["trim_end"] == 4.0  # 2.0 + 2.0

    assert part2["start_seconds"] == 3.0
    assert part2["duration_seconds"] == 4.0  # 7.0 - 3.0
    assert part2["trim_start"] == 4.0
    assert part2["trim_end"] == 8.0


@pytest.mark.asyncio
async def test_keyframe_crud_operations():
    """Verify add_keyframe, update_keyframe, and remove_keyframe operations."""
    doc = json.loads(default_empty_document("Keyframe Test"))
    clip = {
        "id": "clip_animated",
        "type": "video",
        "title": "Animated Video",
        "start_seconds": 0.0,
        "duration_seconds": 5.0,
    }
    doc["timeline"]["tracks"][0]["clips"].append(clip)

    project = await ProjectService.create_project(name="KF Test", initial_document=doc)
    project_id = project.id
    rev = project.revision

    # 1. Add keyframe 1: opacity at 0.0s = 0.0
    res1 = await ProjectService.apply_operation(
        project_id=project_id,
        expected_revision=rev,
        operation_type="add_keyframe",
        payload={
            "clip_id": "clip_animated",
            "keyframe": {"property": "opacity", "time": 0.0, "value": 0.0, "ease": "none"},
        },
    )
    rev = res1["revision"]

    # 2. Add keyframe 2: opacity at 1.0s = 1.0
    res2 = await ProjectService.apply_operation(
        project_id=project_id,
        expected_revision=rev,
        operation_type="add_keyframe",
        payload={
            "clip_id": "clip_animated",
            "keyframe": {"property": "opacity", "time": 1.0, "value": 1.0, "ease": "power2.out"},
        },
    )
    rev = res2["revision"]

    # 3. Add keyframe 3: scale at 0.5s = 1.2
    res3 = await ProjectService.apply_operation(
        project_id=project_id,
        expected_revision=rev,
        operation_type="add_keyframe",
        payload={
            "clip_id": "clip_animated",
            "keyframe": {"property": "scale", "time": 0.5, "value": 1.2, "ease": "back.out"},
        },
    )
    rev = res3["revision"]
    clip_data = res3["document"]["timeline"]["tracks"][0]["clips"][0]
    assert len(clip_data["animations"]) == 3

    # 4. Update keyframe 2: change value to 0.8
    res4 = await ProjectService.apply_operation(
        project_id=project_id,
        expected_revision=rev,
        operation_type="update_keyframe",
        payload={
            "clip_id": "clip_animated",
            "property": "opacity",
            "time": 1.0,
            "patch": {"value": 0.8},
        },
    )
    rev = res4["revision"]
    clip_data = res4["document"]["timeline"]["tracks"][0]["clips"][0]
    op1 = next(a for a in clip_data["animations"] if a["property"] == "opacity" and a["time"] == 1.0)
    assert op1["value"] == 0.8

    # 5. Remove scale keyframe
    res5 = await ProjectService.apply_operation(
        project_id=project_id,
        expected_revision=rev,
        operation_type="remove_keyframe",
        payload={
            "clip_id": "clip_animated",
            "property": "scale",
            "time": 0.5,
        },
    )
    clip_data = res5["document"]["timeline"]["tracks"][0]["clips"][0]
    assert len(clip_data["animations"]) == 2
    assert all(a["property"] == "opacity" for a in clip_data["animations"])


@pytest.mark.asyncio
async def test_update_track_state():
    """Verify update_track_state mutates muted, locked, visible, collapsed flags."""
    doc = json.loads(default_empty_document("Track State Test"))
    track_id = doc["timeline"]["tracks"][0]["id"]

    project = await ProjectService.create_project(name="Track Test", initial_document=doc)
    project_id = project.id
    rev = project.revision

    res = await ProjectService.apply_operation(
        project_id=project_id,
        expected_revision=rev,
        operation_type="update_track_state",
        payload={
            "track_id": track_id,
            "patch": {"muted": True, "locked": True, "visible": False, "collapsed": True},
        },
    )
    track = res["document"]["timeline"]["tracks"][0]
    assert track["muted"] is True
    assert track["locked"] is True
    assert track["visible"] is False
    assert track["collapsed"] is True


def test_gsap_keyframe_projection():
    """Verify HyperFramesAdapter generates valid GSAP tweens from clip animations."""
    doc = json.loads(default_empty_document("GSAP Test"))
    doc["timeline"]["duration_seconds"] = 10.0
    clip = {
        "id": "clip_hero",
        "type": "video",
        "start_seconds": 1.0,
        "duration_seconds": 5.0,
        "asset_file": "hero.mp4",
        "animations": [
            {"property": "opacity", "time": 0.0, "value": 0.0},
            {"property": "opacity", "time": 1.5, "value": 1.0, "ease": "power2.out"},
            {"property": "scale", "time": 0.0, "value": 0.8},
            {"property": "scale", "time": 2.0, "value": 1.1, "ease": "elastic.out"},
        ]
    }
    doc["timeline"]["tracks"][0]["clips"].append(clip)

    html = HyperFramesAdapter.project_doc_to_html(doc)
    assert 'tl.set("#clip_hero", { opacity: 0.0 }, 1.0);' in html
    assert 'tl.to("#clip_hero", { opacity: 1.0, duration: 1.5, ease: "power2.out" }, 1.0);' in html
    assert 'tl.set("#clip_hero", { scale: 0.8 }, 1.0);' in html
    assert 'tl.to("#clip_hero", { scale: 1.1, duration: 2.0, ease: "elastic.out" }, 1.0);' in html
    assert 'id="clip_hero"' in html
