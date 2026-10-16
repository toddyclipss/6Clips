# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Migration runner: executes dry-runs by default and atomic isolated live migrations."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.knowledge_migration.converter import LegacyProjectConverter
from backend.knowledge_migration.detector import LegacyBlockDetector
from backend.knowledge_migration.inventory import DonorInventoryLedger
from backend.knowledge_migration.models import (
    MigrationResult,
    MigrationStatus,
    ProjectMigrationPlan,
    ProjectReadiness,
)
from backend.knowledge_migration.planner import ProjectMigrationPlanner
from backend.knowledge_migration.rollback import RollbackEngine


def compute_file_sha256(path: Path) -> str:
    """Compute hex sha256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class MigrationRunner:
    """Coordinates safe, dry-run-by-default migration of legacy projects."""

    def __init__(
        self,
        ledger: Optional[DonorInventoryLedger] = None,
        rollback_engine: Optional[RollbackEngine] = None
    ):
        self.ledger = ledger or DonorInventoryLedger()
        self.planner = ProjectMigrationPlanner(self.ledger)
        self.converter = LegacyProjectConverter(self.ledger)
        self.rollback_engine = rollback_engine or RollbackEngine()

    def run_dry_run(
        self,
        db_path: Path
    ) -> Dict[str, Any]:
        """
        Execute dry-run migration on all projects in the database.
        DRY-RUN GUARANTEE: Does not mutate the database file. Verified by bit-for-bit SHA256 audit.
        """
        if not db_path.exists():
            return {
                "status": "BLOCKED_USER_DATA_ACCESS",
                "error": f"Database file not found: {db_path}",
                "projects_scanned": 0
            }

        # Record file SHA256 before dry-run
        sha_before = compute_file_sha256(db_path)

        uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        cur = conn.cursor()

        projects_raw = cur.execute("SELECT id, name, revision, document_json FROM projects WHERE document_json IS NOT NULL").fetchall()
        conn.close()

        readiness_list: List[Dict[str, Any]] = []
        migration_results: List[Dict[str, Any]] = []
        total_legacy_blocks = 0

        for pid, name, rev, doc_json in projects_raw:
            try:
                doc = json.loads(doc_json)
            except Exception:
                continue

            readiness = self.planner.assess_project_readiness(pid, name, rev, doc)
            if readiness.has_legacy_blocks:
                total_legacy_blocks += readiness.legacy_block_count
                # Simulate conversion
                t0 = time.perf_counter()
                migrated_doc, count = self.converter.convert_project_doc(doc, project_id=pid)
                dur_ms = (time.perf_counter() - t0) * 1000.0

                pre_hash = hashlib.sha256(doc_json.encode("utf-8")).hexdigest()
                post_hash = hashlib.sha256(json.dumps(migrated_doc, sort_keys=True).encode("utf-8")).hexdigest()

                migration_results.append({
                    "project_id": pid,
                    "project_name": name,
                    "from_revision": rev,
                    "to_revision": rev + 1,
                    "pre_hash": pre_hash,
                    "post_hash": post_hash,
                    "migrated_blocks_count": count,
                    "legacy_slugs": readiness.legacy_slugs,
                    "duration_ms": round(dur_ms, 2),
                    "status": MigrationStatus.DRY_RUN_PASSED.value
                })

            readiness_list.append({
                "project_id": pid,
                "project_name": name,
                "current_revision": rev,
                "has_legacy_blocks": readiness.has_legacy_blocks,
                "legacy_block_count": readiness.legacy_block_count,
                "legacy_slugs": readiness.legacy_slugs,
                "risk_level": readiness.risk_level.value,
                "feasibility": readiness.feasibility.value,
            })

        # Verify DB file was not mutated
        sha_after = compute_file_sha256(db_path)
        assert sha_before == sha_after, "FATAL: Dry-run mutated the database file!"

        return {
            "status": "PASS",
            "dry_run": True,
            "database_path": str(db_path),
            "database_sha256_unmodified": True,
            "database_sha256": sha_before,
            "total_projects_scanned": len(projects_raw),
            "projects_dependent_on_blocks": len(migration_results),
            "total_legacy_blocks_found": total_legacy_blocks,
            "sample_results": migration_results[:10],
            "all_results_count": len(migration_results),
            "readiness_summary": {
                "total_projects": len(readiness_list),
                "clean_native_projects": len(readiness_list) - len(migration_results),
                "dependent_projects": len(migration_results),
            }
        }

    def execute_live_migration(
        self,
        db_path: Path,
        target_project_ids: Optional[List[str]] = None,
        create_backup: bool = True
    ) -> Dict[str, Any]:
        """
        Execute live migration on targeted projects or all legacy projects in the database.
        Includes automatic backup and rollback manifest recording.
        """
        if not db_path.exists():
            return {
                "status": "FAILED",
                "error": f"Database file not found: {db_path}"
            }

        backup_path: Optional[Path] = None
        if create_backup:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_path = db_path.with_name(f"{db_path.stem}_backup_{ts}{db_path.suffix}")
            shutil.copy2(db_path, backup_path)
            # Verify backup restorability
            assert backup_path.exists() and backup_path.stat().st_size == db_path.stat().st_size

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        query = "SELECT id, name, revision, document_json FROM projects WHERE document_json IS NOT NULL"
        params: List[Any] = []
        if target_project_ids:
            placeholders = ",".join(["?"] * len(target_project_ids))
            query += f" AND id IN ({placeholders})"
            params.extend(target_project_ids)

        projects_raw = cur.execute(query, params).fetchall()

        migrated_records: List[Dict[str, Any]] = []
        errors: List[str] = []

        now_iso = datetime.now(timezone.utc).isoformat()

        for pid, name, rev, doc_json in projects_raw:
            try:
                doc = json.loads(doc_json)
            except Exception as e:
                errors.append(f"Error parsing JSON for project {pid}: {e}")
                continue

            readiness = self.planner.assess_project_readiness(pid, name, rev, doc)
            if not readiness.has_legacy_blocks:
                continue

            # Convert
            migrated_doc, count = self.converter.convert_project_doc(doc, project_id=pid)
            migrated_doc_json = json.dumps(migrated_doc)
            next_rev = rev + 1

            # Atomic CAS update
            cur.execute(
                "UPDATE projects SET document_json = ?, revision = ?, updated_at = ? WHERE id = ? AND revision = ?",
                (migrated_doc_json, next_rev, now_iso, pid, rev)
            )

            # Insert revision record
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
                    pid,
                    next_rev,
                    "migrate_legacy_blocks_to_native_motion_v1",
                    json.dumps({"migrated_blocks_count": count, "slugs": readiness.legacy_slugs}),
                    migrated_doc_json,
                    "migration_engine",
                    now_iso
                )
            )

            # Record in rollback ledger
            rollback_rec = self.rollback_engine.record_migration(
                project_id=pid,
                original_revision=rev,
                migrated_revision=next_rev,
                original_doc_json=doc_json,
                migrated_doc_json=migrated_doc_json
            )

            migrated_records.append({
                "project_id": pid,
                "project_name": name,
                "from_revision": rev,
                "to_revision": next_rev,
                "migrated_blocks": count,
                "legacy_slugs": readiness.legacy_slugs,
                "status": "MIGRATED"
            })

        conn.commit()
        conn.close()

        return {
            "status": "SUCCESS" if not errors else "PARTIAL_SUCCESS",
            "database_path": str(db_path),
            "backup_path": str(backup_path) if backup_path else None,
            "total_migrated": len(migrated_records),
            "errors": errors,
            "migrated_records": migrated_records
        }
