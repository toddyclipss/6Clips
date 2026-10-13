import asyncio
import json
import sqlite3
from pathlib import Path
from playwright.async_api import async_playwright

BASE_DIR = Path("c:/Users/toddy/Desktop/ViralMint")
EVIDENCE_DIR = BASE_DIR / "tests" / "visual_evidence"
PORT = 16889
BASE_URL = f"http://127.0.0.1:{PORT}"
ISOLATED_DB = BASE_DIR / "tmp_isolated_test" / "viralmint.db"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await ctx.new_page()

        await page.goto(f"{BASE_URL}/trends", wait_until="networkidle")
        await page.evaluate("""() => {
            localStorage.setItem("6clips_ai_provider", "ollama");
            localStorage.setItem("6clips_ai_model", "gemma4:e4b");
            localStorage.setItem("6clips_ai_reasoning", "low");
        }""")
        await page.reload(wait_until="networkidle")
        await asyncio.sleep(2)

        textarea = page.locator("textarea").first
        await textarea.wait_for(state="visible", timeout=10000)
        
        prompt = "Use video_id apex_clutch_40s. Create a 9:16 gaming highlight from it. Use suggest_clips to pick the best moment, create the project, and render the highlight."
        await textarea.fill(prompt)
        await asyncio.sleep(0.5)

        await page.keyboard.press("Enter")
        print("[Chat] Prompt with video_id apex_clutch_40s submitted.")

        # Monitor for tool executions
        for i in range(45):
            await asyncio.sleep(2)
            content = await page.content()
            if "completed" in content or "Executing" in content or "suggest_clips" in content or "ThoughtChain" in content:
                print(f"[Chat] Active response / tool events detected at t={i*2}s")
                if "completed" in content:
                    print("[Chat] Tool execution completed!")
                    break

        await asyncio.sleep(3)

        expand_buttons = page.locator("button:has-text('completed'), button:has-text('steps'), button:has-text('step')")
        count = await expand_buttons.count()
        if count > 0:
            try:
                await expand_buttons.first.click()
                print("[Chat] Clicked ThoughtChain expand toggle")
                await asyncio.sleep(1)
            except Exception as e:
                print("[Chat] Could not click expand:", e)

        shot_path = EVIDENCE_DIR / "chat_workflow_actual_1920x1080.png"
        await page.screenshot(path=str(shot_path), full_page=True)
        print(f"[Chat] Screenshot saved: {shot_path.name}")

        await page.reload(wait_until="networkidle")
        await asyncio.sleep(2)
        shot_reload = EVIDENCE_DIR / "chat_workflow_reloaded_1920x1080.png"
        await page.screenshot(path=str(shot_reload), full_page=True)
        print(f"[Chat] Reload screenshot saved: {shot_reload.name}")

        await ctx.close()
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
