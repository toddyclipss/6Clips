import os
from PIL import Image, ImageDraw, ImageFont

def build_contact_sheet():
    base_dir = r"c:\Users\toddy\Desktop\ViralMint\artifacts\motion_ux_corrections"
    images_to_include = [
        ("01_editor_layout_fullwidth_timeline_1920x1080.png", "Gate 6: Full-Width Refine Layout (1920x1080) - Timeline Under Left/Center/Right"),
        ("02_catalog_canonical_categories_1920x1080.png", "Gate 4: 8 Canonical Categories & 196 Blocks Index (1920x1080)"),
        ("03_ghost_preview_weight_wave_9x16_1920x1080.png", "Gates 1, 2, 3: Authentic 'weight-wave' Ghost Preview (9:16) - Clean Video Stage, Proportional Fit"),
        ("04_ghost_preview_weight_wave_16x9_1920x1080.png", "Gates 1, 2, 3: Authentic 'weight-wave' Ghost Preview (16:9) - Zero Crop / Pure Stage"),
        ("05_sources_descending_scores_1920x1080.png", "Gate 5: Discovered Sources Ranked Strictly Descending by Virality Score (63.46 -> 27.69)"),
        ("01_editor_layout_fullwidth_timeline_1366x768.png", "Gate 6 & Gate 8: Compact Viewport Integrity (1366x768) - Full-Width Bottom Timeline")
    ]

    loaded = []
    target_w = 960
    target_h = 540

    for fname, label in images_to_include:
        fpath = os.path.join(base_dir, fname)
        if os.path.exists(fpath):
            img = Image.open(fpath).convert("RGB")
            img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
            loaded.append((img, label))
        else:
            print(f"Warning: {fpath} not found")

    if not loaded:
        print("No images found to compile.")
        return

    cols = 2
    rows = (len(loaded) + cols - 1) // cols
    header_h = 90
    card_margin = 20
    label_h = 40

    total_w = cols * target_w + (cols + 1) * card_margin
    total_h = header_h + rows * (target_h + label_h) + (rows + 1) * card_margin

    sheet = Image.new("RGB", (total_w, total_h), color=(15, 23, 42)) # Slate 900
    draw = ImageDraw.Draw(sheet)

    # Title
    draw.text((card_margin, 25), "VIRALMINT — AUTHENTIC HYPERFRAMES PREVIEWS & MOTION UX REMEDIATION", fill=(255, 255, 255))
    draw.text((card_margin, 52), "Visual Verification Contact Sheet: Full-Width Timeline | 8 Canonical Categories | Pure Video Ghost Stage | Descending Scores", fill=(148, 163, 184))

    for idx, (img, label) in enumerate(loaded):
        c = idx % cols
        r = idx // cols
        x = card_margin + c * (target_w + card_margin)
        y = header_h + card_margin + r * (target_h + label_h + card_margin)

        # Draw panel background & border
        draw.rectangle([x - 2, y - 2, x + target_w + 2, y + target_h + label_h + 2], fill=(30, 41, 59), outline=(51, 65, 85), width=1)
        # Paste image
        sheet.paste(img, (x, y))
        # Draw label bar
        draw.rectangle([x, y + target_h, x + target_w, y + target_h + label_h], fill=(15, 23, 42))
        draw.text((x + 12, y + target_h + 12), label, fill=(56, 189, 248))

    out_path = os.path.join(base_dir, "AUTHENTIC_PREVIEWS_AND_UX_CORRECTIONS_CONTACT_SHEET.png")
    sheet.save(out_path, quality=95)
    print(f"Contact sheet saved to {out_path}")

if __name__ == "__main__":
    build_contact_sheet()
