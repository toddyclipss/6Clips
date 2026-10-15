# SPDX-License-Identifier: AGPL-3.0-only
from playwright.sync_api import sync_playwright
from pathlib import Path
from PIL import ImageStat, Image

html_path = Path("backend/catalog/shipped_blocks/news-ticker/news-ticker.html").resolve()
with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    page.goto(html_path.as_uri())
    
    # Check timeline
    has_tl = page.evaluate("() => !!window.__timelines && !!window.__timelines['news-ticker']")
    duration = page.evaluate("() => window.__timelines['news-ticker'].duration()")
    print("Has timeline:", has_tl, "Duration:", duration)
    
    # Seek to 1.5s
    page.evaluate("() => window.__timelines['news-ticker'].seek(1.5)")
    shell_style = page.evaluate("() => document.getElementById('nt-shell').getAttribute('style')")
    shell_opacity = page.evaluate("() => window.getComputedStyle(document.getElementById('nt-shell')).opacity")
    shell_transform = page.evaluate("() => window.getComputedStyle(document.getElementById('nt-shell')).transform")
    print("Shell style:", shell_style)
    print("Shell opacity:", shell_opacity)
    print("Shell transform:", shell_transform)
    
    shot_bytes = page.screenshot()
    import io
    img = Image.open(io.BytesIO(shot_bytes))
    stat = ImageStat.Stat(img)
    print("Mean brightness:", sum(stat.mean) / 3.0)
    browser.close()
