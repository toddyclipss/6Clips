import asyncio
import json
from playwright.async_api import async_playwright
from PIL import Image

async def inspect():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1440, 'height': 900})
        pid = 'd5f13156-fc63-45e5-b448-d347639bc180'
        await page.goto(f'http://127.0.0.1:16888/motion?projectId={pid}', wait_until='networkidle')
        await page.wait_for_timeout(3000)
        
        outer_frame = await (await page.locator('#studio-preview-iframe').element_handle()).content_frame()
        inner_frame = await (await outer_frame.locator('iframe.subcomp-frame').element_handle()).content_frame()
        
        print("=== PREVIEW INSPECTION ===")
        for t in [0.0, 0.1, 0.25, 0.5, 1.0]:
            await outer_frame.evaluate(f"() => {{ if (typeof seekTo === 'function') seekTo({t}); }}")
            await page.wait_for_timeout(300)
            
            p_data = await outer_frame.evaluate("""() => {
                const el = document.querySelector('#elem_fbc05ef7');
                return el ? {
                    styleOpacity: el.style.opacity,
                    computedOpacity: window.getComputedStyle(el).opacity,
                    styleTransform: el.style.transform,
                    visibility: window.getComputedStyle(el).visibility,
                    classes: el.className
                } : null;
            }""")
            
            c_data = await inner_frame.evaluate("""() => {
                const line = document.querySelector('#ww-line');
                const root = document.querySelector('#ww-root');
                return {
                    lineOpacity: line ? window.getComputedStyle(line).opacity : null,
                    lineColor: line ? window.getComputedStyle(line).color : null,
                    rootOpacity: root ? window.getComputedStyle(root).opacity : null
                };
            }""")
            
            snap_path = f"test_preview_t_{t}s.png"
            await page.locator("#studio-preview-iframe").screenshot(path=snap_path)
            im = Image.open(snap_path)
            ext = im.getextrema()
            print(f"Preview t={t}s: parent=#elem_fbc05ef7 {p_data}, child={c_data}, extrema={ext}")
            
        await browser.close()

if __name__ == '__main__':
    asyncio.run(inspect())
