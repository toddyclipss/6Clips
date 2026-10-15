# SPDX-License-Identifier: AGPL-3.0-only
"""Adversarial Render Test for Wave 17 Ported N-Z Blocks."""
import hashlib
import json
import logging
import subprocess
import sys
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image, ImageChops, ImageStat
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[2]
SHIPPED_ROOT = REPO_ROOT / "backend" / "catalog" / "shipped_blocks"

TARGETS = [
    "transitions-3d",
    "transitions-blur",
    "transitions-cover",
    "transitions-destruction",
    "transitions-distortion",
    "transitions-grid",
    "transitions-light",
    "transitions-mechanical",
    "transitions-other",
    "transitions-scale",
    "share-sheet-carousel",
    "snow",
    "starfield",
    "rack-focus",
    "swirl-vortex",
    "vfx-magnetic",
    "vfx-text-cursor",
    "ui-3d-reveal",
]

class StaticServerHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(REPO_ROOT), **kwargs)

    def log_message(self, format, *args):
        pass

def calculate_pixel_delta(img1: Image.Image, img2: Image.Image) -> float:
    diff = ImageChops.difference(img1.convert("RGB"), img2.convert("RGB"))
    stat = ImageStat.Stat(diff)
    return sum(stat.mean) / 3.0

def calculate_brightness(img: Image.Image) -> float:
    stat = ImageStat.Stat(img.convert("RGB"))
    return sum(stat.mean) / 3.0

def run_ffprobe(video_path: Path) -> dict:
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,duration,nb_frames,pix_fmt",
        "-of", "json",
        str(video_path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if res.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {res.stderr}")
    return json.loads(res.stdout)

def encode_mp4(frames, output_path: Path, fps: int = 10) -> None:
    with tempfile.TemporaryDirectory(prefix="w17_ffmpeg_") as tmpdir:
        tmp_path = Path(tmpdir)
        for idx, img in enumerate(frames):
            frame_file = tmp_path / f"frame_{idx:04d}.png"
            img.save(frame_file, format="PNG")

        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", str(tmp_path / "frame_%04d.png"),
            "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "ultrafast",
            str(output_path)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if res.returncode != 0:
            raise RuntimeError(f"FFmpeg encoding failed: {res.stderr}")

def test_block(server_url: str, block_id: str) -> dict:
    page_url = f"{server_url}/backend/catalog/shipped_blocks/{block_id}/{block_id}.html"
    egress_violations = []
    console_errors = []
    frames = []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})

        def handle_route(route):
            req_url = route.request.url
            if not req_url.startswith("http://127.0.0.1") and not req_url.startswith("data:"):
                egress_violations.append(req_url)
                route.abort()
            else:
                route.continue_()

        context.route("**/*", handle_route)
        page = context.new_page()
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        page.goto(page_url, wait_until="networkidle", timeout=15000)

        # Capture at t = 0.5, 1.5, 2.5, 3.5, 4.5
        timestamps = [0.5, 1.5, 2.5, 3.5, 4.5]
        for ts in timestamps:
            # Seek timeline if available
            page.evaluate(f"""
                (function() {{
                    var t = {ts};
                    if (window.__timelines) {{
                        for (var k in window.__timelines) {{
                            if (window.__timelines[k] && typeof window.__timelines[k].seek === 'function') {{
                                window.__timelines[k].seek(t);
                            }}
                        }}
                    }}
                    window.dispatchEvent(new CustomEvent('hf-seek', {{ detail: {{ time: t }} }}));
                }})();
            """)
            page.wait_for_timeout(100)
            png_bytes = page.screenshot()
            import io
            frames.append(Image.open(io.BytesIO(png_bytes)))

        browser.close()

    # Calculate motion delta
    delta1 = calculate_pixel_delta(frames[0], frames[2])
    delta2 = calculate_pixel_delta(frames[1], frames[3])
    max_delta = max(delta1, delta2)
    b_mean = calculate_brightness(frames[1])

    # Encode MP4
    mp4_file = Path(tempfile.gettempdir()) / f"render_{block_id}.mp4"
    encode_mp4(frames, mp4_file)
    probe = run_ffprobe(mp4_file)
    mp4_sha = hashlib.sha256(mp4_file.read_bytes()).hexdigest()

    threshold = 0.05 if block_id in {"snow", "starfield"} else 0.2
    passed = max_delta > threshold and len(egress_violations) == 0 and b_mean > 0.05

    return {
        "block_id": block_id,
        "max_delta": round(max_delta, 2),
        "brightness": round(b_mean, 2),
        "egress_violations": egress_violations,
        "console_errors": console_errors,
        "mp4_sha256": mp4_sha,
        "mp4_stream": probe["streams"][0],
        "passed": passed
    }

def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), StaticServerHandler)
    port = server.server_port
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    server_url = f"http://127.0.0.1:{port}"
    print(f"Test server running at {server_url}")

    results = []
    for slug in TARGETS:
        try:
            res = test_block(server_url, slug)
            results.append(res)
            status_str = "PASS" if res["passed"] else "FAIL"
            print(f"[{status_str}] {slug}: delta={res['max_delta']}% bright={res['brightness']} egress={len(res['egress_violations'])} errors={len(res['console_errors'])} mp4_sha={res['mp4_sha256'][:10]}")
        except Exception as e:
            print(f"[ERROR] {slug}: {e}")
            results.append({"block_id": slug, "passed": False, "error": str(e)})

    server.shutdown()
    passed_count = sum(1 for r in results if r.get("passed"))
    print(f"\nCompleted: {passed_count}/{len(TARGETS)} blocks passed render test!")

if __name__ == "__main__":
    main()
