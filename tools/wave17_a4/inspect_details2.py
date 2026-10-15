from pathlib import Path
import re

donor_dir = Path(r"C:\Users\toddy\Desktop\hyperframes\registry\blocks")

targets2 = [
    "orbit-card",
    "swirl-vortex",
    "ui-3d-reveal",
    "vfx-magnetic",
    "vfx-text-cursor"
]

for t in targets2:
    sdir = donor_dir / t
    html_files = list(sdir.glob("*.html"))
    print(f"\n--- {t} ---")
    for h in html_files:
        content = h.read_text(encoding="utf-8", errors="ignore")
        urls = re.findall(r'(?:href|src)=["\'](https?://[^"\']+)["\']', content)
        print(f"File {h.name}: found URLs: {urls}")
        gsap_calls = set(re.findall(r'gsap\.(\w+)', content))
        timeline_calls = set(re.findall(r'tl\.(\w+)', content))
        print(f"GSAP methods: {gsap_calls}, Timeline methods: {timeline_calls}")
