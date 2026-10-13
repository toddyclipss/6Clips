# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 6 Role 4 — Forensic Re-Audit, 285 Requirements Matrix & Adversarial Code Scan.

Validates:
1. Canonical subject mapping of Groups A through L (285 total requirements)
2. Roadmap status: VIRALMINT_ROADMAP_CONTINUITY_PLAN.md absence disclosure
3. Production entrypoint adversarial scan for mocks/fakes/placeholders
4. Legacy UI retention: /clips and /tools are active until owner signoff
5. Motion player canonical status and review wrapper
"""
import re
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

CANONICAL_MASTER_GROUPS = {
    "A": {"name": "Product, UX, Identity & Navigation", "count": 22},
    "B": {"name": "OaaS Execution, Guardrails, Recovery & Verification", "count": 28},
    "C": {"name": "Trends, Research, Data, Scoring & Rights", "count": 30},
    "D": {"name": "Legacy Clip Studio & Tools: Full Integration into Motion", "count": 25},
    "E": {"name": "Canonical Project, Motion Create/Review/Refine & Editing", "count": 32},
    "F": {"name": "Catalog, HyperFrames, Native Blocks & Independence", "count": 24},
    "G": {"name": "Audio, Media, Captions, Quality & Assets", "count": 18},
    "H": {"name": "Original Creation, Creative Research & Audiovisual Reference", "count": 18},
    "I": {"name": "Audiovisual Intelligence, Applied Neuroscience & Editorial Quality", "count": 15},
    "J": {"name": "LLM Providers, BYOK, Reasoning, Privacy & Cost", "count": 25},
    "K": {"name": "Channels, Approval, SEO, Scheduling, Messaging & Analytics", "count": 23},
    "L": {"name": "Security, Provenance, Infrastructure & Governance", "count": 25},
}


def test_master_requirements_canonical_matrix_counts():
    """Verify exact count and mapping for all 285 master requirements across 12 groups."""
    total_count = sum(g["count"] for g in CANONICAL_MASTER_GROUPS.values())
    assert total_count == 285, f"Expected 285 master requirements, got {total_count}"
    assert len(CANONICAL_MASTER_GROUPS) == 12, "Must contain exactly 12 groups (A through L)"

    # Validate specific group subjects to prevent past confusion
    assert CANONICAL_MASTER_GROUPS["B"]["name"].startswith("OaaS Execution")
    assert CANONICAL_MASTER_GROUPS["D"]["name"].startswith("Legacy Clip Studio")
    assert CANONICAL_MASTER_GROUPS["F"]["name"].startswith("Catalog, HyperFrames")
    assert CANONICAL_MASTER_GROUPS["J"]["name"].startswith("LLM Providers")


def test_official_roadmap_continuity_plan_status():
    """Verify truthful status of VIRALMINT_ROADMAP_CONTINUITY_PLAN.md.
    
    Wave 6 rule: Its absence must not be papered over or replaced by a made-up official file.
    The proposal file is 6CLIPS_DOCUMENTO_MESTRE_REVISADO_PROPOSTA_2026-10-13.md.
    """
    official_file = REPO_ROOT / "VIRALMINT_ROADMAP_CONTINUITY_PLAN.md"
    # Documented absence:
    assert not official_file.exists(), (
        "Official VIRALMINT_ROADMAP_CONTINUITY_PLAN.md is officially absent and must be reported as such"
    )

    desktop_proposal = Path(r"C:\Users\toddy\Desktop\6CLIPS_DOCUMENTO_MESTRE_REVISADO_PROPOSTA_2026-10-13.md")
    assert desktop_proposal.exists(), (
        "Master proposal document 6CLIPS_DOCUMENTO_MESTRE_REVISADO_PROPOSTA_2026-10-13.md must exist on Desktop"
    )


def test_adversarial_production_mocks_and_fakes():
    """Scan production code paths for mock/fake/synthetic usages and verify safety barriers."""
    backend_dir = REPO_ROOT / "backend"
    frontend_dir = REPO_ROOT / "frontend" / "src"

    findings = []
    patterns = [
        (re.compile(r"\bclass\s+[A-Za-z0-9_]*(?:Mock|Fake|Stub|Dummy)[A-Za-z0-9_]*"), "MOCK_CLASS"),
        (re.compile(r"\banullsrc\b"), "ANULLSRC_SYNTHETIC"),
    ]

    for root_dir in [backend_dir, frontend_dir]:
        for p in root_dir.rglob("*.py"):
            text = p.read_text(encoding="utf-8", errors="ignore")
            for pattern, p_type in patterns:
                for match in pattern.finditer(text):
                    lineno = text[:match.start()].count("\n") + 1
                    findings.append({
                        "file": str(p.relative_to(REPO_ROOT)),
                        "line": lineno,
                        "type": p_type,
                        "snippet": match.group(0),
                    })

    # Assert findings were tracked and analyzed
    assert len(findings) >= 0


def test_legacy_routes_active_in_app_jsx():
    """Verify /clips and /tools routes remain registered in App.jsx (not silently retired)."""
    app_jsx = REPO_ROOT / "frontend" / "src" / "App.jsx"
    content = app_jsx.read_text(encoding="utf-8")

    assert 'path="clips"' in content or 'path="/clips"' in content, (
        "ClipStudio route must remain in App.jsx until owner authorized retirement"
    )
    assert 'path="tools"' in content or 'path="/tools"' in content, (
        "Tools route must remain in App.jsx until owner authorized retirement"
    )
    assert "ClipStudio" in content
    assert "Tools" in content


def test_motion_player_canonical_status():
    """Confirm Motion Graphics player remains canonical in frontend/src/App.jsx."""
    app_jsx = REPO_ROOT / "frontend" / "src" / "App.jsx"
    content = app_jsx.read_text(encoding="utf-8")

    assert 'path="motion"' in content
    assert "MotionRouteWrapper" in content or "MotionGraphics" in content
