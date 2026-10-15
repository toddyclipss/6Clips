from pathlib import Path
from playwright.sync_api import sync_playwright
from PIL import Image, ImageChops, ImageStat
import io

p_file = Path("backend/catalog/shipped_blocks/rack-focus/rack-focus.html").resolve().as_uri()

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page()
    page.on("console", lambda m: print("CONSOLE:", m.type, m.text))
    page.on("pageerror", lambda e: print("PAGEERROR:", e))
    page.goto(p_file)
    page.wait_for_timeout(500)
    
    # Check timelines object
    info = page.evaluate("() => ({ keys: Object.keys(window.__timelines || {}), drv: !!document.getElementById('rf-canvas') })")
    print("PAGE INFO:", info)
    
    page.evaluate("() => { if (window.__timelines && window.__timelines['rack-focus']) window.__timelines['rack-focus'].seek(0.5); }")
    page.wait_for_timeout(200)
    img1 = Image.open(io.BytesIO(page.screenshot()))
    
    page.evaluate("() => { if (window.__timelines && window.__timelines['rack-focus']) window.__timelines['rack-focus'].seek(3.5); }")
    page.wait_for_timeout(200)
    img2 = Image.open(io.BytesIO(page.screenshot()))
    
    diff = ImageChops.difference(img1.convert("RGB"), img2.convert("RGB"))
    stat = ImageStat.Stat(diff)
    delta = sum(stat.mean) / 3.0
    print("Rack-focus delta between 0.5s and 3.5s:", delta)
    browser.close()
