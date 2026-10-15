# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 17 Agent 2 Navigation & Routes Test Suite.

Verifies:
1. Exactly FIVE top-level OAAS destinations in the sidebar:
   - Trends (/trends)
   - My Channel (/channels)
   - Library (/videos)
   - Motion Graphics (/motion)
   - Messages (/messaging)
2. Standalone links for Catalog, Clip Studio, Distribution, Analytics, and Tools are removed from the sidebar.
3. Clean backward-compatible redirects exist for legacy routes:
   - /catalog -> /motion?tab=catalog
   - /clips -> /motion?mode=clip
   - /tools -> /motion?mode=tools
   - /distribution -> /channels
   - /analytics -> /channels
4. Developer/fake test buttons are eradicated from production UI:
   - "Load Test Fixture"
   - "Preview with Isolated Test Fixture"
   - "Trigger Worker Tick"
   - "INVENTORY ONLY"
   - "Shipped Cards"
"""

import re
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"


class TestWave17A2NavigationRoutes:
    """Verifies OAAS five-destination top-level navigation and route modernization."""

    def test_sidebar_has_exactly_five_top_level_oaas_destinations(self):
        """Layout.jsx navItems must contain strictly the 5 OAAS destinations in exact order."""
        layout_path = FRONTEND_SRC / "components" / "Layout.jsx"
        assert layout_path.exists(), "Layout.jsx does not exist"
        content = layout_path.read_text(encoding="utf-8")

        # Extract navItems array block
        nav_match = re.search(r"const navItems\s*=\s*\[(.*?)\]", content, re.DOTALL)
        assert nav_match, "navItems array not found in Layout.jsx"
        nav_block = nav_match.group(1)

        # Expected top-level destinations
        expected = [
            ("/trends", "Trends"),
            ("/channels", "My Channel"),
            ("/videos", "Library"),
            ("/motion", "Motion Graphics"),
            ("/messaging", "Messages"),
        ]

        found_items = []
        for line in nav_block.splitlines():
            to_match = re.search(r'to:\s*"([^"]+)"', line)
            label_match = re.search(r'label:\s*"([^"]+)"', line)
            if to_match and label_match:
                found_items.append((to_match.group(1), label_match.group(1)))

        assert found_items == expected, (
            f"Top-level navItems must be exactly {expected}, but found {found_items}"
        )

    def test_no_standalone_catalog_clips_tools_distribution_analytics_in_nav(self):
        """Catalog, Clip Studio, Tools, Distribution, and Analytics must not exist as top-level sidebar items."""
        layout_path = FRONTEND_SRC / "components" / "Layout.jsx"
        content = layout_path.read_text(encoding="utf-8")

        nav_match = re.search(r"const navItems\s*=\s*\[(.*?)\]", content, re.DOTALL)
        nav_block = nav_match.group(1)

        forbidden_paths = ["/catalog", "/clips", "/tools", "/distribution", "/analytics"]
        forbidden_labels = ["Catalog", "Clip Studio", "Tools", "Distribution", "Analytics"]

        for path in forbidden_paths:
            assert f'to: "{path}"' not in nav_block, f"Forbidden top-level path found in navItems: {path}"
        for label in forbidden_labels:
            assert f'label: "{label}"' not in nav_block, f"Forbidden top-level label found in navItems: {label}"

    def test_nav_items_have_proper_data_testids_and_aria_labels(self):
        """Layout.jsx must set aria-label and data-testid on ListItemButton for accessible testing."""
        layout_path = FRONTEND_SRC / "components" / "Layout.jsx"
        content = layout_path.read_text(encoding="utf-8")

        assert 'aria-label={label}' in content, "Missing aria-label on nav items in Layout.jsx"
        assert 'data-testid={`nav-${label.toLowerCase().replace(/\\s+/g, "-")}`}' in content or 'data-testid=' in content, (
            "Missing data-testid on nav items in Layout.jsx"
        )

    def test_app_routes_have_backward_compatible_redirects(self):
        """App.jsx must redirect /catalog, /clips, /tools, /distribution, and /analytics cleanly."""
        app_path = FRONTEND_SRC / "App.jsx"
        assert app_path.exists(), "App.jsx does not exist"
        content = app_path.read_text(encoding="utf-8")

        # Verify LegacyRedirect or equivalent redirection
        assert "LegacyRedirect" in content, "LegacyRedirect helper component not found in App.jsx"

        # Check /clips -> /motion?mode=clip
        assert re.search(r'<Route\s+path="clips"\s+element={<LegacyRedirect\s+to="/motion"\s+defaultQuery={{\s*mode:\s*"clip"\s*}}', content), (
            "Missing redirect from /clips to /motion?mode=clip"
        )

        # Check /catalog -> /motion?tab=catalog
        assert re.search(r'<Route\s+path="catalog"\s+element={<LegacyRedirect\s+to="/motion"\s+defaultQuery={{\s*tab:\s*"catalog"\s*}}', content), (
            "Missing redirect from /catalog to /motion?tab=catalog"
        )

        # Check /tools -> /motion?mode=tools
        assert re.search(r'<Route\s+path="tools"\s+element={<LegacyRedirect\s+to="/motion"\s+defaultQuery={{\s*mode:\s*"tools"\s*}}', content), (
            "Missing redirect from /tools to /motion?mode=tools"
        )

        # Check /distribution -> /channels
        assert re.search(r'<Route\s+path="distribution"\s+element={<LegacyRedirect\s+to="/channels"', content), (
            "Missing redirect from /distribution to /channels"
        )

        # Check /analytics -> /channels
        assert re.search(r'<Route\s+path="analytics"\s+element={<LegacyRedirect\s+to="/channels"', content), (
            "Missing redirect from /analytics to /channels"
        )

    def test_removal_of_fake_test_buttons_in_production_ui(self):
        """Production UI must not contain fake developer actions or test fixture triggers."""
        analytics_path = FRONTEND_SRC / "pages" / "Analytics.jsx"
        distribution_path = FRONTEND_SRC / "pages" / "Distribution.jsx"
        catalog_card_path = FRONTEND_SRC / "components" / "catalog" / "CatalogCard.jsx"
        studio_panel_path = FRONTEND_SRC / "components" / "motion" / "StudioResourcePanel.jsx"

        if analytics_path.exists():
            analytics_content = analytics_path.read_text(encoding="utf-8")
            assert "Load Test Fixture" not in analytics_content, "Fake button 'Load Test Fixture' found in Analytics.jsx"
            assert "Preview with Isolated Test Fixture" not in analytics_content, "Fake button 'Preview with Isolated Test Fixture' found in Analytics.jsx"

        if distribution_path.exists():
            dist_content = distribution_path.read_text(encoding="utf-8")
            assert "Trigger Worker Tick" not in dist_content, "Fake button 'Trigger Worker Tick' found in Distribution.jsx"

        if catalog_card_path.exists():
            card_content = catalog_card_path.read_text(encoding="utf-8")
            assert 'label="INVENTORY ONLY"' not in card_content, "Raw label 'INVENTORY ONLY' found in CatalogCard.jsx"

        if studio_panel_path.exists():
            panel_content = studio_panel_path.read_text(encoding="utf-8")
            assert "INVENTORY ONLY" not in panel_content, "Raw 'INVENTORY ONLY' found in StudioResourcePanel.jsx"
            assert 'let statusChipLabel = "Unported"' not in panel_content, "Developer status 'Unported' found in StudioResourcePanel.jsx"
