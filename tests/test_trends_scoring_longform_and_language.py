# Copyright (c) 2026 ViralMint. All rights reserved.
# Automated E2E test for trends scoring, long-form discovery, and new-chat language isolation.
import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
from pathlib import Path
import sys

from playwright.async_api import async_playwright

import os
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Strictly enforce isolated test database and storage
ISOLATED_DATA_DIR = ROOT / "tmp_isolated_test"
ISOLATED_DATA_DIR.mkdir(parents=True, exist_ok=True)
os.environ["DATA_DIR"] = str(ISOLATED_DATA_DIR)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{ISOLATED_DATA_DIR / 'viralmint.db'}"
os.environ["STORAGE_ROOT"] = str(ISOLATED_DATA_DIR / "storage")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_trends_scoring")

PORT = 16889
BASE_URL = f"http://127.0.0.1:{PORT}"
EVIDENCE_DIR = ROOT / "tests" / "visual_evidence"
PROD_DB = ROOT / "viralmint.db"
INITIAL_PROD_HASH = hashlib.sha256(PROD_DB.read_bytes()).hexdigest().upper()


def verify_prod_db_hash():
    if not PROD_DB.exists():
        raise FileNotFoundError(f"Production DB {PROD_DB} does not exist!")
    h = hashlib.sha256(PROD_DB.read_bytes()).hexdigest().upper()
    assert h == INITIAL_PROD_HASH, f"CRITICAL: Production DB hash mutated! {h} != {INITIAL_PROD_HASH}"
    logger.info(f"Production DB hash verified untouched: {h}")


def test_virality_scorer_unit():
    logger.info("=== [Unit 1] Testing Deterministic Virality Scorer ===")
    from backend.services.virality_scorer import calculate_viral_opportunity_score

    # Video 1: High view velocity, recent upload
    v1 = {
        "views": 150000,
        "likes": 8500,
        "comments": 420,
        "duration_seconds": 966,
        "upload_date": datetime.now(timezone.utc) - timedelta(days=3),
    }
    s1 = calculate_viral_opportunity_score(v1)
    logger.info("Score 1 (150k views, 3 days old): %s", s1["score"])
    assert 60.0 <= s1["score"] <= 100.0, f"Expected high score, got {s1['score']}"
    assert s1["views_per_hour"] > 1000

    # Video 2: Public search without likes/comments
    v2 = {
        "views": 80000,
        "likes": 0,
        "comments": 0,
        "duration_seconds": 1200,
        "upload_date": datetime.now(timezone.utc) - timedelta(days=5),
    }
    s2 = calculate_viral_opportunity_score(v2)
    logger.info("Score 2 (80k views, 5 days, no likes): %s, unavailable: %s", s2["score"], s2["unavailable_fields"])
    assert 40.0 <= s2["score"] <= 90.0, f"Expected moderate/high score, got {s2['score']}"
    assert "likes" in s2["unavailable_fields"]
    assert "comments" in s2["unavailable_fields"]

    # Video 3: Low views, old upload
    v3 = {
        "views": 500,
        "likes": 12,
        "comments": 1,
        "duration_seconds": 600,
        "upload_date": datetime.now(timezone.utc) - timedelta(days=28),
    }
    s3 = calculate_viral_opportunity_score(v3)
    logger.info("Score 3 (500 views, 28 days old): %s", s3["score"])
    assert s3["score"] < 40.0, f"Expected low score, got {s3['score']}"

    logger.info("SUCCESS: Virality scorer unit tests passed!")


def test_duration_suitability_unit():
    logger.info("=== [Unit 2] Testing Long-Form Duration Suitability ===")
    from backend.services.youtube_trends import classify_suitability_for_clips

    # 45s (Shorts)
    c1 = classify_suitability_for_clips(45, target_clips=3, clip_duration_sec=60)
    assert c1["status"] == "unsuitable_too_short"
    assert c1["is_suitable"] is False

    # 190s (Marginal: >180s but <240s)
    c2 = classify_suitability_for_clips(190, target_clips=3, clip_duration_sec=60)
    assert c2["status"] == "marginal"
    assert c2["is_suitable"] is True

    # 966s (~16m long-form gameplay)
    c3 = classify_suitability_for_clips(966, target_clips=3, clip_duration_sec=60)
    assert c3["status"] == "suitable_longform"
    assert c3["is_suitable"] is True

    # None (Unknown)
    c4 = classify_suitability_for_clips(None, target_clips=3, clip_duration_sec=60)
    assert c4["status"] == "unknown_duration"
    assert c4["is_suitable"] is False

    logger.info("SUCCESS: Duration suitability unit tests passed!")


async def test_chat_and_trends_browser(browser):
    logger.info("=== [Browser] Testing Real English Request & Trends Scoring ===")
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    # Viewport 1: 1920x1080 Desktop
    ctx = await browser.new_context(viewport={"width": 1920, "height": 1080})
    page = await ctx.new_page()

    await page.goto(f"{BASE_URL}/", wait_until="networkidle")
    await asyncio.sleep(2)

    # 1. Click "New chat" to guarantee brand new conversation
    new_chat_btn = page.locator("button:has-text('New chat')").first
    if await new_chat_btn.is_visible():
        await new_chat_btn.click()
        await asyncio.sleep(1)

    # 2. Send the exact real-world English prompt:
    # "Find a viral Fortnite video and turn it into three 60-second clips."
    english_prompt = "Find a viral Fortnite video and turn it into three 60-second clips."
    logger.info("Sending English prompt: '%s'", english_prompt)

    input_box = page.locator('textarea[placeholder*="Ask anything"], textarea[aria-label="Chat input"], textarea').first
    await input_box.wait_for(state="visible", timeout=10000)
    await input_box.fill(english_prompt)
    await page.keyboard.press("Enter")

    # 3. Wait for execution and tool completion
    logger.info("Waiting for Main Agent tool execution and English response...")
    try:
        await page.wait_for_selector("[data-role='assistant']", timeout=90000)
    except Exception as e:
        logger.warning("Wait assistant selector: %s", e)

    # Allow streaming response to complete
    await asyncio.sleep(15)

    # 4. Verify assistant response is in English!
    assistant_texts = await page.locator("[data-role='assistant']").all_text_contents()
    reply = assistant_texts[-1] if assistant_texts else ""
    logger.info("Assistant reply snippet (first 300 chars):\n%s", reply[:300])

    reply_lower = reply.lower()
    # Must NOT contain Portuguese phrases
    assert "encontrei vários vídeos" not in reply_lower, "Assistant must NOT answer in Portuguese!"
    assert "aviso de direitos" not in reply_lower, "Assistant must NOT render Portuguese rights notice!"
    assert "vídeos virais em alta" not in reply_lower, "Assistant must NOT render Portuguese header!"

    # Must contain English indicators & Rights notice
    assert any(w in reply_lower for w in ("found", "trending", "fortnite", "viral")), "Assistant should summarize discovered videos in English!"
    assert any(w in reply_lower for w in ("rights", "authorization", "license", "gameplay", "permission")), "Assistant must present Rights Notice in English!"

    # 5. Capture multi-viewport screenshots of the English Chat workflow
    shot_1080 = EVIDENCE_DIR / "chat_workflow_english_1920x1080.png"
    await page.screenshot(path=str(shot_1080), full_page=True)
    logger.info("Captured 1920x1080 English Chat screenshot: %s", shot_1080.name)

    # 6. Test /trends page cards and table
    logger.info("Navigating to /trends to inspect scored cards and table...")
    await page.goto(f"{BASE_URL}/trends", wait_until="networkidle")
    await asyncio.sleep(3)

    # Verify visible cards do NOT show "Score 0.0"
    card_texts = await page.locator(".MuiCard-root").all_text_contents()
    logger.info("Inspecting %d trends cards...", len(card_texts))
    scores_found = []
    zero_scores = 0
    for ct in card_texts:
        if "Score 0.0" in ct:
            zero_scores += 1
        import re
        m = re.search(r"Score\s+([\d\.]+)", ct)
        if m:
            scores_found.append(float(m.group(1)))

    logger.info("Scores found on visible cards: %s (zero_scores=%d)", scores_found[:10], zero_scores)
    assert zero_scores == 0, f"No cards should display Score 0.0! Found {zero_scores} cards with Score 0.0"
    assert len(scores_found) > 0, "Expected non-zero viral scores on cards"
    assert any(s > 30.0 for s in scores_found), "Expected genuine positive viral scores"

    # Screenshot of cards view at 1920x1080
    shot_cards = EVIDENCE_DIR / "trends_scored_cards_1920x1080.png"
    await page.screenshot(path=str(shot_cards), full_page=True)
    logger.info("Captured /trends Cards screenshot: %s", shot_cards.name)

    # Switch to Table view
    table_btn = page.locator("button:has-text('Table')").first
    if await table_btn.is_visible():
        await table_btn.click()
        await asyncio.sleep(1)

    shot_table = EVIDENCE_DIR / "trends_scored_table_1920x1080.png"
    await page.screenshot(path=str(shot_table), full_page=True)
    logger.info("Captured /trends Table screenshot: %s", shot_table.name)

    await ctx.close()

    # Viewport 2: 1440x900
    ctx_900 = await browser.new_context(viewport={"width": 1440, "height": 900})
    page_900 = await ctx_900.new_page()
    await page_900.goto(f"{BASE_URL}/", wait_until="networkidle")
    await asyncio.sleep(2)
    shot_900 = EVIDENCE_DIR / "chat_workflow_english_1440x900.png"
    await page_900.screenshot(path=str(shot_900), full_page=True)
    logger.info("Captured 1440x900 screenshot: %s", shot_900.name)
    await ctx_900.close()

    # Viewport 3: 1366x768
    ctx_768 = await browser.new_context(viewport={"width": 1366, "height": 768})
    page_768 = await ctx_768.new_page()
    await page_768.goto(f"{BASE_URL}/", wait_until="networkidle")
    await asyncio.sleep(2)
    shot_768 = EVIDENCE_DIR / "chat_workflow_english_1366x768.png"
    await page_768.screenshot(path=str(shot_768), full_page=True)
    logger.info("Captured 1366x768 screenshot: %s", shot_768.name)
    await ctx_768.close()


async def setup_settings():
    from backend.database import AsyncSessionLocal
    from backend.models.user_settings import UserSettings
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(UserSettings).where(UserSettings.user_id == "local").limit(1))
        us = res.scalars().first()
        if not us:
            us = UserSettings(user_id="local")
            db.add(us)
        us.ai_provider = "ollama"
        us.ai_model = "gemma4:e4b"
        us.ai_reasoning_level = "high"
        await db.commit()
    logger.info("[Setup] UserSettings set to Ollama gemma4:e4b (High reasoning)")


async def main():
    verify_prod_db_hash()
    test_virality_scorer_unit()
    test_duration_suitability_unit()
    await setup_settings()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        await test_chat_and_trends_browser(browser)
        await browser.close()

    verify_prod_db_hash()
    logger.info("\nALL TESTS PASSED! VIRAL SCORING, LONG-FORM DISCOVERY & LANGUAGE ISOLATION VERIFIED!")


if __name__ == "__main__":
    asyncio.run(main())
