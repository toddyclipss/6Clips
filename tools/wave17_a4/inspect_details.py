from pathlib import Path
import re

donor_dir = Path(r"C:\Users\toddy\Desktop\hyperframes\registry\blocks")

targets = [
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
    "starfield"
]

for t in targets:
    sdir = donor_dir / t
    html_files = list(sdir.glob("*.html"))
    print(f"\n--- {t} ---")
    for h in html_files:
        content = h.read_text(encoding="utf-8", errors="ignore")
        # Check for remote links / scripts / styles
        urls = re.findall(r'(?:href|src)=["\'](https?://[^"\']+)["\']', content)
        print(f"File {h.name}: found URLs: {urls}")
        # Check GSAP functions used
        gsap_calls = set(re.findall(r'gsap\.(\w+)', content))
        timeline_calls = set(re.findall(r'tl\.(\w+)', content))
        print(f"GSAP methods: {gsap_calls}, Timeline methods: {timeline_calls}")
