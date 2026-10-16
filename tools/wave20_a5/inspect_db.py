# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Tool: tools/wave20_a5/inspect_db.py
Inspect production database viralmint.db in strict read-only mode to check tables,
projects, timeline blocks, and legacy references.
"""

import json
import sqlite3
from pathlib import Path

PROD_DB = Path(r"C:\Users\toddy\Desktop\ViralMint\viralmint.db")

def main():
    if not PROD_DB.exists():
        print(f"ERROR: {PROD_DB} does not exist!")
        return

    uri = f"file:{PROD_DB.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    cur = conn.cursor()

    tables = [row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print("=== Tables in viralmint.db ===")
    for t in tables:
        count = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {count} rows")

    # Let's inspect projects table schema and content if exists
    if "projects" in tables:
        print("\n=== Projects Table Columns ===")
        cols = cur.execute("PRAGMA table_info(projects)").fetchall()
        for col in cols:
            print(f"  {col[1]} ({col[2]})")
        
        projects = cur.execute("SELECT id, name, created_at, updated_at FROM projects").fetchall()
        print(f"\nTotal projects: {len(projects)}")
        for p in projects[:10]:
            print(f"  Project ID: {p[0]} | Name: {p[1]}")

    if "project_revisions" in tables:
        print("\n=== Project Revisions Table Columns ===")
        cols = cur.execute("PRAGMA table_info(project_revisions)").fetchall()
        for col in cols:
            print(f"  {col[1]} ({col[2]})")
        revs = cur.execute("SELECT COUNT(*) FROM project_revisions").fetchone()[0]
        print(f"Total revisions: {revs}")

    conn.close()

if __name__ == "__main__":
    main()
