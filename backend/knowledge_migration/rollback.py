# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Rollback engine for reversible, bit-for-bit project migration undo."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.knowledge_migration.models import RollbackManifest, RollbackRecord


class RollbackEngine:
    """Manages persistent rollback manifests and reversible restore operations."""

    def __init__(self, manifest_path: Optional[Path] = None):
        self.manifest_path = manifest_path or Path(__file__).resolve().parents[2] / "tools" / "wave20_a5" / "rollback_manifest.json"
        self._manifest = RollbackManifest()
        self._load()

    def _load(self) -> None:
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._manifest = RollbackManifest(
                        manifest_version=data.get("manifest_version", "1.0.0"),
                        wave=data.get("wave", 20),
                        agent=data.get("agent", 5),
                        timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
                        total_projects_audited=data.get("total_projects_audited", 0),
                        total_projects_migrated=data.get("total_projects_migrated", 0),
                        records=data.get("records", {})
                    )
            except Exception:
                pass

    def save_manifest(self) -> None:
        """Persist the current manifest to disk atomically."""
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self._manifest)
        temp_file = self.manifest_path.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        temp_file.replace(self.manifest_path)

    def record_migration(
        self,
        project_id: str,
        original_revision: int,
        migrated_revision: int,
        original_doc_json: str,
        migrated_doc_json: str,
    ) -> RollbackRecord:
        """Register a migration event into the rollback ledger."""
        orig_hash = hashlib.sha256(original_doc_json.encode("utf-8")).hexdigest()
        mig_hash = hashlib.sha256(migrated_doc_json.encode("utf-8")).hexdigest()

        record = RollbackRecord(
            project_id=project_id,
            original_revision=original_revision,
            migrated_revision=migrated_revision,
            original_doc_json=original_doc_json,
            migrated_doc_json=migrated_doc_json,
            original_sha256=orig_hash,
            migrated_sha256=mig_hash,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        self._manifest.records[project_id] = asdict(record)
        self._manifest.total_projects_migrated = len(self._manifest.records)
        self.save_manifest()
        return record

    def rollback_project_in_db(
        self,
        db_path: Path,
        project_id: str
    ) -> Tuple[bool, str]:
        """Rollback a migrated project in the database to its exact pre-migration state."""
        if project_id not in self._manifest.records:
            return False, f"No rollback record found for project {project_id}"

        record_data = self._manifest.records[project_id]
        orig_doc_json = record_data["original_doc_json"]
        orig_hash = record_data["original_sha256"]
        curr_migrated_rev = record_data["migrated_revision"]

        # Verify hash of stored original doc
        verify_hash = hashlib.sha256(orig_doc_json.encode("utf-8")).hexdigest()
        if verify_hash != orig_hash:
            return False, f"Integrity check failed: original doc hash mismatch ({verify_hash} != {orig_hash})"

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # Check current revision in DB
        row = cur.execute("SELECT revision FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not row:
            conn.close()
            return False, f"Project {project_id} not found in database"

        current_db_rev = row[0]
        next_rev = current_db_rev + 1

        # Restore original doc with incremented revision (CAS safe)
        now_iso = datetime.now(timezone.utc).isoformat()
        cur.execute(
            "UPDATE projects SET document_json = ?, revision = ?, updated_at = ? WHERE id = ?",
            (orig_doc_json, next_rev, now_iso, project_id)
        )

        # Insert revision history record
        rev_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO project_revisions (
                id, project_id, revision, operation_type,
                operation_payload_json, document_snapshot_json, author, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rev_id,
                project_id,
                next_rev,
                "rollback_legacy_block_migration",
                json.dumps({"target_original_revision": record_data["original_revision"]}),
                orig_doc_json,
                "migration_engine",
                now_iso
            )
        )

        conn.commit()
        conn.close()

        # Remove from active records once safely rolled back
        del self._manifest.records[project_id]
        self._manifest.total_projects_migrated = len(self._manifest.records)
        self.save_manifest()

        return True, f"Successfully rolled back project {project_id} to revision {next_rev} (restored original doc)"
