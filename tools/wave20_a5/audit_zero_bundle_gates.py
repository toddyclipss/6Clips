# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Tool: tools/wave20_a5/audit_zero_bundle_gates.py
Evaluates GT-39, GT-40, GT-41, and GT-42 gates based on empirical test evidence.
Saves evaluation report to tools/wave20_a5/gate_evaluation_report.json.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.knowledge_migration.zero_bundle_audit import ZeroBundleAuditor

MIGRATION_LEDGER = REPO_ROOT / "tools" / "wave20_a5" / "migration_readiness_ledger.json"
PROOF_REPORT = REPO_ROOT / "tools" / "wave20_a5" / "isolated_migration_proof_report.json"
GATE_REPORT = REPO_ROOT / "tools" / "wave20_a5" / "gate_evaluation_report.json"

def main():
    print("=== Wave 20 Agent 5: Gate Audit (GT-39 through GT-42) ===")

    dry_run_passed = False
    projects_with_blocks = 0
    if MIGRATION_LEDGER.exists():
        with open(MIGRATION_LEDGER, "r", encoding="utf-8") as f:
            data = json.load(f)
            dry_run_passed = (data.get("status") == "PASS" and data.get("database_sha256_unmodified") is True)
            projects_with_blocks = data.get("projects_dependent_on_blocks", 0)

    rollback_verified = False
    if PROOF_REPORT.exists():
        with open(PROOF_REPORT, "r", encoding="utf-8") as f:
            data = json.load(f)
            rollback_verified = (
                data.get("status") == "PASS"
                and data.get("bit_for_bit_rollback_verified") is True
                and data.get("physical_mp4_proof", {}).get("codec_name") == "h264"
            )

    auditor = ZeroBundleAuditor()
    gates = auditor.evaluate_wave20_gates(
        projects_with_blocks_count=projects_with_blocks,
        dry_run_passed=dry_run_passed,
        rollback_verified=rollback_verified
    )

    print("\n--- Evaluated Gates ---")
    for gid in ["GT-39", "GT-40", "GT-41", "GT-42"]:
        info = gates[gid]
        print(f"[{info['status']}] {gid}: {info['name']}")
        print(f"      Notes: {info['notes']}")

    print(f"\nOverall Wave 20 Foundation Gate: {'PASS' if gates['WAVE20_FOUNDATION_PASS'] else 'BLOCKED'}")
    print(f"Full Zero-Imported-Bundle Cutover Gate: {'PASS' if gates['FULL_MIGRATION_COMPLETE'] else 'PENDING_OWNER_DATABASE_CUTOVER'}")

    with open(GATE_REPORT, "w", encoding="utf-8") as f:
        json.dump(gates, f, indent=2)

    print(f"\nGate report saved to: {GATE_REPORT}")

if __name__ == "__main__":
    main()
