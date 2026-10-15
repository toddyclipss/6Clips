import re
from pathlib import Path
import sys

def check(slug):
    p = Path(r"C:\Users\toddy\Desktop\hyperframes\registry\blocks") / slug
    htmls = list(p.glob("*.html"))
    print(f"=== {slug} ===")
    for h in htmls:
        txt = h.read_text(encoding="utf-8", errors="ignore")
        urls = re.findall(r'(?:href|src)=["\'](https?://[^"\']+)["\']', txt)
        scripts = re.findall(r'<script[^>]*>', txt)
        print(f"  {h.name} ({len(txt)} chars):")
        print(f"    scripts: {scripts}")
        print(f"    urls: {urls}")

if __name__ == "__main__":
    slugs = sys.argv[1:] if len(sys.argv) > 1 else ["rack-focus", "spiral-galaxy", "ui-3d-reveal", "wireframe-portal-title"]
    for s in slugs:
        check(s)
