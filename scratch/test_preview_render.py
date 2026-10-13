import asyncio
import os
import sys
sys.path.insert(0, '.')
os.environ['VIRALMINT_DATA_DIR'] = 'c:/Users/toddy/Desktop/ViralMint/tmp_isolated_test'

from playwright.async_api import async_playwright
from backend.services.hyperframes_adapter import HyperFramesAdapter

async def test():
    # Sync project to studio
    res = await HyperFramesAdapter.sync_project_to_studio('6169c61a-9805-43fa-9230-7806f4ed922b', 5)
    html_path = res['html_path']
    file_url = f"file:///{html_path.replace(os.sep, '/')}"
    print("Testing file_url:", file_url)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        await page.goto(file_url, wait_until="networkidle")
        
        # Check video element
        v_info = await page.evaluate("""() => {
            const v = document.querySelector('video');
            return {
                src: v ? v.src : null,
                readyState: v ? v.readyState : null,
                videoWidth: v ? v.videoWidth : null,
                videoHeight: v ? v.videoHeight : null,
                currentTime: v ? v.currentTime : null,
                error: v && v.error ? v.error.message : null
            };
        }""")
        print("Video info:", v_info)
        
        # Screenshot stage
        stage = page.locator('#stage')
        await stage.screenshot(path="scratch/stage_test.png")
        print("Stage screenshot saved to scratch/stage_test.png")
        await browser.close()

asyncio.run(test())
