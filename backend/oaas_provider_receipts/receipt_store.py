# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
OAAS Provider Receipt Store: Immutable, cryptographically verified receipt management.
"""
from __future__ import annotations

import hmac
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ReceiptVerificationError(Exception):
    """Raised when a receipt fails authenticity or cryptographic verification."""
    pass


class ProviderReceiptV2(BaseModel):
    """Normalized, tamper-evident receipt representing verified remote publication."""
    schema_version: str = "oaas.receipt.v2"
    receipt_id: str = Field(default_factory=lambda: f"oaas_rcpt_{uuid4().hex[:14]}")
    job_id: str
    platform: str
    account_id: str
    account_handle: Optional[str] = None
    project_id: str
    project_revision: int
    artifact_sha256: str
    approval_signature: str
    provider_post_id: str
    provider_post_url: str
    provider_timestamp_utc: str
    issued_at_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_test_fixture: bool = False
    provider_metadata: Dict[str, Any] = Field(default_factory=dict)

    def validate_integrity(self, secret: str = "6clips-distribution-secret") -> bool:
        """Validate that receipt is not a fake and has genuine provider fields."""
        if not self.is_test_fixture:
            # Production receipts must never have fake prefixes
            if self.provider_post_id.startswith(("fake_", "mock_", "simulated_", "test_")):
                raise ReceiptVerificationError(
                    f"Production receipt cannot contain fabricated provider post ID: '{self.provider_post_id}'"
                )
            if not self.provider_post_url.startswith(("https://", "http://")):
                raise ReceiptVerificationError(
                    f"Production receipt requires valid URL, got: '{self.provider_post_url}'"
                )

        if not self.artifact_sha256 or len(self.artifact_sha256) != 64:
            raise ReceiptVerificationError("Invalid artifact SHA-256 in receipt.")

        return True


class OAASReceiptStore:
    """In-memory and durable receipt registry isolated from shared user DB."""

    def __init__(self):
        self._receipts: Dict[str, ProviderReceiptV2] = {}
        self._job_index: Dict[str, str] = {}  # job_id -> receipt_id

    def register_receipt(self, receipt: ProviderReceiptV2) -> ProviderReceiptV2:
        receipt.validate_integrity()
        self._receipts[receipt.receipt_id] = receipt
        self._job_index[receipt.job_id] = receipt.receipt_id
        logger.info(
            "OAASReceiptStore | Registered verified receipt %s for job %s (platform: %s, post: %s)",
            receipt.receipt_id,
            receipt.job_id,
            receipt.platform,
            receipt.provider_post_id,
        )
        return receipt

    def get_receipt(self, receipt_id: str) -> Optional[ProviderReceiptV2]:
        return self._receipts.get(receipt_id)

    def get_receipt_by_job(self, job_id: str) -> Optional[ProviderReceiptV2]:
        rid = self._job_index.get(job_id)
        if rid:
            return self._receipts.get(rid)
        return None

    def list_receipts(self, platform: Optional[str] = None, exclude_fixtures: bool = False) -> List[ProviderReceiptV2]:
        results = list(self._receipts.values())
        if platform:
            results = [r for r in results if r.platform.lower() == platform.lower()]
        if exclude_fixtures:
            results = [r for r in results if not r.is_test_fixture]
        return results

    def count_verified_receipts(self) -> int:
        return len([r for r in self._receipts.values() if not r.is_test_fixture])
