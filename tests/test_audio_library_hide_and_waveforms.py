# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for audio library hiding, unhiding, safe fallback, and authentic waveform extraction."""
import json
import pytest
from pathlib import Path
from starlette.testclient import TestClient

from backend.main import create_app
from backend.database import init_db, AsyncSessionLocal
from backend.services.music_service import MUSIC_DIR
from backend.services import library_index


def _ensure_test_music():
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    sample = MUSIC_DIR / "bundled_ambient.mp3"
    if not sample.exists():
        # Write 1 sec dummy mp3 or read from storage
        repo_music = Path("storage/music")
        if repo_music.exists():
            for f in repo_music.glob("*.mp3"):
                (MUSIC_DIR / f.name).write_bytes(f.read_bytes())


@pytest.fixture
def client():
    _ensure_test_music()
    app = create_app()
    return TestClient(app)


@pytest.mark.asyncio
async def test_audio_hiding_and_unhiding(client):
    """Verify tracks can be hidden from library and unhidden."""
    _ensure_test_music()
    await init_db()

    target = "bundled_ambient.mp3"
    # Ensure starting in unhidden state
    client.post(f"/api/music/{target}/unhide")

    async with AsyncSessionLocal() as db:
        res = await library_index.query(db, media="audio")
        keys = [it["id"] for it in res["items"] if it["source"] == "music"]
        assert target in keys, f"Expected {target} in library query"

    # Hide track via music endpoint
    hide_resp = client.post(f"/api/music/{target}/hide")
    assert hide_resp.status_code == 200
    assert hide_resp.json() == {"ok": True, "hidden": target}

    # Verify track is no longer in library
    async with AsyncSessionLocal() as db:
        res2 = await library_index.query(db, media="audio")
        keys2 = [it["id"] for it in res2["items"] if it["source"] == "music"]
        assert target not in keys2, f"Expected {target} to be hidden from library query"

    # Unhide track via library endpoint
    unhide_resp = client.post(f"/api/library/track/{target}/unhide")
    assert unhide_resp.status_code == 200
    assert unhide_resp.json() == {"ok": True, "unhidden": target}

    # Verify track reappears in library
    async with AsyncSessionLocal() as db:
        res3 = await library_index.query(db, media="audio")
        keys3 = [it["id"] for it in res3["items"] if it["source"] == "music"]
        assert target in keys3, f"Expected {target} to reappear in library query"


@pytest.mark.asyncio
async def test_audio_safe_delete_fallback_to_hide(client):
    """Verify safe delete with hide_if_blocked=True hides bundled/referenced tracks."""
    _ensure_test_music()
    target = "bundled_ambient.mp3"
    client.post(f"/api/music/{target}/unhide")

    # Regular delete should fail with 403
    del_fail = client.delete(f"/api/music/{target}")
    assert del_fail.status_code == 403

    # Delete with hide_if_blocked=True should succeed and return reason="bundled"
    del_hide = client.delete(f"/api/music/{target}?hide_if_blocked=true")
    assert del_hide.status_code == 200
    data = del_hide.json()
    assert data["ok"] is True
    assert data["hidden"] == target
    assert data["reason"] == "bundled"

    # Verify physical file still exists on disk
    assert (MUSIC_DIR / target).is_file(), "Physical file must be preserved"

    # Cleanup: unhide
    client.post(f"/api/music/{target}/unhide")


def test_audio_waveform_endpoints(client):
    """Verify real waveform peak extraction endpoints."""
    _ensure_test_music()
    target = "bundled_ambient.mp3"

    # 1. /api/music/{filename}/waveform
    res = client.get(f"/api/music/{target}/waveform?count=32")
    assert res.status_code == 200
    data = res.json()
    assert data["filename"] == target
    assert len(data["peaks"]) == 32
    assert all(0.05 <= p <= 1.0 for p in data["peaks"])

    # 2. /api/library/waveform/trk:{filename}
    res2 = client.get(f"/api/library/waveform/trk:{target}?count=46")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["key"] == f"trk:{target}"
    assert len(data2["peaks"]) == 46
    assert all(0.05 <= p <= 1.0 for p in data2["peaks"])
