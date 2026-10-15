#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
import re
from pathlib import Path

donor_root = Path(r"C:\Users\toddy\Desktop\hyperframes\registry\blocks")
shipped_root = Path(__file__).resolve().parents[2] / "backend" / "catalog" / "shipped_blocks"
all_donor = sorted([d.name for d in donor_root.iterdir() if d.is_dir()])
shipped_slugs = set(d.name for d in shipped_root.iterdir() if d.is_dir())
am_unported = [s for s in all_donor if s[0].lower() <= 'm' and s not in shipped_slugs]

all_scripts = set()
script_to_blocks = {}
for s in am_unported:
    html_file = donor_root / s / f"{s}.html"
    if not html_file.exists():
        continue
    html = html_file.read_text(encoding="utf-8", errors="ignore")
    scripts = re.findall(r'<script[^>]*src=["\']([^"\']+)["\']', html, re.I)
    for sc in scripts:
        all_scripts.add(sc)
        script_to_blocks.setdefault(sc, []).append(s)

print("All distinct script sources in donor A-M unported:")
for sc in sorted(all_scripts):
    print(f"  {sc} ({len(script_to_blocks[sc])} blocks)")
