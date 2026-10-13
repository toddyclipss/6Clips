# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for Wave 3 Upload Handler and Storage Quota Service."""
import io
import shutil
from pathlib import Path
import pytest
from unittest.mock import patch

from fastapi import HTTPException

from backend.library_workflows.upload_handler import UploadHandler, sanitize_filename
from backend.library_workflows.quota_service import (
    QuotaService,
    StorageQuotaExceededError,
    DiskSpaceExceededError,
    DEFAULT_USER_QUOTA_BYTES,
    MIN_DISK_FREE_BUFFER_BYTES,
)


def test_sanitize_filename_traversal():
    assert sanitize_filename("../../etc/passwd.mp4") == "passwd.mp4"
    assert sanitize_filename("..\\..\\windows\\system32\\calc.exe.mp4") == "calc.exe.mp4"
    assert sanitize_filename("subfolder/my_video.mp4") == "my_video.mp4"
    assert sanitize_filename("null\x00byte.mp4") == "nullbyte.mp4"
    assert sanitize_filename("   spaced  name .mp4 ") == "spaced  name.mp4"


def test_sanitize_filename_fallback():
    assert sanitize_filename("") == "uploaded_media.mp4"
    assert sanitize_filename("....") == "uploaded_media.mp4"
    assert sanitize_filename("/ \\ : * ? < > |") == "uploaded_media.mp4"


def test_quota_service_summary():
    summary = QuotaService.get_quota_summary(user_id="test_user")
    assert summary["user_id"] == "test_user"
    assert "used_bytes" in summary
    assert "used_mb" in summary
    assert summary["quota_bytes"] == DEFAULT_USER_QUOTA_BYTES
    assert "quota_percent" in summary
    assert "disk_free_mb" in summary


def test_quota_service_capacity_allowed():
    # 10 MB upload with 50 GB free disk and 0 GB used
    with patch.object(QuotaService, "get_disk_free_bytes", return_value=50 * 1024 * 1024 * 1024):
        with patch.object(QuotaService, "get_user_storage_used_bytes", return_value=100 * 1024 * 1024):
            # Should not raise
            QuotaService.check_capacity(10 * 1024 * 1024, user_quota_bytes=1024 * 1024 * 1024)


def test_quota_service_exceeded_user_limit():
    with patch.object(QuotaService, "get_disk_free_bytes", return_value=50 * 1024 * 1024 * 1024):
        with patch.object(QuotaService, "get_user_storage_used_bytes", return_value=900 * 1024 * 1024):
            # Limit is 1000MB, current used 900MB, incoming 150MB -> exceeds quota
            with pytest.raises(StorageQuotaExceededError, match="Storage quota exceeded"):
                QuotaService.check_capacity(150 * 1024 * 1024, user_quota_bytes=1000 * 1024 * 1024)


def test_quota_service_disk_space_exceeded():
    # Free disk is only 40 MB, but MIN_DISK_FREE_BUFFER_BYTES is 50 MB
    with patch.object(QuotaService, "get_disk_free_bytes", return_value=40 * 1024 * 1024):
        with patch.object(QuotaService, "get_user_storage_used_bytes", return_value=0):
            with pytest.raises(DiskSpaceExceededError, match="Insufficient disk space"):
                QuotaService.check_capacity(10 * 1024 * 1024)


def test_chunked_upload_lifecycle(tmp_path: Path):
    # Initialize chunk session
    init_res = UploadHandler.init_chunked_session(
        filename="test_upload.mp4",
        total_bytes=3000,
        total_chunks=3,
        user_id="local",
    )
    session_id = init_res["session_id"]
    assert init_res["total_chunks"] == 3

    # Upload chunks out of order: 1, 0, 2
    c1 = b"B" * 1000
    c0 = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2avc1mp41" + b"A" * (1000 - 32)
    c2 = b"C" * 1000

    r1 = UploadHandler.write_chunk(session_id, 1, c1)
    assert r1["received_chunks"] == 1
    assert r1["is_complete"] is False

    r0 = UploadHandler.write_chunk(session_id, 0, c0)
    assert r0["received_chunks"] == 2
    assert r0["is_complete"] is False

    r2 = UploadHandler.write_chunk(session_id, 2, c2)
    assert r2["received_chunks"] == 3
    assert r2["is_complete"] is True

    # Assemble and complete
    assembled_path = tmp_path / "assembled.mp4"
    assembled_path.write_bytes(c0 + c1 + c2)
    assert assembled_path.stat().st_size == 3000


def test_chunked_upload_invalid_index():
    init_res = UploadHandler.init_chunked_session(
        filename="test_bound.mp4",
        total_bytes=1000,
        total_chunks=2,
        user_id="local",
    )
    session_id = init_res["session_id"]

    with pytest.raises(HTTPException) as exc_info:
        UploadHandler.write_chunk(session_id, 5, b"data")
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        UploadHandler.write_chunk(session_id, -1, b"data")
    assert exc_info.value.status_code == 400
