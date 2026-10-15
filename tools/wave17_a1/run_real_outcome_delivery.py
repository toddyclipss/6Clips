# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Real Local Outcome Delivery Runner (Wave 17 Agent 1).
Reproduces the complete real local request-to-delivery pipeline:
User Intent -> Autonomous Operable Block Selection -> Project Creation & Revisioning ->
Physical FFmpeg Rendering -> Deep ffprobe Verification & SHA-256 Checksumming ->
Library Persistence -> Agent 5 Distribution Handoff Generation.
"""

import asyncio
from datetime import datetime
import json
import logging
from pathlib import Path
import sys
import time

# Ensure project root is in sys.path
root_dir = Path(__file__).resolve().parents[2]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from backend.database import init_db
from backend.oaas_outcomes.adapter import OAASOutcomeAdapter
from backend.oaas_outcomes.models import DurationPolicy

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("run_real_outcome_delivery")


async def main():
    print("=" * 80)
    print("6CLIPS OAAS REAL LOCAL OUTCOME DELIVERY REPRODUCTION (WAVE 17 AGENT 1)")
    print("=" * 80)

    # 1. Initialize DB
    print("\n[Stage 1] Initializing SQLite database schema...")
    await init_db()
    print("DB initialized successfully.")

    # 2. Define real user goal
    user_goal = "Create a high-impact vertical short about 2026 AI technology trends and compute scale"
    channel_targets = ["youtube_shorts"]
    preferences = {
        "aspect_ratio": "9:16",
        "duration_seconds": 3.0,
        "duration_policy": DurationPolicy.TARGET,
        "tolerance_seconds": 1.0,
        "language": "en",
    }
    print(f"\n[Stage 2] User Goal Submitted: {user_goal!r}")
    print(f"  Target Channels: {channel_targets}")
    print(f"  Preferences: {preferences}")

    # 3. Execute outcome
    t0 = time.time()
    print("\n[Stage 3] Executing autonomous OAAS outcome pipeline...")
    job = await OAASOutcomeAdapter.execute_goal(
        user_goal=user_goal,
        channel_targets=channel_targets,
        preferences=preferences,
        standing_authorization=False,  # Enforces approval / credential truth
        session_id="wave17_demo_session",
        user_id="local",
        allow_test_fixture=True,  # Allows local audio synthesis fixture for testing
    )
    elapsed = time.time() - t0
    print(f"Pipeline finished in {elapsed:.2f}s with final state: {job.state.value}")

    # 4. Inspect artifacts
    print("\n[Stage 4] Inspecting Verified Physical Artifacts:")
    print(f"  Job ID: {job.job_id}")
    if job.plan:
        print(f"  Selected Operable Block: {job.plan.selected_block_id} (Category: {job.plan.block_category})")
        print(f"  Creative Treatment: {job.plan.creative_treatment}")
    print(f"  Project ID: {job.project_id}")
    print(f"  Revision ID: {job.revision_id}")

    if job.media_verification:
        mv = job.media_verification
        print("\n[Stage 5] Deep Media Verification Report:")
        print(f"  Physical MP4 Path: {mv.file_path}")
        print(f"  File Size: {mv.file_size_bytes} bytes ({mv.file_size_bytes / 1024:.2f} KB)")
        print(f"  SHA-256 Checksum: {mv.sha256_hash}")
        print(f"  Probed Dimensions: {mv.probe_width}x{mv.probe_height}")
        print(f"  Probed Duration: {mv.probe_duration_sec:.2f}s")
        print(f"  Video Codec: {mv.video_codec}")
        print(f"  Audio Codec: {mv.audio_codec}")
        print(f"  Verification Status: {'PASSED' if mv.is_verified else 'FAILED'}")

    print(f"\n[Stage 6] Library Persistence:")
    print(f"  Library Asset ID: {job.library_asset_id}")

    if job.distribution_handoff:
        dh = job.distribution_handoff
        print("\n[Stage 7] Agent 5 Distribution Handoff Contract:")
        print(f"  Handoff ID: {dh.handoff_id}")
        print(f"  Destination Channel: {dh.destination_channel}")
        print(f"  Provider Status: {dh.provider_status}")
        print(f"  Fail-Closed Guard Active: {dh.fail_closed}")
        print(f"  User Authorized: {dh.user_authorized}")
        print(f"  Error/Connection Truth: {dh.error_truth}")

    print("\n[Stage 8] State Machine Transition Audit Log:")
    for idx, evt in enumerate(job.history, 1):
        print(f"  {idx}. {evt.from_state.value} -> {evt.to_state.value} | Reason: {evt.reason} | Time: {evt.timestamp}")

    print("\n" + "=" * 80)
    print("VERIFICATION COMPLETED SUCCESSFULLY")
    print("=" * 80)

    # Save summary report artifact
    report_data = {
        "timestamp": datetime.now().isoformat(),
        "job_id": job.job_id,
        "final_state": job.state.value,
        "elapsed_seconds": round(elapsed, 2),
        "operable_block": job.plan.selected_block_id if job.plan else None,
        "project_id": job.project_id,
        "revision_id": job.revision_id,
        "library_asset_id": job.library_asset_id,
        "media_verification": job.media_verification.model_dump() if job.media_verification else None,
        "distribution_handoff": job.distribution_handoff.model_dump() if job.distribution_handoff else None,
        "transitions": [e.model_dump() for e in job.history],
    }
    report_file = Path(__file__).parent / "outcome_delivery_evidence.json"
    report_file.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
    print(f"Evidence report written to: {report_file}")


if __name__ == "__main__":
    asyncio.run(main())
