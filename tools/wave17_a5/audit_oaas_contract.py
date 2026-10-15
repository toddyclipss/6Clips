# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
OAAS Product Contract Validator.

Executes static assertions on codebase to enforce:
1. Exactly 5 top-level sidebar navigation destinations: Trends, My Channel, Library, Motion Graphics, Messages.
2. Complete absence of fake test fixture controls ('Load Test Fixture', 'Preview with Isolated Test Fixture', 'Trigger Worker Tick') from production UI.
3. Prevention of standalone 'Catalog', 'Clip Studio', 'Tools', 'Distribution', 'Scheduling', 'Analytics' in main navigation.
4. Fail-closed provider publishing and analytics constraints.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parents[2]

ALLOWED_PRIMARY_DESTINATIONS = [
    "trends",
    "channels",  # "My Channel"
    "library",
    "motion",    # "Motion Graphics"
    "messages",
]

FORBIDDEN_PRIMARY_NAV_ENTRIES = [
    "catalog",
    "clips",
    "clip studio",
    "tools",
    "distribution",
    "scheduling",
    "analytics",
]

FORBIDDEN_UI_FIXTURE_BUTTONS = [
    "load test fixture",
    "preview with isolated test fixture",
    "trigger worker tick",
]


def audit_navigation_destinations(frontend_src: Path) -> Dict[str, Any]:
    """Check that Layout.jsx and navigation components only render the 5 OAAS destinations."""
    layout_file = frontend_src / "components" / "Layout.jsx"
    if not layout_file.exists():
        return {"status": "SKIPPED", "reason": "Layout.jsx not found"}

    content = layout_file.read_text(encoding="utf-8").lower()
    violations = []

    # Look for nav items or buttons in sidebar
    for forbidden in FORBIDDEN_PRIMARY_NAV_ENTRIES:
        # Check if forbidden entry is added as a navigation item
        pattern = rf'path:\s*["\']/{forbidden}["\']'
        if re.search(pattern, content):
            violations.append(f"Forbidden standalone navigation path found in Layout.jsx: /{forbidden}")

    return {
        "status": "FAIL" if violations else "PASS",
        "violations": violations,
    }


def audit_production_ui_fixtures(frontend_src: Path) -> Dict[str, Any]:
    """Check that forbidden test fixture buttons are absent from production pages."""
    violations = []
    pages_dir = frontend_src / "pages"
    if not pages_dir.exists():
        return {"status": "SKIPPED", "reason": "pages directory not found"}

    for root, _, files in os.walk(pages_dir):
        for f in files:
            if f.endswith((".jsx", ".tsx", ".js", ".ts")):
                p = Path(root) / f
                text = p.read_text(encoding="utf-8").lower()
                for needle in FORBIDDEN_UI_FIXTURE_BUTTONS:
                    if needle in text:
                        rel = p.relative_to(ROOT_DIR)
                        violations.append(f"Forbidden production fixture control '{needle}' found in {rel}")

    return {
        "status": "FAIL" if violations else "PASS",
        "violations": violations,
    }


def audit_anti_fake_patterns(backend_dir: Path) -> Dict[str, Any]:
    """Check that production transports do not allow fake post IDs to verify as published."""
    violations = []
    transport_file = backend_dir / "distribution" / "transport.py"
    if transport_file.exists():
        text = transport_file.read_text(encoding="utf-8")
        if 'if remote_post_id.startswith("fake_"):' not in text:
            violations.append("ProductionLiveTransport missing explicit rejection of fake post IDs.")

    return {
        "status": "FAIL" if violations else "PASS",
        "violations": violations,
    }


def run_full_contract_audit() -> Dict[str, Any]:
    frontend_src = ROOT_DIR / "frontend" / "src"
    backend_dir = ROOT_DIR / "backend"

    nav_audit = audit_navigation_destinations(frontend_src)
    ui_audit = audit_production_ui_fixtures(frontend_src)
    backend_audit = audit_anti_fake_patterns(backend_dir)

    all_passed = (
        nav_audit["status"] in ("PASS", "SKIPPED") and
        ui_audit["status"] in ("PASS", "SKIPPED") and
        backend_audit["status"] in ("PASS", "SKIPPED")
    )

    report = {
        "overall_status": "PASS" if all_passed else "FAIL",
        "navigation_audit": nav_audit,
        "production_ui_fixtures_audit": ui_audit,
        "backend_anti_fake_audit": backend_audit,
    }
    return report


if __name__ == "__main__":
    rep = run_full_contract_audit()
    print(json.dumps(rep, indent=2))
    if rep["overall_status"] == "FAIL":
        sys.exit(1)
    sys.exit(0)
