# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Unit and Contract Tests for Wave 18 Agent 3:
Original HyperFrames A-M Real Preview and Export Fidelity.
"""
import json
from pathlib import Path
import re
import pytest

from backend.catalog_runtime.ports.wave18_a3.adapter import (
    AM_VERIFIED_100_BLOCKS,
    AM_BLOCKED_DEPENDENCY_12_BLOCKS,
    AM_BLOCKED_RIGHTS_9_BLOCKS,
    AM_RETIRED_2_BLOCKS,
    ALL_AM_121_DONOR_BLOCKS,
    Agent3PortAdapter,
    agent3_port_adapter,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIPPED_BLOCKS = REPO_ROOT / "backend" / "catalog" / "shipped_blocks"
DONOR_BLOCKS = Path(r"C:\Users\toddy\Desktop\hyperframes\registry\blocks")


def test_am_canonical_121_census():
    """Verify exact count of 121 original A-M donor identities."""
    assert len(ALL_AM_121_DONOR_BLOCKS) == 121
    assert len(AM_VERIFIED_100_BLOCKS) == 100
    assert len(AM_BLOCKED_DEPENDENCY_12_BLOCKS) == 12
    assert len(AM_BLOCKED_RIGHTS_9_BLOCKS) == 9
    assert len(AM_RETIRED_2_BLOCKS) == 2

    # Check partition disjointness
    s_ver = set(AM_VERIFIED_100_BLOCKS)
    s_dep = set(AM_BLOCKED_DEPENDENCY_12_BLOCKS.keys())
    s_rig = set(AM_BLOCKED_RIGHTS_9_BLOCKS.keys())
    s_ret = set(AM_RETIRED_2_BLOCKS)

    assert s_ver.isdisjoint(s_dep), f"Overlap between verified and dependency: {s_ver & s_dep}"
    assert s_ver.isdisjoint(s_rig), f"Overlap between verified and rights: {s_ver & s_rig}"
    assert s_dep.isdisjoint(s_rig), f"Overlap between dependency and rights: {s_dep & s_rig}"
    assert s_ret.isdisjoint(ALL_AM_121_DONOR_BLOCKS), f"Retired substitute leaked into donor originals: {s_ret & set(ALL_AM_121_DONOR_BLOCKS)}"

    # Check donor blocks directory presence
    if DONOR_BLOCKS.exists():
        donor_dirs = [d.name for d in DONOR_BLOCKS.iterdir() if d.is_dir()]
        donor_am = [b for b in donor_dirs if "a" <= b[0].lower() <= "m"]
        assert len(donor_am) == 121
        for b in ALL_AM_121_DONOR_BLOCKS:
            assert b in donor_am, f"Original ID {b} not found in upstream donor registry"


def test_adapter_get_ports():
    """Verify adapter exposes all 100 verified original blocks."""
    ports = agent3_port_adapter.get_ports()
    assert len(ports) == 100
    for p in ports:
        assert p["id"] in AM_VERIFIED_100_BLOCKS
        assert p["rights_status"] == "VERIFIED_PERMISSIVE"
        assert p["runtime_status"] == "USER_PREVIEW_VERIFIED"
        assert p["is_operational"] is True
        assert "16:9" in p["supported_aspects"]
        assert "9:16" in p["supported_aspects"]
        assert p["duration"] > 0


def test_adapter_get_blocked_backlog():
    """Verify adapter exposes all 21 blocked originals with valid obstacle descriptions."""
    backlog = agent3_port_adapter.get_blocked_backlog()
    assert len(backlog) == 21
    for bid, data in backlog.items():
        assert data["rights_cleared"] is False
        assert data["status"] in ("BLOCKED_RIGHTS", "BLOCKED_DEPENDENCY")
        assert len(data["reason"]) > 10
        assert data["donor_source_path"].startswith("registry/blocks/")


def test_preview_html_generation_and_csp():
    """Verify preview HTML contains strict airgapped zero-egress CSP and responsive stage."""
    # Test 16:9
    html_16_9 = agent3_port_adapter.get_preview_html("aurora", aspect_ratio="16:9")
    assert "Content-Security-Policy" in html_16_9
    assert "default-src 'none'" in html_16_9
    assert "connect-src 'none'" in html_16_9
    assert "wave18-a3-stage" in html_16_9

    # Test 9:16
    html_9_16 = agent3_port_adapter.get_preview_html("data-chart", aspect_ratio="9:16", variables={"title": "Test Q4"})
    assert "Content-Security-Policy" in html_9_16
    assert "window.__hyperframes" in html_9_16
    assert "Test Q4" in html_9_16


def test_preview_html_quarantine_rejections():
    """Verify quarantined or retired blocks cannot be served by preview HTML."""
    # Retired substitute
    with pytest.raises(ValueError, match="retired"):
        agent3_port_adapter.get_preview_html("creator-hud")

    with pytest.raises(ValueError, match="retired"):
        agent3_port_adapter.get_preview_html("glitch-transition")

    # Rights blocked
    with pytest.raises(PermissionError, match="quarantined"):
        agent3_port_adapter.get_preview_html("apple-money-count")

    # Dependency blocked
    with pytest.raises(PermissionError, match="quarantined"):
        agent3_port_adapter.get_preview_html("glass-shard-title")


def test_project_insertion_edit_and_reopen():
    """Verify versioned project revision CAS lifecycle."""
    init_proj = {
        "id": "proj_unit_test",
        "name": "Unit Test Project",
        "revision": 0,
        "document": {"timeline": {"tracks": []}},
    }

    # Insert block
    v1 = agent3_port_adapter.insert_into_project(init_proj, "bar-chart-race", start_time=1.0)
    assert v1["revision"] == 1
    tracks = v1["document"]["timeline"]["tracks"]
    assert len(tracks) == 1
    items = tracks[0]["items"]
    assert len(items) == 1
    item = items[0]
    assert item["block_id"] == "bar-chart-race"
    assert item["start"] == 1.0

    # Edit block
    v2 = agent3_port_adapter.edit_project_block(v1, item["id"], {"chart_title": "Top Cryptos"})
    assert v2["revision"] == 2
    edited_item = v2["document"]["timeline"]["tracks"][0]["items"][0]
    assert edited_item["variables"]["chart_title"] == "Top Cryptos"

    # Reopen
    reopened = agent3_port_adapter.reopen_project(v2)
    assert reopened["status"] == "VALID"
    assert reopened["revision"] == 2
    assert reopened["total_blocks"] == 1


def test_shipped_blocks_zero_unvendored_cdn():
    """Verify that all 100 verified shipped blocks have zero external CDN imports."""
    cdn_pattern = r"https?://(cdn\.jsdelivr\.net|cdnjs\.cloudflare\.com|unpkg\.com|fonts\.googleapis\.com)"
    for slug in AM_VERIFIED_100_BLOCKS:
        bdir = SHIPPED_BLOCKS / slug
        html_f = bdir / f"{slug}.html"
        if not html_f.exists():
            html_f = bdir / "index.html"
        assert html_f.exists(), f"Missing HTML file for {slug}"
        content = html_f.read_text(encoding="utf-8")
        matches = list(set([m.group(0) for m in re.finditer(cdn_pattern, content)]))
        assert not matches, f"Block '{slug}' contains unvendored remote CDN: {matches}"
