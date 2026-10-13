# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Quota Service: disk capacity validation and per-user storage quota enforcement."""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from backend.config import settings

logger = logging.getLogger(__name__)

# Default 20 GB per user
DEFAULT_USER_QUOTA_BYTES = 20 * 1024 * 1024 * 1024
# Minimum disk free buffer (50 MB)
MIN_DISK_FREE_BUFFER_BYTES = 50 * 1024 * 1024


class QuotaError(Exception):
    """Base error for quota and disk space limitations."""
    pass


class StorageQuotaExceededError(QuotaError):
    """Raised when user exceeds their configured storage quota."""
    pass


class DiskSpaceExceededError(QuotaError):
    """Raised when physical disk has insufficient free space for media upload."""
    pass


class QuotaService:
    """Manages disk space safety checks and user media storage limits."""

    @classmethod
    def get_disk_free_bytes(cls, target_path: Optional[Path] = None) -> int:
        """Query physical free disk space for the target storage volume."""
        p = target_path or settings.STORAGE_ROOT
        try:
            total, used, free = shutil.disk_usage(p)
            return free
        except Exception as e:
            logger.warning("Failed to check disk usage on %s: %s", p, e)
            return 1024 * 1024 * 1024 * 10  # Fallback 10GB in testing

    @classmethod
    def get_user_storage_used_bytes(cls, user_id: str = "local") -> int:
        """Calculate total storage consumed by a user across storage directories."""
        total_bytes = 0
        search_dirs = [
            settings.VIDEOS_DIR,
            settings.AUDIO_DIR,
            settings.GENERATED_DIR,
            settings.STORAGE_ROOT / "music",
        ]
        for sdir in search_dirs:
            if sdir.is_dir():
                for f in sdir.glob("*"):
                    if f.is_file():
                        try:
                            total_bytes += f.stat().st_size
                        except OSError:
                            pass
        return total_bytes

    @classmethod
    def check_capacity(
        cls,
        incoming_bytes: int,
        target_dir: Optional[Path] = None,
        user_id: str = "local",
        user_quota_bytes: int = DEFAULT_USER_QUOTA_BYTES,
    ) -> None:
        """
        Validate both physical disk space and user quota before persisting upload.
        Raises DiskSpaceExceededError or StorageQuotaExceededError if capacity is insufficient.
        """
        # 1. Physical disk space check
        free_bytes = cls.get_disk_free_bytes(target_dir)
        if free_bytes < (incoming_bytes + MIN_DISK_FREE_BUFFER_BYTES):
            raise DiskSpaceExceededError(
                f"Insufficient disk space. Free: {round(free_bytes / (1024*1024), 1)}MB, "
                f"Required: {round((incoming_bytes + MIN_DISK_FREE_BUFFER_BYTES) / (1024*1024), 1)}MB."
            )

        # 2. User storage quota check
        used_bytes = cls.get_user_storage_used_bytes(user_id)
        if (used_bytes + incoming_bytes) > user_quota_bytes:
            raise StorageQuotaExceededError(
                f"Storage quota exceeded. Used: {round(used_bytes / (1024*1024), 1)}MB, "
                f"Quota: {round(user_quota_bytes / (1024*1024), 1)}MB."
            )

    @classmethod
    def get_quota_summary(cls, user_id: str = "local") -> Dict[str, Any]:
        """Return formatted storage summary for UI indicators."""
        free_bytes = cls.get_disk_free_bytes()
        used_bytes = cls.get_user_storage_used_bytes(user_id)
        return {
            "user_id": user_id,
            "used_bytes": used_bytes,
            "used_mb": round(used_bytes / (1024 * 1024), 2),
            "quota_bytes": DEFAULT_USER_QUOTA_BYTES,
            "quota_mb": round(DEFAULT_USER_QUOTA_BYTES / (1024 * 1024), 2),
            "quota_percent": round((used_bytes / DEFAULT_USER_QUOTA_BYTES) * 100, 1),
            "disk_free_bytes": free_bytes,
            "disk_free_mb": round(free_bytes / (1024 * 1024), 2),
        }
