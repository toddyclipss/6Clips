# SPDX-License-Identifier: AGPL-3.0-only
from pathlib import Path

donor_root = Path(r"C:\Users\toddy\Desktop\hyperframes\registry\blocks")
names = [
    "whip-pan", "ripple-waves", "sdf-iris", "ridged-burn", "thermal-distortion",
    "transitions-push", "transitions-dissolve", "transitions-radial",
    "transitions-cover", "transitions-scale", "transitions-grid", "transitions-blur"
]

for name in names:
    p = donor_root / name / f"{name}.html"
    if not p.exists():
        print(f"{name}: NOT FOUND")
        continue
    html = p.read_text(encoding="utf-8")
    has_gl = "webgl" in html.lower()
    has_gsap = "gsap" in html.lower()
    has_timelines = "__timelines" in html
    print(f"{name}: len={len(html)} webgl={has_gl} gsap={has_gsap} timelines={has_timelines}")
