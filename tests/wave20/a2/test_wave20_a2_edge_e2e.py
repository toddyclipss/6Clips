"""
Wave 20 Agent 2: End-to-End Test in Real Microsoft Edge Browser.
Tests responsive layout (1920x1080, 1440x900, 1366x768), verifies zero phantom project creation on empty state,
validates Create and Review stages, Advanced Editing toggle, and legacy route redirection.
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
SCREENSHOTS_DIR = REPO_ROOT / "tools" / "wave20_a2" / "screenshots"

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
        # Silence standard HTTP logs during testing
        pass

@pytest.fixture(scope="module")
def spa_server():
    """Starts the local SPA server on port 5174."""
    if not (DIST_DIR / "index.html").exists():
        pytest.fail("frontend/dist/index.html does not exist. Run 'npm run build' first.")

    SPAHandler.api_calls.clear()
    server = ThreadingHTTPServer(("127.0.0.1", 5174), SPAHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.5)
    yield "http://127.0.0.1:5174"
    server.shutdown()

class TestEdgeMinimalMotionUX:
    """Verifies UX in Microsoft Edge across resolutions."""

    def run_edge_capture(self, edge_bin, url, width, height, screenshot_name=None, dump_dom=False):
        cmd = [
            edge_bin,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            f"--window-size={width},{height}",
            "--virtual-time-budget=2500",
        ]
        if screenshot_name:
            out_img = SCREENSHOTS_DIR / screenshot_name
            cmd.append(f"--screenshot={out_img}")
        if dump_dom:
            cmd.append("--dump-dom")
        
        cmd.append(url)
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return res

    def test_edge_responsive_resolutions(self, spa_server):
        edge_bin = find_edge_binary()
        if not edge_bin:
            pytest.skip("Microsoft Edge binary not found on Windows host")

        resolutions = [
            (1920, 1080, "edge_1920x1080_create.png"),
            (1440, 900, "edge_1440x900_create.png"),
            (1366, 768, "edge_1366x768_create.png"),
        ]

        for w, h, shot in resolutions:
            res = self.run_edge_capture(edge_bin, f"{spa_server}/motion", w, h, screenshot_name=shot)
            assert res.returncode == 0, f"Edge headless run failed for {w}x{h}"
            img_path = SCREENSHOTS_DIR / shot
            assert img_path.exists(), f"Expected screenshot {shot} was not created"
            assert img_path.stat().st_size > 5000, f"Screenshot {shot} is empty or corrupted"

    def test_edge_rendered_dom_and_ui_elements(self, spa_server):
        edge_bin = find_edge_binary()
        if not edge_bin:
            pytest.skip("Microsoft Edge binary not found on Windows host")

        res = self.run_edge_capture(edge_bin, f"{spa_server}/motion", 1920, 1080, dump_dom=True)
        assert res.returncode == 0
        dom = res.stdout

        # Verify Sidebar 5 destinations
        assert "Motion Graphics" in dom
        assert "Trends" in dom
        assert "My Channel" in dom
        assert "Library" in dom
        assert "Messages" in dom

        # Verify Create & Review stages (and absence of Refine tab)
        assert "stage-tab-create" in dom
        assert "stage-tab-review" in dom
        assert "stage-tab-refine" not in dom

        # Verify unobtrusive Advanced Editing button
        assert "studio-toolbar-advanced-editing-btn" in dom

        # Verify empty state text
        assert "No Project Loaded" in dom or "Enter your video goals in Chat" in dom or "Describe your video in Chat" in dom

        # Verify no 196 catalog cards / tabs
        assert "catalogInventory" not in dom
        assert "Ask AI to insert block in chat" not in dom

    def test_edge_empty_state_no_phantom_project(self, spa_server):
        """Verifies that visiting /motion as a first-time empty project does NOT call POST /api/projects."""
        edge_bin = find_edge_binary()
        if not edge_bin:
            pytest.skip("Microsoft Edge binary not found on Windows host")

        initial_posts = [c for c in SPAHandler.api_calls if c[0] == "POST" and "projects" in c[1]]
        self.run_edge_capture(edge_bin, f"{spa_server}/motion", 1440, 900)
        new_posts = [c for c in SPAHandler.api_calls if c[0] == "POST" and "projects" in c[1]]
        
        assert len(new_posts) == len(initial_posts), "Visiting empty /motion triggered unwanted POST /api/projects"

    def test_edge_legacy_routes_redirect_to_motion(self, spa_server):
        """Verifies legacy /catalog and /clips redirect cleanly in Edge without crashing."""
        edge_bin = find_edge_binary()
        if not edge_bin:
            pytest.skip("Microsoft Edge binary not found on Windows host")

        # Test /catalog
        res_cat = self.run_edge_capture(edge_bin, f"{spa_server}/catalog", 1440, 900, dump_dom=True)
        assert res_cat.returncode == 0
        assert "stage-tab-create" in res_cat.stdout
        assert "No Project Loaded" in res_cat.stdout or "Enter your video goals in Chat" in res_cat.stdout or "Describe your video in Chat" in res_cat.stdout

        # Test /clips
        res_clips = self.run_edge_capture(edge_bin, f"{spa_server}/clips", 1440, 900, dump_dom=True)
        assert res_clips.returncode == 0
        assert "stage-tab-create" in res_clips.stdout
