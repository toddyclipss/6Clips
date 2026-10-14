import json
import re
from pathlib import Path

donor_root = Path(r"C:\Users\toddy\Desktop\hyperframes\registry\blocks")
slugs = [
    'aurora', 'flowing-gradient', 'holographic', 'plasma', 'stripes',
    'blob', 'fractal-noise', 'frost', 'godrays', 'goo', 'lens-flare', 'liquid-metal',
    'marble', 'mesh-gradient', 'nebula', 'prism', 'sine-wave', 'strands', 'swirl',
    'voronoi', 'water', 'waveform'
]

for s in slugs:
    p = donor_root / s
    item_p = p / "registry-item.json"
    html_p = p / f"{s}.html"
    item = json.loads(item_p.read_text(encoding="utf-8")) if item_p.exists() else {}
    html = html_p.read_text(encoding="utf-8") if html_p.exists() else ""

    item_vars = item.get("variables", [])
    html_vars = []
    m = re.search(r'data-composition-variables=([\'"])(.*?)\1', html, re.DOTALL)
    if m:
        try:
            html_vars = json.loads(m.group(2))
        except Exception:
            pass

    print(f"[{s}]")
    print(f"  item_vars ({len(item_vars)}): {item_vars}")
    print(f"  html_vars ({len(html_vars)}): {html_vars}")
