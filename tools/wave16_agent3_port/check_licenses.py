#!/usr/bin/env python3
import json
import re
from pathlib import Path

donor_root = Path(r"C:\Users\toddy\Desktop\hyperframes\registry\blocks")
shipped_root = Path(__file__).resolve().parents[2] / "backend" / "catalog" / "shipped_blocks"
all_donor = sorted([d.name for d in donor_root.iterdir() if d.is_dir()])
shipped_slugs = set(d.name for d in shipped_root.iterdir() if d.is_dir())
am_unported = [s for s in all_donor if s[0].lower() <= 'm' and s not in shipped_slugs]

blocked_rights = {
    "apple-money-count": "Proprietary Apple trademark and audio assets",
    "blue-sweater-intro-video": "Proprietary personal creator likeness/avatar asset (joe-sai-avatar.png)",
    "chatgpt-exchange": "Proprietary OpenAI ChatGPT brand and trademark",
    "claude-exchange": "Proprietary Anthropic Claude brand and trademark",
    "code-snippet-apple-terminal-pro": "Proprietary Apple macOS Terminal branding and visual trade dress",
    "heygen-avatar-promo-card": "Proprietary HeyGen avatar and service trademark",
    "ios26-liquid-glass": "Proprietary Apple iPhone 3D model (iphone.glb) and 25 trademarked iOS app icons",
    "macos-notification": "Proprietary Apple macOS notification design and trade dress",
    "macos-tahoe-liquid-glass": "Proprietary Apple MacBook 3D model (macbook.glb) and macOS dock/app icons",
}

print(f"Total unported A-M: {len(am_unported)}")
print(f"Blocked Rights count: {len(blocked_rights)}")
permissive_candidates = [s for s in am_unported if s not in blocked_rights]
print(f"Permissive candidates count: {len(permissive_candidates)}")

# Check if any candidate has license or assets issues
for s in permissive_candidates:
    d = donor_root / s
    reg_f = d / "registry-item.json"
    html_f = d / f"{s}.html"
    reg = json.loads(reg_f.read_text(encoding="utf-8", errors="ignore")) if reg_f.exists() else {}
    html = html_f.read_text(encoding="utf-8", errors="ignore") if html_f.exists() else ""
    assets = [f.name for f in (d / "assets").glob("**/*") if f.is_file()] if (d / "assets").exists() else []
    
    # Check for GPL or proprietary licenses
    license_files = [f for f in assets if "license" in f.lower() or "notice" in f.lower() or "copying" in f.lower()]
    if license_files:
        print(f"{s}: license files={license_files}")
