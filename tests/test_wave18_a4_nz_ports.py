# SPDX-License-Identifier: AGPL-3.0-only
"""Unit and Integration Tests for Wave 18 Agent 4: N-Z Ports & Adversarial QA."""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
import pytest

from backend.catalog_runtime.ports.wave18_a4.adapter import (
    ALL_AGENT4_PORTED_IDS,
    WAVE16_PORTED_IDS,
    WAVE17_PORTED_IDS,
    WAVE18_PORTED_IDS,
    get_ports,
    get_preview_html,
    is_port_available,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIPPED_ROOT = REPO_ROOT / "backend" / "catalog" / "shipped_blocks"
CENSUS_FILE = REPO_ROOT / "scripts" / "qa_wave18" / "nz_census_and_blockers.json"

def test_wave18_all_7_ported_blocks_exist_and_vendored():
    """Verify that all 7 Wave 18 ported blocks exist on disk with complete vendoring."""
    assert len(WAVE18_PORTED_IDS) == 7
    for bid in WAVE18_PORTED_IDS:
        bdir = SHIPPED_ROOT / bid
        assert bdir.is_dir(), f"Block directory missing: {bdir}"

        html_file = bdir / f"{bid}.html"
        assert html_file.is_file(), f"HTML entrypoint missing: {html_file}"

        lib_file = bdir / "lib" / "gsap_offline.js"
        assert lib_file.is_file(), f"Offline GSAP library missing: {lib_file}"

        assert (bdir / "LICENSE.txt").is_file(), f"LICENSE.txt missing in {bdir}"
        assert (bdir / "NOTICE.txt").is_file(), f"NOTICE.txt missing in {bdir}"
        assert (bdir / "RUNTIME-LICENSE.txt").is_file(), f"RUNTIME-LICENSE.txt missing in {bdir}"
        assert (bdir / ".gitattributes").is_file(), f".gitattributes missing in {bdir}"
        assert (bdir / "port-evidence.json").is_file(), f"port-evidence.json missing in {bdir}"
        assert (bdir / "registry-item.json").is_file(), f"registry-item.json missing in {bdir}"

def test_wave18_port_evidence_hash_integrity():
    """Verify that port-evidence.json contains exact sha256 of the on-disk HTML."""
    for bid in WAVE18_PORTED_IDS:
        bdir = SHIPPED_ROOT / bid
        html_file = bdir / f"{bid}.html"
        ev_file = bdir / "port-evidence.json"

        actual_sha = hashlib.sha256(html_file.read_bytes()).hexdigest()
        evidence = json.loads(ev_file.read_text(encoding="utf-8"))

        assert evidence["schema_version"] == 1
        assert evidence["id"] == bid
        assert evidence["wave"] == 18
        assert evidence["license_status"] == "VERIFIED_PERMISSIVE"
        assert evidence["offline_vendored"] is True
        assert evidence["output_html_sha256"] == actual_sha, (
            f"SHA mismatch for {bid}: expected {evidence['output_html_sha256']}, got {actual_sha}"
        )

def test_wave18_offline_csp_and_no_remote_cdns():
    """Verify zero external network egress and strict CSP in all 7 Wave 18 blocks."""
    for bid in WAVE18_PORTED_IDS:
        html_file = SHIPPED_ROOT / bid / f"{bid}.html"
        text = html_file.read_text(encoding="utf-8")

        # Check for strict CSP
        assert "Content-Security-Policy" in text, f"Missing CSP header in {bid}"
        assert "default-src 'none'" in text, f"CSP default-src 'none' missing in {bid}"

        # Check no active remote script or link tags
        remote_scripts = re.findall(r'<script[^>]+src=["\'](https?://[^"\']+)["\']', text, flags=re.IGNORECASE)
        assert len(remote_scripts) == 0, f"Found remote scripts in {bid}: {remote_scripts}"

        remote_links = re.findall(r'<link[^>]+href=["\'](https?://[^"\']+)["\']', text, flags=re.IGNORECASE)
        assert len(remote_links) == 0, f"Found remote links in {bid}: {remote_links}"

def test_wave18_runtime_adapter_exports_all_39_blocks():
    """Verify get_ports exports 39 N-Z blocks (14 Wave 16 + 18 Wave 17 + 7 Wave 18)."""
    assert len(ALL_AGENT4_PORTED_IDS) == 39
    ports = get_ports(REPO_ROOT)
    exported_ids = {p["id"] for p in ports}

    for bid in ALL_AGENT4_PORTED_IDS:
        assert bid in exported_ids, f"Port {bid} not exported by adapter"
        assert is_port_available(bid) is True

    assert is_port_available("unknown-block-xyz") is False

def test_wave18_runtime_adapter_preview_html_generation():
    """Verify get_preview_html generates sandboxed HTML with variable bindings and 9:16 / 16:9 scaling."""
    # Test 16:9
    html_16_9 = get_preview_html("orbit-card", aspect_ratio="16:9", variables={"feature1Title": "VAL1"}, repo_root=REPO_ROOT)
    assert 'Content-Security-Policy' in html_16_9
    assert 'window.__hyperframes.getVariables' in html_16_9
    assert 'VAL1' in html_16_9
    assert 'width: 1920px' in html_16_9

    # Test 9:16
    html_9_16 = get_preview_html("orbit-card", aspect_ratio="9:16", variables={"feature1Title": "VAL2"}, repo_root=REPO_ROOT)
    assert 'VAL2' in html_9_16
    assert 'width: 1080px' in html_9_16

def test_wave18_census_ledger_integrity():
    """Verify nz_census_and_blockers.json structure, total 75 N-Z blocks, 52 shipped, 23 blocked."""
    assert CENSUS_FILE.is_file(), f"Census file missing: {CENSUS_FILE}"
    data = json.loads(CENSUS_FILE.read_text(encoding="utf-8"))

    assert data["schema_version"] == 1
    assert data["wave"] == 18
    assert data["agent"] == "agent-4"

    summary = data["summary"]
    assert summary["total_nz_blocks"] == 75
    assert summary["total_shipped"] == 52
    assert summary["total_blocked"] == 23
    assert summary["shipped_pre_wave16"] == 13
    assert summary["shipped_wave16"] == 14
    assert summary["shipped_wave17"] == 18
    assert summary["shipped_wave18"] == 7

    assert summary["blocked_trademark"] == 11
    assert summary["blocked_gis_maps"] == 5
    assert summary["blocked_3d_engines"] == 7

    blocks = data["blocks"]
    assert len(blocks) == 75

    shipped_blocks = [b for b in blocks if b["status"] == "SHIPPED"]
    assert len(shipped_blocks) == 52

    blocked_blocks = [b for b in blocks if b["status"] == "BLOCKED"]
    assert len(blocked_blocks) == 23

    # Ensure blocked blocks have clear reasons and families
    for b in blocked_blocks:
        assert b["blocker_family"] in {"TRADEMARK_AND_PLATFORM_ASSETS", "EXTERNAL_GIS_DATASETS", "UNVENDORED_3D_ENGINES"}
        assert b["rights_status"] in {"TRADEMARK_PROTECTED", "EXTERNAL_NETWORK_DEPENDENT", "UNVENDORED_UPSTREAM_ENGINE"}
        assert len(b["blocker_reason"]) > 20
        # Blocked blocks must not exist as fake files in shipped_blocks
        assert not (SHIPPED_ROOT / b["slug"]).exists(), f"Blocked block {b['slug']} should not be in shipped_blocks"
