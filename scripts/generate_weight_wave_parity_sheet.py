import os
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path("artifacts/motion_ux_corrections")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def capture_weight_wave_matrix():
    print("Capturing weight-wave comparison frames...")
    frames = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # 1. Direct HyperFrames original block renders
        # In 16:9 (native 1920x1080)
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        for t in [0.5, 1.5, 2.5]:
            page.goto("http://127.0.0.1:16888/api/projects/catalog/blocks/weight-wave/preview?aspect_ratio=16:9")
            page.wait_for_timeout(400)
            page.evaluate(f"() => {{ if (window.__timelines && window.__timelines['preview_weight-wave']) window.__timelines['preview_weight-wave'].seek({t}, false); }}")
            page.wait_for_timeout(200)
            p_out = OUTPUT_DIR / f"ww_orig_169_t{t}.png"
            page.screenshot(path=str(p_out))
            frames[f"orig_169_{t}"] = p_out
        page.close()

        # In 9:16 (1080x1920 virtual portrait)
        page_port = browser.new_page(viewport={"width": 1080, "height": 1920})
        for t in [0.5, 1.5, 2.5]:
            page_port.goto("http://127.0.0.1:16888/api/projects/catalog/blocks/weight-wave/preview?aspect_ratio=9:16")
            page_port.wait_for_timeout(400)
            page_port.evaluate(f"() => {{ if (window.__timelines && window.__timelines['preview_weight-wave']) window.__timelines['preview_weight-wave'].seek({t}, false); }}")
            page_port.wait_for_timeout(200)
            p_out = OUTPUT_DIR / f"ww_orig_916_t{t}.png"
            page_port.screenshot(path=str(p_out))
            frames[f"orig_916_{t}"] = p_out
        page_port.close()

        # Helper to navigate to catalog & hover weight-wave
        def open_catalog_and_hover(pg):
            cat_btn = pg.locator('button:has-text("Catalog & Media")').first
            if cat_btn.is_visible():
                cat_btn.click()
                pg.wait_for_timeout(400)
            cat_chip = pg.locator('button:has-text("HyperFrames Catalog")').first
            if cat_chip.is_visible():
                cat_chip.click()
                pg.wait_for_timeout(600)
            else:
                tabs = pg.locator('.MuiTabs-root button')
                if tabs.count() >= 3:
                    tabs.nth(2).click()
                    pg.wait_for_timeout(600)

            type_chip = pg.locator('span:text-is("Typography")').first
            if type_chip.is_visible():
                type_chip.click()
                pg.wait_for_timeout(400)

            ww_card = pg.locator('[data-testid="catalog-card-weight-wave"]').first
            if ww_card.is_visible():
                ww_card.hover()
                pg.wait_for_timeout(800)
            return ww_card

        def seek_in_frame(pg, target_time):
            for f in pg.frames:
                if "weight-wave" in f.url:
                    try:
                        f.evaluate(f"""() => {{
                            if (window.__timelines) {{
                                for (let k in window.__timelines) {{
                                    window.__timelines[k].seek({target_time}, false);
                                }}
                            }}
                        }}""")
                    except Exception:
                        pass

        # 2. Live in-editor Ghost Previews in /motion (9:16 Mode)
        p_916 = browser.new_page(viewport={"width": 1920, "height": 1080})
        p_916.goto("http://127.0.0.1:16888/motion")
        p_916.wait_for_timeout(2000)
        open_catalog_and_hover(p_916)
        for t in [0.5, 1.5, 2.5]:
            seek_in_frame(p_916, t)
            p_916.wait_for_timeout(250)
            p_out = OUTPUT_DIR / f"ww_ghost_916_t{t}.png"
            stage_el = p_916.locator('[data-testid="studio-preview-stage"]').first
            stage_el.screenshot(path=str(p_out))
            frames[f"ghost_916_{t}"] = p_out
        p_916.close()

        # 3. Live in-editor Ghost Previews in /motion (16:9 Mode)
        p_169 = browser.new_page(viewport={"width": 1920, "height": 1080})
        p_169.goto("http://127.0.0.1:16888/motion")
        p_169.wait_for_timeout(2000)
        # Click 16:9 aspect button
        aspect_btn = p_169.locator('button:has-text("16:9")').first
        aspect_btn.click()
        p_169.wait_for_timeout(600)
        open_catalog_and_hover(p_169)
        for t in [0.5, 1.5, 2.5]:
            seek_in_frame(p_169, t)
            p_169.wait_for_timeout(250)
            p_out = OUTPUT_DIR / f"ww_ghost_169_t{t}.png"
            stage_el = p_169.locator('[data-testid="studio-preview-stage"]').first
            stage_el.screenshot(path=str(p_out))
            frames[f"ghost_169_{t}"] = p_out
        p_169.close()

        browser.close()

    print("All comparison frames captured successfully.")
    return frames

def build_weight_wave_contact_sheet(frames):
    print("Building weight-wave comparison contact sheet...")
    poster_916 = Path("storage/catalog_posters/weight-wave_c7e1d443c713d24c_9x16.png")
    poster_169 = Path("storage/catalog_posters/weight-wave_c7e1d443c713d24c_16x9.png")

    card_w = 420
    card_h = 240
    margin = 16
    header_h = 80
    cols = 4
    rows = 4

    sheet_w = cols * card_w + (cols + 1) * margin
    sheet_h = header_h + rows * (card_h + 30) + (rows + 1) * margin

    sheet = Image.new("RGB", (sheet_w, sheet_h), color=(15, 23, 42)) # Slate 900
    draw = ImageDraw.Draw(sheet)

    draw.text((margin, 20), "VIRALMINT — WEIGHT-WAVE BLOCK GEOMETRY & PARITY AUDIT", fill=(255, 255, 255))
    draw.text((margin, 46), "Side-by-side verification: Original HyperFrames vs Cached Poster vs In-Editor Ghost Stage (9:16 & 16:9 across t=0.5s, 1.5s, 2.5s)", fill=(148, 163, 184))

    items = [
        # Row 1: 9:16 Portrait Progression
        ("ww_orig_916_0.5", "1. Orig HyperFrames (9:16, t=0.5s)", frames.get("orig_916_0.5")),
        ("ww_orig_916_1.5", "2. Orig HyperFrames (9:16, t=1.5s)", frames.get("orig_916_1.5")),
        ("ww_orig_916_2.5", "3. Orig HyperFrames (9:16, t=2.5s)", frames.get("orig_916_2.5")),
        ("poster_916", "4. Cached Catalog Poster (9:16)", poster_916),

        # Row 2: 9:16 In-Editor Ghost Preview
        ("ghost_916_0.5", "5. Ghost Stage /motion (9:16, t=0.5s)", frames.get("ghost_916_0.5")),
        ("ghost_916_1.5", "6. Ghost Stage /motion (9:16, t=1.5s)", frames.get("ghost_916_1.5")),
        ("ghost_916_2.5", "7. Ghost Stage /motion (9:16, t=2.5s)", frames.get("ghost_916_2.5")),
        ("ghost_916_fit", "8. Ghost Bounds Parity (9:16)", frames.get("ghost_916_1.5")),

        # Row 3: 16:9 Landscape Progression
        ("ww_orig_169_0.5", "9. Orig HyperFrames (16:9, t=0.5s)", frames.get("orig_169_0.5")),
        ("ww_orig_169_1.5", "10. Orig HyperFrames (16:9, t=1.5s)", frames.get("orig_169_1.5")),
        ("ww_orig_169_2.5", "11. Orig HyperFrames (16:9, t=2.5s)", frames.get("orig_169_2.5")),
        ("poster_169", "12. Cached Catalog Poster (16:9)", poster_169),

        # Row 4: 16:9 In-Editor Ghost Preview
        ("ghost_169_0.5", "13. Ghost Stage /motion (16:9, t=0.5s)", frames.get("ghost_169_0.5")),
        ("ghost_169_1.5", "14. Ghost Stage /motion (16:9, t=1.5s)", frames.get("ghost_169_1.5")),
        ("ghost_169_2.5", "15. Ghost Stage /motion (16:9, t=2.5s)", frames.get("ghost_169_2.5")),
        ("ghost_169_fit", "16. Ghost Bounds Parity (16:9)", frames.get("ghost_169_1.5")),
    ]

    for idx, (key, label, fpath) in enumerate(items):
        c = idx % cols
        r = idx // cols
        x = margin + c * (card_w + margin)
        y = header_h + margin + r * (card_h + 30 + margin)

        draw.rectangle([x - 1, y - 1, x + card_w + 1, y + card_h + 31], fill=(30, 41, 59), outline=(51, 65, 85))

        if fpath and Path(fpath).exists():
            with Image.open(fpath) as im:
                im_thumb = Image.new("RGB", (card_w, card_h), (11, 15, 25))
                im_copy = im.convert("RGB")
                im_copy.thumbnail((card_w, card_h), Image.Resampling.LANCZOS)
                offset_x = (card_w - im_copy.width) // 2
                offset_y = (card_h - im_copy.height) // 2
                im_thumb.paste(im_copy, (offset_x, offset_y))
                sheet.paste(im_thumb, (x, y))

        draw.rectangle([x, y + card_h, x + card_w, y + card_h + 30], fill=(15, 23, 42))
        draw.text((x + 8, y + card_h + 8), label, fill=(56, 189, 248))

    out_sheet = OUTPUT_DIR / "WEIGHT_WAVE_VISUAL_COMPARISON_CONTACT_SHEET.png"
    sheet.save(out_sheet, quality=95)
    print(f"Deliverable 1 contact sheet saved to {out_sheet}")

if __name__ == "__main__":
    f_map = capture_weight_wave_matrix()
    build_weight_wave_contact_sheet(f_map)
