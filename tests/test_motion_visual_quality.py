# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Regression tests for motion visual quality, typography fitting, and composition layout."""
import pytest
from pathlib import Path
from backend.services.hyperframes_adapter import HyperFramesAdapter
from backend.services.registry_adapter import RegistryAdapter


def test_vertical_composition_typography_adaptation(tmp_path: Path):
    """Verify that vertical (9:16) compositions dynamically scale LINE_MAX_WIDTH and avoid text clipping."""
    dest_dir = tmp_path / "compositions"
    dest_dir.mkdir(parents=True, exist_ok=True)

    staged_html = RegistryAdapter.stage_block_instance(
        block_name="weight-wave",
        version_hash="c7e1d443c713d24c",
        instance_id="test_ww_vertical",
        dest_compositions_dir=dest_dir,
        variables={"text": "RESONANCE DYNAMICS"},
        aspect_ratio="9:16",
        stage_dimensions=(1080, 1920),
    )

    content = staged_html.read_text(encoding="utf-8")
    assert "var LINE_MAX_WIDTH = 960;" in content
    assert "width: 960px;" in content
    assert "__adaptBlockGeometry" in content
    assert 'maxWidth = "100vw"' in content


def test_landscape_composition_typography_adaptation(tmp_path: Path):
    """Verify that landscape (16:9) compositions retain native typography metrics."""
    dest_dir = tmp_path / "compositions"
    dest_dir.mkdir(parents=True, exist_ok=True)

    staged_html = RegistryAdapter.stage_block_instance(
        block_name="weight-wave",
        version_hash="c7e1d443c713d24c",
        instance_id="test_ww_landscape",
        dest_compositions_dir=dest_dir,
        variables={"text": "RESONANCE DYNAMICS"},
        aspect_ratio="16:9",
        stage_dimensions=(1920, 1080),
    )

    content = staged_html.read_text(encoding="utf-8")
    assert "var LINE_MAX_WIDTH = 1760;" in content
    assert "__adaptBlockGeometry" in content


def test_caption_positioning_and_video_fit_in_composition_html():
    """Verify that HyperFramesAdapter projects caption layout zones and video fit modes into stage HTML."""
    doc = {
        "title": "Layout Regression Test",
        "aspect_ratio": "16:9",
        "timeline": {
            "duration_seconds": 5.0,
            "fps": 30,
            "tracks": [
                {
                    "id": "t_video",
                    "type": "video",
                    "clips": [
                        {
                            "id": "clip_vid",
                            "type": "video",
                            "file": "test.mp4",
                            "fit": "cover",
                            "layer_order": 0,
                        }
                    ],
                },
                {
                    "id": "t_captions",
                    "type": "captions",
                    "clips": [
                        {
                            "id": "clip_cap_top",
                            "type": "captions",
                            "caption_text": "HEADER BADGE",
                            "position": "top",
                            "layer_order": 5,
                        }
                    ],
                },
            ],
        },
    }

    html = HyperFramesAdapter.project_doc_to_html(doc)
    assert 'class="caption-block caption-pos-top"' in html
    assert "object-fit: cover;" in html
    assert ".caption-pos-top" in html
    assert ".caption-pos-bottom" in html


def test_media_elements_have_single_style_attribute():
    """Verify that generated <video> and <img> elements have exactly one style attribute and no duplicates."""
    import re

    doc = {
        "title": "Style Attribute Regression",
        "aspect_ratio": "16:9",
        "timeline": {
            "duration_seconds": 6.0,
            "tracks": [
                {
                    "id": "t_media",
                    "type": "video",
                    "clips": [
                        {
                            "id": "clip_vid_cover",
                            "type": "video",
                            "file": "test_bg.mp4",
                            "fit": "cover",
                            "layer_order": 0,
                        },
                        {
                            "id": "clip_vid_contain",
                            "type": "video",
                            "file": "test_fg.mp4",
                            "fit": "contain",
                            "layer_order": 1,
                        },
                        {
                            "id": "clip_img_cover",
                            "type": "image",
                            "file": "test_bg.png",
                            "fit": "cover",
                            "layer_order": 2,
                        },
                        {
                            "id": "clip_img_contain",
                            "type": "image",
                            "file": "test_fg.png",
                            "fit": "contain",
                            "layer_order": 3,
                        },
                    ],
                }
            ],
        },
    }

    html = HyperFramesAdapter.project_doc_to_html(doc)

    # Find all <video ...> and <img ...> element tags
    video_tags = re.findall(r"<video[^>]*>", html)
    img_tags = re.findall(r"<img[^>]*>", html)

    assert len(video_tags) == 2, f"Expected 2 video tags, found: {len(video_tags)}"
    assert len(img_tags) == 2, f"Expected 2 img tags, found: {len(img_tags)}"

    for tag in video_tags + img_tags:
        # Exactly one style attribute
        style_matches = re.findall(r'\bstyle\s*=', tag)
        assert len(style_matches) == 1, f"Element has {len(style_matches)} style attributes: {tag}"

        # No duplicate attributes of any kind
        attr_names = re.findall(r'([a-zA-Z0-9_\-]+)\s*=', tag)
        assert len(attr_names) == len(set(attr_names)), f"Element has duplicate attributes: {tag}"

    # Verify fit modes are correctly embedded in inline styles
    assert 'id="clip_vid_cover"' in video_tags[0]
    assert 'object-fit: cover' in video_tags[0]

    assert 'id="clip_vid_contain"' in video_tags[1]
    assert 'object-fit: contain' in video_tags[1]

    assert 'id="clip_img_cover"' in img_tags[0]
    assert 'object-fit: cover' in img_tags[0]

    assert 'id="clip_img_contain"' in img_tags[1]
    assert 'object-fit: contain' in img_tags[1]


@pytest.mark.asyncio
async def test_chromium_computes_intended_media_object_fit():
    """Verify that headless Chromium parses the single style attribute and computes the intended objectFit."""
    from playwright.async_api import async_playwright

    doc = {
        "title": "Chromium Object Fit Test",
        "aspect_ratio": "16:9",
        "timeline": {
            "duration_seconds": 4.0,
            "tracks": [
                {
                    "id": "t_media",
                    "type": "video",
                    "clips": [
                        {
                            "id": "vid_cover",
                            "type": "video",
                            "file": "test_bg.mp4",
                            "fit": "cover",
                            "layer_order": 0,
                        },
                        {
                            "id": "vid_contain",
                            "type": "video",
                            "file": "test_fg.mp4",
                            "fit": "contain",
                            "layer_order": 1,
                        },
                        {
                            "id": "img_cover",
                            "type": "image",
                            "file": "test_bg.png",
                            "fit": "cover",
                            "layer_order": 2,
                        },
                        {
                            "id": "img_contain",
                            "type": "image",
                            "file": "test_fg.png",
                            "fit": "contain",
                            "layer_order": 3,
                        },
                    ],
                }
            ],
        },
    }

    html = HyperFramesAdapter.project_doc_to_html(doc)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html)

        vid_cover_fit = await page.eval_on_selector("#vid_cover", "el => window.getComputedStyle(el).objectFit")
        vid_contain_fit = await page.eval_on_selector("#vid_contain", "el => window.getComputedStyle(el).objectFit")
        img_cover_fit = await page.eval_on_selector("#img_cover", "el => window.getComputedStyle(el).objectFit")
        img_contain_fit = await page.eval_on_selector("#img_contain", "el => window.getComputedStyle(el).objectFit")

        assert vid_cover_fit == "cover", f"Expected 'cover' on #vid_cover, got: {vid_cover_fit}"
        assert vid_contain_fit == "contain", f"Expected 'contain' on #vid_contain, got: {vid_contain_fit}"
        assert img_cover_fit == "cover", f"Expected 'cover' on #img_cover, got: {img_cover_fit}"
        assert img_contain_fit == "contain", f"Expected 'contain' on #img_contain, got: {img_contain_fit}"

        await browser.close()

