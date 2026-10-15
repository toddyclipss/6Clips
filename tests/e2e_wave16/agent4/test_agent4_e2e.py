# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""Wave 16 Agent 4 End-to-End Test Suite."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

import pytest
from backend.catalog_runtime.ports.wave16_agent4.adapter import (
    AGENT4_PORTED_IDS,
    get_ports,
    get_preview_html,
    is_port_available,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SHIPPED_ROOT = REPO_ROOT / "backend" / "catalog" / "shipped_blocks"
DONOR_BLOCKS = Path(r"C:\Users\toddy\Desktop\hyperframes\registry\blocks")

def test_e2e_all_ports_metadata_and_integrity():
    """Verify end-to-end descriptor, packaging, and hash integrity for all 14 blocks."""
    ports = get_ports(REPO_ROOT)
    assert len(ports) == 14
    port_ids = {p["id"] for p in ports}
    assert port_ids == set(AGENT4_PORTED_IDS)

    for p in ports:
        bid = p["id"]
        bdir = REPO_ROOT / p["path"]
        assert bdir.exists()

        # Check port-evidence.json matches disk file hashes
        ev_file = bdir / "port-evidence.json"
        assert ev_file.exists()
        evidence = json.loads(ev_file.read_text(encoding="utf-8"))

        html_file = bdir / f"{bid}.html"
        current_html_sha = hashlib.sha256(html_file.read_bytes()).hexdigest()
        assert current_html_sha == evidence["output_html_sha256"]

        # Check donor file was not modified
        donor_html = DONOR_BLOCKS / bid / f"{bid}.html"
        if donor_html.exists():
            donor_sha = hashlib.sha256(donor_html.read_bytes()).hexdigest()
            assert donor_sha == evidence["source_sha256"]

def test_e2e_preview_html_rendering():
    """Verify preview HTML generation with variables across all 14 blocks."""
    for bid in AGENT4_PORTED_IDS:
        html = get_preview_html(
            bid,
            aspect_ratio="16:9",
            variables={"title": "E2E Test Title", "name": "E2E Test Name"},
            repo_root=REPO_ROOT
        )
        assert len(html) > 500
        assert "<meta http-equiv=\"Content-Security-Policy\"" in html
        assert "window.__hyperframes.getVariables" in html
        assert "lib/gsap_offline.js" in html
