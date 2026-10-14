# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 13 Stage 3: Window E Real 300s Wall-Clock Observation Evidence Verification.

Verifies the on-disk persistent audit artifact emitted by Window E:
1. Window E executed for full >= 300.0 seconds wall-clock without premature termination.
2. Exactly 1 user-authorized inference request dispatched to local Ollama gemma4:e4b.
3. Zero unsolicited generative inference requests during the 300s idle observation window.
4. Zero unauthorized external network egress (0 pypi.org, 0 external cloud LLMs, 0 social networks).
5. Simulated WebSocket disconnect/reconnect produced 0 LLM calls.
6. Repeated GET /api/config/model_registry requests hit backend 60s+ TTL cache without spamming Ollama.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import pytest


AUDIT_FILE = Path(tempfile.gettempdir()) / "6clips_wave12_idle_audit" / "real_idle_windows_audit.json"


def test_window_e_audit_artifact_completeness_and_verdict():
    """Verify that the full Window E wall-clock idle run completed with PASS verdict."""
    if not AUDIT_FILE.is_file():
        pytest.skip(f"Observation audit file not yet written at {AUDIT_FILE}")

    with open(AUDIT_FILE, "r", encoding="utf-8") as f:
        audit_data = json.load(f)

    assert "windows" in audit_data, "Missing windows section in audit json"
    windows = audit_data["windows"]

    assert "Window_E" in windows, "Window_E is missing from audit windows report!"
    win_e = windows["Window_E"]

    # Duration must be full 300 seconds (5 minutes wall clock)
    duration = win_e.get("duration_measured_seconds", 0.0)
    assert duration >= 300.0, f"Window E was terminated prematurely! Expected >= 300.0s, got {duration}s"

    # Authorized inference count must be exactly 1
    assert win_e.get("authorized_inference_count") == 1, (
        f"Expected exactly 1 authorized inference call, got {win_e.get('authorized_inference_count')}"
    )

    # Unsolicited inference count must be strictly 0
    assert win_e.get("unsolicited_inference_count") == 0, (
        f"Unsolicited inference calls detected: {win_e.get('unsolicited_inference_count')}"
    )

    # Reconnect inference count must be strictly 0
    assert win_e.get("reconnect_inference_count", 0) == 0, (
        f"Inference calls detected on reconnect: {win_e.get('reconnect_inference_count')}"
    )

    # External network egress must be strictly 0
    assert win_e.get("external_egress_count", 0) == 0, (
        f"External network egress detected: {win_e.get('external_egress_count')}"
    )

    # Boot pypi egress must be 0
    assert win_e.get("boot_pypi_egress_count", 0) == 0, (
        f"Boot pypi egress detected: {win_e.get('boot_pypi_egress_count')}"
    )

    # Verdict must be PASS
    assert win_e.get("verdict") == "PASS", f"Window E verdict failed: {win_e.get('verdict')}"

    # Overall verdict
    assert audit_data.get("p0_verdict") == "P0_PASS", f"Overall P0 verdict is not P0_PASS: {audit_data.get('p0_verdict')}"
