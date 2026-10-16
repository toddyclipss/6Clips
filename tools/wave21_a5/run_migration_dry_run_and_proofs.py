# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 21 Agent 5: Migration Dry-Run, Rollback Integrity Proof, Physical Video Render,
and Truth Gate Evaluator.
Strictly READ-ONLY on production database.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.config import settings
from backend.knowledge_migration.converter import LegacyProjectConverter
from backend.knowledge_migration.runner import MigrationRunner, compute_file_sha256
from backend.knowledge_migration.zero_bundle_audit import ZeroBundleAuditor
from backend.native_motion.renderer import NativeMotionRenderer
from backend.native_motion.schema import NativeMotionSpec


def run_full_dry_run_and_proofs():
    print("[1/5] Discovering production database...")
    db_url = settings.DATABASE_URL
    raw_path = db_url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
    prod_db = Path(raw_path).resolve()
    if not prod_db.exists():
        candidate = Path(r"C:\Users\toddy\Desktop\ViralMint\viralmint.db").resolve()
        if candidate.exists():
            prod_db = candidate

    print(f"Production DB: {prod_db} (size={prod_db.stat().st_size} bytes)")
    prod_sha_initial = compute_file_sha256(prod_db)
    print(f"Initial DB SHA-256: {prod_sha_initial}")

    out_dir = REPO_ROOT / "tools" / "wave21_a5"
    out_dir.mkdir(parents=True, exist_ok=True)
    proofs_dir = out_dir / "proofs"
    proofs_dir.mkdir(parents=True, exist_ok=True)
    scratch_dir = out_dir / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    # 1. Execute Dry Run
    print("\n[2/5] Running dry-run migration across projects and revisions...")
    runner = MigrationRunner()
    dry_run_report = runner.run_dry_run(prod_db)

    prod_sha_post_dry_run = compute_file_sha256(prod_db)
    assert prod_sha_initial == prod_sha_post_dry_run, "FATAL: Dry run modified production database!"
    print(f"Verified DB immutability post dry-run: {prod_sha_post_dry_run}")
    print(f"Projects scanned: {dry_run_report['total_projects_scanned']}, dependent: {dry_run_report['projects_dependent_on_blocks']}")
    print(f"Revisions scanned: {dry_run_report['total_revisions_scanned']}, dependent: {dry_run_report['revisions_dependent_on_blocks']}")

    # Save migration_execution_ledger.json
    ledger_path = out_dir / "migration_execution_ledger.json"
    with open(ledger_path, "w", encoding="utf-8") as f:
        json.dump(dry_run_report, f, indent=2)
    print(f"Saved: {ledger_path}")

    # 2. Run Rollback Rehearsal & Simulated Failures
    print("\n[3/5] Running rollback rehearsals and simulated failures at 25% and 75%...")
    rollback_report = runner.run_rollback_rehearsal(
        source_db_path=prod_db,
        scratch_dir=scratch_dir,
    )
    prod_sha_post_rehearsal = compute_file_sha256(prod_db)
    assert prod_sha_initial == prod_sha_post_rehearsal, "FATAL: Rehearsal modified production database!"

    rollback_proof_path = out_dir / "rollback_and_integrity_proof.json"
    with open(rollback_proof_path, "w", encoding="utf-8") as f:
        json.dump(rollback_report, f, indent=2)
    print(f"Saved: {rollback_proof_path}")
    for k, v in rollback_report["rehearsals"].items():
        print(f"  {k}: bit-for-bit match={v['bit_for_bit_identical']} (status={v['status']})")

    # 3. Evaluate Physical Removal Gate (GT-41)
    print("\n[4/5] Evaluating Wave 21 gates and GT-41 removal gate...")
    auditor = ZeroBundleAuditor()
    gate_evaluation = auditor.evaluate_wave21_gates(
        projects_with_blocks_count=dry_run_report["projects_dependent_on_blocks"],
        revisions_with_blocks_count=dry_run_report["revisions_dependent_on_blocks"],
        dry_run_passed=dry_run_report["status"] == "PASS",
        rollback_verified=rollback_report["status"] == "PASS",
        live_cutover_approved=False,  # Explicitly False: no owner consent provided
    )

    gate_report_path = out_dir / "physical_removal_gate.json"
    with open(gate_report_path, "w", encoding="utf-8") as f:
        json.dump(gate_evaluation, f, indent=2)
    print(f"Saved: {gate_report_path}")
    print(f"GT-39 status: {gate_evaluation['GT-39']['status']}")
    print(f"GT-40 status: {gate_evaluation['GT-40']['status']}")
    print(f"GT-41 status: {gate_evaluation['GT-41']['status']}")
    print(f"GT-42 status: {gate_evaluation['GT-42']['status']}")
    print(f"MIGRATION_DRY_RUN_SAFE: {gate_evaluation['MIGRATION_DRY_RUN_SAFE']}")
    print(f"LIVE_PRODUCTION_CUTOVER_APPROVED: {gate_evaluation['LIVE_PRODUCTION_CUTOVER_APPROVED']}")

    # 4. Render Physical Video Proof of a Migrated Project
    print("\n[5/5] Rendering physical MP4 video proof of migrated project...")
    sample_doc = {
        "schema_version": 1,
        "title": "Migrated Lower Third Proof",
        "aspect_ratio": "9:16",
        "timeline": {
            "fps": 30,
            "duration_seconds": 3.0,
            "tracks": [
                {
                    "id": "track_graphics",
                    "type": "graphics",
                    "clips": [
                        {
                            "id": "legacy_clip_01",
                            "type": "block",
                            "block_id": "lower-third-bild",
                            "start_seconds": 0.0,
                            "duration_seconds": 3.0,
                            "variables": {
                                "TXT_MAIN_1_Line": "DR. ELENA ROSTOVA",
                                "TXT_SUB": "CHIEF QUANTUM ARCHITECT"
                            }
                        }
                    ]
                }
            ]
        }
    }

    converter = LegacyProjectConverter()
    migrated_doc, count = converter.convert_project_doc(sample_doc, project_id="proof_proj")
    spec_file = next(f for f in migrated_doc["code"]["files"] if f["path"] == "native_motion/spec.json")
    spec_data = json.loads(spec_file["content"])
    spec = NativeMotionSpec.model_validate(spec_data)

    proof_mp4 = proofs_dir / "proof_migrated_lower_third.mp4"
    print(f"Rendering spec to MP4 via NativeMotionRenderer: {proof_mp4}")
    render_result = NativeMotionRenderer.render_to_mp4(
        spec=spec,
        output_mp4_path=proof_mp4,
        supersample=False
    )

    proof_meta = {
        "project_id": "proof_proj",
        "migrated_slug": "lower-third-bild",
        "rendered_mp4": str(proof_mp4),
        "sha256": render_result.sha256,
        "duration": render_result.duration,
        "dimensions": f"{render_result.width}x{render_result.height}",
        "fps": render_result.fps,
        "frame_count": render_result.frame_count,
        "codec_name": render_result.codec_name,
        "motion_delta_mid": render_result.motion_delta_mid,
        "motion_delta_end": render_result.motion_delta_end,
        "avg_luminance": render_result.avg_luminance,
        "fully_accepted": render_result.to_dict()["fully_accepted"],
        "rendered_at": datetime.now(timezone.utc).isoformat(),
    }

    proof_meta_file = proofs_dir / "proof_migrated_lower_third.json"
    with open(proof_meta_file, "w", encoding="utf-8") as f:
        json.dump(proof_meta, f, indent=2)

    print(f"\nProof render complete:")
    print(f"  File: {proof_mp4}")
    print(f"  SHA-256: {render_result.sha256}")
    print(f"  Dimensions: {render_result.width}x{render_result.height} @ {render_result.fps}fps")
    print(f"  Frame count: {render_result.frame_count}")
    print(f"  Codec: {render_result.codec_name}")
    print(f"  Motion delta (mid): {render_result.motion_delta_mid:.4f}")
    print(f"  Motion delta (end): {render_result.motion_delta_end:.4f}")
    print(f"  Avg luminance: {render_result.avg_luminance:.2f}")
    print(f"  Fully accepted: {proof_meta['fully_accepted']}")

    # Final DB check
    prod_sha_final = compute_file_sha256(prod_db)
    assert prod_sha_initial == prod_sha_final, "FATAL: Production DB modified at end of run!"
    print(f"\nProduction DB unmodified verified: {prod_sha_final}")


if __name__ == "__main__":
    run_full_dry_run_and_proofs()
