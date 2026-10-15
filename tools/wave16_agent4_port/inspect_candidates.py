# SPDX-License-Identifier: AGPL-3.0-only
import json
from pathlib import Path

donor_root = Path(r"C:\Users\toddy\Desktop\hyperframes\registry\blocks")
candidates = [
    "news-ticker",
    "notification-cascade",
    "orbit-card",
    "organic-light-leak-overlay",
    "share-sheet-carousel",
    "split-flap-board",
    "thread-message-stack",
    "ui-3d-reveal",
    "week-in-merges",
    "whip-pan",
    "ripple-waves",
    "sdf-iris",
    "ridged-burn",
    "thermal-distortion"
]

for name in candidates:
    d = donor_root / name
    if not d.exists():
        print(f"{name}: NOT FOUND")
        continue
    html = d / f"{name}.html"
    reg = d / "registry-item.json"
    
    html_text = html.read_text(encoding="utf-8", errors="replace") if html.exists() else ""
    reg_data = json.loads(reg.read_text(encoding="utf-8")) if reg.exists() else {}
    
    print(f"=== {name} ===")
    print(f"HTML len: {len(html_text)}")
    print(f"Variables: {[v.get('id') for v in reg_data.get('variables', [])]}")
    # Show scripts in html
    import re
    scripts = re.findall(r"<script[\s\S]*?</script>", html_text, re.IGNORECASE)
    print(f"Number of script tags: {len(scripts)}")
    for i, s in enumerate(scripts):
        src = re.findall(r'src=["\']([^"\']+)["\']', s)
        print(f"  Script {i}: src={src} len={len(s)}")
        if not src:
            # show first 100 chars
            snippet = s.replace("\n", " ")[:120]
            print(f"    inline: {snippet}")
    print()
