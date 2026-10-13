import asyncio
from playwright.async_api import async_playwright
from pathlib import Path

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = await ctx.new_page()
        await page.goto('http://127.0.0.1:16889/motion?projectId=6169c61a-9805-43fa-9230-7806f4ed922b&mode=refine', wait_until='networkidle')
        code_tab_btn = page.locator("[data-testid='studio-toolbar-code-btn']")
        await code_tab_btn.wait_for(state='visible', timeout=10000)
        await code_tab_btn.click()
        await page.wait_for_selector("[data-testid='studio-code-workspace']", timeout=10000)
        await asyncio.sleep(1)
        shot = Path('tests/visual_evidence/code_ownership_forked_1920x1080.png')
        await page.screenshot(path=str(shot), full_page=True)
        print('Captured code ownership screenshot:', shot.name)
        await ctx.close()
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
