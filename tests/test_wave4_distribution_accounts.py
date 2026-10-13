# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for Phase 10 Account and OAuth boundaries: scope checks, state evaluation, and security."""
import pytest
from datetime import datetime, timedelta, timezone

from backend.distribution.account_boundary import (
    AccountBoundaryManager,
    AccountSecurityError,
)
from backend.distribution.models import AccountState


def test_account_not_connected():
    acc = AccountBoundaryManager.evaluate_account_readiness(
        account_id="",
        platform="youtube",
        is_connected=False,
    )
    assert acc.state == AccountState.NOT_CONNECTED
    assert acc.can_publish is False


def test_account_insufficient_scopes():
    acc = AccountBoundaryManager.evaluate_account_readiness(
        account_id="yt_channel_1",
        platform="youtube",
        is_connected=True,
        granted_scopes=["https://www.googleapis.com/auth/youtube.readonly"],  # Missing youtube.upload
    )
    assert acc.state == AccountState.INSUFFICIENT_SCOPES
    assert acc.can_publish is False

    with pytest.raises(AccountSecurityError):
        AccountBoundaryManager.assert_account_can_publish(acc)


def test_account_expired():
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    acc = AccountBoundaryManager.evaluate_account_readiness(
        account_id="tiktok_user_1",
        platform="tiktok",
        is_connected=True,
        granted_scopes=["video.upload", "video.publish"],
        token_expires_at_utc=yesterday,
    )
    assert acc.state == AccountState.EXPIRED
    assert acc.can_publish is False


def test_account_ready_to_publish():
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    acc = AccountBoundaryManager.evaluate_account_readiness(
        account_id="tiktok_user_1",
        platform="tiktok",
        is_connected=True,
        granted_scopes=["video.upload", "video.publish"],
        token_expires_at_utc=tomorrow,
    )
    assert acc.state == AccountState.READY
    assert acc.can_publish is True
    # Should not raise
    AccountBoundaryManager.assert_account_can_publish(acc)


def test_account_no_sensitive_tokens_in_model():
    acc = AccountBoundaryManager.evaluate_account_readiness(
        account_id="x_user_1",
        platform="x",
        is_connected=True,
        granted_scopes=["tweet.write", "tweet.read", "users.read"],
    )
    d = acc.model_dump()
    assert "access_token" not in d
    assert "refresh_token" not in d
    assert "client_secret" not in d
