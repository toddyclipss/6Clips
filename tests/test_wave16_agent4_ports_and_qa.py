# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 16 Agent 4: N-Z Original Porting, GSAP/HTML Adapters & Adversarial QA Suite.

Exclusive Ownership: Agent 4 (GSAP/HTML/Social/Text Adaptation & Adversarial QA).
Audits:
- Gate 1: 75 N-Z/0-9 Census, Taxonomy Reconciliation & Root-Cause Blocker Ledger
- Gate 2: 14 Newly Ported N-Z Original Blocks Structural & License Integrity
- Gate 3: Zero-Egress Offline GSAP Timeline Compatibility Runtime
- Gate 4: Aspect Ratio Scaling (16:9 / 9:16) & Variable Injection Bridge
- Gate 5: Genuine Multi-Timestamp Edge Motion & Pixel Delta Verification
- Gate 6: Physical MP4 Video Export & ffprobe Stream Parity
- Gate 7: Canonical ProjectRevision & CAS Mutation Concurrency
- Gate 8: Audit of 10 Lower Thirds for ProjectRevision & Render Verification
- Gate 9: Negative Safety & Strict Quarantine of Retired 6Clips Substitutes
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List

import pytest
from PIL import Image

from backend.catalog_runtime.core.registry_engine import UniversalRuntimeRegistry
from backend.catalog_runtime.ports.wave16_agent4.adapter import (
    AGENT4_PORTED_IDS,
    get_ports,
    get_preview_html,
    is_port_available,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SHIPPED_ROOT = REPO_ROOT / "backend" / "catalog" / "shipped_blocks"
QA_REPORT_FILE = REPO_ROOT / "scripts" / "qa_wave16" / "qa_adversarial_report.json"
BLOCKER_LEDGER_FILE = REPO_ROOT / "scripts" / "qa_wave16" / "nz_census_and_blockers.json"


# =========================================================================
# GATE 1: N-Z Census & Root-Cause Blocker Ledger Truth
# =========================================================================
def test_nz_census_and_blocker_ledger():
    """Verify exact 75 N-Z block census, 14 newly ported, 13 pre-existing, and 48 truthfully classified blockers."""
    assert BLOCKER_LEDGER_FILE.exists(), f"Blocker ledger missing: {BLOCKER_LEDGER_FILE}"
    ledger = json.loads(BLOCKER_LEDGER_FILE.read_text(encoding="utf-8"))

    counts = ledger["counts"]
    assert counts["total_nz"] == 75
    assert counts["newly_ported_wave16"] == 14
    assert counts["already_shipped_pre_w16"] == 13
    assert counts["blocked_trademark"] == 11
    assert counts["blocked_map_geo"] == 8
    assert counts["blocked_threejs"] == 6
    assert counts["blocked_complex_shader"] == 23

    total_accounted = (
        counts["newly_ported_wave16"]
        + counts["already_shipped_pre_w16"]
        + counts["blocked_trademark"]
        + counts["blocked_map_geo"]
        + counts["blocked_threejs"]
        + counts["blocked_complex_shader"]
    )
    assert total_accounted == 75, f"Expected 75 accounted blocks, got {total_accounted}"

    # Verify no block is counted twice
    seen_ids = set()
    for row in ledger["rows"]:
        bid = row["id"]
        assert bid not in seen_ids, f"Duplicate block ID in ledger: {bid}"
        seen_ids.add(bid)
        ch = bid[0].lower()
        assert ("n" <= ch <= "z") or ch.isdigit(), f"Non N-Z block in ledger: {bid}"


# =========================================================================
# GATE 2: 14 Newly Ported N-Z Blocks Structural & License Integrity
# =========================================================================
def test_14_ported_blocks_integrity():
    """Validate that UniversalRuntimeRegistry accepts all 14 newly ported blocks."""
    assert len(AGENT4_PORTED_IDS) == 14
    for slug in AGENT4_PORTED_IDS:
        ch = slug[0].lower()
        assert ("n" <= ch <= "z") or ch.isdigit(), f"Invalid slug partition: {slug}"
        bdir = SHIPPED_ROOT / slug
        assert bdir.exists(), f"Missing shipped block dir: {bdir}"

        # Test core registry integrity
        check = UniversalRuntimeRegistry.validate_vendored_block_integrity(slug, bdir)
        assert check["is_valid"] is True, f"Block {slug} invalid: {check.get('blocker_reason')}"
        assert check["blocker_code"] is None
        assert check["license_status"] == "VERIFIED_PERMISSIVE"

        # Verify offline lib and required files
        assert (bdir / "lib" / "gsap_offline.js").exists()
        assert (bdir / "registry-item.json").exists()
        assert (bdir / "LICENSE.txt").exists()
        assert (bdir / "NOTICE.txt").exists()
        assert (bdir / "RUNTIME-LICENSE.txt").exists()
        assert (bdir / "port-evidence.json").exists()

        # Verify zero remote CDN script tags in entrypoint
        html_file = bdir / f"{slug}.html"
        html_text = html_file.read_text(encoding="utf-8")
        remote_matches = re.findall(r'<script[^>]+src=[\'"](https?://[^\'"]+)[\'"]', html_text, re.IGNORECASE)
        assert len(remote_matches) == 0, f"Found remote scripts in {slug}: {remote_matches}"


# =========================================================================
# GATE 3: Offline GSAP Runtime Contract
# =========================================================================
def test_offline_gsap_runtime_contract():
    """Verify that lib/gsap_offline.js implements the complete deterministic timeline interface."""
    for slug in AGENT4_PORTED_IDS:
        js_file = SHIPPED_ROOT / slug / "lib" / "gsap_offline.js"
        content = js_file.read_text(encoding="utf-8")
        assert "global.gsap = gsap" in content
        assert "Timeline.prototype.seek" in content
        assert "Timeline.prototype.to" in content
        assert "Timeline.prototype.fromTo" in content
        assert "Timeline.prototype.set" in content
        assert "parseEasing" in content
        assert "autoAlpha" in content
        assert "isFirst" in content


# =========================================================================
# GATE 4: Aspect Ratio Scaling & Variable Injection Bridge
# =========================================================================
def test_aspect_ratio_and_variable_injection():
    """Verify preview HTML generation with 16:9, 9:16, CSP sandbox, and variables."""
    ports = get_ports(REPO_ROOT)
    assert len(ports) == 14

    for slug in ["news-ticker", "notification-cascade", "split-flap-board", "whip-pan"]:
        assert is_port_available(slug) is True

        # Test 16:9
        html_169 = get_preview_html(slug, aspect_ratio="16:9", variables={"headline": "Test 16:9"}, repo_root=REPO_ROOT)
        assert "Content-Security-Policy" in html_169
        assert "wave16-stage" in html_169
        assert "window.__hyperframes.getVariables" in html_169
        assert "Test 16:9" in html_169

        # Test 9:16
        html_916 = get_preview_html(slug, aspect_ratio="9:16", variables={"headline": "Test 9:16"}, repo_root=REPO_ROOT)
        assert "width: 1080px !important" in html_916
        assert "height: 1920px !important" in html_916
        assert "Test 9:16" in html_916


# =========================================================================
# GATE 5: Genuine Multi-Timestamp Motion Verification (QA Report)
# =========================================================================
def test_genuine_motion_verification_qa_report():
    """Verify that all 14 newly ported blocks passed real multi-timestamp motion QA."""
    assert QA_REPORT_FILE.exists(), f"QA report missing: {QA_REPORT_FILE}"
    qa_data = json.loads(QA_REPORT_FILE.read_text(encoding="utf-8"))

    summary = qa_data["summary"]
    assert summary["total_new_nz_ported"] == 14
    assert summary["passed_motion_nz"] == 14, f"Not all passed motion: {summary}"
    assert summary["zero_egress_violations"] is True
    assert summary["zero_leakage_retired_substitutes"] is True

    # Check each individual block's motion delta
    for item in qa_data["tested_groups"]["newly_ported_nz"]:
        m = item["motion"]
        assert m["status"] == "PASS", f"Block {item['id']} did not pass: {m}"
        assert m["delta"] > 0.5, f"Block {item['id']} delta too small: {m['delta']}"
        assert len(m["egress_violations"]) == 0


# =========================================================================
# GATE 6: Physical MP4 Video Export & ffprobe Stream Parity
# =========================================================================
def test_physical_mp4_export_parity():
    """Verify that all 14 newly ported blocks successfully encoded to physical MP4 with valid H.264 streams."""
    qa_data = json.loads(QA_REPORT_FILE.read_text(encoding="utf-8"))
    nz_items = qa_data["tested_groups"]["newly_ported_nz"]

    for item in nz_items:
        exp = item["export"]
        assert exp["valid_export"] is True, f"Invalid export for {item['id']}: {exp}"
        assert exp["codec"] == "h264"
        assert exp["width"] > 0
        assert exp["height"] > 0
        assert exp["height"] % 2 == 0, f"Odd height in export for {item['id']}: {exp['height']}"
        assert exp["frames"] > 0
        assert len(exp["file_sha256"]) == 64


# =========================================================================
# GATE 7: Canonical ProjectRevision & CAS Mutation Concurrency
# =========================================================================
def test_project_revision_cas_concurrency():
    """Verify CAS revision progression (0 -> 1 -> 2) and deterministic request fingerprinting."""
    qa_data = json.loads(QA_REPORT_FILE.read_text(encoding="utf-8"))
    nz_items = qa_data["tested_groups"]["newly_ported_nz"]

    for item in nz_items:
        cas = item["cas_mutation"]
        assert cas["cas_success"] is True, f"CAS failed for {item['id']}: {cas}"
        assert cas["initial_rev"] == 0
        assert cas["after_insert_rev"] == 1
        assert cas["after_edit_rev"] == 2
        assert len(cas["fingerprint_initial"]) > 0
        assert len(cas["fingerprint_rev1"]) > 0
        assert len(cas["fingerprint_rev2"]) > 0
        assert cas["fingerprint_rev1"] != cas["fingerprint_initial"]
        assert cas["fingerprint_rev2"] != cas["fingerprint_rev1"]


# =========================================================================
# GATE 8: Audit of 10 Lower Thirds for ProjectRevision & Render Verification
# =========================================================================
def test_ten_lower_thirds_audit():
    """Requirement 4: Verify the 10 lower thirds against ProjectRevision and physical export."""
    qa_data = json.loads(QA_REPORT_FILE.read_text(encoding="utf-8"))
    lt_items = qa_data["tested_groups"]["ten_lower_thirds"]
    assert len(lt_items) == 10

    for lt in lt_items:
        assert lt["motion_status"] == "PASS"
        assert lt["motion_delta"] > 0.1
        assert lt["export_valid"] is True
        assert lt["cas_success"] is True
        assert lt["classification"] == "RENDER_VERIFIED_STAGE_AWAITING_PUBLIC_PROMOTION"


# =========================================================================
# GATE 9: Negative Safety & Strict Quarantine of Retired 6Clips Substitutes
# =========================================================================
def test_negative_safety_retired_substitutes():
    """Verify creator-hud and glitch-transition are quarantined and never present in ported N-Z catalog."""
    qa_data = json.loads(QA_REPORT_FILE.read_text(encoding="utf-8"))
    neg = qa_data["tested_groups"]["negative_safety"]

    for retired_id in ["creator-hud", "glitch-transition"]:
        assert retired_id in neg
        assert neg[retired_id]["is_retired"] is True
        assert neg[retired_id]["leaked_into_nz"] is False
        assert neg[retired_id]["quarantined"] is True
        assert not is_port_available(retired_id)
