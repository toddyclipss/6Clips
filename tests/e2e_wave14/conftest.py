# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""Pytest fixtures for Wave 14 Stage 3 Independent Adversarial Validation."""

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
EVIDENCE_DIR = Path(tempfile.gettempdir()) / "6clips_wave14_validation_evidence"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_DIR = Path(tempfile.gettempdir()) / "6clips_wave14_validation_video"
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

USER_SITE_PACKAGES = r"C:\Users\toddy\AppData\Roaming\Python\Python314\site-packages"


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
    Enables forensic diagnostics and isolated database/media paths in %TEMP%.
    Uses file-backed logging to avoid 64KB Windows pipe buffer deadlocks.
    """
    temp_dir = tempfile.mkdtemp(prefix="viralmint_w14_val_")
    db_path = os.path.join(temp_dir, "viralmint_w14_test.db")
    media_dir = os.path.join(temp_dir, "media")
    os.makedirs(media_dir, exist_ok=True)

    port = find_free_port()
    env = os.environ.copy()
    env["SIXCLIPS_IDLE_NET_AUDIT"] = "1"
    env["VIRALMINT_DATA_DIR"] = temp_dir
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    env["VIRALMINT_FRONTEND_DIST"] = str(FRONTEND_DIST)
    env["MEDIA_DIR"] = media_dir
    # Ensure both REPO_ROOT and roaming site-packages are in PYTHONPATH
    python_paths = [str(REPO_ROOT), USER_SITE_PACKAGES]
    if env.get("PYTHONPATH"):
        python_paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = ";".join(python_paths)

    log_path = os.path.join(temp_dir, "uvicorn_w14_validation.log")
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
    deadline = time.time() + 35.0
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

    server_pids = get_child_pids(proc.pid)

    yield {
        "base_url": base_url,
        "port": port,
        "proc": proc,
        "server_pids": server_pids,
        "temp_dir": temp_dir,
        "evidence_dir": EVIDENCE_DIR,
        "video_dir": VIDEO_DIR,
        "media_dir": media_dir,
        "log_path": log_path,
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
    """Launch a real Chromium / Microsoft Edge browser context."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="msedge")
        yield browser
        browser.close()
