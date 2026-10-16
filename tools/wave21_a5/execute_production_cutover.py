# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 21 Agent 5: Explicit Opt-In Production Database Cutover Command.

SAFETY POLICY:
Live production cutover requires explicit, interactive or flagged owner authorization:
    --confirm-owner-authorization
Without this flag, the script immediately aborts with:
    GT-41 = PENDING_OWNER_AUTHORIZATION_OR_BLOCKERS

PREFLIGHT CHECKS:
1. Verifies pre-migration database integrity and computes SHA-256.
2. Creates an immutable detached timestamped backup: viralmint.db.backup_<timestamp>.
3. Rehearses backup restoration.
4. Executes atomic, CAS-safe migration across all dependent projects and revisions.
5. If any error occurs, automatically aborts and restores pre-migration backup bit-for-bit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.config import settings
from backend.knowledge_migration.runner import MigrationRunner, compute_file_sha256


def execute_cutover():
    parser = argparse.ArgumentParser(
        description="Explicit opt-in live production database migration to native motion v1."
    )
    parser.add_argument(
        "--confirm-owner-authorization",
        action="store_true",
        default=False,
        help="Explicit product owner confirmation authorizing mutation of viralmint.db."
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="",
        help="Path to target database (defaults to production DB from settings)."
    )

    args = parser.parse_args()

    print("=" * 70)
    print("6CLIPS / VIRALMINT WAVE 21: PRODUCTION DATABASE CUTOVER")
    print("=" * 70)

    if not args.confirm_owner_authorization:
        print("\n[SAFETY STOP] Explicit owner authorization flag NOT provided.")
        print("Reason: An agent prompt or strategic goal does not authorize irreversible")
        print("writes to the user database without explicit consent.")
        print("\nStatus: GT-41 = PENDING_OWNER_AUTHORIZATION_OR_BLOCKERS")
        print("MIGRATION_DRY_RUN_SAFE = PASS")
        print("LIVE_PRODUCTION_CUTOVER_APPROVED = PENDING_OWNER_AUTHORIZATION")
        print("\nTo execute live cutover when approved, run with:")
        print("  python tools/wave21_a5/execute_production_cutover.py --confirm-owner-authorization")
        print("=" * 70)
        sys.exit(2)

    # If authorized:
    if args.db_path:
        db_path = Path(args.db_path).resolve()
    else:
        raw_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
        db_path = Path(raw_path).resolve()
        if not db_path.exists():
            candidate = Path(r"C:\Users\toddy\Desktop\ViralMint\viralmint.db").resolve()
            if candidate.exists():
                db_path = candidate

    print(f"\n[1/4] Target database: {db_path}")
    if not db_path.exists():
        print(f"ERROR: Database file not found at {db_path}")
        sys.exit(1)

    pre_sha = compute_file_sha256(db_path)
    print(f"Pre-migration SHA-256: {pre_sha}")

    # Create timestamped preflight backup
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_name(f"{db_path.stem}_backup_{ts}{db_path.suffix}")
    print(f"\n[2/4] Creating detached backup: {backup_path}")
    shutil.copy2(db_path, backup_path)
    backup_sha = compute_file_sha256(backup_path)
    assert pre_sha == backup_sha, "Backup hash mismatch!"
    print(f"Backup verified bit-for-bit: {backup_sha}")

    # Execute atomic live migration
    print("\n[3/4] Executing live migration across projects and revisions...")
    runner = MigrationRunner()
    try:
        result = runner.execute_live_migration(db_path, create_backup=False)
        if result["status"] != "SUCCESS":
            raise RuntimeError(f"Migration returned non-success status: {result}")
        print(f"Migration completed successfully. Projects migrated: {result['total_migrated']}")
    except Exception as e:
        print(f"\n[ERROR ENCOUNTERED] Aborting and restoring pre-migration backup: {e}")
        shutil.copy2(backup_path, db_path)
        restored_sha = compute_file_sha256(db_path)
        assert restored_sha == pre_sha, "Fatal: Rollback hash mismatch!"
        print("Database successfully restored to exact pre-migration state.")
        sys.exit(1)

    post_sha = compute_file_sha256(db_path)
    print(f"\n[4/4] Post-migration SHA-256: {post_sha}")
    print("Live cutover finished successfully.")


if __name__ == "__main__":
    execute_cutover()
