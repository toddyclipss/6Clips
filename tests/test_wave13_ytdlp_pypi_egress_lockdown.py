# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 13 Agent 5: External Egress Lockdown (yt-dlp / pypi.org), Schedulers & Distribution Audit.

Verifies:
1. Default environment fail-closed behavior: calling check_ytdlp_version() with age_days > 30 (e.g. 56)
   spawns 0 pip subprocesses and makes 0 network connections to pypi.org.
2. Direct invocation of _try_update_ytdlp() without ENABLE_YTDLP_AUTO_UPDATE=1 is blocked
   and recorded as BLOCKED_WITH_REASON in audit records and disk logs.
3. Requiring both ENABLE_YTDLP_AUTO_UPDATE=1 AND explicit user authorization for update execution.
4. pypi.org and files.pythonhosted.org are strictly rejected in egress_audit platform allowlist.
5. Outbound video operations (download, metadata extraction, channel listing) fail closed when
   user_authorized=False, recording sanitized audit events.
6. Provenance URL sanitization strips all query tokens, auth parameters, and secrets.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

import backend.services.ytdlp_service as ys
from backend.distribution.egress_audit import (
    BLOCKED_PACKAGE_REGISTRIES,
    check_outbound_allowlist,
    clear_audit_events,
    get_audit_dir,
    get_current_log_path,
    get_recent_audit_events,
    is_audit_enabled,
    is_package_registry_blocked,
    record_egress_event,
)


@pytest.fixture(autouse=True)
def setup_audit_env(monkeypatch):
    """Enable audit recording and ensure clean in-memory buffer."""
    monkeypatch.setenv("SIXCLIPS_IDLE_NET_AUDIT", "1")
    monkeypatch.delenv("ENABLE_YTDLP_AUTO_UPDATE", raising=False)
    ys._last_update_attempt = 0.0
    ys._consecutive_download_failures = 0
    clear_audit_events()
    yield
    clear_audit_events()


def test_check_ytdlp_version_default_env_zero_pip_and_zero_pypi_egress():
    """
    Task A & C: check_ytdlp_version() with age_days == 56 (> 30) under default environment
    settings spawns 0 pip subprocesses and emits 0 network connections to pypi.org.
    """
    with patch("subprocess.run") as mock_run, \
         patch.object(ys, "_get_ytdlp_age_days", return_value=56):

        result = ys.check_ytdlp_version()

        # Zero pip / subprocess calls
        mock_run.assert_not_called()

        assert result["update_attempted"] is False
        assert result["blocked_reason"] == "AUTO_UPDATE_DISABLED_BY_DEFAULT"
        assert result["age_days"] == 56

        # Audit event recorded with BLOCKED_WITH_REASON
        events = get_recent_audit_events(component="ytdlp_service")
        assert len(events) >= 1
        blocked_event = events[-1]
        assert blocked_event["destination_host"] == "pypi.org"
        assert blocked_event["endpoint_class"] == "BLOCKED_WITH_REASON"
        assert blocked_event["outcome_status"] == "BLOCKED_WITH_REASON"
        assert blocked_event["callsite"] == "check_ytdlp_version"
        assert blocked_event.get("reason") == "AUTO_UPDATE_DISABLED_BY_DEFAULT"


def test_try_update_ytdlp_direct_without_env_flag_blocked_and_audited():
    """
    Task A & C: Calling _try_update_ytdlp() directly without ENABLE_YTDLP_AUTO_UPDATE=1
    is blocked and logged as BLOCKED_WITH_REASON in audit records.
    """
    with patch("subprocess.run") as mock_run:
        updated = ys._try_update_ytdlp()

        assert updated is False
        mock_run.assert_not_called()

        events = get_recent_audit_events(component="ytdlp_service")
        assert len(events) >= 1
        blocked = events[-1]
        assert blocked["destination_host"] == "pypi.org"
        assert blocked["endpoint_class"] == "BLOCKED_WITH_REASON"
        assert blocked["outcome_status"] == "BLOCKED_WITH_REASON"
        assert blocked["callsite"] == "_try_update_ytdlp"
        assert blocked.get("reason") == "AUTO_UPDATE_DISABLED_BY_DEFAULT"


def test_try_update_ytdlp_with_env_flag_but_unauthorized_blocked(monkeypatch):
    """
    _try_update_ytdlp requires BOTH ENABLE_YTDLP_AUTO_UPDATE=1 AND explicit user authorization.
    If env is set but user_authorized=False, it must remain blocked.
    """
    monkeypatch.setenv("ENABLE_YTDLP_AUTO_UPDATE", "1")

    with patch("subprocess.run") as mock_run:
        updated = ys._try_update_ytdlp(user_authorized=False)

        assert updated is False
        mock_run.assert_not_called()

        events = get_recent_audit_events(component="ytdlp_service")
        assert len(events) >= 1
        assert events[-1]["endpoint_class"] == "BLOCKED_WITH_REASON"


def test_try_update_ytdlp_authorized_and_enabled_executes_pip(monkeypatch):
    """
    When BOTH ENABLE_YTDLP_AUTO_UPDATE=1 AND user_authorized=True, the pip update
    is permitted to execute, recording an AUTHORIZED_PACKAGE_UPDATE audit event.
    """
    monkeypatch.setenv("ENABLE_YTDLP_AUTO_UPDATE", "1")

    with patch("sys.frozen", create=True, new=False), \
         patch("subprocess.run") as mock_run, \
         patch("importlib.reload"):
        mock_run.return_value = MagicMock(returncode=0, stdout="Successfully installed yt-dlp", stderr="")

        updated = ys._try_update_ytdlp(user_authorized=True)

        assert updated is True
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "-m" in cmd and "pip" in cmd and "install" in cmd
        assert any(isinstance(arg, str) and arg.startswith("yt-dlp>=") for arg in cmd)

        events = get_recent_audit_events(component="ytdlp_service")
        assert any(e["endpoint_class"] == "AUTHORIZED_PACKAGE_UPDATE" for e in events)


def test_record_download_failure_fail_closed_zero_pip_calls():
    """
    Task B: Consecutive download failure escalation must fail closed and NOT spawn pip
    under default environment settings.
    """
    with patch("subprocess.run") as mock_run, \
         patch.object(ys, "_get_ytdlp_age_days", return_value=56):

        for _ in range(ys._FAILURE_THRESHOLD_FOR_UPDATE):
            ys._record_download_failure()

        # Zero pip calls
        mock_run.assert_not_called()

        events = get_recent_audit_events(component="ytdlp_service")
        assert any(e["endpoint_class"] == "BLOCKED_WITH_REASON" and e["destination_host"] == "pypi.org" for e in events)


def test_pypi_and_package_registries_strictly_blocked_in_allowlist():
    """
    Task A: pypi.org and files.pythonhosted.org remain strictly blocked by default
    in backend/distribution/egress_audit.py during normal idle/runtime operation.
    """
    assert is_package_registry_blocked("pypi.org") is True
    assert is_package_registry_blocked("files.pythonhosted.org") is True
    assert is_package_registry_blocked("pypi.python.org") is True
    assert is_package_registry_blocked("upload.pypi.org") is True
    assert is_package_registry_blocked("www.googleapis.com") is False

    # check_outbound_allowlist must reject pypi across all platform contexts
    assert check_outbound_allowlist("youtube", "pypi.org") is False
    assert check_outbound_allowlist("distribution", "pypi.org") is False
    assert check_outbound_allowlist("analytics", "files.pythonhosted.org") is False
    assert check_outbound_allowlist("generic", "pypi.python.org") is False


def test_url_sanitization_strips_tokens_and_secrets():
    """
    Task B: Sanitized provenance URL must preserve video/playlist IDs but strip
    query tokens, auth parameters, and secrets.
    """
    raw_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&token=supersecret123&authuser=0&key=AIzaSyXYZ"
    host, clean_path = ys._sanitize_url_for_audit(raw_url)

    assert host == "www.youtube.com"
    assert "v=dQw4w9WgXcQ" in clean_path
    assert "supersecret123" not in clean_path
    assert "AIzaSyXYZ" not in clean_path
    assert "authuser" not in clean_path


@pytest.mark.asyncio
async def test_ytdlp_unauthorized_download_fails_closed():
    """
    Task B: Outbound download without active user authorization fails closed with PermissionError
    and records an audit event.
    """
    with pytest.raises(PermissionError, match="Outbound video download blocked"):
        await ys.download_video("https://www.youtube.com/watch?v=test12345", user_authorized=False)

    events = get_recent_audit_events(component="ytdlp_service")
    assert any(e["callsite"] == "download_video" and e["endpoint_class"] == "BLOCKED_WITH_REASON" for e in events)


@pytest.mark.asyncio
async def test_ytdlp_unauthorized_metadata_and_channel_listing_fail_closed():
    """
    Task B: Outbound metadata extraction and channel listing fail closed without user authorization.
    """
    with pytest.raises(PermissionError, match="Outbound metadata extraction blocked"):
        await ys.get_video_info("https://www.youtube.com/watch?v=test12345", user_authorized=False)

    with pytest.raises(PermissionError, match="Outbound channel listing blocked"):
        await ys.list_channel_videos("https://www.youtube.com/@somechannel", user_authorized=False)

    events = get_recent_audit_events(component="ytdlp_service")
    assert any(e["callsite"] == "get_video_info" and e["endpoint_class"] == "BLOCKED_WITH_REASON" for e in events)
    assert any(e["callsite"] == "list_channel_videos" and e["endpoint_class"] == "BLOCKED_WITH_REASON" for e in events)


def test_audit_log_persisted_to_temp_disk():
    """
    Audit events must be persisted to the external %TEMP%/6clips_wave12_idle_audit/ JSONL file.
    """
    ys._try_update_ytdlp(user_authorized=False)

    log_path = get_current_log_path()
    assert log_path.exists()
    assert log_path.stat().st_size > 0

    with open(log_path, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]

    assert any(
        entry.get("destination_host") == "pypi.org" and
        entry.get("endpoint_class") == "BLOCKED_WITH_REASON" and
        entry.get("reason") == "AUTO_UPDATE_DISABLED_BY_DEFAULT"
        for entry in lines
    )


def test_check_ytdlp_version_fresh_binary_no_update():
    """
    When installed yt-dlp is fresh (<= 30 days old), check_ytdlp_version reports
    the version without attempting any update.
    """
    with patch("subprocess.run") as mock_run, \
         patch.object(ys, "_get_ytdlp_age_days", return_value=12):

        result = ys.check_ytdlp_version()

        mock_run.assert_not_called()
        assert result["update_attempted"] is False
        assert result["age_days"] == 12
