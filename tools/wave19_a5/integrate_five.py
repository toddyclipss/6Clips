# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
r"""
Wave 19 Five-Branch Integration Verification & Manifest Generator
Author: Agent 5 (Original Tools Forensic Parity & Five-Branch Integrator)
"""

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

AGENT_TIPS = {
    "agent1": {
        "name": "Agent 1 - Chat-First OAAS Orchestration & Agent Ingestion",
        "branch": "wave19/01-chat-first-outcomes",
        "expected_tip": "dfc97149ad5c7afaff1e8895df07985c63af692f",
        "ready_file": "tools/wave19_a1/READY.json"
    },
    "agent2": {
        "name": "Agent 2 - Clean Native Motion UI & Ephemeral Hover Stage",
        "branch": "wave19/02-clean-native-motion-ui",
        "expected_tip": "bf39ff786f84e3e13b6b8e09301083e12bf6d6b5",
        "ready_file": "tools/wave19_a2/READY.json"
    },
    "agent3": {
        "name": "Agent 3 - Legacy Clip Studio Native Parity in Motion",
        "branch": "wave19/03-legacy-clipstudio-native",
        "expected_tip": "0526f70443eeac388a6356e1e12898674eb32690",
        "ready_file": "tools/wave19_a3/READY.json"
    },
    "agent4": {
        "name": "Agent 4 - HyperFrames True Preview, Source Categories & Anti-Fake QA",
        "branch": "wave19/04-donor-preview-categories-qa",
        "expected_tip": "07dbdc19c72d4afea0b364cba84791265917e805",
        "ready_file": "tools/wave19_a4/READY.json"
    },
    "agent5": {
        "name": "Agent 5 - Original 21 Tools Forensic Parity & Five-Branch Integrator",
        "branch": "wave19/05-native-original-tools-integrator",
        "expected_tip": "d4822950ab158a8f99799d1e444607a278e6ce1d",
        "ready_file": "tools/wave19_a5/READY.json"
    }
}

def verify_ancestor(tip_sha: str) -> bool:
    try:
        res = subprocess.run(
            ["git", "merge-base", "--is-ancestor", tip_sha, "HEAD"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True
        )
        return res.returncode == 0
    except subprocess.CalledProcessError:
        return False

def verify_integration():
    print("=== Wave 19 Five-Branch Integration Audit ===")
    print(f"Repository Root: {REPO_ROOT}")

    # 1. Check HEAD SHA
    head_proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT), capture_output=True, text=True, check=True)
    head_sha = head_proc.stdout.strip()
    print(f"Integration HEAD SHA: {head_sha}")

    # 2. Check Ancestry for all 5 tips
    ancestry_results = {}
    all_ancestors = True
    for key, info in AGENT_TIPS.items():
        is_anc = verify_ancestor(info["expected_tip"])
        ready_path = REPO_ROOT / info["ready_file"]
        ancestry_results[key] = {
            "name": info["name"],
            "tip_sha": info["expected_tip"],
            "is_ancestor_of_head": is_anc,
            "ready_exists": ready_path.exists()
        }
        status_str = "PASS" if is_anc else "FAIL"
        print(f"  [{status_str}] {info['name']}: {info['expected_tip']} -> ancestor? {is_anc}")
        if not is_anc:
            all_ancestors = False

    # 3. Check 196 Donor Inventory Truth
    ledger_path = REPO_ROOT / "backend/catalog_inventory/196_REAL_RUNNING_UI_PREVIEW_LEDGER.json"
    ledger_valid = False
    total_inventoried = 0
    owner_observed_count = 0
    browser_animated_count = 0
    blocked_count = 0
    if ledger_path.exists():
        with open(ledger_path, "r", encoding="utf-8") as f:
            ldata = json.load(f)
            census = ldata.get("census", {})
            total_inventoried = census.get("INVENTORIED", 0)
            owner_observed_count = census.get("10_OWNER_OBSERVED_BASELINE", 0)
            browser_animated_count = census.get("BROWSER_ANIMATED", 0)
            blocked_count = census.get("UNSHIPPED_PENDING_OR_BLOCKED", 0)
            ledger_valid = (total_inventoried == 196 and owner_observed_count == 10 and browser_animated_count == 131)

    print(f"  196 Donor Ledger: total={total_inventoried}, owner_observed={owner_observed_count}, browser_animated={browser_animated_count}, blocked={blocked_count}")

    # 4. Check 21 Legacy Tools Parity
    tools_truth_path = REPO_ROOT / "tools/wave19_a5/legacy_tools_truth.json"
    tools_csv_path = REPO_ROOT / "docs/wave19_tools_legacy_parity/tools_parity_matrix.csv"
    tools_parity_valid = False
    total_tools = 0
    if tools_truth_path.exists() and tools_csv_path.exists():
        with open(tools_truth_path, "r", encoding="utf-8") as f:
            tdata = json.load(f)
            total_tools = tdata.get("total_tools_audited", 0)
            tools_parity_valid = (total_tools == 22 and tdata.get("total_passed") == 22)

    print(f"  Tools Parity: total_tools={total_tools}, valid={tools_parity_valid}")

    # 5. Check Navigation Destinations in Layout.jsx
    layout_path = REPO_ROOT / "frontend/src/components/Layout.jsx"
    nav_valid = False
    if layout_path.exists():
        content = layout_path.read_text(encoding="utf-8")
        has_motion = '"Motion Graphics"' in content or "'Motion Graphics'" in content
        has_trends = '"Trends"' in content or "'Trends'" in content
        has_channels = '"My Channel"' in content or "'My Channel'" in content
        has_library = '"Library"' in content or "'Library'" in content
        has_messages = '"Messages"' in content or "'Messages'" in content
        nav_valid = has_motion and has_trends and has_channels and has_library and has_messages

    print(f"  Navigation 5 Destinations: valid={nav_valid}")

    overall_status = "PASS" if (all_ancestors and ledger_valid and tools_parity_valid and nav_valid) else "FAIL"

    manifest = {
        "wave": 19,
        "integration_head_sha": head_sha,
        "overall_status": overall_status,
        "five_agents_ancestors_verified": all_ancestors,
        "agents": ancestry_results,
        "donor_catalog_196": {
            "total_inventoried": total_inventoried,
            "owner_observed_baseline": owner_observed_count,
            "browser_animated_verified": browser_animated_count,
            "blocked_truthfully_classified": blocked_count,
            "ledger_path": str(ledger_path.relative_to(REPO_ROOT))
        },
        "tools_parity": {
            "total_tools_audited": total_tools,
            "matrix_csv": str(tools_csv_path.relative_to(REPO_ROOT)),
            "ledger_json": str(tools_truth_path.relative_to(REPO_ROOT))
        },
        "navigation_verified": nav_valid
    }

    manifest_path = REPO_ROOT / "tools/wave19_a5/wave19_integration_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Wrote integration manifest to: {manifest_path}")
    print(f"Overall Integration Status: {overall_status}")
    return overall_status == "PASS"

if __name__ == "__main__":
    success = verify_integration()
    sys.exit(0 if success else 1)
