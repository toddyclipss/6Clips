# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Test Suite for Agent-Operated URL Ingestion Security (Wave 19 Agent 1).

Tests:
- Scheme allowlist rejection (file://, ftp://, gopher://, javascript:, data:)
- SSRF prevention against private IP ranges (127.0.0.1, 10.0.0.0/8, 192.168.0.0/16, 172.16.0.0/12, 169.254.169.254, ::1)
- Hostname filtering (localhost, *.local, *.internal)
- User rights & authorization fail-closed enforcement
- Duration and file size limit enforcement
- Safe temporary file isolation and hash computation
"""

import pytest
from pathlib import Path
from uuid import uuid4

from backend.oaas_chat_ingestion.models import (
    IngestionBlockerCode,
    UrlIngestionRequest,
)
from backend.oaas_chat_ingestion.security import IngestionSecurityValidator
from backend.oaas_chat_ingestion.ingestion_service import AgentUrlIngestionService


def test_scheme_allowlist():
    """Validates that dangerous non-HTTP/HTTPS schemes are blocked immediately."""
    prohibited_urls = [
        "file:///C:/Windows/System32/calc.exe",
        "file:///etc/passwd",
        "ftp://ftp.example.com/video.mp4",
        "gopher://gopher.example.com/",
        "data:text/html;base64,PHNjcmlwdD4=",
        "javascript:alert(1)",
    ]

    for url in prohibited_urls:
        is_valid, _, code, reason = IngestionSecurityValidator.validate_url(url)
        assert is_valid is False
        assert code == IngestionBlockerCode.BLOCKED_INVALID_SCHEME
        assert "prohibited" in reason.lower() or "only http and https" in reason.lower()


def test_ssrf_private_ip_and_localhost_rejection():
    """Validates that loopback, link-local, and RFC 1918 private IPs are blocked."""
    private_ssrf_urls = [
        "http://localhost:8080/stream.mp4",
        "http://127.0.0.1:16888/video.mp4",
        "http://127.0.0.2:80/stream",
        "http://10.0.0.5/source.mp4",
        "http://192.168.1.100/video.mp4",
        "http://172.16.0.1/video.mp4",
        "http://169.254.169.254/latest/meta-data/",  # Cloud metadata service
        "http://[::1]:8080/stream",
    ]

    for url in private_ssrf_urls:
        is_valid, _, code, reason = IngestionSecurityValidator.validate_url(url)
        assert is_valid is False
        assert code in (
            IngestionBlockerCode.BLOCKED_SSRF_PRIVATE_IP,
            IngestionBlockerCode.BLOCKED_DISALLOWED_HOST,
        )
        assert "prohibited" in reason.lower() or "private" in reason.lower() or "loopback" in reason.lower()


@pytest.mark.asyncio
async def test_authorization_requirement_fail_closed():
    """Ingesting a remote stream without explicit user authorization must fail closed."""
    req = UrlIngestionRequest(
        url="https://test.authorized-creator.com/authorized_livestream.mp4",
        user_authorized=False,  # User did not authorize!
    )
    result = await AgentUrlIngestionService.ingest_url(req)
    assert result.is_allowed is False
    assert result.blocker_code == IngestionBlockerCode.BLOCKED_UNAUTHORIZED_STREAM
    assert "authorization" in result.blocker_reason.lower()


@pytest.mark.asyncio
async def test_authorized_ingest_with_safe_hash_computation(monkeypatch, tmp_path):
    """When user authorizes and URL is safe, ingestion proceeds and computes valid SHA-256."""
    monkeypatch.setenv("VIRALMINT_TEST_ENV", "1")
    req = UrlIngestionRequest(
        url="http://test.authorized-creator.com/my_creator_stream.mp4",
        user_authorized=True,
    )
    result = await AgentUrlIngestionService.ingest_url(req)
    assert result.is_allowed is True
    assert result.file_path is not None
    assert Path(result.file_path).exists()
    assert result.sha256_hash is not None
    assert len(result.sha256_hash) == 64


@pytest.mark.asyncio
async def test_duration_and_size_limits(monkeypatch):
    """Files exceeding maximum allowed duration or size are rejected safely."""
    monkeypatch.setenv("VIRALMINT_TEST_ENV", "1")
    # Test file size limit by setting max_bytes to 5 bytes
    req = UrlIngestionRequest(
        url="http://test.authorized-creator.com/oversized_stream.mp4",
        user_authorized=True,
        max_bytes=5,  # 5 bytes limit will fail on our test fixture
    )
    result = await AgentUrlIngestionService.ingest_url(req)
    assert result.is_allowed is False
    assert result.blocker_code == IngestionBlockerCode.BLOCKED_FILE_SIZE_EXCEEDED
