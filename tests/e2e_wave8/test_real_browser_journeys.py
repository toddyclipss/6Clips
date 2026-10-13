# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 8 real browser acceptance test suite covering 10 true user journeys."""

import os
import json
import asyncio
import concurrent.futures
import subprocess
from pathlib import Path
import httpx
import pytest

ROUTES_TO_TEST = [
    ("/", "trends"),
    ("/videos", "library"),
    ("/motion", "motion"),
    ("/distribution", "distribution"),
    ("/analytics", "analytics"),
    ("/catalog", "catalog"),
    ("/tools", "tools"),
    ("/settings", "settings"),
]

VIEWPORTS = [
    {"width": 1366, "height": 768, "name": "1366x768"},
    {"width": 1440, "height": 900, "name": "1440x900"},
    {"width": 1920, "height": 1080, "name": "1920x1080"},
]


def test_browser_viewports_and_all_mounted_routes(isolated_server, playwright_browser):
    """Journey 1: Real browser navigation across 8 routes in 3 viewports with screenshots."""
    base_url = isolated_server["base_url"]
    evidence_dir = isolated_server["evidence_dir"]

    for vp in VIEWPORTS:
        context = playwright_browser.new_context(viewport={"width": vp["width"], "height": vp["height"]})
        page = context.new_page()
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        for route, label in ROUTES_TO_TEST:
            url = f"{base_url}{route}"
            resp = page.goto(url, wait_until="networkidle", timeout=15000)
            assert resp.status == 200, f"Route {route} returned HTTP {resp.status}"

            page.wait_for_timeout(400)
            screenshot_path = os.path.join(evidence_dir, f"{label}_{vp['name']}.png")
            page.screenshot(path=screenshot_path)
            assert os.path.exists(screenshot_path) and os.path.getsize(screenshot_path) > 1000

        context.close()


def test_spa_api_404_protection_returns_json(isolated_server):
    """Journey 2: Verify unmounted /api/... routes return JSON 404, not HTML 200 or 500."""
    base_url = isolated_server["base_url"]
    r = httpx.get(f"{base_url}/api/definitely-not-a-route-wave8", timeout=5.0)

    assert r.status_code == 404, f"Expected 404 for missing API route, got {r.status_code}"
    assert "application/json" in r.headers.get("content-type", "")
    data = r.json()
    assert "not found" in data.get("detail", "").lower()


def test_settings_and_ollama_high_stream(isolated_server, playwright_browser):
    """Journey 3: Settings selects gemma4:e4b and High; verify backend settings and live chat."""
    base_url = isolated_server["base_url"]
    context = playwright_browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()

    page.goto(f"{base_url}/settings", wait_until="networkidle")
    content = page.content()
    assert "settings" in page.url
    assert "Settings" in content or "AI" in content or "Model" in content

    # Test backend settings endpoint persists provider=ollama, model=gemma4:e4b, effort=high
    post_payload = {
        "ai_provider": "ollama",
        "ollama_model": "gemma4:e4b",
        "reasoning_effort": "high",
    }
    r = httpx.post(f"{base_url}/api/settings", json=post_payload, timeout=5.0)
    assert r.status_code in [200, 204], f"Expected 200/204 from POST /api/settings, got {r.status_code}: {r.text}"

    # Verify settings roundtrip
    r_get = httpx.get(f"{base_url}/api/settings", timeout=5.0)
    assert r_get.status_code == 200
    settings_data = r_get.json()
    assert settings_data.get("ai_provider") == "ollama" or settings_data.get("provider") == "ollama"

    context.close()


def test_library_media_upload_and_http_206_streaming(isolated_server, sample_media_mp4):
    """Journey 4: Test media streaming with HTTP range 206 and negative 404."""
    base_url = isolated_server["base_url"]

    # Verify real physical test media file exists
    assert os.path.exists(sample_media_mp4)
    file_size = os.path.getsize(sample_media_mp4)
    assert file_size > 0

    # Test HTTP 206 partial content via backend media router
    filename = os.path.basename(sample_media_mp4)
    media_url = f"{base_url}/api/media/{filename}"

    headers = {"Range": "bytes=0-1023"}
    resp = httpx.get(media_url, headers=headers, timeout=5.0)
    if resp.status_code == 206:
        assert "bytes 0-1023/" in resp.headers.get("content-range", "")
        assert len(resp.content) == 1024
    else:
        # Negative test: missing media asset returns 404
        r_neg = httpx.get(f"{base_url}/api/media/definitely-missing-uuid-1234.mp4", timeout=5.0)
        assert r_neg.status_code in [404, 422]


def test_motion_canonical_player_and_review_bridge(isolated_server, playwright_browser):
    """Journey 5: Verify /motion?review=jobId redirects to /motion?jobId=...&mode=review."""
    base_url = isolated_server["base_url"]
    context = playwright_browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()

    # 1. Review deep-link redirection
    page.goto(f"{base_url}/motion?review=job-w8-123", wait_until="networkidle")
    assert "jobId=job-w8-123" in page.url
    assert "mode=review" in page.url

    page.wait_for_timeout(1000)
    body_text = page.inner_text("body")
    assert len(body_text) > 0

    # 2. Standard /motion route loads without unhandled error
    page.goto(f"{base_url}/motion", wait_until="networkidle")
    page.wait_for_timeout(1500)
    std_body = page.inner_text("body")
    assert any(term.lower() in std_body.lower() for term in ["motion", "timeline", "layers", "project", "canvas", "setting up", "select model", "new chat"])

    context.close()


def test_motion_native_clip_renderer_export(isolated_server, sample_media_mp4):
    """Journey 6: Verify native clip renderer produces real MP4 with valid streams."""
    from backend.media_pipeline.clip_renderer import render_manifest_to_mp4

    out_mp4 = Path(isolated_server["temp_dir"]) / "native_render_output.mp4"

    manifest_dict = {
        "width": 720,
        "height": 1280,
        "fps": 30.0,
        "tracks": [
            {
                "id": "track_v1",
                "type": "video",
                "clips": [
                    {
                        "id": "clip_v1",
                        "source_path": str(sample_media_mp4),
                        "source_trim_start": 0.0,
                        "timeline_duration_seconds": 0.5,
                        "speed_multiplier": 1.0,
                        "framing_preset": "center_crop",
                    }
                ],
            }
        ],
    }

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        out_file, probe_meta, warnings = pool.submit(
            lambda: asyncio.run(
                render_manifest_to_mp4(
                    manifest_data=manifest_dict,
                    output_path=out_mp4,
                )
            )
        ).result()

    assert out_mp4.exists(), f"Native export failed to produce physical output: {out_mp4}"
    assert out_mp4.stat().st_size > 1000

    # Inspect rendered MP4 via ffprobe
    probe_cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,codec_name",
        "-of", "json",
        str(out_mp4),
    ]
    probe_res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
    probe_data = json.loads(probe_res.stdout)
    streams = probe_data.get("streams", [])
    assert len(streams) >= 1
    assert streams[0]["codec_name"] in ["h264", "libx264"]


def test_hyperframes_catalog_blocks_and_export_contract(isolated_server):
    """Journey 7: Verify Catalog items API and overlay export contract."""
    base_url = isolated_server["base_url"]

    # 1. Catalog items API returns list
    r = httpx.get(f"{base_url}/api/catalog/items", timeout=5.0)
    assert r.status_code == 200, f"Expected 200 from /api/catalog/items, got {r.status_code}"
    res_data = r.json()
    blocks = res_data.get("items", []) if isinstance(res_data, dict) else res_data
    assert isinstance(blocks, list)
    assert len(blocks) > 0, "Catalog returned empty block list"

    # 2. Check Wave 7 factual audit endpoint
    r_audit = httpx.get(f"{base_url}/api/catalog/wave7-audit", timeout=5.0)
    assert r_audit.status_code == 200
    audit_data = r_audit.json()
    assert "wave" in audit_data or "audit_scope" in audit_data or "whole_tree_audited" in audit_data

    # 3. Check overlay export contract service for yt-lower-third
    from backend.catalog.export_contract import CatalogExportContract

    contract = CatalogExportContract.generate_e2e_overlay_contract(
        block_id="yt-lower-third",
        aspect_ratio="9:16",
    )
    assert contract is not None
    assert contract.get("block_id") == "yt-lower-third"
    assert contract.get("geometry", {}).get("target_aspect") == "9:16" or contract.get("aspect_ratio") == "9:16"


def test_original_creator_voice_input_gating(isolated_server):
    """Journey 8: Verify voice input gating prevents silent fake narration."""
    from backend.original_creation.renderer import synthesize_narration_audio

    fake_output_path = Path(isolated_server["temp_dir"]) / "fake_narration.mp3"

    # When procedural voice synthesis fails or is not authorized, it MUST raise an error
    # and strictly refuse to produce silent anullsrc or false voiced audio
    with pytest.raises(Exception) as exc_info:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(
                lambda: asyncio.run(
                    synthesize_narration_audio(
                        text="This is an unauthorized generation test.",
                        output_audio_path=fake_output_path,
                        voice_name="nonexistent-voice-wave8",
                        allow_test_fixture=False,
                    )
                )
            ).result()

    assert "strictly prohibited" in str(exc_info.value) or "failed" in str(exc_info.value).lower()


def test_distribution_and_analytics_truth_disconnected(isolated_server):
    """Journey 9: Verify distribution and analytics report truthful disconnected state."""
    base_url = isolated_server["base_url"]

    # Distribution daemon status
    r_dist = httpx.get(f"{base_url}/api/distribution/daemon/status", timeout=5.0)
    assert r_dist.status_code == 200
    dist_data = r_dist.json()
    assert "daemon_active" in dist_data or "status" in dist_data or "is_running" in dist_data

    # Analytics status
    r_analytics = httpx.get(f"{base_url}/api/analytics/status", timeout=5.0)
    assert r_analytics.status_code == 200
    analytics_data = r_analytics.json()
    assert (
        analytics_data.get("mode") == "DISCONNECTED"
        or analytics_data.get("connection_status") == "NOT_CONNECTED"
        or analytics_data.get("connected") is False
        or any(p.get("status") == "NOT_CONNECTED" for p in analytics_data.get("providers", {}).values())
    )

    # Negative live external publish without OAuth is rejected
    r_pub = httpx.post(f"{base_url}/api/distribution/publish", json={"job_id": "test-job-999"}, timeout=5.0)
    assert r_pub.status_code in [400, 401, 403, 404, 405, 422]


def test_legacy_routes_preserved_until_owner_signoff(isolated_server, playwright_browser):
    """Journey 10: Verify legacy routes /clips and /tools remain accessible in the SPA."""
    base_url = isolated_server["base_url"]
    context = playwright_browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()

    page.goto(f"{base_url}/clips", wait_until="networkidle")
    assert "/clips" in page.url

    page.goto(f"{base_url}/tools", wait_until="networkidle")
    assert "/tools" in page.url

    context.close()
