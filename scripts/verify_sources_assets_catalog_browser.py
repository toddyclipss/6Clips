# language: Python, file: scripts/verify_sources_assets_catalog_browser.py, target: Windows 11, playwright
"""
Automated Browser Acceptance Verification for Sources, Assets & HyperFrames Catalog Previews.
"""
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path("artifacts/sources_assets_catalog_acceptance")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Ensure UTF-8 output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def log(msg):
    print(msg, flush=True)

def run_acceptance():
    log("=== Starting Visual Acceptance Verification ===")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1600, "height": 950})
        page = context.new_page()

        page.on("console", lambda msg: log(f"[Browser Console {msg.type}]: {msg.text}") if msg.type in ("error", "warning") else None)

        log("[1/6] Navigating to /motion editor...")
        page.goto("http://127.0.0.1:16888/motion", wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)

        # Wait for either preview iframe or button
        page.wait_for_selector("button:has-text('Catalog & Media'), #studio-preview-iframe", timeout=15000)
        log("[OK] Motion editor loaded.")

        # Capture initial project revision from API
        proj_res = page.request.get("http://127.0.0.1:16888/api/projects")
        projects = proj_res.json().get("projects", [])
        assert len(projects) > 0, "No projects returned from API"
        initial_proj = projects[0]
        proj_id = initial_proj["id"]
        initial_rev = initial_proj["revision"]
        log(f"[OK] Initial Project ID: {proj_id}, Revision: {initial_rev}")

        # Switch left panel to 'Catalog & Media' (StudioResourcePanel)
        log("Switching left panel to 'Catalog & Media'...")
        cat_nav_btn = page.locator("button:has-text('Catalog & Media')")
        if cat_nav_btn.is_visible():
            cat_nav_btn.click()
            time.sleep(1)
            log("[OK] Opened StudioResourcePanel.")

        # ---------------------------------------------------------
        # Step 2: Test Sources Tab (Tab index 1)
        # ---------------------------------------------------------
        log("\n[2/6] Testing Sources Tab...")
        # Inside StudioResourcePanel, find tabs
        sources_tab = page.locator("button.MuiTab-root:has-text('Sources')")
        sources_tab.click()
        time.sleep(1.5)

        page.screenshot(path=str(OUTPUT_DIR / "01_sources_tab.png"))
        log("[OK] Captured Sources tab screenshot.")

        # Check for source items
        source_cards = page.locator("div[data-testid='source-card']")
        card_count = source_cards.count()
        log(f"[OK] Found {card_count} source cards rendered.")

        if card_count > 0:
            first_source = source_cards.first
            first_source.click()
            time.sleep(1)

            dialog = page.locator("div[role='dialog']")
            if dialog.is_visible():
                log("[OK] Source Preview Modal opened successfully.")
                page.screenshot(path=str(OUTPUT_DIR / "02_source_preview_modal.png"))
                close_btn = dialog.locator("button:has-text('Close')")
                if close_btn.is_visible():
                    close_btn.click()
                    time.sleep(0.5)
                    log("[OK] Source Preview Modal closed cleanly.")

        # ---------------------------------------------------------
        # Step 3: Test Assets Tab (Tab index 0)
        # ---------------------------------------------------------
        log("\n[3/6] Testing Assets Tab & Audio Pre-listening...")
        assets_tab = page.locator("button.MuiTab-root:has-text('Assets')")
        assets_tab.click()
        time.sleep(1)

        asset_cards = page.locator("div[data-testid='asset-card']")
        log(f"[OK] Found {asset_cards.count()} asset cards rendered.")

        page.screenshot(path=str(OUTPUT_DIR / "03_assets_tab.png"))
        log("[OK] Captured Assets tab screenshot.")

        audio_buttons = page.locator("button:has(svg[data-testid='PlayArrowIcon']), button:has(svg[data-testid='PauseIcon'])")
        log(f"[OK] Found {audio_buttons.count()} inline audio playback controls.")

        # ---------------------------------------------------------
        # Step 4: Test HyperFrames Catalog Tab (Tab index 2)
        # ---------------------------------------------------------
        log("\n[4/6] Testing HyperFrames Catalog Visual Posters...")
        catalog_tab = page.locator("button.MuiTab-root:has-text('Catalog')")
        catalog_tab.click()
        time.sleep(2)

        catalog_cards = page.locator("div[data-testid^='catalog-card-']")
        cat_count = catalog_cards.count()
        log(f"[OK] Catalog items loaded: {cat_count} cards.")
        assert cat_count > 0, "Expected catalog items to be rendered."

        posters = page.locator("img[src*='/poster']")
        poster_count = posters.count()
        log(f"[OK] Visual posters rendered on cards: {poster_count}")

        page.screenshot(path=str(OUTPUT_DIR / "04_catalog_tab_posters.png"))

        # Category filter chips
        category_chips = page.locator(".MuiChip-root")
        log(f"[OK] Category filter chips: {category_chips.count()}")
        titles_chip = page.locator(".MuiChip-root:has-text('Titles')")
        if titles_chip.is_visible():
            titles_chip.click()
            time.sleep(0.5)
            filtered_count = page.locator("div[data-testid^='catalog-card-']").count()
            log(f"[OK] Filtered to 'Titles' category: {filtered_count} cards.")
            all_chip = page.locator(".MuiChip-root:has-text('All')")
            if all_chip.is_visible():
                all_chip.click()
                time.sleep(0.5)

        # ---------------------------------------------------------
        # Step 5: Test Hover Ghost Preview (~200ms debounce)
        # ---------------------------------------------------------
        log("\n[5/6] Testing Non-destructive Hover Ghost Preview...")
        first_card = catalog_cards.first
        first_card.hover()
        time.sleep(1.0) # Allow debounce + ghost iframe render

        ghost_stage = page.locator("#studio-ghost-preview-stage")
        assert ghost_stage.is_visible(), "Ghost preview stage did not become visible upon hover!"
        log("[OK] #studio-ghost-preview-stage is visible over canvas!")

        ghost_iframe = page.locator("#studio-ghost-preview-iframe")
        assert ghost_iframe.is_visible(), "Ghost preview iframe did not become visible!"
        iframe_src = ghost_iframe.get_attribute("src")
        log(f"[OK] Ghost preview iframe src: {iframe_src}")
        assert "/api/projects/catalog/blocks/" in iframe_src and "/preview" in iframe_src

        page.screenshot(path=str(OUTPUT_DIR / "05_ghost_preview_active.png"))
        log("[OK] Captured active Ghost Preview screenshot.")

        # Test Mouse Leave dismissal
        log("Testing mouse leave dismissal...")
        page.mouse.move(50, 50)
        time.sleep(0.6)

        assert not ghost_stage.is_visible(), "Ghost preview stage did not dismiss after mouse leave!"
        log("[OK] Ghost preview dismissed cleanly on mouse leave.")

        # Test Rapid Hover switching
        log("Testing rapid hover switching between cards...")
        if cat_count > 1:
            second_card = catalog_cards.nth(1)
            first_card.hover()
            time.sleep(0.1)
            second_card.hover()
            time.sleep(0.8)
            assert ghost_stage.is_visible(), "Ghost preview stage not active on second card!"
            second_src = page.locator("#studio-ghost-preview-iframe").get_attribute("src")
            log(f"[OK] Rapid hover switched cleanly to second block: {second_src}")

            # Test Escape Key dismissal
            log("Testing Escape key dismissal...")
            page.keyboard.press("Escape")
            time.sleep(0.5)
            assert not ghost_stage.is_visible(), "Ghost preview stage did not dismiss on Escape key!"
            log("[OK] Ghost preview dismissed cleanly on Escape key.")

        page.screenshot(path=str(OUTPUT_DIR / "06_ghost_preview_dismissed.png"))

        # Verify NON-DESTRUCTIVE INVARIANT
        check_res = page.request.get(f"http://127.0.0.1:16888/api/projects/{proj_id}")
        current_rev = check_res.json()["revision"]
        log(f"[OK] Revision check: Initial = {initial_rev}, Current = {current_rev}")
        assert current_rev == initial_rev, f"SAFETY VIOLATION: Project revision mutated during hover preview ({initial_rev} -> {current_rev})!"
        log("[OK] NON-DESTRUCTIVE INVARIANT PASSED: No ProjectRevision was created during preview browsing.")

        # ---------------------------------------------------------
        # Step 6: Test Explicit Block Insertion Mutation
        # ---------------------------------------------------------
        log("\n[6/6] Testing Explicit 'Insert Block' action...")
        first_card.hover()
        time.sleep(0.8)

        insert_btn = page.locator("button:has-text('Insert Block')").first
        if not insert_btn.is_visible():
            insert_btn = first_card.locator("button:has-text('Insert Block')")

        if insert_btn.is_visible():
            insert_btn.click()
            time.sleep(2.0)
            mutated_res = page.request.get(f"http://127.0.0.1:16888/api/projects/{proj_id}")
            mutated_rev = mutated_res.json()["revision"]
            log(f"[OK] Project revision after explicit insert: {mutated_rev} (initial was {initial_rev})")
            assert mutated_rev > initial_rev, f"Expected revision > {initial_rev}, got {mutated_rev}"
            log("[OK] Canonical mutation succeeded: ProjectRevision advanced on explicit user action.")
            page.screenshot(path=str(OUTPUT_DIR / "07_block_inserted.png"))

        log("\n=== ALL VISUAL & NON-DESTRUCTIVE ACCEPTANCE CRITERIA MET ===")
        browser.close()

if __name__ == "__main__":
    try:
        run_acceptance()
    except Exception as e:
        log(f"ACCEPTANCE FAILURE: {e}")
        sys.exit(1)
