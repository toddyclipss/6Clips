# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Durable, restart-persistent Analytics Repository (Phase 11).

Guarantees:
- Persistent disk storage in isolated storage root (zero shared production DB mutation).
- Atomic file writes using temp file + fsync + replace.
- Process restart recovery.
- Tenant isolation (creator_id partitioned).
- Missing metrics (None) preserved without converting to zero.
- Event notification outbox persistence with token/PII safety.
- Rate-limit backoff state persistence across restarts.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from backend.config import settings
from backend.analytics.models import (
    AnalyticsEventNotification,
    AnalyticsProvider,
    MetricObservationV1,
    PublishedReceiptV1,
    ReceiptConfirmationStatus,
)

logger = logging.getLogger(__name__)


class AnalyticsRepository:
    """
    Thread-safe and process-restart-durable analytics repository.
    Persists published receipts, metric observations, notifications, and provider backoffs.
    """

    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir is not None:
            self._dir = base_dir
        elif "PYTEST_CURRENT_TEST" in os.environ:
            import tempfile
            self._dir = Path(tempfile.mkdtemp(prefix="test_analytics_"))
        else:
            self._dir = settings.STORAGE_ROOT / "analytics"

        self._dir.mkdir(parents=True, exist_ok=True)

        self._receipts_file = self._dir / "receipts.json"
        self._observations_file = self._dir / "observations.json"
        self._notifications_file = self._dir / "notifications.json"
        self._backoff_file = self._dir / "rate_limit_backoffs.json"
        self._lock = Lock()

        # In-memory index caches loaded from durable storage
        self._receipts: Dict[str, PublishedReceiptV1] = {}
        self._observations: List[MetricObservationV1] = []
        self._notifications: List[AnalyticsEventNotification] = []
        self._backoffs: Dict[str, str] = {}

        self._load_from_disk()

    # ── Internal Storage Helpers ──────────────────────────────────────────────

    def _atomic_write_json(self, target_file: Path, data: Any) -> None:
        """Write JSON data atomically using temporary file and atomic replace."""
        target_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = target_file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target_file)

    def _read_json(self, file_path: Path) -> Any:
        if not file_path.exists():
            return None
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
            return None

    def _load_from_disk(self) -> None:
        """Hydrate memory state from durable persistent files on startup/restart."""
        with self._lock:
            # 1. Receipts
            raw_receipts = self._read_json(self._receipts_file)
            if raw_receipts and isinstance(raw_receipts, dict):
                for rid, rdata in raw_receipts.items():
                    try:
                        self._receipts[rid] = PublishedReceiptV1(**rdata)
                    except Exception as e:
                        logger.warning("Skipping corrupted receipt %s: %s", rid, e)

            # 2. Observations
            raw_obs = self._read_json(self._observations_file)
            if raw_obs and isinstance(raw_obs, list):
                for odata in raw_obs:
                    try:
                        self._observations.append(MetricObservationV1(**odata))
                    except Exception as e:
                        logger.warning("Skipping corrupted observation: %s", e)

            # 3. Notifications
            raw_notifs = self._read_json(self._notifications_file)
            if raw_notifs and isinstance(raw_notifs, list):
                for ndata in raw_notifs:
                    try:
                        self._notifications.append(AnalyticsEventNotification(**ndata))
                    except Exception as e:
                        logger.warning("Skipping corrupted notification: %s", e)

            # 4. Backoff states
            raw_backoffs = self._read_json(self._backoff_file)
            if raw_backoffs and isinstance(raw_backoffs, dict):
                self._backoffs = raw_backoffs

    # ── Receipt Persistence ───────────────────────────────────────────────────

    def save_receipt(self, receipt: PublishedReceiptV1) -> PublishedReceiptV1:
        """Persist a published receipt atomically to disk."""
        with self._lock:
            self._receipts[receipt.receipt_id] = receipt
            # Flush updated receipts to disk
            serialized = {rid: r.model_dump(mode="json") for rid, r in self._receipts.items()}
            self._atomic_write_json(self._receipts_file, serialized)
        return receipt

    def get_receipt(self, receipt_id: str) -> Optional[PublishedReceiptV1]:
        """Fetch a receipt by ID."""
        with self._lock:
            return self._receipts.get(receipt_id)

    def list_receipts(self, creator_id: Optional[str] = "local") -> List[PublishedReceiptV1]:
        """List receipts strictly filtered by tenant creator_id for isolation."""
        with self._lock:
            receipts = list(self._receipts.values())

        if creator_id is not None:
            receipts = [r for r in receipts if r.creator_id == creator_id]

        return sorted(receipts, key=lambda x: x.created_at, reverse=True)

    # ── Observation Persistence ───────────────────────────────────────────────

    def record_observation(self, obs: MetricObservationV1) -> MetricObservationV1:
        """Persist a metric observation atomically, preserving missing vs zero values."""
        with self._lock:
            self._observations.append(obs)
            serialized = [o.model_dump(mode="json") for o in self._observations]
            self._atomic_write_json(self._observations_file, serialized)
        return obs

    def get_observations_for_receipt(
        self,
        receipt_id: str,
        creator_id: Optional[str] = None,
    ) -> List[MetricObservationV1]:
        """Get all observations for a receipt, optionally enforcing tenant ownership."""
        with self._lock:
            if creator_id is not None:
                receipt = self._receipts.get(receipt_id)
                if not receipt or receipt.creator_id != creator_id:
                    return []
            return [o for o in self._observations if o.receipt_id == receipt_id]

    # ── Event Notification Outbox ─────────────────────────────────────────────

    def record_notification(self, notification: AnalyticsEventNotification) -> AnalyticsEventNotification:
        """
        Record an event notification idempotently to disk outbox.
        Ensures no duplicates within identical event_type + receipt_id.
        """
        with self._lock:
            existing = [
                n for n in self._notifications
                if n.event_type == notification.event_type and n.receipt_id == notification.receipt_id
            ]
            if existing:
                return existing[-1]

            self._notifications.append(notification)
            serialized = [n.model_dump(mode="json") for n in self._notifications]
            self._atomic_write_json(self._notifications_file, serialized)
            return notification

    def list_notifications(
        self,
        creator_id: Optional[str] = None,
    ) -> List[AnalyticsEventNotification]:
        """List notifications, optionally isolated by tenant creator_id."""
        with self._lock:
            notifs = list(self._notifications)
            if creator_id is not None:
                # Filter notifications belonging to receipts of this creator
                creator_receipt_ids = {
                    r.receipt_id for r in self._receipts.values() if r.creator_id == creator_id
                }
                notifs = [n for n in notifs if n.receipt_id in creator_receipt_ids or n.receipt_id is None]
        return notifs

    # ── Rate Limit Backoff Persistence ────────────────────────────────────────

    def set_rate_limit_backoff(self, provider: AnalyticsProvider, until: datetime) -> None:
        """Persist provider rate-limit backoff until timestamp."""
        with self._lock:
            self._backoffs[provider.value] = until.isoformat()
            self._atomic_write_json(self._backoff_file, self._backoffs)

    def get_rate_limit_backoff(self, provider: AnalyticsProvider) -> Optional[datetime]:
        """Retrieve persisted rate-limit backoff timestamp for a provider."""
        with self._lock:
            val = self._backoffs.get(provider.value)
            if not val:
                return None
            try:
                dt = datetime.fromisoformat(val)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except Exception:
                return None
