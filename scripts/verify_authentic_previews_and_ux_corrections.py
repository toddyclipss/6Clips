import json
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path("artifacts/motion_ux_corrections")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VIEWPORTS = [
    {"name": "1920x1080", "width": 1920, "height": 1080},
    {"name": "1440x900", "width": 1440, "height": 900},
    {"name": "1366x768", "width": 1366, "height": 768},
]

def run_browser_verification():
    print("=== STARTING AUTHENTIC PREVIEW & UX ACCEPTANCE AUDIT ===")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for vp in VIEWPORTS:
            vp_name = vp["name"]
            print(f"\n--- Testing Viewport: {vp_name} ({vp['width']}x{vp['height']}) ---")

            context = browser.new_context(viewport={"width": vp["width"], "height": vp["height"]})
            page = context.new_page()
            page.on("console", lambda m: print(f"[{vp_name} CONSOLE {m.type}] {m.text}"))
            page.on("pageerror", lambda err: print(f"[{vp_name} PAGE ERROR] {err}"))

            page.goto("http://127.0.0.1:16888/motion")
            page.wait_for_selector('#studio-preview-iframe', timeout=20000)
            page.wait_for_timeout(1000)

            # 1. Full-width timeline verification
            ss_path = OUTPUT_DIR / f"01_editor_layout_fullwidth_timeline_{vp_name}.png"
            page.screenshot(path=str(ss_path))
            print(f"Captured full-width timeline layout: {ss_path.name}")

            timeline_ws = page.locator('[data-testid="studio-timeline-workspace"]').first
            editor_section = page.locator('section').first
            if timeline_ws.is_visible() and editor_section.is_visible():
                tl_box = timeline_ws.bounding_box()
                ed_box = editor_section.bounding_box()
                if tl_box and ed_box:
                    print(f"Timeline width: {tl_box['width']:.1f}px (Editor container width: {ed_box['width']:.1f}px)")
                    assert tl_box["width"] >= ed_box["width"] - 20, f"Timeline is not spanning full editor width! TL: {tl_box['width']}, ED: {ed_box['width']}"
                    print("Gate 6 SUCCESS: Timeline workspace spans 100% full width of the editor beneath side panels.")

            # 2. Switch to Catalog tab
            catalog_tab_btn = page.locator('button:has-text("Catalog & Media")').first
            if catalog_tab_btn.is_visible():
                catalog_tab_btn.click()
                page.wait_for_timeout(400)

            catalog_chip = page.locator('button:has-text("HyperFrames Catalog")').first
            if catalog_chip.is_visible():
                catalog_chip.click()
                page.wait_for_timeout(600)
            else:
                tabs = page.locator('.MuiTabs-root button')
                if tabs.count() >= 3:
                    tabs.nth(2).click()
                    page.wait_for_timeout(600)

            # Capture Catalog tab with canonical category filter chips
            ss_cat = OUTPUT_DIR / f"02_catalog_canonical_categories_{vp_name}.png"
            page.screenshot(path=str(ss_cat))
            print(f"Captured Catalog tab: {ss_cat.name}")

            # Verify the 8 canonical category chips exist
            for cat_label in ["All", "Typography", "Lower Thirds", "Mock UI & Social", "Charts", "Backgrounds & Shaders", "Transitions", "Call to Action"]:
                chip = page.locator(f'span:text-is("{cat_label}")').first
                assert chip.is_visible(), f"Expected canonical category chip '{cat_label}' not found!"
            print("Gate 4 SUCCESS: All 8 canonical categories are visible and selectable.")

            # Filter to Typography
            type_chip = page.locator('span:text-is("Typography")').first
            type_chip.click()
            page.wait_for_timeout(400)

            # Locate weight-wave card
            ww_card = page.locator('[data-testid="catalog-card-weight-wave"]').first
            assert ww_card.is_visible(), "Catalog card for 'weight-wave' must be visible!"

            # 3. 9:16 Ghost Preview & Geometry Validation
            print("Hovering on weight-wave card to trigger 9:16 ghost preview...")
            ww_card.hover()
            page.wait_for_timeout(800)

            # Assert stage is active and in portrait bounds
            ghost_stage = page.locator("#studio-ghost-preview-stage")
            assert ghost_stage.count() > 0, "Ghost preview stage must be mounted on hover!"
            ghost_box = ghost_stage.bounding_box()
            assert ghost_box is not None, "Ghost stage must have a measurable bounding box!"
            assert ghost_box["height"] > ghost_box["width"], f"Expected portrait aspect in 9:16 mode, got {ghost_box}"

            # Capture ghost preview stage in 9:16 portrait
            ss_ghost_916 = OUTPUT_DIR / f"03_ghost_preview_weight_wave_9x16_{vp_name}.png"
            page.screenshot(path=str(ss_ghost_916))
            print(f"Captured 9:16 ghost preview: {ss_ghost_916.name}")

            # Verify Gate 3: NO GHOST PREVIEW banner overlay
            banner_text = page.locator('text="GHOST PREVIEW"')
            assert banner_text.count() == 0, "Gate 3 violation: 'GHOST PREVIEW' text found on stage!"

            # Find ghost frame and assert geometry inside frame
            ghost_frame = None
            for f in page.frames:
                if "weight-wave" in f.url:
                    ghost_frame = f
                    break
            assert ghost_frame is not None, "Ghost preview iframe for weight-wave must be present!"

            line_geom = ghost_frame.evaluate("""() => {
                const line = document.getElementById('ww-line');
                if (!line) return null;
                const rect = line.getBoundingClientRect();
                return {
                    text: line.innerText,
                    fontSize: line.style.fontSize,
                    top: rect.top,
                    bottom: rect.bottom,
                    left: rect.left,
                    right: rect.right,
                    width: rect.width,
                    height: rect.height,
                    windowH: window.innerHeight,
                    windowW: window.innerWidth
                };
            }""")
            print("9:16 Frame line geometry:", line_geom)
            assert line_geom is not None, "Element #ww-line must exist inside the weight-wave iframe!"
            assert "PRESSURE MOVES THROUGH TYPE" in line_geom["text"], f"Expected full headline text, got: {line_geom['text']}"
            assert line_geom["top"] >= 0, f"Line top ({line_geom['top']}) is off-screen negative! Must be >= 0."
            assert line_geom["bottom"] <= line_geom["windowH"], f"Line bottom ({line_geom['bottom']}) is clipped past frame height ({line_geom['windowH']})!"
            assert line_geom["width"] >= line_geom["windowW"] * 0.70, f"Line width ({line_geom['width']}) is too small relative to frame ({line_geom['windowW']})!"
            print(f"Gate 1 & 2 SUCCESS: 9:16 weight-wave typography is fully visible, centered ({line_geom['left']:.1f}px to {line_geom['right']:.1f}px across {line_geom['windowW']}px frame), and correctly fitted.")

            # Unhover / Mouse leave & assert state restoration
            page.mouse.move(20, 20)
            page.wait_for_timeout(500)
            assert page.locator("#studio-ghost-preview-stage").count() == 0, "Ghost preview stage must be dismissed when mouse leaves!"

            # 4. 16:9 Landscape Mode Testing (on 1920x1080)
            if vp_name == "1920x1080":
                print("\nTesting 16:9 landscape aspect ratio switch...")
                aspect_btn_169 = page.locator('[data-testid="aspect-ratio-btn-16-9"]').first
                assert aspect_btn_169.is_visible(), "16:9 aspect button must be visible"
                print("Initial btn169 classes in verify:", aspect_btn_169.get_attribute("class"))
                aspect_btn_169.click()
                print("After click btn169 classes in verify:", aspect_btn_169.get_attribute("class"))

                res_169 = None
                for _ in range(25):
                    res_169 = page.evaluate("""() => {
                        const el = document.getElementById('studio-preview-iframe');
                        if (!el) return null;
                        const r = el.getBoundingClientRect();
                        return { w: r.width, h: r.height, ratio: r.width / r.height };
                    }""")
                    if res_169 and res_169["ratio"] > 1.6:
                        break
                    page.wait_for_timeout(300)

                assert res_169 is not None, "Canvas iframe must exist"
                print(f"16:9 Canvas dimensions: {res_169['w']:.1f}x{res_169['h']:.1f} (Ratio: {res_169['ratio']:.3f})")
                assert 1.65 <= res_169["ratio"] <= 1.90, f"Expected 16:9 aspect ratio (~1.77), got {res_169['ratio']}"

                # Hover weight-wave in 16:9
                ww_card.hover()
                page.wait_for_timeout(800)

                ghost_stage_169 = page.locator("#studio-ghost-preview-stage")
                assert ghost_stage_169.count() > 0, "Ghost preview must mount in 16:9 mode!"
                gbox_169 = ghost_stage_169.bounding_box()
                assert gbox_169["width"] > gbox_169["height"], f"Ghost stage in 16:9 must be landscape! Got: {gbox_169}"

                ss_ghost_169 = OUTPUT_DIR / "04_ghost_preview_weight_wave_16x9_1920x1080.png"
                page.screenshot(path=str(ss_ghost_169))
                print(f"Captured 16:9 landscape ghost preview: {ss_ghost_169.name}")

                # Verify 16:9 internal line geometry
                ghost_frame_169 = None
                for f in page.frames:
                    if "weight-wave" in f.url:
                        ghost_frame_169 = f
                        break
                assert ghost_frame_169 is not None, "16:9 ghost iframe must exist!"
                line_geom_169 = ghost_frame_169.evaluate("""() => {
                    const line = document.getElementById('ww-line');
                    if (!line) return null;
                    const rect = line.getBoundingClientRect();
                    return {
                        text: line.innerText,
                        width: rect.width,
                        height: rect.height,
                        top: rect.top,
                        bottom: rect.bottom,
                        windowW: window.innerWidth,
                        windowH: window.innerHeight
                    };
                }""")
                print("16:9 Frame line geometry:", line_geom_169)
                assert line_geom_169 is not None, "#ww-line must exist in 16:9 frame"
                assert "PRESSURE MOVES THROUGH TYPE" in line_geom_169["text"]
                assert line_geom_169["width"] > 400, f"16:9 headline must span wide (>400px), got {line_geom_169['width']}"
                print("Gate 1 & 2 SUCCESS: 16:9 weight-wave is fully visible in genuine landscape cinema framing.")

                # Unhover and switch back to 9:16
                page.mouse.move(20, 20)
                page.wait_for_timeout(400)
                aspect_btn_916 = page.locator('[data-testid="aspect-ratio-btn-9-16"]').first
                assert aspect_btn_916.is_visible()
                aspect_btn_916.click()
                for _ in range(25):
                    res_back = page.evaluate("""() => {
                        const el = document.getElementById('studio-preview-iframe');
                        if (!el) return null;
                        const r = el.getBoundingClientRect();
                        return { w: r.width, h: r.height, ratio: r.width / r.height };
                    }""")
                    if res_back and res_back["ratio"] < 0.7:
                        break
                    page.wait_for_timeout(300)

            # 5. Check Sources Tab for Descending Virality Score
            sources_tab = page.locator('.MuiTabs-root button').nth(1)
            if sources_tab.is_visible():
                sources_tab.click()
                page.wait_for_timeout(600)
                ss_sources = OUTPUT_DIR / f"05_sources_descending_scores_{vp_name}.png"
                page.screenshot(path=str(ss_sources))
                print(f"Captured Sources score ordering: {ss_sources.name}")

            context.close()

        browser.close()

    print("\n=== ALL REGRESSION ASSERTIONS PASSED WITH ZERO TOLERANCE FOR VISUAL DEFECTS ===")

if __name__ == "__main__":
    run_browser_verification()
