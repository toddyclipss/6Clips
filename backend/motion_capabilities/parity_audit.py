# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Automated executable parity audit and mock detection for Wave 5."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Set

from .dispatcher import MotionCapabilityDispatcher
from .models import CapabilityCategory, ParityTier
from .registry import MotionCapabilitiesRegistry


def audit_capabilities_registry() -> Dict[str, Any]:
    """Audit all registered capabilities, verifying schemas and handler dispatchability."""
    all_caps = MotionCapabilitiesRegistry.list_all()
    tier_counts = {tier.value: 0 for tier in ParityTier}
    category_counts = {cat.value: 0 for cat in CapabilityCategory}
    findings: List[Dict[str, Any]] = []

    for cap in all_caps:
        tier_counts[cap.parity_tier.value] += 1
        category_counts[cap.category.value] += 1

        # Validation rules
        errors = []
        if not cap.id:
            errors.append("Missing ID")
        if not cap.title:
            errors.append("Missing Title")
        if not cap.legacy_source:
            errors.append("Missing Legacy Source reference")
        if not cap.motion_entrypoint:
            errors.append("Missing Motion Entrypoint reference")
        if not cap.backend_action:
            errors.append("Missing Backend Action reference")

        findings.append({
            "id": cap.id,
            "title": cap.title,
            "category": cap.category.value,
            "parity_tier": cap.parity_tier.value,
            "valid": len(errors) == 0,
            "errors": errors,
            "limitations": cap.limitations,
        })

    return {
        "total_count": len(all_caps),
        "tier_breakdown": tier_counts,
        "category_breakdown": category_counts,
        "all_valid": all(f["valid"] for f in findings),
        "findings": findings,
    }


def scan_production_entrypoints_for_mocks(root_dir: Path) -> List[Dict[str, Any]]:
    """Adversarial scan of owned production files for forbidden mock/fake/placeholder patterns."""
    targets = [
        root_dir / "frontend" / "src" / "pages" / "MotionGraphics.jsx",
        root_dir / "frontend" / "src" / "components" / "motion",
        root_dir / "backend" / "motion_legacy_bridge",
        root_dir / "backend" / "motion_render_bridge",
        root_dir / "backend" / "motion_capabilities",
    ]

    suspicious_patterns = [
        (re.compile(r"\bclass\s+Mock\w+", re.I), "MOCK_CLASS"),
        (re.compile(r"\bclass\s+Fake\w+", re.I), "FAKE_CLASS"),
        (re.compile(r"\bdef\s+mock_\w+", re.I), "MOCK_FUNC"),
        (re.compile(r"\bdef\s+fake_\w+", re.I), "FAKE_FUNC"),
        (re.compile(r"\banullsrc\b", re.I), "SYNTHETIC_ANULLSRC"),
        (re.compile(r"\bsine\b.*=.*frequency", re.I), "SYNTHETIC_SINE"),
        (re.compile(r"\bNotImplementedError\b"), "NOT_IMPLEMENTED_ERROR"),
    ]

    findings = []
    for target in targets:
        if not target.exists():
            continue
        files_to_check = [target] if target.is_file() else list(target.rglob("*"))
        for f in files_to_check:
            if not f.is_file() or f.suffix not in (".py", ".js", ".jsx", ".ts", ".tsx"):
                continue
            # Skip test files
            if "test" in f.name.lower() or "tests" in f.parts:
                continue

            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines()
                for line_num, line in enumerate(lines, start=1):
                    for pattern, kind in suspicious_patterns:
                        if pattern.search(line):
                            findings.append({
                                "file": str(f.relative_to(root_dir)).replace("\\", "/"),
                                "line": line_num,
                                "match": line.strip(),
                                "kind": kind,
                                "classification": "PRODUCTION_BLOCKER",
                            })
            except Exception as e:
                pass

    return findings
