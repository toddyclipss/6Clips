# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Targeted unit tests for media streaming security, path traversal protection, and authorization."""
import tempfile
from pathlib import Path
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from backend.api.videos import _safe_resolve_path, ALLOWED_MEDIA_EXTENSIONS, stream_video, serve_media_with_range
from backend.api.downloaded import stream_downloaded
from backend.models.downloaded_video import DownloadedVideo
from backend.models.generated_video import GeneratedVideo
from backend.database import AsyncSessionLocal, init_db
from backend.config import settings


@pytest.fixture(autouse=True)
def ensure_directories():
    settings.STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    (settings.MOTION_DIR / "studio").mkdir(parents=True, exist_ok=True)


def test_safe_resolve_path_allowed_storage_root():
    """Valid media file in STORAGE_ROOT resolves successfully."""
    test_media = settings.STORAGE_ROOT / "test_sample.mp4"
    test_media.touch()
    try:
        resolved = _safe_resolve_path(str(test_media))
        assert resolved == test_media.resolve()
    finally:
        test_media.unlink(missing_ok=True)


def test_safe_resolve_path_allowed_motion_studio_dir():
    """Valid media file in MOTION_DIR/studio resolves successfully."""
    test_media = settings.MOTION_DIR / "studio" / "sample_video.webm"
    test_media.touch()
    try:
        resolved = _safe_resolve_path(str(test_media))
        assert resolved == test_media.resolve()
    finally:
        test_media.unlink(missing_ok=True)


def test_safe_resolve_path_rejects_motion_outside_studio():
    """Media file outside MOTION_DIR/studio is rejected with HTTP 403."""
    test_media = settings.MOTION_DIR / "unauthorized_motion.mp4"
    test_media.touch()
    try:
        with pytest.raises(HTTPException) as exc:
            _safe_resolve_path(str(test_media))
        assert exc.value.status_code == 403
        assert "outside allowed directories" in exc.value.detail
    finally:
        test_media.unlink(missing_ok=True)


def test_safe_resolve_path_rejects_path_traversal():
    """Traversal attempts outside allowed roots raise HTTP 403 Forbidden."""
    with tempfile.NamedTemporaryFile(suffix=".mp4") as tmp:
        outside_path = Path(tmp.name)
        with pytest.raises(HTTPException) as exc:
            _safe_resolve_path(str(outside_path))
        assert exc.value.status_code == 403
        assert "outside allowed directories" in exc.value.detail


def test_safe_resolve_path_rejects_non_media_extensions():
    """Source code, secrets, databases, text files, and configs raise HTTP 403 Forbidden."""
    forbidden_files = [
        settings.MOTION_DIR / "studio" / "server.py",
        settings.MOTION_DIR / "studio" / "package.json",
        settings.STORAGE_ROOT / "database.db",
        settings.STORAGE_ROOT / ".env",
        settings.MOTION_DIR / "studio" / "script.ts",
        settings.STORAGE_ROOT / "notes.txt",
    ]
    for p in forbidden_files:
        p.touch()
        try:
            with pytest.raises(HTTPException) as exc:
                _safe_resolve_path(str(p))
            assert exc.value.status_code == 403
            assert "not permitted for media streaming" in exc.value.detail
        finally:
            p.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_stream_downloaded_cross_user_authorization_rejection():
    """stream_downloaded rejects requests when requesting user does not match record owner."""
    await init_db()
    test_media = settings.STORAGE_ROOT / "user_sample.mp4"
    test_media.touch()

    async with AsyncSessionLocal() as db:
        dv = DownloadedVideo(
            id="test-auth-vid-1",
            user_id="user_alice",
            title="Alice Private Video",
            video_path=str(test_media),
        )
        db.add(dv)
        await db.commit()

    try:
        mock_request = Request({
            "type": "http",
            "headers": [(b"x-user-id", b"user_bob")],
            "query_string": b"",
        })
        with pytest.raises(HTTPException) as exc:
            await stream_downloaded("test-auth-vid-1", mock_request)
        assert exc.value.status_code == 403
        assert "unauthorized media record" in exc.value.detail
    finally:
        async with AsyncSessionLocal() as db:
            row = await db.get(DownloadedVideo, "test-auth-vid-1")
            if row:
                await db.delete(row)
                await db.commit()
        test_media.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_stream_downloaded_missing_record_returns_404():
    """stream_downloaded returns 404 for nonexistent records."""
    mock_request = Request({"type": "http", "headers": [], "query_string": b""})
    with pytest.raises(HTTPException) as exc:
        await stream_downloaded("nonexistent-video-id-999", mock_request)
    assert exc.value.status_code == 404
    assert "Video not found" in exc.value.detail


@pytest.mark.asyncio
async def test_stream_range_requests_valid_and_invalid():
    """serve_media_with_range handles valid partial content (206) and unsatisfiable range (416)."""
    test_media = settings.STORAGE_ROOT / "range_test.mp4"
    test_media.write_bytes(b"0123456789" * 10)  # 100 bytes
    try:
        # Valid range bytes=0-9
        req_valid = Request({
            "type": "http",
            "headers": [(b"range", b"bytes=0-9")],
        })
        res_valid = serve_media_with_range(test_media, req_valid)
        assert res_valid.status_code == 206
        assert res_valid.headers["Content-Range"] == "bytes 0-9/100"

        # Invalid range bytes=500-600
        req_invalid = Request({
            "type": "http",
            "headers": [(b"range", b"bytes=500-600")],
        })
        with pytest.raises(HTTPException) as exc:
            serve_media_with_range(test_media, req_invalid)
        assert exc.value.status_code == 416
    finally:
        test_media.unlink(missing_ok=True)
