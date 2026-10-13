# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 6 Fixtures: Isolated FastAPI backend and Playwright Edge browser."""
import os
import sys
import time
import socket
import tempfile
import shutil
import subprocess
import pytest
import httpx
from pathlib import Path


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def isolated_server():
    """Spin up an isolated FastAPI backend serving the built SPA in a temp directory."""
    temp_dir = tempfile.mkdtemp(prefix="viralmint_w6_e2e_")
    port = _get_free_port()

    repo_root = Path(__file__).resolve().parent.parent.parent
    frontend_dist = repo_root / "frontend" / "dist"
    assert frontend_dist.exists(), f"Frontend dist directory missing at {frontend_dist}"

    env = os.environ.copy()
    env["VIRALMINT_DATA_DIR"] = temp_dir
    env["VIRALMINT_FRONTEND_DIST"] = str(frontend_dist)
    env["PORT"] = str(port)
    env["HOST"] = "127.0.0.1"
    current_pythonpath = os.environ.get("PYTHONPATH", "")
    site_packages = r"C:\Users\toddy\AppData\Roaming\Python\Python314\site-packages"
    env["PYTHONPATH"] = f"{repo_root};{site_packages};{current_pythonpath}"

    log_path = Path(temp_dir) / "server.log"
    log_file = open(log_path, "w", encoding="utf-8")

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(port)],
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )

    base_url = f"http://127.0.0.1:{port}"
    server_ready = False
    for _ in range(80):
        time.sleep(0.5)
        try:
            r = httpx.get(f"{base_url}/api/settings", timeout=2.0)
            if r.status_code == 200:
                server_ready = True
                break
        except Exception:
            pass

    if not server_ready:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        try:
            log_file.close()
            out = log_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            out = "Could not read log"
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError(f"Isolated server failed to start within 40s. Output:\n{out}")

    yield {
        "base_url": base_url,
        "port": port,
        "temp_dir": temp_dir,
        "proc": proc,
        "log_path": log_path,
    }

    # Teardown
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()
    try:
        log_file.close()
    except Exception:
        pass
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="session")
def playwright_browser():
    """Launch headless browser using system Edge via Playwright channel='msedge'."""
    from playwright.sync_api import sync_playwright
    p = sync_playwright().start()
    browser = p.chromium.launch(channel="msedge", headless=True)
    yield browser
    browser.close()
    p.stop()
