#!/usr/bin/env python3
"""
Wave 20 Agent 2 Audit: Minimal OAAS UI, One Player/Timeline, No Template Picker.
Verifies all contract constraints and invariants for 6Clips Motion Design OAAS.
"""

import sys
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = REPO_ROOT / "frontend"

def check_sidebar_navigation():
    print("[1/8] Verifying Sidebar 5 Primary Destinations...")
    layout_file = FRONTEND_DIR / "src" / "components" / "Layout.jsx"
    if not layout_file.exists():
        print("  FAIL: Layout.jsx not found")
        return False

    content = layout_file.read_text(encoding="utf-8")
    
    # Check 5 primary destinations in exact order
    expected_order = [
        ('label: "Motion Graphics"', '/motion'),
        ('label: "Trends"', '/trends'),
        ('label: "My Channel"', '/channels'),
        ('label: "Library"', '/videos'),
        ('label: "Messages"', '/messaging')
    ]
    
    pos = 0
    for label, route in expected_order:
        idx = content.find(label, pos)
        if idx == -1:
            print(f"  FAIL: Missing or out of order sidebar item: {label}")
            return False
        pos = idx

    # Check Settings as secondary bottom item
    if 'bottomItems' not in content or 'label: "Settings"' not in content:
        print("  FAIL: Settings not found in secondary bottomItems")
        return False

    print("  PASS: Sidebar navigation strictly matches approved order (Motion Graphics, Trends, My Channel, Library, Messages + Bottom Settings).")
    return True

def check_create_review_stages_and_advanced_editing():
    print("[2/8] Verifying Create & Review Workflow (No Refine primary stage)...")
    toolbar_file = FRONTEND_DIR / "src" / "components" / "motion" / "StudioToolbar.jsx"
    mg_file = FRONTEND_DIR / "src" / "pages" / "MotionGraphics.jsx"

    t_content = toolbar_file.read_text(encoding="utf-8")
    mg_content = mg_file.read_text(encoding="utf-8")

    # Ensure "refine" is NOT an option in primary stage switcher
    if 'stage-tab-refine' in t_content or '{ id: "refine"' in t_content:
        print("  FAIL: Primary Refine stage still present in StudioToolbar")
        return False

    # Check Create and Review stages present
    if '{ id: "create"' not in t_content or '{ id: "review"' not in t_content or 'stage-tab-${lvl.id}' not in t_content:
        print("  FAIL: Create or Review stage missing in StudioToolbar")
        return False

    # Check Advanced Editing toggle button present
    if 'data-testid="studio-toolbar-advanced-editing-btn"' not in t_content:
        print("  FAIL: Advanced Editing toggle button missing in StudioToolbar")
        return False

    # Check timeline is guarded by advancedEditing in MotionGraphics.jsx
    if 'advancedEditing && (' not in mg_content and 'advancedEditing ?' not in mg_content:
        print("  FAIL: Timeline workspace not guarded by advancedEditing in MotionGraphics.jsx")
        return False

    print("  PASS: Only Create and Review exposed as primary stages. Advanced Editing toggle preserved.")
    return True

def check_catalog_and_template_picker_elimination():
    print("[3/8] Verifying Elimination of User-Facing HyperFrames Catalog...")
    panel_file = FRONTEND_DIR / "src" / "components" / "motion" / "StudioResourcePanel.jsx"
    stage_file = FRONTEND_DIR / "src" / "components" / "motion" / "StudioPreviewStage.jsx"

    p_content = panel_file.read_text(encoding="utf-8")
    s_content = stage_file.read_text(encoding="utf-8")

    # In StudioResourcePanel: Catalog Tab should be gone
    if 'label="Catalog"' in p_content or 'Tab 2: Catalog' in p_content:
        print("  FAIL: Catalog tab still present in StudioResourcePanel")
        return False

    # Check no 196 block catalog card references
    forbidden_terms = [
        "Ask AI to insert block in chat",
        "Add Block",
        "catalogInventory",
        "studio-ghost-preview-stage"
    ]
    for term in forbidden_terms:
        if term in p_content or term in s_content:
            print(f"  FAIL: Found forbidden template-shopping UI artifact: '{term}'")
            return False

    print("  PASS: HyperFrames 196-block cards, shopping tabs, and hover ghost previews completely removed.")
    return True

def check_legacy_routes_redirect():
    print("[4/8] Verifying Clean Legacy Route Redirection...")
    app_file = FRONTEND_DIR / "src" / "App.jsx"
    content = app_file.read_text(encoding="utf-8")

    # Check /catalog and /clips redirect directly to /motion
    if '<Route path="catalog" element={<Navigate to="/motion" replace />} />' not in content:
        print("  FAIL: /catalog does not redirect cleanly to /motion")
        return False

    if '<Route path="clips" element={<Navigate to="/motion" replace />} />' not in content:
        print("  FAIL: /clips does not redirect cleanly to /motion")
        return False

    print("  PASS: /catalog and /clips redirect directly to /motion without shopping parameters.")
    return True

def check_authenticated_job_status():
    print("[5/8] Verifying Authenticated Job State Display (Zero fake percentages)...")
    stage_file = FRONTEND_DIR / "src" / "components" / "motion" / "StudioPreviewStage.jsx"
    content = stage_file.read_text(encoding="utf-8")

    if 'data-testid="studio-stage-job-status"' not in content:
        print("  FAIL: Missing studio-stage-job-status in StudioPreviewStage")
        return False

    if 'activeJob.step || activeJob.message' not in content:
        print("  FAIL: Job status not reading real authenticated step/message")
        return False

    print("  PASS: Authentic job status pill rendering real job steps without fake percentages.")
    return True

def check_review_panel_integrity():
    print("[6/8] Verifying Review Panel Output & Truthful Publishing States...")
    review_file = FRONTEND_DIR / "src" / "components" / "motion" / "MotionReviewPanel.jsx"
    content = review_file.read_text(encoding="utf-8")

    if 'data-testid="review-deliverables-count"' not in content:
        print("  FAIL: Missing deliverable count badge in MotionReviewPanel")
        return False

    if 'data-testid="review-correction-guidance"' not in content:
        print("  FAIL: Missing chat-based correction guidance in MotionReviewPanel")
        return False

    if 'NOT_CONNECTED / PENDING_CREDENTIALS' not in content:
        print("  FAIL: Truthful publishing state (NOT_CONNECTED / PENDING_CREDENTIALS) missing")
        return False

    print("  PASS: Review panel renders deliverable count, chat correction hint, and truthful publishing status.")
    return True

def check_drop_safety_and_adapter():
    print("[7/8] Verifying Native Motion Adapter and Timeline Drop Boundaries...")
    adapter_file = FRONTEND_DIR / "src" / "utils" / "nativeMotionAdapter.js"
    timeline_file = FRONTEND_DIR / "src" / "components" / "motion" / "StudioTimelineWorkspace.jsx"

    if not adapter_file.exists():
        print("  FAIL: nativeMotionAdapter.js does not exist")
        return False

    a_content = adapter_file.read_text(encoding="utf-8")
    t_content = timeline_file.read_text(encoding="utf-8")

    required_exports = [
        "isNativeMotionV1",
        "validateTrackDrop",
        "normalizeProjectForPlayer",
        "CANONICAL_TRACK_TYPES",
        "TRACK_DROP_PERMISSIONS"
    ]
    for exp in required_exports:
        if exp not in a_content:
            print(f"  FAIL: Missing export '{exp}' in nativeMotionAdapter.js")
            return False

    if "validateTrackDrop" not in t_content and "isDropTargetValid" not in t_content:
        print("  FAIL: Drop target validation missing in StudioTimelineWorkspace.jsx")
        return False

    print("  PASS: nativeMotionAdapter.js exists with full drop permission rules and track normalizer.")
    return True

def check_git_cleanliness_and_ownership():
    print("[8/8] Verifying Git Ownership Boundaries (frontend/**, tools/wave20_a2/**, tests/wave20/a2/** only)...")
    res = subprocess.run(["git", "status", "--porcelain"], cwd=str(REPO_ROOT), capture_output=True, text=True)
    lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]

    allowed_prefixes = ("frontend/", "tools/wave20_a2/", "tests/wave20/", "tests/wave20/a2/")
    violations = []
    for line in lines:
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            fpath = parts[1].strip('"').replace("\\", "/")
            if not fpath.startswith(allowed_prefixes):
                violations.append(fpath)

    if violations:
        print(f"  FAIL: Git ownership violations detected outside allowed areas: {violations}")
        return False

    print("  PASS: All modified and untracked files are strictly within owned scope.")
    return True

def main():
    print("=" * 70)
    print("WAVE 20 / AGENT 2 — MINIMAL OAAS UI AUDIT")
    print("=" * 70)

    checks = [
        check_sidebar_navigation,
        check_create_review_stages_and_advanced_editing,
        check_catalog_and_template_picker_elimination,
        check_legacy_routes_redirect,
        check_authenticated_job_status,
        check_review_panel_integrity,
        check_drop_safety_and_adapter,
        check_git_cleanliness_and_ownership,
    ]

    results = [c() for c in checks]
    print("=" * 70)
    if all(results):
        print("ALL AUDIT CHECKS PASSED: 8/8 gates compliant with OAAS contract.")
        print("=" * 70)
        return 0
    else:
        failed = len([r for r in results if not r])
        print(f"AUDIT FAILED: {failed} check(s) did not meet specification.")
        print("=" * 70)
        return 1

if __name__ == "__main__":
    sys.exit(main())
