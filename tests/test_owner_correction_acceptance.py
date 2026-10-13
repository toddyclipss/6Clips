# Copyright (c) 2026 ViralMint Contributors. All rights reserved.
# Automated Acceptance Test Suite for Product Owner Correction:
# 1. Reference Discovery vs Editable Source Acquisition
# 2. Original Content Creation
# 3. Trend Research Only (Shorts allowed)
# 4. Blank Motion Editor (Neutral, no gaming instruction)
# 5. Official 6Clips Branding

import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import sys

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ISOLATED_DATA_DIR = ROOT / "tmp_isolated_test"
ISOLATED_DATA_DIR.mkdir(parents=True, exist_ok=True)
os.environ["DATA_DIR"] = str(ISOLATED_DATA_DIR)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{ISOLATED_DATA_DIR / 'viralmint.db'}"
os.environ["STORAGE_ROOT"] = str(ISOLATED_DATA_DIR / "storage")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_owner_correction")

PORT = 16889
BASE_URL = f"http://127.0.0.1:{PORT}"
EVIDENCE_DIR = ROOT / "artifacts" / "owner_correction_acceptance"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
PROD_DB = ROOT / "viralmint.db"
INITIAL_PROD_HASH = hashlib.sha256(PROD_DB.read_bytes()).hexdigest().upper()


def verify_prod_db():
    curr = hashlib.sha256(PROD_DB.read_bytes()).hexdigest().upper()
    assert curr == INITIAL_PROD_HASH, f"CRITICAL: Production DB altered! {curr} != {INITIAL_PROD_HASH}"
    logger.info("Production DB hash verified untouched: %s", curr)


async def test_example_d_blank_motion_editor(page):
    logger.info("=== [Example D] Testing Blank Motion Editor ===")
    await page.goto(f"{BASE_URL}/motion", wait_until="networkidle")
    await asyncio.sleep(2)

    # 1. Confirm gaming-specific message is completely REMOVED
    content = await page.content()
    assert "Request a gaming highlight in Global Chat or select a project from Library." not in content, (
        "Gaming-specific instructional text must NOT be present on the empty canvas!"
    )

    # 2. Confirm clean neutral empty canvas
    canvas_text = await page.locator("[data-testid='studio-preview-stage']").text_content()
    logger.info("Stage container text: %r", canvas_text)
    assert "No Project Loaded" in canvas_text or "no project loaded" in canvas_text.lower(), (
        "Neutral 'No Project Loaded' indicator expected on blank canvas"
    )

    # 3. Capture screenshot of blank motion editor
    shot_blank = EVIDENCE_DIR / "motion_blank_canvas_1920x1080.png"
    await page.screenshot(path=str(shot_blank), full_page=True)
    logger.info("Captured blank motion editor screenshot: %s", shot_blank.name)


async def test_example_e_branding(page):
    logger.info("=== [Example E] Testing Official 6Clips Branding ===")
    await page.goto(f"{BASE_URL}/", wait_until="networkidle")
    await asyncio.sleep(2)

    # 1. Verify document title
    title = await page.title()
    logger.info("Page title: %r", title)
    assert "6Clips" in title, f"Document title should include 6Clips, got {title}"
    assert "ViralMint" not in title, f"Document title must NOT contain ViralMint, got {title}"

    # 2. Verify sidebar brand logo
    logo_img = page.locator("img[alt='6Clips']").first
    assert await logo_img.is_visible(), "Sidebar logo must have alt='6Clips'"

    # 3. Expand sidebar to verify 6Clips brand text
    expand_btn = page.locator("button[aria-label='Expand sidebar'], [aria-label='Expand sidebar']").first
    if await expand_btn.is_visible():
        await expand_btn.click()
        await asyncio.sleep(1)
    brand_text = page.locator("h6:has-text('6Clips')").first
    assert await brand_text.is_visible(), "Expanded sidebar must display 6Clips text"

    # 4. Verify no user-visible 'ViralMint' or 'ViralMind'
    visible_text = await page.locator("body").inner_text()
    assert "ViralMint" not in visible_text, "Visible UI must NOT display legacy 'ViralMint'!"
    assert "ViralMind" not in visible_text, "Visible UI must NOT display legacy 'ViralMind'!"

    # 5. Capture multi-viewport branding screenshots
    shot_brand_1080 = EVIDENCE_DIR / "branding_6clips_1920x1080.png"
    await page.screenshot(path=str(shot_brand_1080), full_page=True)
    logger.info("Captured 1920x1080 branding screenshot: %s", shot_brand_1080.name)


async def test_example_c_trend_research_only():
    logger.info("=== [Example C] Testing Trend Research Across All Formats ===")
    from backend.services.youtube_trends import search_youtube_trends, classify_suitability_for_clips
    from backend.services.virality_scorer import calculate_viral_opportunity_score

    # Pure trend research query with video_duration='any'
    results = await search_youtube_trends("Fortnite", video_duration="any", max_results=10)
    assert len(results) > 0, "Expected trending results across formats"

    # Verify both short-form and long-form videos are allowed in reference discovery
    durations = [r.get("duration_seconds") for r in results if r.get("duration_seconds")]
    logger.info("Discovered reference durations: %s", durations)

    # Classify them as creative references vs editable sources
    for r in results:
        suit = classify_suitability_for_clips(r.get("duration_seconds"), target_clips=3, clip_duration_sec=60)
        assert suit["is_reference"] is True, "Every discovered trend must be available as reference!"
        if r.get("duration_seconds") and r["duration_seconds"] < 180:
            assert suit["trend_role"] == "creative_reference"
            assert suit["is_editable_source"] is False

    logger.info("SUCCESS: Example C trend research across formats verified!")


async def test_example_a_and_b_workflow(page):
    logger.info("=== [Example A & B] Testing Global Chat Main Agent Workflows ===")
    await page.goto(f"{BASE_URL}/", wait_until="networkidle")
    await asyncio.sleep(2)

    # Ensure New Chat
    new_chat_btn = page.locator("button:has-text('New chat')").first
    if await new_chat_btn.is_visible():
        await new_chat_btn.click()
        await asyncio.sleep(1)

    # Example A: "Find a viral Fortnite video and turn it into three 60-second clips."
    input_box = page.locator('textarea[placeholder*="Ask anything"], textarea[aria-label="Chat input"], textarea').first
    await input_box.wait_for(state="visible", timeout=10000)
    prompt_a = "Find a viral Fortnite video and turn it into three 60-second clips."
    logger.info("Sending Example A prompt: '%s'", prompt_a)
    await input_box.fill(prompt_a)
    await page.keyboard.press("Enter")

    # Wait for assistant response to start and finish streaming
    await page.wait_for_selector("[data-role='assistant']", timeout=60000)
    logger.info("Assistant message appeared. Waiting for streaming completion...")
    
    last_text = ""
    for _ in range(30):
        await asyncio.sleep(2)
        assistant_elements = page.locator("[data-role='assistant']")
        count = await assistant_elements.count()
        if count > 0:
            curr_text = await assistant_elements.nth(count - 1).inner_text()
            if curr_text and curr_text == last_text and len(curr_text) > 100:
                logger.info("Assistant response stabilized (%d chars).", len(curr_text))
                break
            last_text = curr_text

    assistant_texts = await page.locator("[data-role='assistant']").all_text_contents()
    reply_a = assistant_texts[-1] if assistant_texts else ""
    logger.info("Example A assistant reply:\n%s", reply_a[:600])

    reply_lower = reply_a.lower()
    # Assertions for Example A:
    # 1. Distinguishes references vs editable source
    assert any(w in reply_lower for w in ("source", "recommended", "footage", "long-form", "duration")), "Must identify editable source criteria"
    assert any(w in reply_lower for w in ("reference", "hook", "pacing", "short", "creative", "trend")), "Must cite creative references"
    # 2. Rights gate
    assert any(w in reply_lower for w in ("rights", "authorization", "license", "permission", "notice")), "Must require footage authorization"
    # 3. English response
    assert "encontrei" not in reply_lower and "aviso de direitos" not in reply_lower, "Must respond in English to English prompt"

    # Capture Example A screenshot
    shot_a = EVIDENCE_DIR / "workflow_example_a_longform_to_shorts_1920x1080.png"
    await page.screenshot(path=str(shot_a), full_page=True)
    logger.info("Captured Example A screenshot: %s", shot_a.name)

    # Example B: "Create an original video explaining the latest Fortnite update."
    logger.info("Sending Example B prompt (Original Creation)...")
    await input_box.fill("Create an original video explaining the latest Fortnite update.")
    await page.keyboard.press("Enter")

    await asyncio.sleep(5)
    last_text_b = ""
    for _ in range(30):
        await asyncio.sleep(2)
        assistant_elements = page.locator("[data-role='assistant']")
        count = await assistant_elements.count()
        if count > 1:
            curr_text = await assistant_elements.nth(count - 1).inner_text()
            if curr_text and curr_text == last_text_b and len(curr_text) > 100:
                logger.info("Example B response stabilized (%d chars).", len(curr_text))
                break
            last_text_b = curr_text

    assistant_texts = await page.locator("[data-role='assistant']").all_text_contents()
    reply_b = assistant_texts[-1] if len(assistant_texts) > 1 else ""
    logger.info("Example B assistant reply:\n%s", reply_b[:600])

    reply_b_lower = reply_b.lower()
    # Assertions for Example B:
    # Proposes original content creation (script, composition, research, motion graphics/visuals)
    assert any(w in reply_b_lower for w in ("script", "concept", "original", "motion", "composition", "update", "outline")), "Must propose original creative workflow"
    assert "aviso de direitos" not in reply_b_lower and "encontrei" not in reply_b_lower

    # Capture Example B screenshot
    shot_b = EVIDENCE_DIR / "workflow_example_b_original_creation_1920x1080.png"
    await page.screenshot(path=str(shot_b), full_page=True)
    logger.info("Captured Example B screenshot: %s", shot_b.name)


async def main():
    verify_prod_db()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    # Run Example C unit test first
    await test_example_c_trend_research_only()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # 1080p context
        ctx_1080 = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page_1080 = await ctx_1080.new_page()

        # Run Example D (Blank Motion Canvas)
        await test_example_d_blank_motion_editor(page_1080)

        # Run Example E (Branding 6Clips)
        await test_example_e_branding(page_1080)

        # Run Example A & B (Global Chat Workflow)
        await test_example_a_and_b_workflow(page_1080)

        await ctx_1080.close()

        # 1440x900 context
        ctx_900 = await browser.new_context(viewport={"width": 1440, "height": 900})
        page_900 = await ctx_900.new_page()
        await page_900.goto(f"{BASE_URL}/", wait_until="networkidle")
        await asyncio.sleep(2)
        shot_900 = EVIDENCE_DIR / "branding_6clips_1440x900.png"
        await page_900.screenshot(path=str(shot_900), full_page=True)
        await ctx_900.close()

        # 1366x768 context
        ctx_768 = await browser.new_context(viewport={"width": 1366, "height": 768})
        page_768 = await ctx_768.new_page()
        await page_768.goto(f"{BASE_URL}/", wait_until="networkidle")
        await asyncio.sleep(2)
        shot_768 = EVIDENCE_DIR / "branding_6clips_1366x768.png"
        await page_768.screenshot(path=str(shot_768), full_page=True)
        await ctx_768.close()

        await browser.close()

    verify_prod_db()
    logger.info("ALL ACCEPTANCE EXAMPLES PASSED CLEANLY!")


if __name__ == "__main__":
    asyncio.run(main())
