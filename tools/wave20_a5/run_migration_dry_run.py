# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Tool: tools/wave20_a5/run_migration_dry_run.py
Runs dry-run migration on all projects in viralmint.db with strict immutability checks.
Generates tools/wave20_a5/migration_readiness_ledger.json.
"""

import json
import sys
from pathlib import Path

# Add project root to path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.knowledge_migration.runner import MigrationRunner, compute_file_sha256

PROD_DB = Path(r"C:\Users\toddy\Desktop\ViralMint\viralmint.db")
OUTPUT_LEDGER = REPO_ROOT / "tools" / "wave20_a5" / "migration_readiness_ledger.json"

def main():
    print("=== Wave 20 Agent 5: Legacy Project Migration Dry-Run ===")
    if not PROD_DB.exists():
        print(f"ERROR: {PROD_DB} does not exist!")
        sys.exit(1)

    sha_pre = compute_file_sha256(PROD_DB)
    print(f"Production DB Path: {PROD_DB}")
    print(f"Production DB Pre-Run SHA256: {sha_pre}")

    runner = MigrationRunner()
    result = runner.run_dry_run(PROD_DB)

    sha_post = compute_file_sha256(PROD_DB)
    print(f"Production DB Post-Run SHA256: {sha_post}")
    assert sha_pre == sha_post, "CRITICAL ERROR: Production DB was mutated during dry run!"

    print("\n--- Dry Run Audit Results ---")
    print(f"Status: {result['status']}")
    print(f"Total Projects Scanned: {result['total_projects_scanned']}")
    print(f"Clean Native Projects: {result['readiness_summary']['clean_native_projects']}")
    print(f"Projects Dependent on Legacy Blocks: {result['projects_dependent_on_blocks']}")
    print(f"Total Legacy Block Clips Found: {result['total_legacy_blocks_found']}")

    with open(OUTPUT_LEDGER, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"\nMigration readiness ledger saved to: {OUTPUT_LEDGER}")
    print("DRY-RUN IMMUTABILITY GUARANTEE: 100% VERIFIED.")

if __name__ == "__main__":
    main()
