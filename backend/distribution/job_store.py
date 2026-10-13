# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Atomic file-based persistent job store for Distribution jobs and receipts."""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional
from threading import Lock

from backend.config import settings
from backend.distribution.models import (
    DistributionJob,
    DistributionStatus,
    PublishedReceiptV1,
)

logger = logging.getLogger(__name__)


class DistributionJobStore:
    """Thread-safe persistent store for distribution jobs and receipts."""

    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir is not None:
            self._dir = base_dir
        elif "PYTEST_CURRENT_TEST" in os.environ:
            import tempfile
            self._dir = Path(tempfile.mkdtemp(prefix="test_distribution_"))
        else:
            self._dir = settings.STORAGE_ROOT / "distribution"

        self._dir.mkdir(parents=True, exist_ok=True)
        self._jobs_file = self._dir / "jobs.json"
        self._receipts_file = self._dir / "receipts.json"
        self._lock = Lock()


    def _atomic_write(self, target_file: Path, data: dict) -> None:
        """Write JSON data atomically using temporary file and atomic replace."""
        target_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = target_file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target_file)

    def _read_json(self, file_path: Path) -> dict:
        if not file_path.exists():
            return {}
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Corrupted JSON encountered in %s: %s. Quarantining file.", file_path, e)
            try:
                import time
                quarantine_target = file_path.with_name(
                    f"{file_path.stem}.corrupted.{int(time.time())}{file_path.suffix}"
                )
                file_path.rename(quarantine_target)
                logger.info("Quarantined corrupted file to %s", quarantine_target)
            except Exception as q_err:
                logger.warning("Could not quarantine corrupted file %s: %s", file_path, q_err)
            return {}

    def save_job(self, job: DistributionJob) -> None:
        """Persist or update a distribution job atomically."""
        with self._lock:
            data = self._read_json(self._jobs_file)
            data[job.job_id] = job.model_dump()
            self._atomic_write(self._jobs_file, data)

    def get_job(self, job_id: str) -> Optional[DistributionJob]:
        """Fetch a distribution job by ID."""
        with self._lock:
            data = self._read_json(self._jobs_file)
            raw = data.get(job_id)
            if not raw:
                return None
            return DistributionJob(**raw)

    def get_job_by_idempotency_key(self, idempotency_key: str) -> Optional[DistributionJob]:
        """Fetch a job by idempotency key to prevent duplicate job creation."""
        if not idempotency_key:
            return None
        with self._lock:
            data = self._read_json(self._jobs_file)
            for item in data.values():
                if item.get("idempotency_key") == idempotency_key:
                    return DistributionJob(**item)
            return None

    def list_jobs(
        self,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        status: Optional[DistributionStatus] = None,
    ) -> List[DistributionJob]:
        """List distribution jobs with optional filters."""
        with self._lock:
            data = self._read_json(self._jobs_file)
            jobs = [DistributionJob(**item) for item in data.values()]

        filtered = []
        for j in jobs:
            if user_id and j.user_id != user_id and user_id != "admin":
                continue
            if project_id and j.project_id != project_id:
                continue
            if status and j.status != status:
                continue
            filtered.append(j)

        # Sort newest first
        return sorted(filtered, key=lambda x: x.created_at, reverse=True)

    def save_receipt(self, receipt: PublishedReceiptV1) -> None:
        """Persist an immutable publishing receipt atomically."""
        with self._lock:
            data = self._read_json(self._receipts_file)
            data[receipt.receipt_id] = receipt.model_dump()
            self._atomic_write(self._receipts_file, data)

    def get_receipt(self, receipt_id: str) -> Optional[PublishedReceiptV1]:
        """Fetch a publishing receipt by ID."""
        with self._lock:
            data = self._read_json(self._receipts_file)
            raw = data.get(receipt_id)
            if not raw:
                return None
            return PublishedReceiptV1(**raw)

    def list_receipts(self, project_id: Optional[str] = None) -> List[PublishedReceiptV1]:
        """List confirmed publishing receipts."""
        with self._lock:
            data = self._read_json(self._receipts_file)
            receipts = [PublishedReceiptV1(**item) for item in data.values()]

        if project_id:
            receipts = [r for r in receipts if r.project_id == project_id]

        return sorted(receipts, key=lambda x: x.published_at_utc, reverse=True)
