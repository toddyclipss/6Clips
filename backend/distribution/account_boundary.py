# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Account and OAuth boundary: scope verification, account state evaluation, and credential security."""
from __future__ import annotations

import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone

from backend.distribution.models import AccountState, PlatformAccount, PlatformKind

logger = logging.getLogger(__name__)


class AccountSecurityError(Exception):
    """Raised when account state prohibits publishing or credential leakage is detected."""
    pass


class AccountBoundaryManager:
    """Manages platform account readiness, scope checks, and token safety."""

    # Official required scopes per platform
    REQUIRED_SCOPES = {
        PlatformKind.YOUTUBE.value: [
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube.readonly",
        ],
        PlatformKind.TIKTOK.value: [
            "video.upload",
            "video.publish",
        ],
        PlatformKind.INSTAGRAM.value: [
            "instagram_content_publish",
            "instagram_basic",
        ],
        PlatformKind.X.value: [
            "tweet.write",
            "tweet.read",
            "users.read",
        ],
    }

    @classmethod
    def evaluate_account_readiness(
        cls,
        account_id: str,
        platform: str,
        user_id: str = "local",
        account_name: str = "",
        handle: Optional[str] = None,
        granted_scopes: Optional[List[str]] = None,
        token_expires_at_utc: Optional[str] = None,
        is_connected: bool = False,
    ) -> PlatformAccount:
        """
        Evaluate account readiness and required scopes.
        Never emits raw tokens or credentials.
        """
        platform = platform.lower()
        req_scopes = cls.REQUIRED_SCOPES.get(platform, [])
        granted = granted_scopes or []

        if not is_connected or not account_id:
            state = AccountState.NOT_CONNECTED
            can_publish = False
        elif token_expires_at_utc and cls._is_expired(token_expires_at_utc):
            state = AccountState.EXPIRED
            can_publish = False
        elif not cls._has_all_scopes(granted, req_scopes):
            state = AccountState.INSUFFICIENT_SCOPES
            can_publish = False
        else:
            state = AccountState.READY
            can_publish = True

        return PlatformAccount(
            account_id=account_id,
            user_id=user_id,
            platform=platform,
            account_name=account_name or f"{platform.capitalize()} Account",
            handle=handle,
            state=state,
            granted_scopes=granted,
            required_scopes=req_scopes,
            can_publish=can_publish,
        )

    @staticmethod
    def _is_expired(expires_at_utc: str) -> bool:
        try:
            exp = datetime.fromisoformat(expires_at_utc.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) >= exp
        except Exception:
            return True

    @staticmethod
    def _has_all_scopes(granted: List[str], required: List[str]) -> bool:
        granted_set = set(granted)
        return all(r in granted_set for r in required)

    @classmethod
    def assert_account_can_publish(cls, account: PlatformAccount) -> None:
        """Enforce that account is in READY state and has publishing permission."""
        if account.state != AccountState.READY or not account.can_publish:
            raise AccountSecurityError(
                f"Account '{account.account_id}' for {account.platform} cannot publish. "
                f"Current state: {account.state.value}. Required scopes: {account.required_scopes}"
            )
