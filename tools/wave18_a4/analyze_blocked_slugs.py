import os
import re
import json
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

report = []

for slug in blocked:
    s_dir = donor_dir / slug
    htmls = list(s_dir.glob("*.html"))
    if not htmls:
        report.append({"slug": slug, "status": "NO_HTML"})
        continue
    content = htmls[0].read_text(encoding="utf-8", errors="ignore")
    scripts = re.findall(r'<script[^>]*src=["\']([^"\']+)["\']', content)
    imports = re.findall(r'import\s+.*?from\s+["\']([^"\']+)["\']', content)
    import_maps = re.findall(r'"imports":\s*\{([^}]+)\}', content)
    assets_dir = s_dir / "assets"
    models_dir = s_dir / "models"
    assets_files = [f.name for f in assets_dir.glob("*")] if assets_dir.exists() else []
    models_files = [f.name for f in models_dir.glob("*")] if models_dir.exists() else []
    has_canvas = "<canvas" in content.lower()
    has_webgl = "gl.createShader" in content or "createProgram" in content
    
    report.append({
        "slug": slug,
        "scripts": scripts,
        "imports": imports,
        "import_maps": import_maps,
        "assets": assets_files,
        "models": models_files,
        "canvas": has_canvas,
        "webgl": has_webgl
    })

print(json.dumps(report, indent=2))
