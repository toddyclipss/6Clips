# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for Library audio asset handling, duration probing, and safe music deletion semantics."""
import json
import pytest
from pathlib import Path
from starlette.testclient import TestClient

from backend.main import create_app
from backend.database import init_db, AsyncSessionLocal
from backend.models.project import Project
from backend.services.music_service import MUSIC_DIR
from backend.services import library_index


def _ensure_test_music_files():
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    repo_music = Path("storage/music")
    if repo_music.exists():
        for f in repo_music.glob("*.mp3"):
            target = MUSIC_DIR / f.name
            if not target.exists():
                target.write_bytes(f.read_bytes())
    # Ensure all test-referenced bundled tracks exist
    sample = next(MUSIC_DIR.glob("*.mp3"), None)
    if sample:
        sample_bytes = sample.read_bytes()
        for b_name in ("bundled_ambient.mp3", "ambient_calm.mp3", "lofi_chill.mp3"):
            target = MUSIC_DIR / b_name
            if not target.exists():
                target.write_bytes(sample_bytes)



@pytest.fixture
def client():
    _ensure_test_music_files()
    app = create_app()
    return TestClient(app)


@pytest.mark.asyncio
async def test_music_duration_probing_in_library():
    """Verify library indexing probes and reports actual duration for music tracks."""
    _ensure_test_music_files()
    await init_db()
    async with AsyncSessionLocal() as db:
        res = await library_index.query(db, media="audio")
        tracks = [i for i in res["items"] if i["source"] == "music"]
        assert len(tracks) > 0, "Expected at least one music track in storage/music"
        for t in tracks:
            # Bundled tracks have real duration probed (e.g. 30.0s)
            assert t["duration_seconds"] is not None
            assert t["duration_seconds"] > 0
            if t["id"] in ("bundled_ambient.mp3", "ambient_calm.mp3", "lofi_chill.mp3"):
                assert t["is_bundled"] is True


@pytest.mark.asyncio
async def test_music_safe_delete_semantics(client):
    """Verify path traversal, bundled guard, project-ref guard, and user deletion."""
    _ensure_test_music_files()
    await init_db()

    # 1. Traversal guard
    resp = client.delete("/api/music/test..mp3")
    assert resp.status_code == 400

    resp = client.delete("/api/library/track/test..mp3")
    assert resp.status_code == 400

    # 2. Non-existent track
    resp = client.delete("/api/music/nonexistent_ghost_track.mp3")
    assert resp.status_code == 404

    # 3. Bundled track deletion rejection (HTTP 403 Forbidden)
    for bundled in ("bundled_ambient.mp3", "ambient_calm.mp3", "lofi_chill.mp3"):
        resp = client.delete(f"/api/music/{bundled}")
        assert resp.status_code == 403
        assert "bundled" in resp.json()["detail"].lower()

        # Also via /api/library/track/
        resp_lib = client.delete(f"/api/library/track/{bundled}")
        assert resp_lib.status_code == 403

    # 4. Create dummy user tracks for testing
    user_free_track = MUSIC_DIR / "test_user_free_track.mp3"
    user_ref_track = MUSIC_DIR / "test_user_referenced_track.mp3"

    sample_bytes = (MUSIC_DIR / "lofi_chill.mp3").read_bytes()
    user_free_track.write_bytes(sample_bytes)
    user_ref_track.write_bytes(sample_bytes)

    try:
        # Create a Project referencing user_ref_track
        async with AsyncSessionLocal() as db:
            doc = {
                "schema_version": 2,
                "title": "Commercial Campaign 2026",
                "aspect_ratio": "9:16",
                "timeline": {
                    "fps": 30,
                    "duration_seconds": 10.0,
                    "tracks": [
                        {
                            "id": "track_audio_bgm",
                            "type": "audio",
                            "name": "BGM",
                            "clips": [
                                {
                                    "id": "clip_audio_1",
                                    "asset_id": "trk:test_user_referenced_track.mp3",
                                    "file": "test_user_referenced_track.mp3",
                                    "start_seconds": 0.0,
                                    "duration_seconds": 10.0,
                                }
                            ],
                        }
                    ],
                },
                "assets": [
                    {
                        "id": "trk:test_user_referenced_track.mp3",
                        "file": "test_user_referenced_track.mp3",
                    }
                ],
            }
            test_proj = Project(
                id="proj_test_audio_ref_99",
                name="Commercial Campaign 2026",
                aspect_ratio="9:16",
                revision=3,
                document_json=json.dumps(doc),
            )
            db.add(test_proj)
            await db.commit()

        # 5. Attempting to delete user_ref_track must be rejected (HTTP 409 Conflict)
        resp = client.delete("/api/music/test_user_referenced_track.mp3")
        assert resp.status_code == 409
        err_msg = resp.json()["detail"]
        assert "referenced by project 'Commercial Campaign 2026'" in err_msg
        assert "revision 3" in err_msg
        assert user_ref_track.exists(), "Referenced track must NOT be unlinked"

        # 6. Deleting user_free_track must succeed (HTTP 200)
        resp_del = client.delete("/api/music/test_user_free_track.mp3")
        assert resp_del.status_code == 200
        assert resp_del.json() == {"ok": True, "deleted": "test_user_free_track.mp3"}
        assert not user_free_track.exists(), "User track must be unlinked from disk"

    finally:
        # Cleanup
        if user_free_track.exists():
            user_free_track.unlink(missing_ok=True)
        if user_ref_track.exists():
            user_ref_track.unlink(missing_ok=True)

        async with AsyncSessionLocal() as db:
            proj = await db.get(Project, "proj_test_audio_ref_99")
            if proj:
                await db.delete(proj)
                await db.commit()
