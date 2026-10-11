# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Unit tests for Timeline Track Operations (add, delete, reorder, rename, move_clip compatibility)."""
import pytest
import json
from uuid import uuid4

from backend.database import init_db
from backend.models.project import default_empty_document
from backend.services.project_service import ProjectService, ProjectError
from backend.services.hyperframes_adapter import HyperFramesAdapter


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.mark.asyncio
async def test_add_track_operation():
    """Verify add_track adds typed track and supports custom IDs, names, and insert positions."""
    doc = json.loads(default_empty_document("Track Add Test"))
    project = await ProjectService.create_project(name="Track Add", initial_document=doc)
    pid = project.id
    rev = project.revision

    # 1. Add audio track (music)
    res1 = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=rev,
        operation_type="add_track",
        payload={"type": "audio", "name": "Background Music", "track_id": "track_audio_bgm"},
    )
    rev = res1["revision"]
    tracks = res1["document"]["timeline"]["tracks"]
    assert any(t["id"] == "track_audio_bgm" and t["name"] == "Background Music" and t["type"] == "audio" for t in tracks)

    # 2. Add graphics track with insert_index
    res2 = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=rev,
        operation_type="add_track",
        payload={"type": "graphics", "name": "Lower Thirds", "insert_index": 1},
    )
    rev = res2["revision"]
    tracks = res2["document"]["timeline"]["tracks"]
    assert tracks[1]["type"] == "graphics"
    assert tracks[1]["name"] == "Lower Thirds"

    # 3. Invalid track type should raise ProjectError
    with pytest.raises(ProjectError, match="Invalid track type"):
        await ProjectService.apply_operation(
            project_id=pid,
            expected_revision=rev,
            operation_type="add_track",
            payload={"type": "invalid_type", "name": "Bad Track"},
        )

    # 4. Duplicate track_id should raise ProjectError
    with pytest.raises(ProjectError, match="already exists"):
        await ProjectService.apply_operation(
            project_id=pid,
            expected_revision=rev,
            operation_type="add_track",
            payload={"type": "audio", "track_id": "track_audio_bgm"},
        )


@pytest.mark.asyncio
async def test_delete_track_operation():
    """Verify delete_track protections: base track immunity, active clip checks, and locked clip blocks."""
    doc = json.loads(default_empty_document("Track Delete Test"))
    project = await ProjectService.create_project(name="Track Delete", initial_document=doc)
    pid = project.id
    rev = project.revision

    # Add a secondary audio track
    res1 = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=rev,
        operation_type="add_track",
        payload={"type": "audio", "track_id": "track_sfx", "name": "SFX"},
    )
    rev = res1["revision"]

    # Add clip to SFX track
    res2 = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=rev,
        operation_type="add_clip",
        payload={
            "track_id": "track_sfx",
            "clip": {"id": "clip_sfx_1", "type": "audio", "title": "Whoosh", "duration_seconds": 1.5},
        },
    )
    rev = res2["revision"]

    # 1. Attempt to delete protected base track should fail
    with pytest.raises(ProjectError, match="Cannot delete protected base track"):
        await ProjectService.apply_operation(
            project_id=pid,
            expected_revision=rev,
            operation_type="delete_track",
            payload={"track_id": "track_video_main"},
        )

    # 2. Deleting track with active clips without force should fail
    with pytest.raises(ProjectError, match="containing active clips"):
        await ProjectService.apply_operation(
            project_id=pid,
            expected_revision=rev,
            operation_type="delete_track",
            payload={"track_id": "track_sfx", "force": False},
        )

    # 3. Lock clip in track, force delete should be blocked by locked clip
    res_lock = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=rev,
        operation_type="set_element_lock",
        payload={"clip_id": "clip_sfx_1", "locked": True},
    )
    rev = res_lock["revision"]

    with pytest.raises(ProjectError, match="is locked"):
        await ProjectService.apply_operation(
            project_id=pid,
            expected_revision=rev,
            operation_type="delete_track",
            payload={"track_id": "track_sfx", "force": True},
        )

    # 4. Unlock clip and force delete should succeed
    res_unlock = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=rev,
        operation_type="set_element_lock",
        payload={"clip_id": "clip_sfx_1", "locked": False},
    )
    rev = res_unlock["revision"]

    res_del = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=rev,
        operation_type="delete_track",
        payload={"track_id": "track_sfx", "force": True},
    )
    tracks = res_del["document"]["timeline"]["tracks"]
    assert not any(t["id"] == "track_sfx" for t in tracks)


@pytest.mark.asyncio
async def test_reorder_and_rename_track_operations():
    """Verify reorder_tracks and rename_track operations."""
    doc = json.loads(default_empty_document("Reorder Track Test"))
    project = await ProjectService.create_project(name="Reorder Track", initial_document=doc)
    pid = project.id
    rev = project.revision

    # Rename track_audio_main
    res_rn = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=rev,
        operation_type="rename_track",
        payload={"track_id": "track_audio_main", "name": "Primary Voiceover"},
    )
    rev = res_rn["revision"]
    tracks = res_rn["document"]["timeline"]["tracks"]
    aud_track = next(t for t in tracks if t["id"] == "track_audio_main")
    assert aud_track["name"] == "Primary Voiceover"

    # Reorder tracks: swap order
    orig_ids = [t["id"] for t in tracks]
    reversed_ids = list(reversed(orig_ids))

    res_ro = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=rev,
        operation_type="reorder_tracks",
        payload={"track_ids": reversed_ids},
    )
    new_tracks = res_ro["document"]["timeline"]["tracks"]
    assert [t["id"] for t in new_tracks] == reversed_ids

    # Invalid reorder (missing an ID) should fail
    with pytest.raises(ProjectError, match="must include all existing track IDs"):
        await ProjectService.apply_operation(
            project_id=pid,
            expected_revision=res_ro["revision"],
            operation_type="reorder_tracks",
            payload={"track_ids": reversed_ids[:-1]},
        )


@pytest.mark.asyncio
async def test_move_clip_compatibility_and_locks():
    """Verify move_clip type compatibility checks and locked track rejection."""
    doc = json.loads(default_empty_document("Move Clip Test"))
    project = await ProjectService.create_project(name="Move Clip", initial_document=doc)
    pid = project.id
    rev = project.revision

    # Add audio clip to track_audio_main
    res1 = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=rev,
        operation_type="add_clip",
        payload={
            "track_id": "track_audio_main",
            "clip": {"id": "clip_audio_voice", "type": "audio", "title": "Voice", "duration_seconds": 3.0},
        },
    )
    rev = res1["revision"]

    # 1. Moving audio clip to video track should be rejected
    with pytest.raises(ProjectError, match="Cannot move audio clip"):
        await ProjectService.apply_operation(
            project_id=pid,
            expected_revision=rev,
            operation_type="move_clip",
            payload={"clip_id": "clip_audio_voice", "new_track_id": "track_video_main"},
        )

    # 2. Add a second audio track
    res2 = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=rev,
        operation_type="add_track",
        payload={"type": "audio", "track_id": "track_audio_aux", "name": "Aux Audio"},
    )
    rev = res2["revision"]

    # 3. Lock destination track, move should fail
    res_lock = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=rev,
        operation_type="update_track_state",
        payload={"track_id": "track_audio_aux", "patch": {"locked": True}},
    )
    rev = res_lock["revision"]

    with pytest.raises(ProjectError, match="to locked track"):
        await ProjectService.apply_operation(
            project_id=pid,
            expected_revision=rev,
            operation_type="move_clip",
            payload={"clip_id": "clip_audio_voice", "new_track_id": "track_audio_aux"},
        )

    # 4. Unlock destination track and move audio clip: should succeed
    res_unlock = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=rev,
        operation_type="update_track_state",
        payload={"track_id": "track_audio_aux", "patch": {"locked": False}},
    )
    rev = res_unlock["revision"]

    res_move = await ProjectService.apply_operation(
        project_id=pid,
        expected_revision=rev,
        operation_type="move_clip",
        payload={"clip_id": "clip_audio_voice", "new_track_id": "track_audio_aux", "start_seconds": 2.5},
    )
    tracks = res_move["document"]["timeline"]["tracks"]
    aux = next(t for t in tracks if t["id"] == "track_audio_aux")
    assert any(c["id"] == "clip_audio_voice" and c["start_seconds"] == 2.5 for c in aux["clips"])


def test_caption_stacking_parity():
    """Verify HyperFramesAdapter stacks multi-track captions cleanly without collision."""
    doc = json.loads(default_empty_document("Caption Parity Test"))
    doc["timeline"]["duration_seconds"] = 10.0

    # Track 1 (default captions)
    cap_track1 = next(t for t in doc["timeline"]["tracks"] if t["type"] == "captions")
    cap_track1["clips"].append({
        "id": "cap_main",
        "type": "caption",
        "caption_text": "Primary Dialogue",
        "start_seconds": 0.0,
        "duration_seconds": 4.0,
    })

    # Track 2 (secondary translation / speaker label)
    doc["timeline"]["tracks"].append({
        "id": "track_captions_sub",
        "type": "captions",
        "name": "Subtitles (Spanish)",
        "clips": [{
            "id": "cap_sub",
            "type": "caption",
            "caption_text": "Diálogo Principal",
            "start_seconds": 0.0,
            "duration_seconds": 4.0,
            "color": "#a7f3d0",
        }]
    })

    html = HyperFramesAdapter.project_doc_to_html(doc)
    assert "Primary Dialogue" in html
    assert "Diálogo Principal" in html
    # Primary track uses default bottom: 20%
    assert 'id="cap_main"' in html
    # Secondary track uses stacked bottom calc to prevent collision and custom color
    assert 'bottom: calc(20% + 72px)' in html
    assert 'color: #a7f3d0' in html
