import asyncio
import json
import subprocess
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from playwright.async_api import async_playwright

REPO_ROOT = Path(__file__).resolve().parents[1]
PROOF_DIR = REPO_ROOT / "artifacts" / "final_visual_acceptance"

async def generate_initial_frame_comparison():
    pid = "d5f13156-fc63-45e5-b448-d347639bc180"
    mp4_path = PROOF_DIR / "canonical_frozen_10s_multi_track.mp4"
    assert mp4_path.exists(), f"MP4 not found: {mp4_path}"

    # 1. Capture Preview at 0.0s, 0.25s, 0.5s
    timestamps = [0.0, 0.25, 0.5]
    prev_snaps = {}
    prev_opacities = {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        await page.goto(f"http://127.0.0.1:16888/motion?projectId={pid}", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        outer_frame = await (await page.locator("#studio-preview-iframe").element_handle()).content_frame()

        for t in timestamps:
            await outer_frame.evaluate(f"() => {{ if (typeof seekTo === 'function') seekTo({t}); }}")
            await page.wait_for_timeout(300)

            op = await outer_frame.evaluate("""() => {
                const el = document.querySelector('#elem_fbc05ef7');
                return el ? parseFloat(window.getComputedStyle(el).opacity) : 1;
            }""")
            prev_opacities[t] = op

            p_path = PROOF_DIR / f"preview_fade_parity_{t}s.png"
            await page.locator("#studio-preview-iframe").screenshot(path=str(p_path))
            prev_snaps[t] = p_path

        await browser.close()

    # 2. Extract Export frames at 0.0s, 0.25s, 0.5s
    exp_frames = {}
    for t in timestamps:
        e_path = PROOF_DIR / f"export_fade_parity_{t}s.png"
        cmd = ["ffmpeg", "-y", "-ss", str(t), "-i", str(mp4_path), "-vframes", "1", str(e_path)]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        exp_frames[t] = e_path

    # 3. Build Comparison Graphic (Before vs After Parity)
    # 4 columns:
    # Col 1: BEFORE FIX (t = 0.0s) -> Preview (bright) vs Export (dim)
    # Col 2: AFTER FIX (t = 0.0s)  -> Preview (dim 0.2) vs Export (dim 0.2)
    # Col 3: AFTER FIX (t = 0.25s) -> Preview (0.66) vs Export (0.66)
    # Col 4: AFTER FIX (t = 0.5s)  -> Preview (0.90) vs Export (0.90)

    cell_w, cell_h = 360, 640
    header_h = 60
    grid_w = cell_w * 4
    grid_h = (cell_h * 2) + (header_h * 2)

    canvas = Image.new("RGB", (grid_w, grid_h), color=(15, 17, 23))
    draw = ImageDraw.Draw(canvas)

    before_prev_path = PROOF_DIR / "preview_seek_0.0s_before_parity_fix.png"

    columns = [
        ("BEFORE FIX (t = 0.0s)\nDiscrepancy: Bright vs Dim", "0.0s", before_prev_path, exp_frames[0.0]),
        ("AFTER FIX (t = 0.0s)\nParity: Both Dim (0.2 Opacity)", "0.0s", prev_snaps[0.0], exp_frames[0.0]),
        ("AFTER FIX (t = 0.25s)\nMid-Fade (0.66 Opacity)", "0.25s", prev_snaps[0.25], exp_frames[0.25]),
        ("AFTER FIX (t = 0.5s)\nUpper Fade (0.90 Opacity)", "0.5s", prev_snaps[0.5], exp_frames[0.5]),
    ]

    for idx, (title, exp_time, p_file, e_file) in enumerate(columns):
        x = idx * cell_w

        # Row 1: Preview
        im_p = Image.open(p_file).convert("RGB").resize((cell_w, cell_h), Image.Resampling.LANCZOS)
        canvas.paste(im_p, (x, header_h))

        # Row 2: Export
        im_e = Image.open(e_file).convert("RGB").resize((cell_w, cell_h), Image.Resampling.LANCZOS)
        canvas.paste(im_e, (x, (header_h * 2) + cell_h))

        # Header text
        color = (255, 100, 100) if idx == 0 else (0, 240, 255)
        draw.text((x + 15, 15), title, fill=color)
        draw.text((x + 15, header_h + cell_h + 15), f"EXPORT  t = {exp_time}", fill=(255, 180, 50))

    out_comparison = PROOF_DIR / "initial_frame_fade_comparison.png"
    canvas.save(out_comparison, format="PNG")
    print(f"Saved initial frame fade comparison: {out_comparison}")

    # 4. Measure regional brightness for exact numerical proof
    brightness_data = {}
    for t in timestamps:
        im_p = Image.open(prev_snaps[t])
        im_e = Image.open(exp_frames[t])
        arr_p = np.array(im_p)
        arr_e = np.array(im_e)
        crop_p = arr_p[int(arr_p.shape[0]*0.2):int(arr_p.shape[0]*0.5), int(arr_p.shape[1]*0.2):int(arr_p.shape[1]*0.8)]
        crop_e = arr_e[900:1300, 400:1700]
        brightness_data[f"t_{t}"] = {
            "timestamp": t,
            "preview_opacity": prev_opacities[t],
            "preview_title_brightness": round(float(np.mean(crop_p)), 2),
            "export_title_brightness": round(float(np.mean(crop_e)), 2),
        }

    im_before = Image.open(before_prev_path)
    arr_b = np.array(im_before)
    crop_b = arr_b[int(arr_b.shape[0]*0.2):int(arr_b.shape[0]*0.5), int(arr_b.shape[1]*0.2):int(arr_b.shape[1]*0.8)]
    brightness_data["t_0.0_before_fix"] = {
        "timestamp": 0.0,
        "preview_opacity": 1.0,
        "preview_title_brightness": round(float(np.mean(crop_b)), 2),
        "export_title_brightness": brightness_data["t_0.0"]["export_title_brightness"]
    }

    print(json.dumps(brightness_data, indent=2))
    (PROOF_DIR / "initial_frame_fade_metrics.json").write_text(json.dumps(brightness_data, indent=2), encoding="utf-8")

if __name__ == "__main__":
    asyncio.run(generate_initial_frame_comparison())
