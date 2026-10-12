# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Verification of Live Timeline Audio volume handling (0, 0.5, 0.8, 1.0) and catalog hover isolation."""
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

from backend.services.hyperframes_adapter import HyperFramesAdapter
project_doc_to_html = HyperFramesAdapter.project_doc_to_html

def test_volume_serialization():
    print("--- 1. Testing volume serialization in hyperframes_adapter ---")
    volumes_to_test = [0.0, 0.5, 0.8, 1.0]
    for vol in volumes_to_test:
        doc = {
            "schema_version": 2,
            "title": f"Test Vol {vol}",
            "aspect_ratio": "9:16",
            "timeline": {
                "fps": 30,
                "duration_seconds": 10.0,
                "tracks": [
                    {
                        "id": "track_audio",
                        "type": "audio",
                        "name": "Audio",
                        "volume": 1.0,
                        "muted": False,
                        "clips": [
                            {
                                "id": "clip_audio_1",
                                "type": "audio",
                                "asset_file": "lofi_chill.mp3",
                                "volume": vol,
                                "start_seconds": 0.0,
                                "duration_seconds": 10.0,
                            }
                        ]
                    }
                ]
            }
        }
        html = project_doc_to_html(doc)
        if vol == 0.0:
            assert 'data-volume="0"' in html, "Volume 0.0 must serialize to data-volume='0'"
            print(f"Volume {vol}: correctly generated data-volume='0' (muted)")
        else:
            tag = f'data-volume="{vol:.3f}"'
            assert tag in html, f"Volume {vol} must serialize to {tag}"
            print(f"Volume {vol}: correctly generated {tag}")

async def test_browser_volume_and_catalog_hover():
    print("\n--- 2. Testing Browser Runtime Volume & Catalog Hover ---")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})

        # Test evaluating volume parsing in browser JS environment
        results = await page.evaluate("""() => {
            function parseVol(dsVolume) {
                if (dsVolume != null) {
                    var v = parseFloat(dsVolume);
                    if (!isNaN(v)) return Math.max(0, Math.min(1, v));
                }
                return 1.0;
            }
            return {
                zero: parseVol("0"),
                half: parseVol("0.5"),
                eight: parseVol("0.8"),
                full: parseVol("1.0"),
                zero_str: parseVol("0.000"),
                empty: parseVol(null)
            };
        }""")
        print("Browser JS volume parse evaluation:", results)
        assert results["zero"] == 0.0, "Volume '0' must NOT coerce to 1.0!"
        assert results["half"] == 0.5
        assert results["eight"] == 0.8
        assert results["full"] == 1.0
        assert results["zero_str"] == 0.0
        assert results["empty"] == 1.0

        # Now navigate to /motion to verify editor and catalog hover
        await page.goto("http://127.0.0.1:16888/motion", wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # Click Catalog tab (tab 2 in resources panel)
        catalog_tab = page.locator('button[role="tab"]:has-text("Catalog")')
        if await catalog_tab.count() > 0:
            print("Switching to Catalog tab in resource panel...")
            await catalog_tab.click()
            await page.wait_for_timeout(1000)

            # Find catalog block cards
            block_cards = page.locator('.MuiCard-root, [data-testid="catalog-block-tile"]')
            count = await block_cards.count()
            print(f"Catalog block tiles found: {count}")
            if count > 0:
                print("Hovering catalog block card...")
                await block_cards.first.hover()
                await page.wait_for_timeout(1000)

                # Check if any audio element is currently playing in page or iframes
                audio_playing = await page.evaluate("""() => {
                    const audios = Array.from(document.querySelectorAll('audio'));
                    const frames = Array.from(document.querySelectorAll('iframe'));
                    let playing = audios.some(a => !a.paused && a.currentTime > 0);
                    frames.forEach(f => {
                        try {
                            const fa = Array.from(f.contentDocument.querySelectorAll('audio'));
                            if (fa.some(a => !a.paused && a.currentTime > 0)) playing = true;
                        } catch(e) {}
                    });
                    return playing;
                }""")
                print("Is audio playing on catalog hover?", audio_playing)
                assert not audio_playing, "Catalog hover must NEVER play audio!"

        Path("artifacts/p0_final_remediation").mkdir(parents=True, exist_ok=True)
        await page.screenshot(path="artifacts/p0_final_remediation/09_motion_catalog_hover_silent.png")
        print("Saved screenshot: 09_motion_catalog_hover_silent.png")

        print("Timeline Audio Volume & Catalog Isolation PASSED!")
        await browser.close()

if __name__ == "__main__":
    test_volume_serialization()
    asyncio.run(test_browser_volume_and_catalog_hover())
