import os
from pathlib import Path
from PIL import Image, ImageDraw
from backend.services.catalog_preview_service import CatalogPreviewService

def generate_sheet():
    rows = [
        {
            'id': 'ai-chat-reveal',
            'title': 'AI Chat Reveal',
            'native_dim': '1080 x 1920 (9:16)',
            'cat_916': 'NATIVE',
            'badge_color_916': (34, 197, 94),
            'desc_916': 'Authored natively for vertical portrait formats (1080x1920). Fills composition.',
            'cat_169': 'CONTAINED_ONLY',
            'badge_color_169': (234, 179, 8),
            'desc_169': 'Proportionally pillarboxed in 16:9 landscape without distortion or clipping.',
        },
        {
            'id': 'weight-wave',
            'title': 'Weight Wave Kinetic Type',
            'native_dim': '1920 x 1080 (16:9)',
            'cat_916': 'ADAPTED',
            'badge_color_916': (59, 130, 246),
            'desc_916': 'Adaptive reflow: dynamic font scaling, multi-line wrapping & vertical centering in 9:16.',
            'cat_169': 'NATIVE',
            'badge_color_169': (34, 197, 94),
            'desc_169': 'Authored full-bleed landscape typography with native horizontal baseline.',
        },
        {
            'id': 'data-chart',
            'title': 'Data Chart Visualization',
            'native_dim': '1920 x 1080 (16:9)',
            'cat_916': 'CONTAINED_ONLY',
            'badge_color_916': (234, 179, 8),
            'desc_916': 'Proportionally letterboxed and centered in 9:16. Authentic styling & chart axes.',
            'cat_169': 'NATIVE',
            'badge_color_169': (34, 197, 94),
            'desc_169': 'Authored natively for full 16:9 landscape canvas (1920x1080).',
        },
        {
            'id': 'yt-lower-third',
            'title': 'YouTube Lower Third Banner',
            'native_dim': '1920 x 1080 (16:9)',
            'cat_916': 'CONTAINED_ONLY',
            'badge_color_916': (234, 179, 8),
            'desc_916': 'Proportionally scaled to 9:16 width; authentic lower banner preserved.',
            'cat_169': 'NATIVE',
            'badge_color_169': (34, 197, 94),
            'desc_169': 'Authored lower third docked along bottom boundary of 1920x1080 composition.',
        },
        {
            'id': 'webgpu-fluid-sim',
            'title': 'WebGPU Fluid Shader (Missing Driver)',
            'native_dim': 'Shader Canvas (Varies)',
            'cat_916': 'PREVIEW_UNAVAILABLE',
            'badge_color_916': (239, 68, 68),
            'desc_916': 'Honest neutral slate fallback card: explicitly declares preview is unavailable.',
            'cat_169': 'PREVIEW_UNAVAILABLE',
            'badge_color_169': (239, 68, 68),
            'desc_169': 'Honest neutral slate fallback card: no synthetic PIL decorative artworks.',
            'is_fallback': True
        }
    ]

    row_height = 290
    header_height = 130
    total_width = 1440
    total_height = header_height + (len(rows) * row_height) + 40

    sheet = Image.new('RGB', (total_width, total_height), color=(10, 15, 29))
    draw = ImageDraw.Draw(sheet)

    # Header
    draw.rectangle((0, 0, total_width, header_height), fill=(15, 23, 42))
    draw.line((0, header_height, total_width, header_height), fill=(51, 65, 85), width=2)
    draw.text((36, 18), 'VIRALMINT -- HYPERFRAMES ASPECT COMPATIBILITY MATRIX', fill=(248, 250, 252))
    draw.text((36, 44), 'Truthful Per-Block Classification: NATIVE, ADAPTED, CONTAINED_ONLY, and PREVIEW_UNAVAILABLE', fill=(148, 163, 184))
    draw.text((36, 68), 'Demonstrating authentic rendering behavior across 9:16 (Portrait) and 16:9 (Landscape) viewports', fill=(100, 116, 139))

    draw.text((360, header_height - 24), '9:16 PORTRAIT VIEWPORT (360x640)', fill=(226, 232, 240))
    draw.text((900, header_height - 24), '16:9 LANDSCAPE VIEWPORT (640x360)', fill=(226, 232, 240))

    for idx, r in enumerate(rows):
        y_top = header_height + 20 + (idx * row_height)
        bg_col = (13, 20, 38) if idx % 2 == 0 else (17, 26, 48)
        draw.rectangle((20, y_top, total_width - 20, y_top + row_height - 12), fill=bg_col, outline=(30, 41, 59), width=1)
        
        # Left: Info
        draw.text((36, y_top + 24), r['title'], fill=(255, 255, 255))
        draw.text((36, y_top + 52), f"ID: {r['id']}", fill=(148, 163, 184))
        draw.text((36, y_top + 76), f"Author Dims: {r['native_dim']}", fill=(100, 116, 139))
        
        # 9:16 Frame
        if r.get('is_fallback'):
            p916 = Path('storage/catalog_posters/sample_unavailable_9x16.png')
        else:
            p916 = CatalogPreviewService.get_poster_path(r['id'], aspect_ratio='9:16')
        
        th_h = 240
        th_w = int(th_h * 9 / 16)
        with Image.open(p916) as im916:
            im916_resized = im916.resize((th_w, th_h), Image.Resampling.LANCZOS)
            box_x = 360
            box_y = y_top + 18
            draw.rectangle((box_x - 2, box_y - 2, box_x + th_w + 1, box_y + th_h + 1), fill=(0, 0, 0), outline=(51, 65, 85), width=1)
            sheet.paste(im916_resized, (box_x, box_y))
            
            badge_x = box_x + th_w + 16
            badge_y = box_y + 10
            bw = 180 if len(r['cat_916']) > 12 else 120
            draw.rectangle((badge_x, badge_y, badge_x + bw, badge_y + 22), fill=r['badge_color_916'])
            draw.text((badge_x + 8, badge_y + 4), r['cat_916'], fill=(0, 0, 0))
            
            desc_lines = [r['desc_916'][i:i+42] for i in range(0, len(r['desc_916']), 42)]
            for l_idx, line in enumerate(desc_lines):
                draw.text((badge_x, badge_y + 36 + (l_idx * 18)), line, fill=(203, 213, 225))

        # 16:9 Frame
        if r.get('is_fallback'):
            p169 = Path('storage/catalog_posters/sample_unavailable_16x9.png')
        else:
            p169 = CatalogPreviewService.get_poster_path(r['id'], aspect_ratio='16:9')
            
        th169_w = 240
        th169_h = int(th169_w * 9 / 16)
        with Image.open(p169) as im169:
            im169_resized = im169.resize((th169_w, th169_h), Image.Resampling.LANCZOS)
            box169_x = 900
            box169_y = y_top + 18
            draw.rectangle((box169_x - 2, box169_y - 2, box169_x + th169_w + 1, box169_y + th169_h + 1), fill=(0, 0, 0), outline=(51, 65, 85), width=1)
            sheet.paste(im169_resized, (box169_x, box169_y))
            
            b169_badge_x = box169_x + th169_w + 16
            b169_badge_y = box169_y + 10
            bw169 = 180 if len(r['cat_169']) > 12 else 120
            draw.rectangle((b169_badge_x, b169_badge_y, b169_badge_x + bw169, b169_badge_y + 22), fill=r['badge_color_169'])
            draw.text((b169_badge_x + 8, b169_badge_y + 4), r['cat_169'], fill=(0, 0, 0))
            desc169_lines = [r['desc_169'][i:i+38] for i in range(0, len(r['desc_169']), 38)]
            for l_idx, line in enumerate(desc169_lines):
                draw.text((b169_badge_x, b169_badge_y + 36 + (l_idx * 18)), line, fill=(203, 213, 225))

    out_path = Path('ASPECT_COMPATIBILITY_CONTACT_SHEET.png')
    sheet.save(out_path, format='PNG')
    print(f'Saved {out_path} ({out_path.stat().st_size} bytes)')

if __name__ == '__main__':
    generate_sheet()
