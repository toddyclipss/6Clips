import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path("artifacts/motion_ux_corrections")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

REPRESENTATIVE_BLOCKS = [
    ("weight-wave", "Typography", "9:16", "Oscillating variable-font kinetic headline"),
    ("yt-lower-third", "Lower Thirds", "16:9", "Clean YouTube broadcast lower-third bar"),
    ("ai-chat-reveal", "Mock UI & Social", "9:16", "Realistic conversational message bubble reveal"),
    ("data-chart", "Charts", "16:9", "Animated statistical analytics chart"),
    ("aurora", "Backgrounds & Shaders", "9:16", "Procedural atmospheric WebGPU color shader"),
    ("flash-through-white", "Transitions", "16:9", "High-exposure cinematic flash transition"),
]

def capture_and_build_representative_sheet():
    print("Capturing 6 representative blocks for Deliverable 2...")
    captured = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        for block_id, cat, aspect, desc in REPRESENTATIVE_BLOCKS:
            w, h = (360, 640) if aspect == "9:16" else (640, 360)
            page = browser.new_page(viewport={"width": w, "height": h})
            url = f"http://127.0.0.1:16888/api/projects/catalog/blocks/{block_id}/preview?aspect_ratio={aspect}"
            page.goto(url)
            page.wait_for_timeout(1000)
            
            # Seek timeline if available
            page.evaluate("""() => {
                if (window.tl && typeof window.tl.seek === 'function') window.tl.seek(1.5, false);
                if (window.__timelines) {
                    for (var k in window.__timelines) {
                        if (window.__timelines[k] && typeof window.__timelines[k].seek === 'function') {
                            window.__timelines[k].seek(1.5, false);
                        }
                    }
                }
            }""")
            page.wait_for_timeout(300)
            
            out_png = OUTPUT_DIR / f"rep_{block_id}_{aspect.replace(':', 'x')}.png"
            page.screenshot(path=str(out_png))
            page.close()
            captured.append((block_id, cat, aspect, desc, out_png))
            print(f"Captured {block_id} ({cat}, {aspect})")

        browser.close()

    # Build 2-column x 3-row contact sheet
    card_w = 480
    card_h = 280
    margin = 20
    header_h = 80
    label_h = 50
    cols = 2
    rows = 3

    sheet_w = cols * card_w + (cols + 1) * margin
    sheet_h = header_h + rows * (card_h + label_h) + (rows + 1) * margin

    sheet = Image.new("RGB", (sheet_w, sheet_h), color=(15, 23, 42)) # Slate 900
    draw = ImageDraw.Draw(sheet)

    draw.text((margin, 20), "VIRALMINT — AUTHENTIC HYPERFRAMES PREVIEW COVERAGE SAMPLE", fill=(255, 255, 255))
    draw.text((margin, 46), "Demonstrating 6 authentic representative components across categories, aspect ratios and visual shaders", fill=(148, 163, 184))

    for idx, (bname, cat, aspect, desc, fpath) in enumerate(captured):
        c = idx % cols
        r = idx // cols
        x = margin + c * (card_w + margin)
        y = header_h + margin + r * (card_h + label_h + margin)

        draw.rectangle([x - 1, y - 1, x + card_w + 1, y + card_h + label_h + 1], fill=(30, 41, 59), outline=(51, 65, 85))

        if fpath.exists():
            with Image.open(fpath) as im:
                thumb = Image.new("RGB", (card_w, card_h), (11, 15, 25))
                im_c = im.convert("RGB")
                im_c.thumbnail((card_w, card_h), Image.Resampling.LANCZOS)
                ox = (card_w - im_c.width) // 2
                oy = (card_h - im_c.height) // 2
                thumb.paste(im_c, (ox, oy))
                sheet.paste(thumb, (x, y))

        draw.rectangle([x, y + card_h, x + card_w, y + card_h + label_h], fill=(15, 23, 42))
        draw.text((x + 10, y + card_h + 8), f"{cat.upper()} • {bname} ({aspect})", fill=(56, 189, 248))
        draw.text((x + 10, y + card_h + 28), desc, fill=(148, 163, 184))

    out_file = OUTPUT_DIR / "REPRESENTATIVE_BLOCKS_HONEST_PREVIEW_CONTACT_SHEET.png"
    sheet.save(out_file, quality=95)
    print(f"Deliverable 2 contact sheet saved to {out_file}")

if __name__ == "__main__":
    capture_and_build_representative_sheet()
