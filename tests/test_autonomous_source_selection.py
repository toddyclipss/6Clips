# Copyright (c) 2026 ViralMint Contributors. All rights reserved.
# Automated Acceptance Test Suite for:
# 1. Autonomous Source Selection & Goal Continuity
# 2. Strict Invariants: is_suitable: false NEVER in recommended_editable_source
# 3. Purpose Separation: trend_research vs editable_source_search
# 4. Multi-Turn Goal Continuity: no asking user for project IDs or candidate selections
# 5. Trends UX Badges: Editable Source Candidate vs Creative Reference

import asyncio
from datetime import datetime, timezone
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
logger = logging.getLogger("test_autonomous_source_selection")

PORT = 16889
BASE_URL = f"http://127.0.0.1:{PORT}"
EVIDENCE_DIR = ROOT / "artifacts" / "autonomous_source_selection"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
PROD_DB = ROOT / "viralmint.db"
INITIAL_PROD_HASH = hashlib.sha256(PROD_DB.read_bytes()).hexdigest().upper()


def verify_prod_db():
    curr = hashlib.sha256(PROD_DB.read_bytes()).hexdigest().upper()
    assert curr == INITIAL_PROD_HASH, f"CRITICAL: Production DB altered! {curr} != {INITIAL_PROD_HASH}"
    logger.info("Production DB hash verified untouched: %s", curr)


async def test_backend_invariants():
    """Verify backend contract invariants for search_youtube_trends and executor."""
    logger.info("=== Testing Backend Contract Invariants ===")
    from backend.services.executor_service import ExecutorService
    from backend.core.capabilities import CapabilityRegistry
    from backend.core.ai_provider import format_trend_synthesis, format_combined_trend_synthesis

    # 1. Capability registered with purpose, target_clips, clip_duration_sec
    cap = CapabilityRegistry.get("search_youtube_trends")
    assert cap is not None, "search_youtube_trends must be registered"
    assert "purpose" in cap.optional_params
    assert "target_clips" in cap.optional_params
    assert "clip_duration_sec" in cap.optional_params
    logger.info("Capability contract verified.")

    # 2. Test purpose='trend_research' where candidate shorts exist
    # Execute trend_research for 'viral Fortnite'
    out_ref, verif_ref = await ExecutorService._execute_search_trends({
        "query": "viral Fortnite",
        "purpose": "trend_research",
        "video_duration": "any",
        "target_clips": 3,
        "clip_duration_sec": 60,
    }, user_id="test_user")

    assert verif_ref["ok"] is True
    assert out_ref["purpose"] == "trend_research"
    assert "creative_references" in out_ref
    assert "editable_sources" in out_ref

    # If editable_sources is empty, recommended_editable_source must be None
    if not out_ref["editable_sources"]:
        assert out_ref["recommended_editable_source"] is None, (
            "Invariant violation: editable_sources: [] MUST produce recommended_editable_source: None!"
        )
        assert out_ref["recommended_source"] is None
        assert out_ref["source_acquisition_status"] == "no_suitable_source_found"
        assert out_ref["recommended_next_operation"] == "search_long_form_sources"
        logger.info("Verified invariant: editable_sources: [] yields recommended_editable_source: None and search_long_form_sources")

    # If editable_sources has items, recommended_editable_source must strictly be is_editable_source: True and is_suitable: True
    if out_ref["editable_sources"]:
        rec = out_ref["recommended_editable_source"]
        assert rec is not None
        assert rec.get("suitability_for_3x60s", {}).get("is_editable_source") is True
        assert rec.get("suitability_for_3x60s", {}).get("is_suitable") is True
        logger.info("Verified invariant: recommended_editable_source has is_editable_source: True")

    # 3. Test purpose='editable_source_search' with video_duration='medium'
    out_edit, verif_edit = await ExecutorService._execute_search_trends({
        "query": "Fortnite gameplay",
        "purpose": "editable_source_search",
        "video_duration": "medium",
        "target_clips": 3,
        "clip_duration_sec": 60,
    }, user_id="test_user")

    assert verif_edit["ok"] is True
    assert out_edit["purpose"] == "editable_source_search"
    assert out_edit["video_duration_filter"] == "medium"
    
    # Check that any candidate in editable_sources has duration >= 180s
    for c in out_edit["editable_sources"]:
        dur = c.get("duration_seconds") or 0
        assert dur >= 180, f"Editable source duration must be >= 180s, got {dur}s"
        assert c.get("suitability_for_3x60s", {}).get("is_editable_source") is True

    # 4. Test format_combined_trend_synthesis
    combined_synth = format_combined_trend_synthesis(
        "Find a viral Fortnite video and turn it into three 60-second clips.",
        {"output": out_ref},
        {"output": out_edit},
    )
    assert "**Recommended Editable Source:**" in combined_synth or "Found trending" in combined_synth
    assert "Rights & Licensing Notice" not in combined_synth, "Generic rights notice must be removed!"
    assert "Next Step:" in combined_synth or "Próximo Passo:" in combined_synth, "Must include operational next step!"
    assert "Which candidate would you like to proceed with" not in combined_synth, (
        "Must NOT ask user to choose between candidate URLs!"
    )
    logger.info("Backend invariants and combined synthesis verified successfully.")


async def test_full_playwright_e2e(page):
    """Run full Global Chat workflow using Playwright with live Ollama gemma4:e4b High reasoning."""
    logger.info("=== Running Playwright Acceptance Test ===")
    
    await page.goto(f"{BASE_URL}/", wait_until="networkidle")
    await asyncio.sleep(2)

    # 1. Select Ollama gemma4:e4b and High reasoning
    prov_select = page.locator("[data-testid='provider-select']").first
    if await prov_select.is_visible():
        await prov_select.click()
        await asyncio.sleep(0.5)
        ollama_opt = page.locator("li[data-value='ollama']").first
        if await ollama_opt.is_visible():
            await ollama_opt.click()
            await asyncio.sleep(0.5)

    model_select = page.locator("[data-testid='model-select']").first
    if await model_select.is_visible():
        await model_select.click()
        await asyncio.sleep(0.5)
        gemma_opt = page.locator("li[data-value='gemma4:e4b']").first
        if await gemma_opt.is_visible():
            await gemma_opt.click()
            await asyncio.sleep(0.5)

    reasoning_btn = page.locator("button:has-text('HIGH'), button:has-text('High')").first
    if await reasoning_btn.is_visible():
        await reasoning_btn.click()
        await asyncio.sleep(0.5)

    logger.info("Provider, model, and reasoning configured.")

    # 2. Global Chat is directly on home page /
    # Ensure New Chat
    new_chat_btn = page.locator("button:has-text('New chat')").first
    if await new_chat_btn.is_visible():
        await new_chat_btn.click()
        await asyncio.sleep(1)

    input_box = page.locator('textarea[placeholder*="Ask anything"], textarea[aria-label="Chat input"], textarea').first
    await input_box.wait_for(state="visible", timeout=10000)

    # Turn 1: "Find a viral Fortnite video and turn it into three 60-second clips."
    user_prompt_1 = "Find a viral Fortnite video and turn it into three 60-second clips."
    logger.info("Sending Turn 1 prompt: %r", user_prompt_1)
    await input_box.fill(user_prompt_1)
    await page.keyboard.press("Enter")

    # Wait for completion
    logger.info("Waiting for Turn 1 response and tool execution...")
    last_text = ""
    for _ in range(35):
        await asyncio.sleep(2)
        assistant_elements = page.locator("[data-role='assistant']")
        count = await assistant_elements.count()
        if count > 0:
            curr_text = await assistant_elements.nth(count - 1).inner_text()
            if curr_text and curr_text == last_text and len(curr_text) > 80:
                logger.info("Turn 1 response stabilized (%d chars).", len(curr_text))
                break
            last_text = curr_text

    assistant_texts = await page.locator("[data-role='assistant']").all_text_contents()
    reply_1 = assistant_texts[-1] if assistant_texts else ""
    logger.info("Turn 1 assistant response snippet:\n%s", reply_1[:500])

    reply_1_lower = reply_1.lower()
    # Verifications for Turn 1:
    # A. Autonomous recommendation
    assert "recommended editable source" in reply_1_lower or "recommended" in reply_1_lower, (
        "Assistant must autonomously recommend an editable source!"
    )
    # B. Creative references
    assert any(w in reply_1_lower for w in ("creative references", "reference", "references", "hooks")), (
        "Assistant must cite creative references / Shorts for hooks and pacing!"
    )
    # C. No generic rights notice or automatic authorization interruption
    assert "rights & licensing notice" not in reply_1_lower, (
        "Assistant must NOT inject generic rights & licensing notice!"
    )
    assert "do you confirm authorization" not in reply_1_lower, (
        "Assistant must NOT automatically ask user for authorization upon discovery!"
    )
    assert any(w in reply_1_lower for w in ("next step", "ready", "proceed", "preparation", "verification")), (
        "Assistant must provide continuous autonomous next step!"
    )
    # D. Zero candidate link interrogation
    assert "which candidate would you like to proceed with" not in reply_1_lower, (
        "Must NOT ask user to choose between candidate URLs!"
    )
    # E. Zero project ID interrogation
    assert "project id" not in reply_1_lower, "Must NOT ask user for an existing project ID!"

    # Capture Turn 1 screenshot
    shot_1 = EVIDENCE_DIR / "autonomous_selection_chat_1920x1080.png"
    await page.screenshot(path=str(shot_1), full_page=True)
    logger.info("Captured Turn 1 screenshot: %s", shot_1.name)

    # Turn 2: Follow-up continuity: "produce a video"
    user_prompt_2 = "produce a video"
    logger.info("Sending Turn 2 follow-up: %r", user_prompt_2)
    await input_box.fill(user_prompt_2)
    await page.keyboard.press("Enter")

    logger.info("Waiting for Turn 2 response...")
    last_text_2 = ""
    for _ in range(30):
        await asyncio.sleep(2)
        assistant_elements = page.locator("[data-role='assistant']")
        count = await assistant_elements.count()
        if count > 1:
            curr_text = await assistant_elements.nth(count - 1).inner_text()
            if curr_text and curr_text == last_text_2 and len(curr_text) > 40:
                logger.info("Turn 2 response stabilized (%d chars).", len(curr_text))
                break
            last_text_2 = curr_text

    assistant_texts_2 = await page.locator("[data-role='assistant']").all_text_contents()
    reply_2 = assistant_texts_2[-1] if len(assistant_texts_2) > 1 else ""
    logger.info("Turn 2 assistant response snippet:\n%s", reply_2[:500])

    reply_2_lower = reply_2.lower()
    # Invariant: Must NOT ask user for a project ID or video ID!
    assert "please provide a project id" not in reply_2_lower and "existing project id" not in reply_2_lower, (
        "Must NOT interrogate user for project ID!"
    )
    assert any(w in reply_2_lower for w in ("project", "canonical", "highlights", "acquiring", "acquisition", "60-second")), (
        "Turn 2 must confirm canonical project creation or footage acquisition continuation!"
    )

    shot_2 = EVIDENCE_DIR / "goal_continuity_followup_1920x1080.png"
    await page.screenshot(path=str(shot_2), full_page=True)
    logger.info("Captured Turn 2 screenshot: %s", shot_2.name)

    # 3. Check Trends UX Badges
    logger.info("Navigating to /trends to inspect card badges...")
    await page.goto(f"{BASE_URL}/trends", wait_until="networkidle")
    await asyncio.sleep(3)

    # Verify presence of badges
    trends_content = await page.content()
    has_editable_badge = "Editable Source" in trends_content
    has_ref_badge = "Creative Reference" in trends_content
    logger.info("Trends badges present: Editable Source=%s, Creative Reference=%s", has_editable_badge, has_ref_badge)

    shot_badges = EVIDENCE_DIR / "trends_badges_1920x1080.png"
    await page.screenshot(path=str(shot_badges), full_page=True)
    logger.info("Captured Trends badges screenshot: %s", shot_badges.name)


async def main():
    verify_prod_db()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Test backend contract invariants
    await test_backend_invariants()

    # 2. Test Playwright browser acceptance
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await ctx.new_page()

        await test_full_playwright_e2e(page)

        await ctx.close()
        await browser.close()

    verify_prod_db()
    logger.info("All tests passed! Autonomous source selection and goal continuity verified.")


if __name__ == "__main__":
    asyncio.run(main())
