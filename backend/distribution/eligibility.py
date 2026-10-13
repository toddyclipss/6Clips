# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Release Eligibility Verifier: enforces strict gates before media can be scheduled or distributed."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.distribution.models import ApprovalReceipt

logger = logging.getLogger(__name__)


class ReleaseEligibilityError(Exception):
    """Base error for release eligibility rejections."""
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class ReleaseEligibilityVerifier:
    """Verifies that an output artifact meets all release eligibility constraints."""

    @staticmethod
    def calculate_file_sha256(file_path: Path) -> str:
        """Compute SHA-256 hash of physical file."""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    @classmethod
    def verify_physical_artifact(cls, file_path_str: str) -> Tuple[Path, str, int]:
        """Verify that the media artifact physically exists on disk, is non-empty, and compute SHA-256."""
        p = Path(file_path_str)
        if not p.exists():
            raise ReleaseEligibilityError(
                "ARTIFACT_MISSING",
                f"Media artifact does not physically exist on disk: '{file_path_str}'"
            )
        if not p.is_file():
            raise ReleaseEligibilityError(
                "ARTIFACT_NOT_FILE",
                f"Media artifact path is not a regular file: '{file_path_str}'"
            )
        size = p.stat().st_size
        if size == 0:
            raise ReleaseEligibilityError(
                "ARTIFACT_EMPTY",
                f"Media artifact is empty (0 bytes): '{file_path_str}'"
            )
        # Inspect magic bytes for MP4 / QuickTime / WebM
        with open(p, "rb") as f:
            head = f.read(16)
        if not (head[4:8] == b"ftyp" or head.startswith(b"\x1a\x45\xdf\xa3") or head.startswith(b"RIFF")):
            raise ReleaseEligibilityError(
                "UNSUPPORTED_CONTAINER",
                f"Artifact container is not a recognized media format: '{file_path_str}'"
            )

        sha256 = cls.calculate_file_sha256(p)
        return p, sha256, size

    @classmethod
    def verify_editorial_approval(
        cls,
        approval_receipt: Optional[ApprovalReceipt],
        current_project_revision: int,
        current_artifact_sha256: str,
        secret: str = "6clips-distribution-secret",
    ) -> None:
        """Verify explicit, server-authenticated editorial approval for the exact immutable revision."""
        if not approval_receipt:
            raise ReleaseEligibilityError(
                "APPROVAL_MISSING",
                "Explicit editorial approval is required before scheduling or publishing."
            )

        if not approval_receipt.verify_signature(secret):
            raise ReleaseEligibilityError(
                "APPROVAL_SIGNATURE_INVALID",
                "Editorial approval signature is invalid or tampered with."
            )

        if approval_receipt.project_revision != current_project_revision:
            raise ReleaseEligibilityError(
                "APPROVAL_STALE_REVISION",
                f"Approval was granted for revision {approval_receipt.project_revision}, "
                f"but project has advanced to revision {current_project_revision}. Re-approval required."
            )

        if approval_receipt.artifact_sha256 != current_artifact_sha256:
            raise ReleaseEligibilityError(
                "APPROVAL_STALE_ARTIFACT",
                "Approval hash does not match current physical render artifact. Re-approval required."
            )

        if not approval_receipt.consent_for_external_publish:
            raise ReleaseEligibilityError(
                "CONSENT_MISSING",
                "Explicit creator consent for external platform publication has not been granted."
            )

    @classmethod
    def verify_permitted_uses(
        cls,
        permitted_uses: List[str],
        target_platform: str,
    ) -> None:
        """Verify rights and permitted uses allow distribution to target platform."""
        required_perm = f"distribute_{target_platform}"
        general_perms = {"social_distribution", "platform_publish", "all", "commercial_creator"}
        user_perms_set = set(permitted_uses)

        if not (user_perms_set.intersection(general_perms) or required_perm in user_perms_set):
            raise ReleaseEligibilityError(
                "INSUFFICIENT_RIGHTS",
                f"Permitted uses {permitted_uses} do not grant publishing rights for platform '{target_platform}'."
            )

    @classmethod
    def verify_eligibility(
        cls,
        file_path_str: str,
        expected_user_id: str,
        actual_user_id: str,
        current_project_revision: int,
        approval_receipt: Optional[ApprovalReceipt],
        permitted_uses: List[str],
        target_platform: str,
        technical_checks_status: str = "PASS",
        contract_checks_status: str = "PASS",
        secret: str = "6clips-distribution-secret",
    ) -> Dict[str, Any]:
        """Perform comprehensive release eligibility verification."""
        # 1. Ownership check
        if expected_user_id != actual_user_id and actual_user_id != "admin":
            raise ReleaseEligibilityError(
                "OWNERSHIP_MISMATCH",
                f"User '{actual_user_id}' does not own this media artifact."
            )

        # 2. Technical & Contract checks
        if technical_checks_status != "PASS":
            raise ReleaseEligibilityError(
                "TECHNICAL_CHECKS_FAILED",
                f"Technical verification check is '{technical_checks_status}', must be PASS."
            )
        if contract_checks_status != "PASS":
            raise ReleaseEligibilityError(
                "CONTRACT_CHECKS_FAILED",
                f"Contractual verification check is '{contract_checks_status}', must be PASS."
            )

        # 3. Physical media existence and SHA-256
        artifact_path, artifact_sha256, artifact_size = cls.verify_physical_artifact(file_path_str)

        # 4. Editorial approval and external consent
        cls.verify_editorial_approval(
            approval_receipt=approval_receipt,
            current_project_revision=current_project_revision,
            current_artifact_sha256=artifact_sha256,
            secret=secret,
        )

        # 5. Permitted uses for platform
        cls.verify_permitted_uses(permitted_uses, target_platform)

        return {
            "eligible": True,
            "artifact_path": str(artifact_path),
            "artifact_sha256": artifact_sha256,
            "artifact_size_bytes": artifact_size,
            "project_revision": current_project_revision,
            "approval_id": approval_receipt.approval_id if approval_receipt else None,
            "target_platform": target_platform,
        }
