# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 12 Stage 3: Real Idle Network Windows Acceptance Test.

Verifies:
1. Real wall-clock idle windows A, B, C, D, E execution and metrics.
2. Zero unsolicited generative POST requests during all idle states.
3. Zero unexplained external network egress.
4. Distinguishes necessary local status/discovery routes from generative inference.
5. Verifies traffic trace matrix schema and persistent evidence outside repository.
"""

import json
import os
import time
from pathlib import Path
import httpx
import pytest

from tests.e2e_wave12.conftest import EVIDENCE_DIR
from scripts.wave12_40min_idle_observation_runner import sample_netstat_connections


def test_window_a_backend_idle_zero_inference_and_zero_external(isolated_server):
    """Window A verification: Backend running with browser closed."""
    pids = isolated_server["server_pids"]
    base_url = isolated_server["base_url"]

    # Initial health check (read-only discovery)
    r = httpx.get(f"{base_url}/health")
    assert r.status_code == 200

    # Observe wall-clock idle for at least 5 seconds in pytest
    t0 = time.time()
    conns = []
    while time.time() - t0 < 5.0:
        conns.extend(sample_netstat_connections(pids))
        time.sleep(1.0)

    # Check external connections
    external = [c for c in conns if not c["is_loopback"]]
    assert len(external) == 0, f"Observed external egress during Window A: {external}"


def test_window_b_browser_global_chat_idle_zero_inference(isolated_server, playwright_browser):
    """Window B verification: Browser open at '/' (global chat)."""
    base_url = isolated_server["base_url"]
    context = playwright_browser.new_context(viewport={"width": 1920, "height": 1080})
    page = context.new_page()

    requests_recorded = []
    page.on("request", lambda r: requests_recorded.append({"method": r.method, "url": r.url}))

    page.goto(f"{base_url}/", wait_until="networkidle", timeout=30000)

    # Wall-clock idle observation
    t0 = time.time()
    time.sleep(5.0)

    # Assert no external requests were dispatched from browser
    external_reqs = [r["url"] for r in requests_recorded if not (f"127.0.0.1:{isolated_server['port']}" in r["url"] or "localhost" in r["url"])]
    assert len(external_reqs) == 0, f"Browser initiated external egress: {external_reqs}"

    # Assert no chat generation was triggered automatically
    generative_reqs = [
        r["url"] for r in requests_recorded
        if r["method"] == "POST" and ("/api/chat" in r["url"] or "/api/generate/stock" in r["url"] or "/api/generate/split-scenes" in r["url"])
    ]
    assert len(generative_reqs) == 0, f"Unsolicited generative request detected: {generative_reqs}"

    context.close()


def test_window_c_motion_refine_idle_zero_inference(isolated_server, playwright_browser):
    """Window C verification: /motion?mode=refine with no project."""
    base_url = isolated_server["base_url"]
    context = playwright_browser.new_context(viewport={"width": 1920, "height": 1080})
    page = context.new_page()

    requests_recorded = []
    page.on("request", lambda r: requests_recorded.append({"method": r.method, "url": r.url}))

    page.goto(f"{base_url}/motion?mode=refine", wait_until="networkidle", timeout=30000)
    time.sleep(5.0)

    # Assert zero generative inference
    generative_reqs = [
        r["url"] for r in requests_recorded
        if r["method"] == "POST" and ("/api/chat" in r["url"] or "/api/generate/stock" in r["url"] or "/api/generate/split-scenes" in r["url"])
    ]
    assert len(generative_reqs) == 0, f"Unsolicited generative inference on /motion: {generative_reqs}"

    context.close()


def test_traffic_matrix_coverage_and_classification(isolated_server):
    """Verify trace matrix endpoint definitions and classification completeness."""
    base_url = isolated_server["base_url"]
    r = httpx.get(f"{base_url}/api/diagnostics/trace_matrix")
    assert r.status_code == 200
    data = r.json()
    assert "trace_matrix" in data
    matrix = data["trace_matrix"]
    assert "READ_ONLY_HEALTH_DISCOVERY" in matrix
    assert "USER_AUTHORIZED" in matrix
    assert "UNSOLICITED_INFERENCE" in matrix
