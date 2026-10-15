import re
from pathlib import Path

lib_file = Path("backend/catalog/shipped_blocks/aurora/lib/shaders.iife.js")
content = lib_file.read_text(encoding="utf-8", errors="ignore")

# Find shader registrations in shaders.iife.js
# Typically shaders registers objects like { Aurora: ..., Plasma: ... } or window.Shaders = { ... }
names = set(re.findall(r'["\']([A-Za-z0-9_-]+)["\']', content))
slugs = [
    'blob', 'fractal-noise', 'frost', 'godrays', 'goo', 'lens-flare', 'liquid-metal',
    'marble', 'mesh-gradient', 'nebula', 'prism', 'sine-wave', 'strands', 'swirl',
    'voronoi', 'water', 'waveform', 'aurora', 'flowing-gradient', 'holographic', 'plasma', 'stripes'
]

found = {}
for s in slugs:
    clean = s.replace("-", "").lower()
    matches = [n for n in names if n.replace("-", "").lower() == clean]
    if matches:
        found[s] = matches

print(f"Total shader slugs matched: {len(found)} / {len(slugs)}")
for s, m in sorted(found.items()):
    print(f"  {s}: {m}")

# Check what data-shader is used in each donor html file
donor_blocks = Path(r"C:\Users\toddy\Desktop\hyperframes\registry\blocks")
print("\nData-shader values in donor html files:")
for s in slugs:
    html_f = donor_blocks / s / f"{s}.html"
    if html_f.exists():
        txt = html_f.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r'data-shader=["\']([^"\']+)["\']', txt)
        val = m.group(1) if m else "NONE"
        print(f"  {s}: data-shader='{val}'")
