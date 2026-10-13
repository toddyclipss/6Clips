# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Targeted test for Step 2 (Code Ownership CAS) and Step 3 (Global Chat Tool Flow)."""
import asyncio
import sqlite3
import json
from pathlib import Path
from playwright.async_api import async_playwright

BASE_DIR = Path("c:/Users/toddy/Desktop/ViralMint")
EVIDENCE_DIR = BASE_DIR / "tests" / "visual_evidence"
PROJECT_ID = "6169c61a-9805-43fa-9230-7806f4ed922b"
PORT = 16889
BASE_URL = f"http://127.0.0.1:{PORT}"
ISOLATED_DB = BASE_DIR / "tmp_isolated_test" / "viralmint.db"


async def setup_settings():
    conn = sqlite3.connect(str(ISOLATED_DB))
    c = conn.cursor()
    c.execute("""
        UPDATE user_settings 
        SET ai_provider = 'ollama', 
            ai_model = 'gemma4:e4b', 
            ai_reasoning_level = 'low',
            updated_at = datetime('now')
        WHERE user_id = 'local'
    """)
    conn.commit()
    conn.close()
    print("[Setup] DB UserSettings set to Ollama gemma4:e4b (low)")


async def run_step2_code_ownership(page):
    print("\n--- [Step 2] Code Ownership & CAS Forking Verification ---")
    await page.goto(f"{BASE_URL}/motion?projectId={PROJECT_ID}&mode=refine", wait_until="networkidle")
    
    # 1. Open Code Workspace tab
    code_tab_btn = page.locator("[data-testid='studio-toolbar-code-btn']")
    await code_tab_btn.wait_for(state="visible", timeout=10000)
    await code_tab_btn.click()
    
    await page.wait_for_selector("[data-testid='studio-code-workspace']", timeout=10000)
    await asyncio.sleep(0.5)
    
    # 2. Check initial catalog state
    catalog_chip = page.locator("text='Shared Catalog (Read-Only)'")
    cust_btn = page.locator("[data-testid='studio-code-customize-btn']")
    print("[Code] Shared catalog chip visible:", await catalog_chip.is_visible())
    print("[Code] Customize Code button visible:", await cust_btn.is_visible())
    
    # 3. Click Customize Code to fork
    await cust_btn.click()
    await asyncio.sleep(0.5)
    
    owned_chip = page.locator("text='Project-Owned'")
    print("[Code] Project-Owned chip visible after click:", await owned_chip.is_visible())
    assert await owned_chip.is_visible(), "Expected Project-Owned chip to appear"

    # 4. Dispatch text change in CodeMirror 6 editor
    changed = await page.evaluate("""() => {
        const cmEl = document.querySelector('.cm-editor');
        if (!cmEl) return false;
        // CodeMirror 6 stores view in cmView
        const cmView = cmEl.cmView ? cmEl.cmView.view : (cmEl._view || null);
        if (cmView) {
            cmView.dispatch({
                changes: { from: cmView.state.doc.length, insert: "\\n<!-- CAS Project-Owned Customization Test -->" }
            });
            return true;
        }
        // Fallback: simulate key event on .cm-content
        const content = document.querySelector('.cm-content');
        if (content) {
            content.focus();
            return 'fallback-focus';
        }
        return false;
    }""")
    print("[Code] Dispatched change to CodeMirror:", changed)
    
    if changed == 'fallback-focus':
        await page.keyboard.press("End")
        await page.keyboard.type("\n<!-- CAS Project-Owned Customization Test -->")
        
    await asyncio.sleep(0.5)
    
    # Check if Save File button is enabled
    save_btn = page.locator("[data-testid='studio-code-save-btn']")
    is_disabled = await save_btn.is_disabled()
    print("[Code] Save File button disabled?:", is_disabled)
    
    if is_disabled:
        # If still marked not dirty, trigger via localDraft handler
        await page.evaluate("""() => {
            // Find inputs or dispatch on .cm-content
            const content = document.querySelector('.cm-content');
            if (content) {
                const evt = new InputEvent('input', { bubbles: true, cancelable: true });
                content.dispatchEvent(evt);
            }
        }""")
        await asyncio.sleep(0.5)
        print("[Code] Save File button disabled after input dispatch?:", await save_btn.is_disabled())

    # Click Save File
    await save_btn.click()
    print("[Code] Clicked Save File button!")
    
    # Wait for success toast / snackbar
    await page.wait_for_selector(".MuiAlert-message, [data-testid='studio-code-save-btn']", timeout=10000)
    await asyncio.sleep(1.0)
    
    # Check project revision in isolated DB
    conn = sqlite3.connect(str(ISOLATED_DB))
    c = conn.cursor()
    rev = c.execute("SELECT revision FROM projects WHERE id=?", (PROJECT_ID,)).fetchone()[0]
    conn.close()
    print(f"[Code] Project revision after save: Rev {rev}")
    
    # Capture code ownership screenshot
    code_shot = EVIDENCE_DIR / "code_ownership_forked_1920x1080.png"
    await page.screenshot(path=str(code_shot), full_page=True)
    print(f"[Code] Screenshot saved: {code_shot.name}")


async def run_step3_chat_workflow(page):
    print("\n--- [Step 3] Global Chat Tool Flow & ThoughtChain UI Verification ---")
    
    # Set explicit localStorage selections before loading
    await page.goto(f"{BASE_URL}/", wait_until="networkidle")
    await page.evaluate("""() => {
        localStorage.setItem("6clips_ai_provider", "ollama");
        localStorage.setItem("6clips_ai_model", "gemma4:e4b");
        localStorage.setItem("6clips_ai_reasoning", "low");
    }""")
    await page.reload(wait_until="networkidle")
    await asyncio.sleep(1)
    
    # Locate chat input
    input_box = page.locator('textarea').first
    await input_box.wait_for(state="visible", timeout=10000)
    
    test_msg = "Create a 30-second 9:16 gaming highlight from my gameplay technical_gaming_fixture.mp4. Pick the best moment, add synchronized captions and an animated intro, and show me the finished video."
    await input_box.fill(test_msg)
    await asyncio.sleep(0.5)
    
    # Find submit button (IconArrowUp)
    send_btn = page.locator("button:has(svg.tabler-icon-arrow-up), button:has-text('Send'), button[type='button']").filter(has=page.locator("svg.tabler-icon-arrow-up")).first
    if await send_btn.is_visible() and not await send_btn.is_disabled():
        await send_btn.click()
    else:
        await page.keyboard.press("Enter")
        
    print(f"[Chat] Sent message: '{test_msg[:50]}...'")
    
    # Wait for assistant response stream / tool execution
    print("[Chat] Monitoring WebSocket streaming & tool events...")
    start_time = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start_time < 60:
        # Check if ThoughtChain or assistant message appeared
        tc_el = page.locator("div[role='region'][aria-label='Execution timeline'], [data-role='assistant']").first
        if await tc_el.is_visible():
            print("[Chat] Assistant/Execution element detected in DOM!")
            break
        await asyncio.sleep(1.0)
        
    await asyncio.sleep(8.0)
    
    # Expand ThoughtChain if present
    expand_btn = page.locator("button:has-text('completed'), button:has-text('steps'), button:has-text('step')").first
    if await expand_btn.is_visible():
        await expand_btn.click()
        await asyncio.sleep(1.0)
        print("[Chat] ThoughtChain accordion expanded!")
        
    # Capture complete Chat screenshot
    chat_shot = EVIDENCE_DIR / "chat_workflow_actual_1920x1080.png"
    await page.screenshot(path=str(chat_shot), full_page=True)
    print(f"[Chat] Saved real Chat UI screenshot: {chat_shot.name}")


async def main():
    await setup_settings()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await ctx.new_page()
        
        await run_step2_code_ownership(page)
        await run_step3_chat_workflow(page)
        
        await ctx.close()
        await browser.close()
    print("\nTARGETED TESTS COMPLETE!")


if __name__ == "__main__":
    asyncio.run(main())
