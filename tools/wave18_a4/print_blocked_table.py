import re
from pathlib import Path

donor_dir = Path(r"C:\Users\toddy\Desktop\hyperframes\registry\blocks")
blocked = [
    "north-korea-locked-down", "notes-reveal", "nyc-paris-flight", "orbit-card",
    "oscilloscope-trace", "product-turntable", "reddit-post", "slack-notification-ad",
    "spain-map", "spiral-galaxy", "spotify-card", "us-map", "us-map-bubble",
    "us-map-flow", "us-map-hex", "vfx-anamorphic-flare", "vfx-iphone-device",
    "vfx-liquid-background", "vfx-liquid-glass", "vfx-portal", "vfx-shatter",
    "vpn-youtube-spot", "wireframe-portal-title", "world-map", "x-post",
    "yt-comment-card", "yt-lcd-background", "yt-logo-intro", "yt-prism-title",
    "yt-vertical-fill"
]

print(f"{'SLUG':25} | {'SCRIPTS':60} | {'ASSETS'}")
print("-" * 110)
for slug in blocked:
    html = donor_dir / slug / f"{slug}.html"
    if not html.exists():
        continue
    content = html.read_text(encoding="utf-8", errors="ignore")
    scripts = re.findall(r'<script[^>]*src=["\']([^"\']+)["\']', content)
    assets_dir = donor_dir / slug / "assets"
    assets = [f.name for f in assets_dir.glob("*")] if assets_dir.exists() else []
    print(f"{slug:25} | {', '.join(scripts):60} | {', '.join(assets)}")
