import os
import sys
import time
import urllib.request
import json
import asyncio
import subprocess
from pathlib import Path
from playwright.async_api import async_playwright

ISOLATED_DIR = Path("c:/Users/toddy/Desktop/ViralMint/tmp_isolated_test")
env = os.environ.copy()
env["VIRALMINT_DATA_DIR"] = str(ISOLATED_DIR)
env["PORT"] = "16889"

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "16889"],
    env=env,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

async def check_browser():
    try:
        ready = False
        for i in range(20):
            try:
                with urllib.request.urlopen("http://127.0.0.1:16889/api/config", timeout=1) as resp:
                    ready = True
                    break
            except Exception:
                time.sleep(0.5)

        if not ready:
            print("Backend failed to start")
            return

        print("Backend live on 16889. Launching Playwright...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1920, "height": 1080})

            page.on("console", lambda msg: print(f"[CONSOLE {msg.type}] {msg.text}"))
            page.on("pageerror", lambda err: print(f"[PAGE ERROR] {err}"))
            page.on("requestfailed", lambda req: print(f"[REQ FAILED] {req.url} - {req.failure}"))
            page.on("response", lambda resp: print(f"[HTTP {resp.status}] {resp.url}") if "/api/" in resp.url else None)

            url = "http://127.0.0.1:16889/motion?projectId=6169c61a-9805-43fa-9230-7806f4ed922b&mode=review"
            print(f"Navigating to {url}...")
            await page.goto(url, wait_until="networkidle")
            await asyncio.sleep(3)

            # Inspect state
            content = await page.content()
            print("--- EVALUATION ---")
            print("Contains 'No active project loaded':", "No active project loaded" in content)
            print("Contains 'Gaming Highlight Short':", "Gaming Highlight Short" in content)

            # Check buttons
            create_btn = page.locator("button:has-text('Create')")
            review_btn = page.locator("button:has-text('Review')")
            refine_btn = page.locator("button:has-text('Refine')")
            print("Create button count:", await create_btn.count())
            print("Review button count:", await review_btn.count())
            print("Refine button count:", await refine_btn.count())

            # Check which button is active (primary color or styling)
            if await review_btn.count() > 0:
                rev_class = await review_btn.first.get_attribute("class")
                print("Review btn class:", rev_class)

            # Check if video tag or iframe exists
            iframe = page.locator("#studio-preview-iframe")
            print("Iframe count:", await iframe.count())
            if await iframe.count() > 0:
                print("Iframe src:", await iframe.first.get_attribute("src"))

            # Check screenshot
            await page.screenshot(path="scratch/diag_review_screenshot.png")
            print("Screenshot saved to scratch/diag_review_screenshot.png")

            await browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

asyncio.run(check_browser())
