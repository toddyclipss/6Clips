# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""Pytest fixtures for Wave 12 Independent Adversarial Idle-Traffic Acceptance."""

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import httpx
import pytest
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"
EVIDENCE_DIR = Path(tempfile.gettempdir()) / "6clips_wave12_idle_audit"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get_child_pids(parent_pid: int) -> set[int]:
    """Find child PIDs spawned under parent_pid on Windows."""
    pids = {parent_pid}
    try:
        wmic = subprocess.run(
            ["wmic", "process", "where", f"ParentProcessId={parent_pid}", "get", "ProcessId"],
            capture_output=True,
            text=True,
        )
        for num in re.findall(r"\d+", wmic.stdout):
            pids.add(int(num))
    except Exception:
        pass
    return pids


@pytest.fixture(scope="session")
def isolated_server():
    """Launch a real Uvicorn server serving FastAPI backend and built SPA frontend.
    Enables SIXCLIPS_IDLE_NET_AUDIT=1 for full forensic diagnostics.
    Uses file-backed logging to avoid 64KB Windows pipe buffer deadlocks.
    """
    temp_dir = tempfile.mkdtemp(prefix="viralmint_w12_acceptance_")
    db_path = os.path.join(temp_dir, "viralmint_w12_test.db")
    media_dir = os.path.join(temp_dir, "media")
    os.makedirs(media_dir, exist_ok=True)

    port = find_free_port()
    env = os.environ.copy()
    env["SIXCLIPS_IDLE_NET_AUDIT"] = "1"
    env["VIRALMINT_DATA_DIR"] = temp_dir
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    env["VIRALMINT_FRONTEND_DIST"] = str(FRONTEND_DIST)
    env["MEDIA_DIR"] = media_dir
    env["PYTHONPATH"] = f"{REPO_ROOT};{os.path.join(os.environ.get('APPDATA', ''), 'Python', 'Python314', 'site-packages')};{env.get('PYTHONPATH', '')}"

    log_path = os.path.join(temp_dir, "uvicorn_w12.log")
    log_file = open(log_path, "w", encoding="utf-8", errors="replace")

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "info",
        ],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )

    base_url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 30.0
    ready = False

    while time.time() < deadline:
        try:
            r = httpx.get(f"{base_url}/health", timeout=1.0)
            if r.status_code == 200:
                ready = True
                break
        except Exception:
            time.sleep(0.3)

    if not ready:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        log_file.close()
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            captured = f.read()
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError(f"Uvicorn server failed to boot on {base_url}:\n{captured}")

    # Discover server PIDs
    server_pids = get_child_pids(proc.pid)

    yield {
        "base_url": base_url,
        "port": port,
        "proc": proc,
        "server_pids": server_pids,
        "temp_dir": temp_dir,
        "evidence_dir": EVIDENCE_DIR,
        "media_dir": media_dir,
    }

    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        proc.kill()
    log_file.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="session")
def playwright_browser():
    """Launch a real Chromium/Edge browser context."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="msedge")
        yield browser
        browser.close()
