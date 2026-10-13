import sqlite3
import os
import hashlib
from pathlib import Path

DB_PATH = Path("c:/Users/toddy/Desktop/ViralMint/viralmint.db")
ISO_DB_PATH = Path("c:/Users/toddy/Desktop/ViralMint/tmp_isolated_test/viralmint.db")

def hash_file(p):
    if not p.exists(): return "NOT_FOUND"
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while c := f.read(65536):
            h.update(c)
    return h.hexdigest().upper()

def examine_db(path):
    print(f"\n=======================================================")
    print(f"DATABASE: {path}")
    print(f"EXISTS: {path.exists()}")
    if not path.exists():
        return
    print(f"SIZE: {path.stat().st_size} bytes")
    print(f"SHA-256: {hash_file(path)}")
    
    uri = f"file:{path.resolve()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [r[0] for r in cursor.fetchall()]
    print(f"TABLES ({len(tables)}): {tables}")
    
    counts = {}
    for t in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM [{t}]")
            counts[t] = cursor.fetchone()[0]
        except Exception as e:
            counts[t] = f"error: {e}"
    print("\nROW COUNTS:")
    for t, c in counts.items():
        print(f"  {t}: {c}")
        
    print("\nPROJECTS DETAIL:")
    if "projects" in tables:
        cursor.execute("SELECT id, name, revision, created_at, updated_at FROM projects ORDER BY created_at ASC")
        rows = cursor.fetchall()
        for r in rows:
            print(f"  ID: {r[0]} | Name: {r[1]} | Rev: {r[2]} | Created: {r[3]} | Updated: {r[4]}")
            
    print("\nPROJECT REVISIONS DETAIL:")
    if "project_revisions" in tables:
        cursor.execute("SELECT id, project_id, revision, operation_type, author, created_at FROM project_revisions ORDER BY created_at ASC")
        rows = cursor.fetchall()
        for r in rows:
            print(f"  RevID: {r[0]} | ProjID: {r[1]} | Rev: {r[2]} | Op: {r[3]} | Author: {r[4]} | Created: {r[5]}")

    print("\nCHECK FOR SPECIFIED PROJECT ID '71b0dfcd-934a-4c16-bdd4-9b3bfaee87fb':")
    target_id = "71b0dfcd-934a-4c16-bdd4-9b3bfaee87fb"
    found_in = []
    for t in tables:
        cursor.execute(f"PRAGMA table_info([{t}])")
        cols = [c[1] for c in cursor.fetchall()]
        for col in cols:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM [{t}] WHERE CAST([{col}] AS TEXT) LIKE '%{target_id}%'")
                cnt = cursor.fetchone()[0]
                if cnt > 0:
                    found_in.append((t, col, cnt))
            except Exception:
                pass
    if found_in:
        print(f"  FOUND in: {found_in}")
    else:
        print(f"  NOT FOUND in any column of any table!")
        
    # Check raw file bytes for the string
    with open(path, "rb") as f:
        data = f.read()
        target_bytes = target_id.encode("utf-8")
        raw_count = data.count(target_bytes)
        print(f"  Raw string byte occurrences in file: {raw_count}")

    conn.close()

examine_db(DB_PATH)
if ISO_DB_PATH.exists():
    examine_db(ISO_DB_PATH)
