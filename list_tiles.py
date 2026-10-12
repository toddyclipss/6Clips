import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        await page.goto("http://127.0.0.1:16888/videos?media=audio", wait_until="networkidle")
        tiles = await page.locator('[data-testid="asset-tile"]').all()
        for i, t in enumerate(tiles):
            txt = await t.text_content()
            print(f"{i}: {repr(txt)}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
