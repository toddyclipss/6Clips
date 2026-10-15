# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Capture visual proof of Motion Review & Create states across required viewports."""

import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

OUTPUT_DIR = Path("artifacts/motion_review")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VIEWPORTS = [
    {"name": "1366x768", "width": 1366, "height": 768},
    {"name": "1440x900", "width": 1440, "height": 900},
    {"name": "1920x1080", "width": 1920, "height": 1080},
]

MOCK_BATCH_DATA = {
    "schema_version": "production.v1",
    "job_id": "job_prod_demo_3clips",
    "run_id": "run_demo_fortnite_highlights",
    "contract_version": "1.0.0",
    "status": "COMPLETE",
    "outputs": [
        {
            "output_id": "clip_hook_1",
            "project_revision_id": "1",
            "artifact_id": "art_hook_1",
            "media_probe": {
                "width": 1080, "height": 1920, "duration_seconds": 10.0,
                "video_codec": "h264", "audio_codec": "aac", "fps": 30.0,
                "audio_channels": 2, "sample_rate": 48000, "content_hash": "A1B2C3D4",
                "mean_volume_db": -22.4,
            },
            "source_ranges": [
                {
                    "asset_id": "game_1", "start_seconds": 0.0, "end_seconds": 10.0,
                    "duration_seconds": 10.0, "editorial_reason": "Hook & Early Engagement: Captures viewer interest with rapid drop-in",
                    "relevance_score": 9.2,
                }
            ],
            "checks": {"technical": "PASS", "contract": "PASS", "editorial": "NOT_ASSESSED"},
            "preview_ref": "/api/media/production/artifacts/art_hook_1/stream",
            "warnings": ["Center crop 9:16 applied: verify HUD and reticle in player."],
            "state": "SUCCEEDED",
        },
        {
            "output_id": "clip_mid_2",
            "project_revision_id": "2",
            "artifact_id": "art_mid_2",
            "media_probe": {
                "width": 1080, "height": 1920, "duration_seconds": 10.0,
                "video_codec": "h264", "audio_codec": "aac", "fps": 30.0,
                "audio_channels": 2, "sample_rate": 48000, "content_hash": "E5F6G7H8",
                "mean_volume_db": -20.8,
            },
            "source_ranges": [
                {
                    "asset_id": "game_1", "start_seconds": 12.0, "end_seconds": 22.0,
                    "duration_seconds": 10.0, "editorial_reason": "Mid-Game Action & Tension: Intense combat encounter in arena",
                    "relevance_score": 8.7,
                }
            ],
            "checks": {"technical": "PASS", "contract": "PASS", "editorial": "NOT_ASSESSED"},
            "preview_ref": "/api/media/production/artifacts/art_mid_2/stream",
            "warnings": ["Center crop 9:16 applied: verify HUD and reticle in player."],
            "state": "SUCCEEDED",
        },
        {
            "output_id": "clip_climax_3",
            "project_revision_id": "3",
            "artifact_id": "art_climax_3",
            "media_probe": {
                "width": 1080, "height": 1920, "duration_seconds": 10.0,
                "video_codec": "h264", "audio_codec": "aac", "fps": 30.0,
                "audio_channels": 2, "sample_rate": 48000, "content_hash": "I9J0K1L2",
                "mean_volume_db": -19.5,
            },
            "source_ranges": [
                {
                    "asset_id": "game_1", "start_seconds": 24.0, "end_seconds": 34.0,
                    "duration_seconds": 10.0, "editorial_reason": "Climax & Resolution: Final squad wipe and Victory Royale",
                    "relevance_score": 9.5,
                }
            ],
            "checks": {"technical": "PASS", "contract": "PASS", "editorial": "NOT_ASSESSED"},
            "preview_ref": "/api/media/production/artifacts/art_climax_3/stream",
            "warnings": ["Center crop 9:16 applied: verify HUD and reticle in player."],
            "state": "SUCCEEDED",
        },
    ],
    "blockers": [],
    "evidence_refs": ["artifact:art_hook_1", "artifact:art_mid_2", "artifact:art_climax_3"],
}

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        for vp in VIEWPORTS:
            context = await browser.new_context(viewport={"width": vp["width"], "height": vp["height"]})
            page = await context.new_page()

            async def handle_batch_route(route):
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(MOCK_BATCH_DATA),
                )

            await page.route("**/api/media/production/batch/job_prod_demo_3clips", handle_batch_route)

            # Navigate to Review mode with mock batch
            url = f"http://127.0.0.1:16888/motion?mode=review&jobId=job_prod_demo_3clips"
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(3000)

            shot_path = OUTPUT_DIR / f"motion_review_{vp['name']}.png"
            await page.screenshot(path=str(shot_path), full_page=False)
            print(f"Captured: {shot_path} ({shot_path.stat().st_size} bytes)")
            await context.close()

        # Capture Empty Create state at 1920x1080
        ctx_empty = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page_empty = ctx_empty.new_page()
        page_empty = await ctx_empty.new_page()
        await page_empty.goto("http://127.0.0.1:16888/motion?mode=create", wait_until="domcontentloaded", timeout=20000)
        await page_empty.wait_for_timeout(3000)
        empty_path = OUTPUT_DIR / "motion_create_empty_1920x1080.png"
        await page_empty.screenshot(path=str(empty_path), full_page=False)
        print(f"Captured: {empty_path} ({empty_path.stat().st_size} bytes)")
        await ctx_empty.close()

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
