import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1080, "height": 1920})
        content = """<!DOCTYPE html>
<html>
<head>
<style>
@font-face {
  font-family: 'Recursive Wave';
  src: url('http://127.0.0.1:16888/api/projects/test/preview/compositions/assets/fonts/Recursive-wght-slnt-latin.woff2') format('woff2');
}
html, body { width: 1080px; height: 1920px; margin: 0; overflow: hidden; background: #0b0f19; }
#ww-root { position: relative; width: 1080px; height: 1920px; }
#ww-stage { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; transform: translateY(-380px); }
#ww-line { width: 860px; font-family: 'Recursive Wave', sans-serif; font-size: 80px; color: #f5f5f7; text-align: center; white-space: pre-wrap; word-break: normal; overflow-wrap: normal; line-height: 1.18; }
</style>
</head>
<body>
<div id="ww-root">
  <div id="ww-stage">
    <div id="ww-line">PRESSURE MOVES THROUGH TYPE</div>
  </div>
</div>
</body>
</html>"""
        await page.set_content(content)
        await page.wait_for_timeout(500)
        await page.screenshot(path="test_wrap_balanced.png")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test())
