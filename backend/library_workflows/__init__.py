# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Library Workflows package: media probe, chunked upload, quota enforcement, trash lifecycle, and motion contracts."""

from backend.library_workflows.media_probe import (
    MediaProbeError,
    MediaProbeResult,
    MissingMediaError,
    CorruptedMediaError,
    UnrecognizedMediaError,
    probe_media_file,
    detect_magic_container,
)
from backend.library_workflows.quota_service import (
    QuotaService,
    QuotaError,
    StorageQuotaExceededError,
    DiskSpaceExceededError,
)
from backend.library_workflows.upload_handler import (
    UploadHandler,
    UploadError,
    sanitize_filename,
)
from backend.library_workflows.trash_and_lifecycle import (
    TrashManager,
    LifecycleError,
    AssetLockedByProjectError,
    AssetOwnershipError,
)
from backend.library_workflows.motion_contract import (
    MotionAssetIntent,
    MotionContractManager,
    MotionContractError,
    MIME_MOTION_ASSET,
)

__all__ = [
    "MediaProbeError",
    "MediaProbeResult",
    "MissingMediaError",
    "CorruptedMediaError",
    "UnrecognizedMediaError",
    "probe_media_file",
    "detect_magic_container",
    "QuotaService",
    "QuotaError",
    "StorageQuotaExceededError",
    "DiskSpaceExceededError",
    "UploadHandler",
    "UploadError",
    "sanitize_filename",
    "TrashManager",
    "LifecycleError",
    "AssetLockedByProjectError",
    "AssetOwnershipError",
    "MotionAssetIntent",
    "MotionContractManager",
    "MotionContractError",
    "MIME_MOTION_ASSET",
]
