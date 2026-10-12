import asyncio
import pprint
from playwright.async_api import async_playwright

async def inspect():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        html = '<!DOCTYPE html><html><head><style>video { position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: contain; }</style></head><body><video id="v1" style="z-index: 0; " style="object-fit: cover;"></video><video id="v2" style="z-index: 0; object-fit: cover;"></video></body></html>'
        await page.set_content(html)
        info = await page.evaluate('() => ({ v1_fit: getComputedStyle(document.querySelector("#v1")).objectFit, v2_fit: getComputedStyle(document.querySelector("#v2")).objectFit, v1_outer: document.querySelector("#v1").outerHTML, v2_outer: document.querySelector("#v2").outerHTML })')
        pprint.pprint(info)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect())
