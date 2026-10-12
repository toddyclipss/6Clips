import asyncio
import os
from playwright.async_api import async_playwright

timestamps = [0.5, 1.0, 2.0, 4.0]

async def capture_all():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1400, "height": 900})
        
        # --- 9:16 ---
        url_916 = "http://localhost:5173/motion?projectId=53546b29-2e31-4a64-bffd-4c6852d86619"
        await page.goto(url_916, wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)
        
        iframe_elem = page.locator("#studio-preview-iframe")
        await iframe_elem.wait_for(state="visible")
        
        for t in timestamps:
            await page.evaluate("""(targetTime) => {
                const iframe = document.querySelector('#studio-preview-iframe');
                if (iframe && iframe.contentWindow) {
                    iframe.contentWindow.postMessage({ source: 'vm-parent', action: 'seek', time: targetTime }, '*');
                }
            }""", t)
            await page.wait_for_timeout(900)
            
            out_name = f"preview_9x16_t{t:.1f}.png"
            await iframe_elem.screenshot(path=out_name)
            print(f"Captured {out_name}: exists={os.path.exists(out_name)}")

        # --- 16:9 ---
        url_169 = "http://localhost:5173/motion?projectId=e2e7a00b-8f6f-4c4a-bc8b-b3857c4fd1ac"
        await page.goto(url_169, wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)
        
        iframe_elem_169 = page.locator("#studio-preview-iframe")
        await iframe_elem_169.wait_for(state="visible")
        
        for t in timestamps:
            await page.evaluate("""(targetTime) => {
                const iframe = document.querySelector('#studio-preview-iframe');
                if (iframe && iframe.contentWindow) {
                    iframe.contentWindow.postMessage({ source: 'vm-parent', action: 'seek', time: targetTime }, '*');
                }
            }""", t)
            await page.wait_for_timeout(900)
            
            out_name = f"preview_16x9_t{t:.1f}.png"
            await iframe_elem_169.screenshot(path=out_name)
            print(f"Captured {out_name}: exists={os.path.exists(out_name)}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(capture_all())
