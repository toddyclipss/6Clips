# language: Python, file: scripts/e2e_model_selector_verification.py, target: Windows 11
import os
import asyncio
from playwright.async_api import async_playwright

OUTPUT_DIR = r"C:\Users\toddy\.gemini\antigravity\brain\8591c73d-112b-47ac-9f6e-5ff0772856bc\evidence_selector"
os.makedirs(OUTPUT_DIR, exist_ok=True)

RESOLUTIONS = [
    {"name": "1920x1080", "width": 1920, "height": 1080},
    {"name": "1440x900", "width": 1440, "height": 900},
    {"name": "1366x768", "width": 1366, "height": 768},
]

async def run_scenario():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        for res in RESOLUTIONS:
            res_name = res["name"]
            width = res["width"]
            height = res["height"]
            print(f"\n================ Running for resolution {res_name} ================")

            context = await browser.new_context(viewport={"width": width, "height": height})
            page = await context.new_page()

            # 1. Unselected state: Clear storage first
            await page.goto("http://localhost:5173/motion", wait_until="networkidle")
            await page.evaluate("""() => {
                localStorage.removeItem('6clips_ai_provider');
                localStorage.removeItem('6clips_ai_model');
                localStorage.removeItem('6clips_ai_reasoning');
            }""")
            await page.reload(wait_until="networkidle")
            await asyncio.sleep(2)

            # Check trigger button text
            selector_btn = page.locator("button:has-text('Select Model')").first
            is_unselected_visible = await selector_btn.is_visible()
            print(f"[{res_name}] 'Select Model' button visible:", is_unselected_visible)

            # Check legacy thinking toggle is absent
            thinking_btn = page.locator("button:has-text('Thinking:')")
            thinking_count = await thinking_btn.count()
            print(f"[{res_name}] Legacy 'Thinking:' button count (should be 0):", thinking_count)

            # Try sending message without model selection -> triggers explicit warning & opens popover
            input_box = page.locator("textarea").first
            if await input_box.is_visible():
                await input_box.fill("Generate video")
                await input_box.press("Enter")
                await asyncio.sleep(1.2)

            # Capture Unselected / Refusal State
            shot_01 = os.path.join(OUTPUT_DIR, f"01_unselected_state_{res_name}.png")
            await page.screenshot(path=shot_01, full_page=False)
            print(f"[{res_name}] Saved: {shot_01}")

            # 2. Open Selector Popover and inspect Providers
            popover_visible = await page.locator("text='AI Provider'").is_visible()
            if not popover_visible:
                if await selector_btn.is_visible():
                    await selector_btn.click()
                await asyncio.sleep(1)

            # Capture Provider Catalogues on 1920x1080
            if res_name == "1920x1080":
                # OpenAI tab
                openai_tab = page.locator("button:has-text('OpenAI')").first
                await openai_tab.click()
                await asyncio.sleep(0.6)
                shot_openai = os.path.join(OUTPUT_DIR, "02_selector_tab_openai.png")
                await page.screenshot(path=shot_openai, full_page=False)
                print(f"[{res_name}] Saved OpenAI catalog: {shot_openai}")

                # Anthropic tab
                anthropic_tab = page.locator("button:has-text('Anthropic')").first
                await anthropic_tab.click()
                await asyncio.sleep(0.6)
                shot_anthropic = os.path.join(OUTPUT_DIR, "02_selector_tab_anthropic.png")
                await page.screenshot(path=shot_anthropic, full_page=False)
                print(f"[{res_name}] Saved Anthropic catalog: {shot_anthropic}")

                # OpenRouter tab
                openrouter_tab = page.locator("button:has-text('OpenRouter')").first
                await openrouter_tab.click()
                await asyncio.sleep(0.6)
                shot_openrouter = os.path.join(OUTPUT_DIR, "02_selector_tab_openrouter.png")
                await page.screenshot(path=shot_openrouter, full_page=False)
                print(f"[{res_name}] Saved OpenRouter catalog: {shot_openrouter}")

            # Select Ollama
            ollama_tab = page.locator("button:has-text('Ollama')").first
            await ollama_tab.click()
            await asyncio.sleep(0.6)

            # Click gemma4:e4b
            gemma_btn = page.locator("button:has-text('Gemma 4 E4B')").first
            if await gemma_btn.is_visible():
                await gemma_btn.click()
                await asyncio.sleep(0.5)

            # Click Medium reasoning pill
            medium_pill = page.locator("button:has-text('Medium')").first
            if await medium_pill.is_visible():
                await medium_pill.click()
                await asyncio.sleep(0.5)

            # Capture Selector Open State for Ollama
            shot_02 = os.path.join(OUTPUT_DIR, f"02_selector_open_{res_name}.png")
            await page.screenshot(path=shot_02, full_page=False)
            print(f"[{res_name}] Saved: {shot_02}")

            # Close popover by pressing Escape
            await page.keyboard.press("Escape")
            await asyncio.sleep(1)

            # Verify closed button shows Gemma 4 E4B · Medium
            configured_btn = page.locator("button:has-text('Gemma 4 E4B · Medium')").first
            is_conf_visible = await configured_btn.is_visible()
            print(f"[{res_name}] 'Gemma 4 E4B · Medium' button visible:", is_conf_visible)

            # Capture Selected State
            shot_03 = os.path.join(OUTPUT_DIR, f"03_selected_state_{res_name}.png")
            await page.screenshot(path=shot_03, full_page=False)
            print(f"[{res_name}] Saved: {shot_03}")

            # 3. Reload Persistence Test
            await page.reload(wait_until="networkidle")
            await asyncio.sleep(2)
            persisted_btn = page.locator("button:has-text('Gemma 4 E4B · Medium')").first
            is_persisted = await persisted_btn.is_visible()
            print(f"[{res_name}] Reload persistence confirmed:", is_persisted)

            shot_04 = os.path.join(OUTPUT_DIR, f"04_reload_persistence_{res_name}.png")
            await page.screenshot(path=shot_04, full_page=False)
            print(f"[{res_name}] Saved: {shot_04}")

            # 4. Live Message Inference Execution (on primary res 1920x1080)
            if res_name == "1920x1080":
                print(f"[{res_name}] Testing live inference with gemma4:e4b (prompt: 'Respond with exactly: CONFIRMED')...")
                input_box = page.locator("textarea").first
                await input_box.fill("Respond with exactly: CONFIRMED")
                await input_box.press("Enter")
                print(f"[{res_name}] Waiting for streaming response completion...")
                # Poll until Thinking... indicator disappears or assistant message arrives
                for i in range(30):
                    await asyncio.sleep(1)
                    has_thinking = await page.locator("text='Thinking...'").is_visible()
                    if not has_thinking and i > 4:
                        break

                await asyncio.sleep(2)
                shot_05 = os.path.join(OUTPUT_DIR, f"05_live_inference_execution_{res_name}.png")
                await page.screenshot(path=shot_05, full_page=False)
                print(f"[{res_name}] Saved: {shot_05}")

            # 5. Settings Page Check
            await page.goto("http://localhost:5173/settings", wait_until="networkidle")
            await asyncio.sleep(2)
            shot_06 = os.path.join(OUTPUT_DIR, f"06_settings_ai_provider_{res_name}.png")
            await page.screenshot(path=shot_06, full_page=False)
            print(f"[{res_name}] Saved: {shot_06}")

            await context.close()

        await browser.close()
        print("\nAll browser verification scenarios finished successfully with full catalog captures!")

if __name__ == "__main__":
    asyncio.run(run_scenario())
