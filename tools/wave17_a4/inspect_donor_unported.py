import json
from pathlib import Path

donor_dir = Path(r"C:\Users\toddy\Desktop\hyperframes\registry\blocks")

unported = [
    "north-korea-locked-down", "notes-reveal", "nyc-paris-flight", "orbit-card",
    "oscilloscope-trace", "product-turntable", "rack-focus", "reddit-post",
    "share-sheet-carousel", "slack-notification-ad", "snow", "spain-map",
    "spiral-galaxy", "spotify-card", "starfield", "swirl-vortex",
    "transitions-3d", "transitions-blur", "transitions-cover", "transitions-destruction",
    "transitions-distortion", "transitions-grid", "transitions-light", "transitions-mechanical",
    "transitions-other", "transitions-scale", "ui-3d-reveal", "us-map",
    "us-map-bubble", "us-map-flow", "us-map-hex", "vfx-anamorphic-flare",
    "vfx-iphone-device", "vfx-liquid-background", "vfx-liquid-glass", "vfx-magnetic",
    "vfx-portal", "vfx-shatter", "vfx-text-cursor", "vpn-youtube-spot",
    "wireframe-portal-title", "world-map", "x-post", "yt-comment-card",
    "yt-lcd-background", "yt-logo-intro", "yt-prism-title", "yt-vertical-fill"
]

results = []

for slug in unported:
    slug_dir = donor_dir / slug
    if not slug_dir.exists():
        results.append({"slug": slug, "exists": False})
        continue
    files = [f.name for f in slug_dir.glob("**/*") if f.is_file()]
    # check html, js, css, etc.
    html_files = [f for f in files if f.endswith(".html")]
    js_files = [f for f in files if f.endswith(".js")]
    json_files = [f for f in files if f.endswith(".json")]
    
    # Read registry-item.json or similar to find description/dependencies
    reg_item_path = slug_dir / "registry-item.json"
    reg_data = {}
    if reg_item_path.exists():
        try:
            with open(reg_item_path, "r", encoding="utf-8") as f:
                reg_data = json.load(f)
        except Exception as e:
            reg_data = {"error": str(e)}

    # inspect HTML for cdns, threejs, gsap, etc.
    cdns = []
    has_three = False
    has_gsap = False
    has_shader = False
    content_snippet = ""
    if html_files:
        main_html = slug_dir / html_files[0]
        try:
            text = main_html.read_text(encoding="utf-8", errors="ignore")
            if "three" in text.lower() or "three.js" in text.lower() or "three.min.js" in text.lower():
                has_three = True
            if "gsap" in text.lower():
                has_gsap = True
            if "webgl" in text.lower() or "glsl" in text.lower() or "fragmentshader" in text.lower() or "createshader" in text.lower():
                has_shader = True
            for line in text.splitlines():
                if "src=" in line and ("http" in line or "//" in line):
                    cdns.append(line.strip())
        except Exception:
            pass

    results.append({
        "slug": slug,
        "exists": True,
        "files": files,
        "html_files": html_files,
        "has_three": has_three,
        "has_gsap": has_gsap,
        "has_shader": has_shader,
        "external_cdns": cdns,
        "type": reg_data.get("type"),
        "title": reg_data.get("title")
    })

print(f"Scanned {len(results)} unported slugs.")
for r in results:
    f_str = ", ".join(r.get("files", []))
    print(f"[{r['slug']}] html={r.get('html_files')} three={r.get('has_three')} gsap={r.get('has_gsap')} shader={r.get('has_shader')} cdns={len(r.get('external_cdns', []))}")
