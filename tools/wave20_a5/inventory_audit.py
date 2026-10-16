# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Tool: tools/wave20_a5/inventory_audit.py
Performs exhaustive census of canonical donor ID ledger, shipped bundles,
custom retired blocks, project/revision references in viralmint.db, and code references.
Strictly READ-ONLY on all donor and legacy directories and production database.
"""

import json
import re
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Set

DONOR_ROOT = Path(r"C:\Users\toddy\Desktop\hyperframes")
LEGACY_ROOT = Path(r"C:\Users\toddy\Desktop\ViralMint-Legado")
REPO_ROOT = Path(__file__).resolve().parents[2]
PROD_DB = Path(r"C:\Users\toddy\Desktop\ViralMint\viralmint.db")

CUSTOM_RETIRED_BLOCKS = {"creator-hud", "glitch-transition"}

def scan_donor_truth() -> Dict[str, Any]:
    print("[1/5] Auditing donor root (hyperframes)...")
    blocks_dir = DONOR_ROOT / "registry" / "blocks"
    components_dir = DONOR_ROOT / "registry" / "components"
    docs_dir = DONOR_ROOT / "docs"

    donor_blocks = []
    if blocks_dir.exists():
        donor_blocks = sorted([d.name for d in blocks_dir.iterdir() if d.is_dir()])

    donor_components = []
    if components_dir.exists():
        donor_components = sorted([d.name for d in components_dir.iterdir() if d.is_dir()])

    docs_files = list(docs_dir.rglob("*")) if docs_dir.exists() else []
    mdx_files = [f for f in docs_files if f.suffix == ".mdx"]

    return {
        "donor_root": str(DONOR_ROOT),
        "total_donor_blocks": len(donor_blocks),
        "donor_blocks": donor_blocks,
        "total_donor_components": len(donor_components),
        "total_docs_files": len(docs_files),
        "total_mdx_files": len(mdx_files),
    }

def scan_shipped_bundles() -> Dict[str, Any]:
    print("[2/5] Auditing backend/catalog/shipped_blocks...")
    shipped_dir = REPO_ROOT / "backend" / "catalog" / "shipped_blocks"
    if not shipped_dir.exists():
        return {"total_shipped": 0, "bundles": [], "imported_donor_count": 0, "retired_custom_count": 0}

    all_dirs = sorted([d.name for d in shipped_dir.iterdir() if d.is_dir()])
    imported_donor = [d for d in all_dirs if d not in CUSTOM_RETIRED_BLOCKS]
    retired_custom = [d for d in all_dirs if d in CUSTOM_RETIRED_BLOCKS]

    return {
        "total_shipped_dirs": len(all_dirs),
        "imported_donor_count": len(imported_donor),
        "imported_donor_slugs": imported_donor,
        "retired_custom_count": len(retired_custom),
        "retired_custom_slugs": retired_custom,
    }

def scan_database_projects() -> Dict[str, Any]:
    print("[3/5] Auditing production viralmint.db in READ-ONLY mode...")
    if not PROD_DB.exists():
        return {"error": "PROD_DB_NOT_FOUND", "status": "BLOCKED_USER_DATA_ACCESS"}

    uri = f"file:{PROD_DB.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    cur = conn.cursor()

    projects_raw = cur.execute("SELECT id, name, aspect_ratio, revision, document_json FROM projects").fetchall()
    revisions_raw = cur.execute("SELECT id, project_id, revision, operation_type, document_snapshot_json FROM project_revisions").fetchall()
    conn.close()

    projects_with_blocks = {}
    distinct_block_ids = set()

    for pid, name, aspect_ratio, rev, doc_json in projects_raw:
        if not doc_json:
            continue
        try:
            doc = json.loads(doc_json)
        except Exception:
            continue
        
        timeline = doc.get("timeline") or {}
        tracks = timeline.get("tracks") or []
        found_blocks = []
        for track in tracks:
            for clip in track.get("clips") or []:
                bid = clip.get("block_id") or clip.get("blockId")
                if bid:
                    found_blocks.append({
                        "clip_id": clip.get("id"),
                        "block_id": bid,
                        "track_id": track.get("id"),
                        "start_seconds": clip.get("start_seconds", 0.0),
                        "duration_seconds": clip.get("duration_seconds", 0.0),
                        "variables": clip.get("variables", {})
                    })
                    distinct_block_ids.add(bid)
        if found_blocks:
            projects_with_blocks[pid] = {
                "name": name,
                "aspect_ratio": aspect_ratio,
                "current_revision": rev,
                "blocks": found_blocks
            }

    revisions_with_blocks = {}
    for rid, pid, rev, op_type, snap_json in revisions_raw:
        if not snap_json:
            continue
        try:
            doc = json.loads(snap_json)
        except Exception:
            continue
        timeline = doc.get("timeline") or {}
        tracks = timeline.get("tracks") or []
        found_blocks = []
        for track in tracks:
            for clip in track.get("clips") or []:
                bid = clip.get("block_id") or clip.get("blockId")
                if bid:
                    found_blocks.append({
                        "clip_id": clip.get("id"),
                        "block_id": bid,
                        "track_id": track.get("id")
                    })
                    distinct_block_ids.add(bid)
        if found_blocks:
            revisions_with_blocks[rid] = {
                "project_id": pid,
                "revision": rev,
                "operation_type": op_type,
                "blocks_count": len(found_blocks)
            }

    return {
        "total_projects": len(projects_raw),
        "projects_dependent_on_blocks_count": len(projects_with_blocks),
        "total_revisions": len(revisions_raw),
        "revisions_dependent_on_blocks_count": len(revisions_with_blocks),
        "distinct_block_ids_in_db": sorted(list(distinct_block_ids)),
        "projects_with_blocks": projects_with_blocks
    }

def scan_codebase_references() -> Dict[str, Any]:
    print("[4/5] Scanning codebase for runtime references to catalog/blocks...")
    patterns = [
        r"shipped_blocks",
        r"UniversalRuntimeRegistry",
        r"catalogInventory",
        r"catalogOriginals",
        r"kind:\s*['\"]catalog['\"]",
        r"type:\s*['\"]block['\"]",
        r"/catalog/preview/",
        r"/catalog/blocks"
    ]
    ref_findings = {p: [] for p in patterns}

    exclude_dirs = {".git", "node_modules", "dist", "build", ".pytest_cache", "logs"}
    scan_exts = {".py", ".js", ".jsx", ".ts", ".tsx", ".json"}

    for root_dir in [REPO_ROOT / "backend", REPO_ROOT / "frontend" / "src"]:
        if not root_dir.exists():
            continue
        for f in root_dir.rglob("*"):
            if not f.is_file() or f.suffix not in scan_exts:
                continue
            if any(ex in f.parts for ex in exclude_dirs):
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                for pat in patterns:
                    if re.search(pat, content):
                        rel_path = str(f.relative_to(REPO_ROOT)).replace("\\", "/")
                        ref_findings[pat].append(rel_path)
            except Exception:
                pass

    return {k: sorted(list(set(v))) for k, v in ref_findings.items()}

def generate_inventory_report():
    donor = scan_donor_truth()
    shipped = scan_shipped_bundles()
    db_stats = scan_database_projects()
    code_refs = scan_codebase_references()

    report = {
        "wave": 20,
        "agent": 5,
        "timestamp": "2026-10-16T00:40:00Z",
        "donor_census": donor,
        "shipped_bundles_census": shipped,
        "database_census": {
            "total_projects": db_stats.get("total_projects"),
            "projects_dependent_on_blocks_count": db_stats.get("projects_dependent_on_blocks_count"),
            "total_revisions": db_stats.get("total_revisions"),
            "revisions_dependent_on_blocks_count": db_stats.get("revisions_dependent_on_blocks_count"),
            "distinct_block_ids_in_db": db_stats.get("distinct_block_ids_in_db"),
        },
        "codebase_references": code_refs,
        "projects_with_blocks": db_stats.get("projects_with_blocks")
    }

    out_file = REPO_ROOT / "tools" / "wave20_a5" / "inventory_audit_report.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\n[5/5] Report written to: {out_file}")
    print(f"Summary:")
    print(f"  Donor blocks in hyperframes registry: {donor.get('total_donor_blocks')}")
    print(f"  Shipped folders in repo: {shipped.get('total_shipped_dirs')} ({shipped.get('imported_donor_count')} donor + {shipped.get('retired_custom_count')} custom)")
    print(f"  Projects in DB: {db_stats.get('total_projects')} ({db_stats.get('projects_dependent_on_blocks_count')} dependent on blocks)")
    print(f"  Revisions in DB: {db_stats.get('total_revisions')} ({db_stats.get('revisions_dependent_on_blocks_count')} dependent on blocks)")
    print(f"  Distinct block IDs in active projects: {db_stats.get('distinct_block_ids_in_db')}")

if __name__ == "__main__":
    generate_inventory_report()
