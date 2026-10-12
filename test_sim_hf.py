import asyncio
import pprint
from backend.services.hyperframes_adapter import HyperFramesAdapter
from playwright.async_api import async_playwright

async def inspect():
    rev, work = await HyperFramesAdapter.stage_project_for_render('e2e7a00b-8f6f-4c4a-bc8b-b3857c4fd1ac', 2)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1920, 'height': 1080})
        await page.goto((work / 'index.html').as_uri())
        await page.wait_for_timeout(2000)
        
        js_code = """
        () => {
            const video = document.querySelector('video');
            const computedStyle = window.getComputedStyle(video);
            const videoRect = video.getBoundingClientRect();
            const offsetLeft = Number.isFinite(video.offsetLeft) ? video.offsetLeft : 0;
            const offsetTop = Number.isFinite(video.offsetTop) ? video.offsetTop : 0;
            const offsetWidth = video.offsetWidth > 0 ? video.offsetWidth : videoRect.width;
            const offsetHeight = video.offsetHeight > 0 ? video.offsetHeight : videoRect.height;
            
            const img = document.createElement('img');
            img.classList.add('__render_frame__');
            img.id = '__render_frame_' + video.id + '__';
            img.style.pointerEvents = 'none';
            video.parentNode.insertBefore(img, video.nextSibling);
            
            img.style.position = 'absolute';
            img.style.inset = 'auto';
            img.style.left = offsetLeft + 'px';
            img.style.top = offsetTop + 'px';
            img.style.right = 'auto';
            img.style.bottom = 'auto';
            img.style.width = offsetWidth + 'px';
            img.style.height = offsetHeight + 'px';
            img.style.objectFit = computedStyle.objectFit;
            img.style.objectPosition = computedStyle.objectPosition;
            img.style.zIndex = computedStyle.zIndex;
            
            const canvas = document.createElement('canvas');
            canvas.width = 720;
            canvas.height = 1280;
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = 'red';
            ctx.fillRect(0, 0, 720, 1280);
            ctx.fillStyle = 'blue';
            ctx.fillRect(100, 100, 520, 1080);
            img.src = canvas.toDataURL();
            
            return {
                videoComputedObjectFit: computedStyle.objectFit,
                imgStyleObjectFit: img.style.objectFit,
                imgComputedObjectFit: window.getComputedStyle(img).objectFit,
                imgRect: {
                    left: img.getBoundingClientRect().left,
                    top: img.getBoundingClientRect().top,
                    width: img.getBoundingClientRect().width,
                    height: img.getBoundingClientRect().height
                },
                offsetLeft: offsetLeft,
                offsetTop: offsetTop,
                offsetWidth: offsetWidth,
                offsetHeight: offsetHeight
            };
        }
        """
        res = await page.evaluate(js_code)
        pprint.pprint(res)
        await page.screenshot(path='test_hf_img_render.png')
        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect())
