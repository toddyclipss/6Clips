# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 13 Stage 3: Independent Adversarial Acceptance & Truth Audit Suite.

Owned exclusively by Agent 4 (Stage 3 Independent Adversarial Validator).
Covers:
- Task A: Git ancestry proof for Wave 12 Role 4 and Wave 13 Roles 2, 3, 5, and untouched main/viralmint.db.
- Task B: Boot egress verification (zero pip / zero pypi.org egress) and diagnostic routes audit.
- Task C (GT-13): Full 12-block HyperFrames distinct render & 64-char SHA-256 uniqueness audit.
- Task D: Real Microsoft Edge browser validation across 1366x768, 1440x900, 1920x1080 on /motion.
- Canonical Reference Proposal SHA-256 and 285-requirement integrity check.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Dict, List, Set
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from starlette.testclient import TestClient

pytest_plugins = ["tests.e2e_wave12.conftest"]

from backend.main import create_app
from backend.catalog.manifest_service import WAVE4_INTERNALIZED_BLOCKS
from backend.services.catalog_preview_service import CatalogPreviewService
from backend.services.registry_adapter import RegistryAdapter, get_registry_dir
from backend.services.ytdlp_service import check_ytdlp_version, _get_ytdlp_age_days
from backend.api.config import clear_model_registry_cache
from backend.distribution.egress_audit import (
    clear_audit_events as clear_egress_events,
    get_recent_audit_events as get_egress_events,
)
from backend.llm_trace.tracer import (
    clear_audit_events as clear_llm_events,
    get_audit_events as get_llm_events,
    enable_audit as enable_llm_audit,
    disable_audit as disable_llm_audit,
)
from backend.diagnostics import ActivityRecorder


REPO_ROOT = Path(__file__).resolve().parent.parent

# Canonical hashes and baseline commit SHAs
CANONICAL_PROPOSAL_SHA256 = "55fcda09b2654e7b0f57e4fcb317c3a1416864248815cddc2668c7ea53526343"
CANONICAL_PROPOSAL_BYTE_LENGTH = 120418

WAVE12_ROLE4_SHA = "040466eb87af4fb56c6bc392af7b43af14a62bed"
WAVE13_ROLE2_SHA = "0922b5c42f4dc3c6b2eb010c65ec322304737b0b"
WAVE13_ROLE3_SHA = "f6d8ce029d0f1ac5dba947639bc68a6c5f7664af"
WAVE13_ROLE5_SHA = "a91b9e2ee0cb78bb22f3a3483446d236e1663e8b"
CANONICAL_MAIN_SHA = "3608ddb325977cc03e6668082c05b53dbad511bd"


# =========================================================================
# Task A: Git Ancestry & Clean Baseline Preflight
# =========================================================================

def test_task_a_git_ancestry_verification():
    """Verify that Wave 12 Role 4 and all three Wave 13 Stage 1 commits are ancestors of HEAD."""
    for name, sha in [
        ("Wave 12 Role 4", WAVE12_ROLE4_SHA),
        ("Wave 13 Role 2", WAVE13_ROLE2_SHA),
        ("Wave 13 Role 3", WAVE13_ROLE3_SHA),
        ("Wave 13 Role 5", WAVE13_ROLE5_SHA),
    ]:
        res = subprocess.run(
            ["git", "merge-base", "--is-ancestor", sha, "HEAD"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, (
            f"Commit {sha} ({name}) is NOT an ancestor of current HEAD! Returncode={res.returncode}, stderr={res.stderr}"
        )


def test_task_a_main_and_db_untouched():
    """Verify main branch points to canonical commit and viralmint.db is not tracked or dirty."""
    # Check main branch commit
    res = subprocess.run(
        ["git", "rev-parse", "main"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if res.returncode == 0:
        main_sha = res.stdout.strip()
        assert main_sha == CANONICAL_MAIN_SHA, f"main branch SHA mismatch: expected {CANONICAL_MAIN_SHA}, got {main_sha}"

    # Verify viralmint.db is not in git status
    st = subprocess.run(
        ["git", "status", "--porcelain", "viralmint.db"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert st.stdout.strip() == "", f"viralmint.db is modified or tracked in working directory: {st.stdout}"


# =========================================================================
# Canonical Reference Proposal & 285 Requirements Integrity
# =========================================================================

def _find_reference_proposal_path() -> Path:
    candidates = [
        Path(r"C:\Users\toddy\Desktop\6CLIPS_DOCUMENTO_MESTRE_REVISADO_PROPOSTA_2026-10-13.md"),
        Path(r"C:\Users\toddy\Downloads\6CLIPS_WAVE12_FIVE_AGENTS_P0_IDLE_OLLAMA_AND_EXTERNAL_API_FORENSICS_EN\6clips_wave12_prompts\REFERENCE_READ_ONLY_6CLIPS_MASTER_PROPOSAL_2026-10-13.md"),
        REPO_ROOT / "6CLIPS_DOCUMENTO_MESTRE_REVISADO_PROPOSTA_2026-10-13.md",
    ]
    for p in candidates:
        if p.is_file():
            return p
    pytest.skip("Canonical reference proposal file not found on disk")


def test_canonical_master_proposal_sha256_and_byte_length():
    """Verify exact canonical master proposal length (120,418 bytes) and SHA-256."""
    path = _find_reference_proposal_path()
    content = path.read_bytes()
    assert len(content) == CANONICAL_PROPOSAL_BYTE_LENGTH, (
        f"Proposal byte length mismatch: expected {CANONICAL_PROPOSAL_BYTE_LENGTH}, got {len(content)}"
    )
    actual_hash = hashlib.sha256(content).hexdigest().lower()
    assert actual_hash == CANONICAL_PROPOSAL_SHA256, (
        f"Proposal SHA-256 mismatch!\nExpected: {CANONICAL_PROPOSAL_SHA256}\nActual:   {actual_hash}"
    )


def test_canonical_master_proposal_285_requirements_count():
    """Verify proposal tracks exactly 285 individual requirements across 12 buckets (A-L)."""
    path = _find_reference_proposal_path()
    text = path.read_text(encoding="utf-8")

    expected_buckets = {
        "A": 22, "B": 28, "C": 30, "D": 25, "E": 32, "F": 24,
        "G": 18, "H": 18, "I": 15, "J": 25, "K": 23, "L": 25,
    }
    id_pattern = re.compile(r"\b([A-L])(\d{2})\b")
    matches = id_pattern.findall(text)

    unique_by_bucket: Dict[str, Set[str]] = {letter: set() for letter in expected_buckets}
    for letter, num in matches:
        unique_by_bucket[letter].add(f"{letter}{num}")

    for letter, count in expected_buckets.items():
        actual = len(unique_by_bucket[letter])
        assert actual == count, f"Bucket {letter} count mismatch: expected {count}, found {actual}"

    total = sum(len(ids) for ids in unique_by_bucket.values())
    assert total == 285, f"Expected 285 total requirements, got {total}"


# =========================================================================
# Task B: Boot Egress & Server Lifespan Verification
# =========================================================================

def test_task_b_boot_egress_lockdown_zero_pip_zero_pypi(monkeypatch):
    """Verify that checking ytdlp version with age_days > 30 emits 0 pip subprocesses and 0 pypi.org egress."""
    monkeypatch.setenv("SIXCLIPS_IDLE_NET_AUDIT", "1")
    monkeypatch.delenv("ENABLE_YTDLP_AUTO_UPDATE", raising=False)
    clear_egress_events()
    with patch("subprocess.run") as mock_run, \
         patch("backend.services.ytdlp_service._get_ytdlp_age_days", return_value=56):
        res = check_ytdlp_version()
        mock_run.assert_not_called()
        assert res["update_attempted"] is False
        assert res["blocked_reason"] == "AUTO_UPDATE_DISABLED_BY_DEFAULT"

        events = get_egress_events(component="ytdlp_service")
        assert len(events) >= 1
        assert events[-1]["destination_host"] == "pypi.org"
        assert events[-1]["endpoint_class"] == "BLOCKED_WITH_REASON"


def test_task_b_diagnostic_routes_exact_paths_and_loopback_restriction():
    """Verify exact diagnostic routes in router.py: status, events, trace_matrix."""
    app = create_app()
    client = TestClient(app)

    # Status
    r_status = client.get("/api/diagnostics/status")
    assert r_status.status_code == 200
    assert "summary" in r_status.json()

    # Events
    r_events = client.get("/api/diagnostics/events")
    assert r_events.status_code == 200
    assert "events" in r_events.json()

    # Trace matrix
    r_matrix = client.get("/api/diagnostics/trace_matrix")
    assert r_matrix.status_code == 200
    assert "trace_matrix" in r_matrix.json()

    # Loopback check with non-localhost
    from starlette.requests import Request
    from backend.diagnostics.router import _assert_localhost_security

    fake_req = MagicMock(spec=Request)
    fake_req.client = MagicMock()
    fake_req.client.host = "192.168.1.100"
    with pytest.raises(Exception) as exc:
        _assert_localhost_security(fake_req)
    assert "403" in str(exc.value)


def test_task_b_websocket_reconnect_zero_generative_inference():
    """Verify simulated WebSocket connect & disconnect triggers 0 unsolicited LLM calls."""
    enable_llm_audit()
    clear_llm_events()
    app = create_app()
    client = TestClient(app)

    with patch("backend.core.user_intelligence.UserIntelligence.get_smart_suggestions",
               new_callable=AsyncMock) as mock_llm_sugg:
        mock_llm_sugg.return_value = ["Create video"]
        with client.websocket_connect("/ws/chat") as ws:
            ws.send_json({"type": "set_session", "session_id": "sess_w13_acceptance_test"})
            assert not mock_llm_sugg.called

        llm_events = get_llm_events()
        gen_events = [e for e in llm_events if "/api/chat" in e.endpoint_url or "/api/generate" in e.endpoint_url]
        assert len(gen_events) == 0, f"Unsolicited generative calls on WS handshake: {gen_events}"


# =========================================================================
# Task C (GT-13): 12 HyperFrames Blocks Distinct SHA-256 Uniqueness
# =========================================================================

def test_task_c_gt13_12_hyperframes_distinct_sha256_and_ffmpeg_proof():
    """
    Verify all 12 operational HyperFrames blocks:
    1. Render valid MP4s (ffmpeg decode exit code 0).
    2. Have valid 1080x1920 video dimensions.
    3. Generate strictly distinct 64-character SHA-256 hashes (len(set(shas)) == 12).
    4. Shader blocks (aurora, flowing-gradient, holographic, plasma, stripes) do NOT share identical hashes.
    """
    results = CatalogPreviewService.render_all_12_distinct_blocks()
    assert len(results) == 12, f"Expected 12 rendered blocks, got {len(results)}"

    shas: Set[str] = set()
    block_sha_map: Dict[str, str] = {}

    for item in results:
        b_id = item["block_id"]
        sha = item["sha256"]
        path = item["mp4_path"]
        exit_code = item["ffmpeg_decode_exit_code"]

        assert exit_code == 0, f"Block {b_id} ffmpeg decode failed (exit {exit_code})"
        assert os.path.isfile(path), f"Block {b_id} output file missing at {path}"
        assert len(sha) == 64, f"Block {b_id} SHA-256 length is not 64: {sha}"

        # ffprobe validation
        probe_res = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height,codec_name", "-of", "json", path],
            capture_output=True,
            text=True,
        )
        assert probe_res.returncode == 0, f"ffprobe failed for block {b_id}: {probe_res.stderr}"
        probe_data = json.loads(probe_res.stdout)
        streams = probe_data.get("streams", [])
        assert len(streams) > 0, f"No video streams found for block {b_id}"
        assert streams[0]["width"] == 1080
        assert streams[0]["height"] == 1920
        assert streams[0]["codec_name"] == "h264"

        shas.add(sha)
        block_sha_map[b_id] = sha

    # Check 12 strictly distinct hashes
    assert len(shas) == 12, f"Expected 12 unique hashes, got {len(shas)}. Map: {block_sha_map}"

    # Verify shader blocks are mutually distinct and not using old prefix
    shader_blocks = ["aurora", "flowing-gradient", "holographic", "plasma", "stripes"]
    shader_shas = [block_sha_map[b] for b in shader_blocks]
    assert len(set(shader_shas)) == 5, f"Shader blocks must have 5 distinct hashes, got: {shader_shas}"
    for b in shader_blocks:
        assert not block_sha_map[b].startswith("b90d1afe4fd3bac9"), (
            f"Shader block {b} has the broken duplicated hash prefix: {block_sha_map[b]}"
        )


# =========================================================================
# Task D: Real Microsoft Edge Browser Acceptance
# =========================================================================

@pytest.mark.parametrize("viewport", [
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1920, "height": 1080},
])
def test_task_d_edge_browser_motion_viewports(isolated_server, playwright_browser, viewport):
    """
    Verify real Microsoft Edge renders /motion and /motion?mode=refine without crashes,
    with 0 overlapping spinners, and 0 unsolicited Ollama generative requests.
    """
    base_url = isolated_server["base_url"]
    context = playwright_browser.new_context(viewport=viewport)
    page = context.new_page()

    dispatched_generative: List[str] = []
    page_errors: List[str] = []

    page.on("pageerror", lambda err: page_errors.append(str(err)))
    page.on("request", lambda r: (
        dispatched_generative.append(r.url)
        if r.method == "POST" and ("/api/chat" in r.url or "/api/generate" in r.url)
        else None
    ))

    # 1. Test /motion (Create mode default)
    page.goto(f"{base_url}/motion", wait_until="networkidle", timeout=30000)
    time.sleep(2)

    # Assert 0 console/page crashes
    assert len(page_errors) == 0, f"Page errors observed on /motion: {page_errors}"

    # Assert 0 unsolicited generative requests
    assert len(dispatched_generative) == 0, f"Unsolicited generative requests: {dispatched_generative}"

    # 2. Test /motion?mode=refine (manual Refine mode without project)
    page.goto(f"{base_url}/motion?mode=refine", wait_until="networkidle", timeout=30000)
    time.sleep(2)

    assert len(page_errors) == 0, f"Page errors observed on /motion?mode=refine: {page_errors}"
    assert len(dispatched_generative) == 0, f"Unsolicited generative requests: {dispatched_generative}"

    # Check for overlapping loading spinners
    spinners = page.locator(".animate-spin, [role='progressbar'], .loading-spinner")
    spinner_count = spinners.count()
    # At most 1 legitimate loader, never overlapping multiple spinners
    assert spinner_count <= 1, f"Found {spinner_count} simultaneous loading spinners on page"

    context.close()
