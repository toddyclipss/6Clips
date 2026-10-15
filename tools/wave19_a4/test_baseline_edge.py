import os
import sys

sys.path.insert(0, r"C:\Users\toddy\AppData\Roaming\Python\Python314\site-packages")

import json
import time
from pathlib import Path
from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[2]
SHIPPED_BLOCKS = REPO_ROOT / "backend" / "catalog" / "shipped_blocks"
OUT_DIR = REPO_ROOT / "tools" / "wave19_a4" / "baseline_renders"
OUT_DIR.mkdir(parents=True, exist_ok=True)

OWNER_10 = [
    "aurora",
    "data-chart",
    "flowing-gradient",
    "holographic",
    "instagram-follow",
    "plasma",
    "stripes",
    "tiktok-follow",
    "weight-wave",
    "yt-lower-third",
]

def compute_pixel_delta(img1_path: Path, img2_path: Path) -> float:
    """Compute normalized root mean square difference between two images."""
    with Image.open(img1_path) as im1, Image.open(img2_path) as im2:
        im1_rgb = im1.convert("RGB")
        im2_rgb = im2.convert("RGB")
        if im1_rgb.size != im2_rgb.size:
            im2_rgb = im2_rgb.resize(im1_rgb.size)
        diff = ImageChops.difference(im1_rgb, im2_rgb)
        stat = diff.getextrema()
        # Non-zero diff indicates visual motion
        total_diff = sum((max_val - min_val) for min_val, max_val in stat)
        # Average pixel delta normalized to 0..100
        avg_diff = total_diff / (len(stat) * 255.0) * 100.0
        return round(avg_diff, 4)

def test_baseline_in_edge():
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="msedge",
            headless=True,
            args=["--headless=new", "--disable-gpu", "--no-sandbox"]
        )
        context = browser.new_context(viewport={"width": 640, "height": 360})
        page = context.new_page()

        for b in OWNER_10:
            bdir = SHIPPED_BLOCKS / b
            html_file = bdir / f"{b}.html"
            if not html_file.exists():
                html_file = bdir / "index.html"
            if not html_file.exists():
                results[b] = {"status": "FILE_NOT_FOUND"}
                continue

            file_url = f"file:///{html_file.resolve().as_posix()}"
            page.goto(file_url, wait_until="load", timeout=10000)
            page.wait_for_timeout(300)

            # Frame at t=0
            f0_path = OUT_DIR / f"{b}_t0.png"
            page.screenshot(path=str(f0_path))

            # Advance time by 1200ms
            page.wait_for_timeout(1200)
            f1_path = OUT_DIR / f"{b}_t1.png"
            page.screenshot(path=str(f1_path))

            delta = compute_pixel_delta(f0_path, f1_path)
            with Image.open(f0_path) as im:
                extrema = im.convert("L").getextrema()
            is_black = (extrema == (0, 0))

            results[b] = {
                "slug": b,
                "motion_delta": delta,
                "is_solid_black": is_black,
                "has_motion": (delta > 0.05 and not is_black),
                "f0": str(f0_path.relative_to(REPO_ROOT)),
                "f1": str(f1_path.relative_to(REPO_ROOT)),
            }
            print(f"[{b}] motion_delta={delta}, is_black={is_black}, has_motion={results[b]['has_motion']}")

        browser.close()

    summary_file = OUT_DIR / "baseline_summary.json"
    summary_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWrote baseline summary to {summary_file}")

if __name__ == "__main__":
    test_baseline_in_edge()
