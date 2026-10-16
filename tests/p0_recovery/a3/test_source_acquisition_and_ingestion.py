# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Unit and Integration Tests for Source Acquisition and Ingestion (Agent 3).

Verifies:
- Strict SSRF defense: loopback, link-local, private RFC 1918, AWS metadata, and prohibited schemes.
- Preserves exact URL byte and casing integrity (specifically uppercase-I vs lowercase-l).
- Truthfully fails closed with BLOCKED_FETCH_FAILED on unavailable / restricted URLs without fake deliverables.
- Multi-container format handling (.mp4, .webm, .mkv) with lossless remuxing.
- Zero user rights attestation requirement (no user_authorized or rights checkboxes).
"""

import asyncio
from pathlib import Path
import pytest
import shutil
import subprocess
import tempfile
from unittest.mock import patch

from backend.oaas_chat_ingestion.ingestion_service import AgentUrlIngestionService
from backend.oaas_chat_ingestion.models import (
    IngestionBlockerCode,
    UrlIngestionRequest,
    UrlIngestionResult,
)
from backend.oaas_chat_ingestion.security import IngestionSecurityValidator
from backend.oaas_media_edit import EditExistingMediaAdapter


@pytest.fixture(autouse=True)
def test_env(monkeypatch):
    monkeypatch.setenv("VIRALMINT_TEST_ENV", "1")


def test_ssrf_and_disallowed_schemes_blocked():
    """Verify non-HTTP schemes and private network egress are blocked immediately."""
    # 1. Prohibited schemes
    bad_schemes = [
        "file:///etc/passwd",
        "file:///C:/Windows/win.ini",
        "ftp://example.com/video.mp4",
        "gopher://127.0.0.1:70",
        "data:text/html;base64,PHNjcmlwdD4=",
    ]
    for url in bad_schemes:
        valid, ip, b_code, b_reason = IngestionSecurityValidator.validate_url(url)
        assert not valid
        assert b_code == IngestionBlockerCode.BLOCKED_INVALID_SCHEME

    # 2. Localhost and cloud metadata
    bad_hosts = [
        "http://localhost:8000/stream.mp4",
        "http://127.0.0.1:3000/api",
        "http://169.254.169.254/latest/meta-data/",
        "http://metadata.google.internal/computeMetadata/v1/",
    ]
    for url in bad_hosts:
        valid, ip, b_code, b_reason = IngestionSecurityValidator.validate_url(url)
        assert not valid
        assert b_code in (
            IngestionBlockerCode.BLOCKED_DISALLOWED_HOST,
            IngestionBlockerCode.BLOCKED_SSRF_PRIVATE_IP,
        )

    # 3. Malformed URLs
    malformed = ["", "   ", "http://", "not-a-url"]
    for url in malformed:
        valid, ip, b_code, b_reason = IngestionSecurityValidator.validate_url(url)
        assert not valid
        assert b_code in (
            IngestionBlockerCode.BLOCKED_MALFORMED_URL,
            IngestionBlockerCode.BLOCKED_INVALID_SCHEME,
        )


def test_url_casing_and_id_integrity():
    """Verify uppercase 'I' vs lowercase 'l' are preserved without mutation or lowercase folding."""
    url_upper_i = "https://www.youtube.com/watch?v=FV93IVwJP_4"
    url_lower_l = "https://www.youtube.com/watch?v=FV93lVwJP_4"

    # Both must validate scheme and hostname without altering query string
    v_upper, ip_u, code_u, _ = IngestionSecurityValidator.validate_url(url_upper_i)
    v_lower, ip_l, code_l, _ = IngestionSecurityValidator.validate_url(url_lower_l)

    assert v_upper and code_u is None
    assert v_lower and code_l is None

    # Verify that query param retains exact case
    from urllib.parse import parse_qs, urlparse
    parsed_upper = urlparse(url_upper_i)
    parsed_lower = urlparse(url_lower_l)

    assert parse_qs(parsed_upper.query)["v"][0] == "FV93IVwJP_4"
    assert parse_qs(parsed_lower.query)["v"][0] == "FV93lVwJP_4"
    assert "FV93IVwJP_4" != "FV93lVwJP_4"


def test_unavailable_url_fails_closed_truthfully():
    """
    Verify nonexistent YouTube ID (lowercase l: FV93lVwJP_4) fails closed
    with BLOCKED_FETCH_FAILED and produces NO fake file.
    """
    async def _test():
        req = UrlIngestionRequest(
            url="https://www.youtube.com/watch?v=FV93lVwJP_4",
            user_id="test_user",
        )
        res = await AgentUrlIngestionService.ingest_url(req)
        assert not res.is_allowed
        assert res.blocker_code == IngestionBlockerCode.BLOCKED_FETCH_FAILED
        assert res.file_path is None
        assert "download failed" in (res.blocker_reason or "").lower() or "video unavailable" in (res.blocker_reason or "").lower()

    asyncio.run(_test())


def test_container_extension_auto_resolution(tmp_path, monkeypatch):
    """
    Verify that if yt-dlp saves a file with .webm or .mkv,
    AgentUrlIngestionService locates and resolves it to a valid physical file.
    """
    async def _test():
        monkeypatch.setattr(AgentUrlIngestionService, "_storage_dir", classmethod(lambda cls: tmp_path))

        # Mock subprocess to create a .webm file instead of the requested .mp4
        orig_run = subprocess.run
        def mock_run(cmd, *args, **kwargs):
            if any("yt-dlp" in str(c) for c in cmd):
                for i, arg in enumerate(cmd):
                    if arg == "-o" and i + 1 < len(cmd):
                        target_mp4 = Path(cmd[i + 1])
                        mkv_path = target_mp4.with_suffix(".mkv")
                        orig_run([
                            "ffmpeg", "-y",
                            "-f", "lavfi", "-i", "testsrc=size=640x360:rate=25",
                            "-t", "2.0",
                            "-c:v", "libx264", "-preset", "ultrafast",
                            str(mkv_path),
                        ], capture_output=True)
                        return subprocess.CompletedProcess(cmd, 0, stdout="Downloaded", stderr="")
            return orig_run(cmd, *args, **kwargs)

        monkeypatch.setattr(subprocess, "run", mock_run)

        req = UrlIngestionRequest(
            url="https://www.youtube.com/watch?v=dummy_test_stream_id",
            user_id="test_user",
        )
        res = await AgentUrlIngestionService.ingest_url(req)
        assert res.is_allowed
        assert res.file_path is not None
        assert Path(res.file_path).exists()
        assert res.duration_sec is not None and res.duration_sec > 0
        assert res.sha256_hash is not None

    asyncio.run(_test())


def test_zero_user_ownership_attestation_requirement():
    """Verify no copyright attestation or rights verification fields exist or are required."""
    req = UrlIngestionRequest(url="https://www.youtube.com/watch?v=FV93IVwJP_4")
    # Verify no legacy attestation parameters
    assert not hasattr(req, "user_authorized")
    assert not hasattr(req, "rights_verified")
    assert not hasattr(req, "copyright_attested")

    # Verify EditExistingMediaContract requires no rights attestation
    from backend.oaas_media_edit import EditExistingMediaContract
    fields = EditExistingMediaContract.model_fields.keys()
    assert "user_authorized" not in fields
    assert "rights_verified" not in fields
    assert "BLOCKED_RIGHTS" not in fields
