# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Pytest fixtures for Wave 10 Real Browser, Real Backend, and Ollama E2E acceptance."""

import os
import sys
import time
import socket
import tempfile
import shutil
import subprocess
import pytest
import httpx
from playwright.sync_api import sync_playwright

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FRONTEND_DIST = os.path.join(REPO_ROOT, "frontend", "dist")
EVIDENCE_DIR = os.path.join(tempfile.gettempdir(), "viralmint_wave10_evidence")
os.makedirs(EVIDENCE_DIR, exist_ok=True)


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def isolated_server():
    """Launch a real Uvicorn server serving FastAPI backend and built SPA frontend.
    Uses file-backed logging to avoid 64KB Windows pipe buffer deadlocks.
    """
    temp_dir = tempfile.mkdtemp(prefix="viralmint_w10_e2e_")
    db_path = os.path.join(temp_dir, "viralmint_w10_test.db")
    media_dir = os.path.join(temp_dir, "media")
    os.makedirs(media_dir, exist_ok=True)

    port = find_free_port()
    env = os.environ.copy()
    env["VIRALMINT_DATA_DIR"] = temp_dir
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    env["VIRALMINT_FRONTEND_DIST"] = FRONTEND_DIST
    env["MEDIA_DIR"] = media_dir
    env["PYTHONPATH"] = f"{REPO_ROOT};{os.path.join(os.environ.get('APPDATA', ''), 'Python', 'Python314', 'site-packages')};{env.get('PYTHONPATH', '')}"

    log_path = os.path.join(temp_dir, "uvicorn_w10.log")
    log_file = open(log_path, "w", encoding="utf-8", errors="replace")

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "info",
        ],
        cwd=REPO_ROOT,
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

    yield {
        "base_url": base_url,
        "port": port,
        "temp_dir": temp_dir,
        "proc": proc,
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


@pytest.fixture(scope="session")
def sample_media_mp4(isolated_server):
    """Generate a real 2-second 720x1280 (vertical) test MP4 with audio using FFmpeg."""
    target_path = os.path.join(isolated_server["media_dir"], "sample_probe_w10.mp4")
    if not os.path.exists(target_path):
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "lavfi", "-i", "color=c=blue:s=720x1280:d=2:r=30",
            "-f", "lavfi", "-i", "sine=f=440:d=2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            target_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return target_path


@pytest.fixture(scope="session")
def sample_horizontal_mp4(isolated_server):
    """Generate a real 2-second 1920x1080 (horizontal) test MP4 with audio using FFmpeg."""
    target_path = os.path.join(isolated_server["media_dir"], "sample_landscape_w10.mp4")
    if not os.path.exists(target_path):
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "lavfi", "-i", "color=c=darkgreen:s=1920x1080:d=2:r=30",
            "-f", "lavfi", "-i", "sine=f=880:d=2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            target_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return target_path
