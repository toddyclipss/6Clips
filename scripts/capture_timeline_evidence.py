import asyncio
import os
from playwright.async_api import async_playwright

OUTPUT_DIR = r"C:\Users\toddy\.gemini\antigravity\brain\8591c73d-112b-47ac-9f6e-5ff0772856bc\evidence_timeline"
os.makedirs(OUTPUT_DIR, exist_ok=True)

VIEWPORTS = [
    {"width": 1920, "height": 1080, "name": "1920x1080"},
    {"width": 1440, "height": 900, "name": "1440x900"},
    {"width": 1366, "height": 768, "name": "1366x768"},
]

async def capture_for_viewport(pw, vp):
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context(viewport={"width": vp["width"], "height": vp["height"]})
    page = await context.new_page()

    print(f"--- Running capture for {vp['name']} ---")
    await page.goto("http://127.0.0.1:16888/", wait_until="networkidle")
    await asyncio.sleep(2)

    # 1. Switch to the demo session in chat history
    # Click history button in ChatPanel
    history_btn = page.locator("button[aria-label='History'], button:has-text('History'), button[title='History']")
    if await history_btn.count() > 0:
        await history_btn.first.click()
        await asyncio.sleep(1)

        # Click the demo session item
        session_item = page.locator("text='Main Agent Tool Execution Demo'")
        if await session_item.count() > 0:
            await session_item.first.click()
            await asyncio.sleep(1.5)
        else:
            # Fallback: click first session
            first_sess = page.locator("li.MuiListItemButton-root, div.MuiListItemButton-root").first
            if await first_sess.count() > 0:
                await first_sess.click()
                await asyncio.sleep(1.5)

    # State 1: Collapsed default state
    await page.screenshot(
        path=os.path.join(OUTPUT_DIR, f"01_thoughtchain_collapsed_{vp['name']}.png"),
        full_page=False
    )
    print(f"Captured: 01_thoughtchain_collapsed_{vp['name']}.png")

    # State 2: Expand ThoughtChain
    # Look for "Show details" button
    show_details_btn = page.locator("button:has-text('Show details')")
    if await show_details_btn.count() > 0:
        await show_details_btn.first.click()
        await asyncio.sleep(1)

    await page.screenshot(
        path=os.path.join(OUTPUT_DIR, f"02_thoughtchain_expanded_{vp['name']}.png"),
        full_page=False
    )
    print(f"Captured: 02_thoughtchain_expanded_{vp['name']}.png")

    # State 3: Expand ToolInvocation inside ThoughtChain
    # Click on the search_catalog tool item header
    tool_header = page.locator("button:has-text('search_catalog')")
    if await tool_header.count() > 0:
        await tool_header.first.click()
        await asyncio.sleep(0.8)

    await page.screenshot(
        path=os.path.join(OUTPUT_DIR, f"03_tool_invocation_expanded_{vp['name']}.png"),
        full_page=False
    )
    print(f"Captured: 03_tool_invocation_expanded_{vp['name']}.png")

    # State 4: Persistence after reload
    await page.reload(wait_until="networkidle")
    await asyncio.sleep(2)

    await page.screenshot(
        path=os.path.join(OUTPUT_DIR, f"04_timeline_persisted_reload_{vp['name']}.png"),
        full_page=False
    )
    print(f"Captured: 04_timeline_persisted_reload_{vp['name']}.png")

    await browser.close()

async def main():
    async with async_playwright() as pw:
        for vp in VIEWPORTS:
            await capture_for_viewport(pw, vp)
    print("All captures finished successfully!")

if __name__ == "__main__":
    asyncio.run(main())
