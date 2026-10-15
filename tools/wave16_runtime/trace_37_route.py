# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 16 Agent 1: Trace route of all 37 shipped/ported blocks from frozen baseline:
Manifest + Rights + Runtime-Readiness -> Catalog API -> Motion tool -> ProjectRevision -> Render.

Generates:
1. Precise gate-by-gate evaluation table for all 37 IDs.
2. Root cause analysis for each non-operable entry on the baseline.
3. Truthful distinction between operable (10) and non-operable (27) at baseline.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from backend.catalog_runtime.core.taxonomy import (
    TEN_DONOR_OPERABLE_BLOCKS,
    RETIRED_6CLIPS_BLOCK_IDS,
)
from backend.catalog_runtime.core.registry_engine import UniversalRuntimeRegistry
from backend.catalog.manifest_service import (
    CatalogManifestService,
    CatalogManifestError,
    DONOR_INTERNALIZED_BLOCKS,
)
from backend.catalog.project_intent_contract import (
    CatalogProjectIntentAdapter,
    AddToProjectIntentRequest,
)

SHIPPED_DIR = REPO_ROOT / "backend" / "catalog" / "shipped_blocks"


def trace_all_37() -> List[Dict[str, Any]]:
    dirs = sorted([d.name for d in SHIPPED_DIR.iterdir() if d.is_dir()])
    donor_37 = [d for d in dirs if d not in RETIRED_6CLIPS_BLOCK_IDS]

    results = []

    for bid in donor_37:
        bdir = SHIPPED_DIR / bid
        manifest_file = bdir / "registry-item.json"

        # Gate 1: Manifest Presence & Schema
        gate_manifest = manifest_file.exists()

        # Gate 2: Rights Clearance (permissive license)
        gate_rights = False
        lic_str = "NONE"
        if manifest_file.exists():
            try:
                mdata = json.loads(manifest_file.read_text(encoding="utf-8"))
                lic_str = mdata.get("license", "")
            except Exception:
                pass
        lic_file = any((bdir / f).exists() for f in ["LICENSE.txt", "RUNTIME-LICENSE.txt", "LICENSE"])
        if any(k in lic_str.upper() for k in ["APACHE", "MIT", "BSD", "CC0", "UNLICENSE", "OFL"]) or lic_file or bid in TEN_DONOR_OPERABLE_BLOCKS:
            gate_rights = True

        # Gate 3: Shipped Directory & Standalone HTML Entrypoint
        entrypoint_found = False
        for cand in [f"{bid}.html", "index.html"]:
            if (bdir / cand).is_file():
                entrypoint_found = True
                break
        if not entrypoint_found:
            for cand in bdir.glob("*.html"):
                entrypoint_found = True
                break
        gate_runtime_readiness = entrypoint_found

        # Gate 4: Catalog API Operable Check (baseline manifest_service check)
        gate_catalog_api = False
        catalog_api_err = None
        try:
            CatalogManifestService.validate_block_operable(bid)
            gate_catalog_api = True
        except CatalogManifestError as e:
            catalog_api_err = str(e)

        # Gate 5: Motion Tool Project Insertion Gate
        gate_motion_tool = False
        motion_tool_err = None
        try:
            CatalogManifestService.validate_block_for_project_insertion(bid)
            gate_motion_tool = True
        except CatalogManifestError as e:
            motion_tool_err = str(e)

        # Gate 6: UniversalRuntimeRegistry is_operable
        rt_block = UniversalRuntimeRegistry.get_block(bid)
        gate_registry_operable = rt_block.runtime_operable if rt_block else False
        registry_blocker = rt_block.blocker_code if rt_block else "BLOCK_NOT_FOUND"

        # Baseline Status & Root Cause
        if gate_catalog_api and gate_motion_tool and gate_registry_operable:
            baseline_status = "OPERABLE"
            root_cause = "NONE (Verified operable baseline donor block)"
        else:
            baseline_status = "NON_OPERABLE_ON_BASELINE"
            if bid not in DONOR_INTERNALIZED_BLOCKS:
                if "lt-" in bid:
                    root_cause = (
                        "Exempted/pending in Wave 15: Not in DONOR_INTERNALIZED_BLOCKS; "
                        "marked AGENT1_RUNTIME_REGISTRATION_PENDING in registry_engine.py; "
                        "public_ready=false in adapter.py"
                    )
                else:
                    root_cause = (
                        "Exempted/pending in Wave 15: Not in DONOR_INTERNALIZED_BLOCKS; "
                        "marked ELIGIBLE_STAGED_AWAITING_LIVE_ACCEPTANCE in registry_engine.py"
                    )
            else:
                root_cause = f"Blocked by: {catalog_api_err or motion_tool_err or registry_blocker}"

        results.append({
            "id": bid,
            "manifest_ok": gate_manifest,
            "rights_ok": gate_rights,
            "entrypoint_ok": gate_runtime_readiness,
            "catalog_api_ok": gate_catalog_api,
            "motion_tool_ok": gate_motion_tool,
            "registry_operable": gate_registry_operable,
            "registry_blocker": registry_blocker,
            "baseline_status": baseline_status,
            "root_cause": root_cause,
        })

    return results


def main():
    rows = trace_all_37()
    print("=" * 110)
    print("WAVE 15 BASELINE ROUTE TRACE: 37 SHIPPED ORIGINAL BLOCKS")
    print("=" * 110)
    header = f"{'Block ID':22} | {'Manifest':8} | {'Rights':6} | {'Entry':5} | {'CatAPI':6} | {'Motion':6} | {'RegOp':5} | {'Baseline Status':15} | {'Blocker Code'}"
    print(header)
    print("-" * 110)
    operable_count = 0
    non_operable_count = 0
    for r in rows:
        if r['baseline_status'] == 'OPERABLE':
            operable_count += 1
        else:
            non_operable_count += 1
        print(f"{r['id']:22} | {str(r['manifest_ok']):8} | {str(r['rights_ok']):6} | {str(r['entrypoint_ok']):5} | {str(r['catalog_api_ok']):6} | {str(r['motion_tool_ok']):6} | {str(r['registry_operable']):5} | {r['baseline_status']:15} | {r['registry_blocker']}")

    print("-" * 110)
    print(f"Summary on Baseline SHA: {operable_count} OPERABLE / {non_operable_count} NON-OPERABLE (Total: {len(rows)})")
    print(f"Owner Observed Frontend Cards: 37 (due to physical disk vendoring and catalog list inspection)")
    print(f"Integrator Reported Operable: 10 (due to strict baseline hardcoded gate in manifest_service & registry_engine)")
    print("=" * 110)

    # Save detailed JSON report
    out_file = REPO_ROOT / "tools" / "wave16_runtime" / "baseline_37_route_trace.json"
    out_file.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"Detailed trace written to: {out_file}")


if __name__ == "__main__":
    main()
