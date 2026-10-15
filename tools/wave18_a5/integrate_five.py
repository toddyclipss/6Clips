"""
Wave 18 Five-Branch Integration Verification & Manifest Generator
Author: Agent 5 (Native Tools Parity & Integration Automerge)
"""

import os
import sys
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

AGENT_TIPS = {
    "agent1": {
        "name": "Agent 1 - Main Agent Native Motion Actions",
        "branch": "wave18/01-main-agent-native-editor-commands",
        "expected_tip": "7fc01115a7df0492dd26370f17fe3553fe2691df",
        "ready_file": "tools/wave18_a1/READY.json"
    },
    "agent2": {
        "name": "Agent 2 - Single Native Motion UI",
        "branch": "wave18/02-one-player-native-motion-ui",
        "expected_tip": "56a741e5ec408d5d85b37a052ce44b78da5c0ed4",
        "ready_file": "tools/wave18_a2/READY.json"
    },
    "agent3": {
        "name": "Agent 3 - HyperFrames A-M Real Preview",
        "branch": "wave18/03-hyperframes-am-real-preview",
        "expected_tip": "4aa8626ed9bf7ce45ee982d30b05826060a5c05d",
        "ready_file": "tools/wave18_a3/READY.json"
    },
    "agent4": {
        "name": "Agent 4 - HyperFrames N-Z Backlog & Adversarial QA",
        "branch": "wave18/04-nz-preview-adversarial-qa",
        "expected_tip": "d2b44f3e4240dcf35c843016ab9b4abf20c2d7bb",
        "ready_file": "tools/wave18_a4/READY.json"
    },
    "agent5": {
        "name": "Agent 5 - Native Tools Parity & Automerge",
        "branch": "wave18/05-native-tools-parity-automerge",
        "expected_tip": "4c4e10d4a899850fa705a05fc049150737d66ef4",
        "ready_file": "tools/wave18_a5/READY.json"
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
    print(f"=== Wave 18 Five-Branch Integration Audit ===")
    print(f"Repository Root: {REPO_ROOT}")
    
    # 1. Check HEAD
    head_proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT), capture_output=True, text=True, check=True)
    head_sha = head_proc.stdout.strip()
    print(f"Integration HEAD SHA: {head_sha}")
    
    # 2. Check Ancestry for all 5 tips
    ancestry_results = {}
    all_ancestors = True
    for key, info in AGENT_TIPS.items():
        is_anc = verify_ancestor(info["expected_tip"])
        ancestry_results[key] = {
            "name": info["name"],
            "tip_sha": info["expected_tip"],
            "is_ancestor_of_head": is_anc,
            "ready_exists": (REPO_ROOT / info["ready_file"]).exists()
        }
        status_str = "PASS" if is_anc else "FAIL"
        print(f"  [{status_str}] {info['name']}: {info['expected_tip']} -> ancestor? {is_anc}")
        if not is_anc:
            all_ancestors = False
            
    # 3. Check Census & Truth
    ledger_path = REPO_ROOT / "backend/catalog_inventory/wave18_196_per_id_ledger.json"
    ledger_exists = ledger_path.exists()
    item_count = 0
    owner_observed_count = 0
    shipped_count = 0
    if ledger_exists:
        with open(ledger_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            item_count = data.get("total_inventoried", 0)
            items = data.get("entries", {})
            owner_observed_count = data.get("owner_observed_preview_count", sum(1 for item in items.values() if item.get("owner_observed_preview_baseline")))
            shipped_count = data.get("shipped_on_disk_count", sum(1 for item in items.values() if item.get("shipped_on_disk")))
            
    print(f"  Inventory Ledger: {item_count} total, {owner_observed_count} owner-observed, {shipped_count} shipped on disk")

    # 4. Check Parity CSV
    legacy_csv = REPO_ROOT / "docs/wave18_native_parity/legacy_30_capability_parity.csv"
    preview_csv = REPO_ROOT / "docs/wave18_native_parity/hyperframes_196_preview_truth.csv"
    
    parity_valid = legacy_csv.exists() and preview_csv.exists()
    print(f"  Parity CSVs Exist: {parity_valid}")

    # Build manifest
    manifest = {
        "wave": 18,
        "integration_head_sha": head_sha,
        "five_agents_ancestors_verified": all_ancestors,
        "agents": ancestry_results,
        "inventory_truth": {
            "ledger_path": str(ledger_path.relative_to(REPO_ROOT)),
            "total_count": item_count,
            "owner_observed_preview_baseline": owner_observed_count,
            "shipped_on_disk": shipped_count
        },
        "parity_docs": {
            "legacy_30_csv": str(legacy_csv.relative_to(REPO_ROOT)),
            "hyperframes_196_csv": str(preview_csv.relative_to(REPO_ROOT))
        },
        "status": "PASS" if (all_ancestors and parity_valid and item_count == 196 and owner_observed_count == 10) else "FAIL"
    }
    
    manifest_file = REPO_ROOT / "tools/wave18_a5/wave18_integration_manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        
    print(f"Integration Manifest written to: {manifest_file}")
    print(f"Overall Integration Status: {manifest['status']}")
    return manifest["status"] == "PASS"

if __name__ == "__main__":
    success = verify_integration()
    sys.exit(0 if success else 1)
