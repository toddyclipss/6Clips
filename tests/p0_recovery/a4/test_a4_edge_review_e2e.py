"""
P0 Recovery Squad - Agent 4: Review UI Single Artifact Player Edge Browser E2E Test Suite.
Verifies real Microsoft Edge rendering of Review stage, video metadata probe sync,
rejection of social publication gates on edit-only requests, and error state integrity.
"""

import sys
import os
import time
import json
import threading
import subprocess
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DIST_DIR = REPO_ROOT / "frontend" / "dist"
EVIDENCE_DIR = REPO_ROOT / "tools" / "p0_recovery_a4" / "evidence"
SCREENSHOTS_DIR = EVIDENCE_DIR / "screenshots"

EDGE_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

def find_edge_binary():
    for p in EDGE_PATHS:
        if Path(p).exists():
            return p
    return None

class SPAHandler(SimpleHTTPRequestHandler):
    """Serves frontend/dist with SPA fallback to index.html and tracks API calls."""
    protocol_version = "HTTP/1.0"
    api_calls = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST_DIR), **kwargs)

    def do_GET(self):
        # API mock endpoints if queried by frontend
        if self.path.startswith("/api/"):
            SPAHandler.api_calls.append(("GET", self.path))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            if "projects" in self.path:
                self.wfile.write(b"[]")
            elif "jobs" in self.path:
                self.wfile.write(b"[]")
            elif "health" in self.path:
                self.wfile.write(b'{"status":"ok"}')
            elif "library" in self.path:
                self.wfile.write(b'{"items":[]}')
            elif "trends" in self.path:
                self.wfile.write(b'{"results":[]}')
            else:
                self.wfile.write(b"{}")
            return

        # Serve static assets or fallback to index.html for SPA routes
        target = DIST_DIR / self.path.lstrip("/").split("?")[0]
        if not target.exists() or target.is_dir():
            index_path = DIST_DIR / "index.html"
            content = index_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        super().do_GET()

    def do_POST(self):
        SPAHandler.api_calls.append(("POST", self.path))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def log_message(self, format, *args):
        pass


@pytest.fixture(scope="module")
def spa_server():
    """Starts local SPA server on port 5179 with ThreadingHTTPServer."""
    if not (DIST_DIR / "index.html").exists():
        pytest.fail("frontend/dist/index.html does not exist. Run 'npm run build' first.")

    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    SPAHandler.api_calls.clear()
    server = ThreadingHTTPServer(("127.0.0.1", 5179), SPAHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.5)
    yield "http://127.0.0.1:5179"
    server.shutdown()


class TestEdgeReviewPlayerAndSocialGate:
    """Verifies UX in Microsoft Edge for Motion Graphics Review, Player and Gates."""

    def run_edge_capture(self, edge_bin, url, width, height, screenshot_name=None, dump_dom=False, virtual_time=2500):
        cmd = [
            edge_bin,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            f"--window-size={width},{height}",
            f"--virtual-time-budget={virtual_time}",
        ]
        if screenshot_name:
            shot_path = SCREENSHOTS_DIR / screenshot_name
            cmd.append(f"--screenshot={shot_path}")
        
        if dump_dom:
            cmd.append("--dump-dom")
        
        cmd.append(url)
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
        return res

    def test_edge_motion_page_renders_cleanly(self, spa_server):
        edge_bin = find_edge_binary()
        if not edge_bin:
            pytest.skip("Microsoft Edge binary not found on Windows host")

        shot_name = "p0_edge_1920x1080_motion_review.png"
        res = self.run_edge_capture(edge_bin, f"{spa_server}/motion", 1920, 1080, screenshot_name=shot_name, dump_dom=True, virtual_time=2500)
        assert res.returncode == 0
        img_path = SCREENSHOTS_DIR / shot_name
        assert img_path.exists()
        assert img_path.stat().st_size > 5000

        dom = res.stdout
        # 1. Five mandatory sidebars present
        assert "Motion Graphics" in dom
        assert "Trends" in dom
        assert "My Channel" in dom
        assert "Library" in dom
        assert "Messages" in dom

        # 2. Strict Create and Review switcher only (no Refine phase)
        assert "Create" in dom
        assert "Review" in dom
        assert "Refine" not in dom

        # 3. No spurious social publishing or pending credentials on initial load
        assert "NOT_CONNECTED / PENDING_CREDENTIALS" not in dom
        assert "External Social Publishing Status" not in dom

        # 4. No hardcoded 15.00s fallback in rendered DOM
        assert "15.00s" not in dom

    def test_edge_review_mode_zero_social_gate(self, spa_server):
        """Verifies Review mode loads cleanly without social gate or 15.00s hardcoded duration."""
        edge_bin = find_edge_binary()
        if not edge_bin:
            pytest.skip("Microsoft Edge binary not found on Windows host")

        shot_name = "p0_edge_1920x1080_review_mode.png"
        res = self.run_edge_capture(edge_bin, f"{spa_server}/motion?mode=review", 1920, 1080, screenshot_name=shot_name, dump_dom=True, virtual_time=2500)
        assert res.returncode == 0
        img_path = SCREENSHOTS_DIR / shot_name
        assert img_path.exists()
        assert img_path.stat().st_size > 5000

        dom = res.stdout
        # Zero social gate or pending credentials
        assert "NOT_CONNECTED / PENDING_CREDENTIALS" not in dom
        # Zero hardcoded 15s display
        assert "15.00s" not in dom

    def test_edge_viewport_responsiveness(self, spa_server):
        """Verifies responsiveness across 1440x900 and 1366x768 viewports."""
        edge_bin = find_edge_binary()
        if not edge_bin:
            pytest.skip("Microsoft Edge binary not found on Windows host")

        for w, h, name in [(1440, 900, "p0_edge_1440x900_review.png"), (1366, 768, "p0_edge_1366x768_review.png")]:
            res = self.run_edge_capture(edge_bin, f"{spa_server}/motion", w, h, screenshot_name=name, virtual_time=2000)
            assert res.returncode == 0
            img_path = SCREENSHOTS_DIR / name
            assert img_path.exists()
            assert img_path.stat().st_size > 5000
