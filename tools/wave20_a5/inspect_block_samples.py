# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
import sqlite3
import json
from pathlib import Path

PROD_DB = Path(r"C:\Users\toddy\Desktop\ViralMint\viralmint.db")

def main():
    conn = sqlite3.connect(f"file:{PROD_DB.as_posix()}?mode=ro", uri=True)
    cur = conn.cursor()
    found = {}
    for pid, name, rev, doc_json in cur.execute("SELECT id, name, revision, document_json FROM projects WHERE document_json LIKE '%block_id%'").fetchall():
        try:
            doc = json.loads(doc_json)
        except Exception:
            continue
        for track in doc.get("timeline", {}).get("tracks", []):
            for clip in track.get("clips", []):
                bid = clip.get("block_id")
                if bid and bid not in found:
                    found[bid] = {
                        "project_id": pid,
                        "project_name": name,
                        "variables": clip.get("variables"),
                        "duration": clip.get("duration_seconds"),
                        "track_id": track.get("id"),
                        "track_type": track.get("type"),
                    }
    for bid, val in sorted(found.items()):
        print(f"[{bid}] in {val['project_id']} ({val['project_name']}): track={val['track_id']}, dur={val['duration']}, vars={val['variables']}")
    conn.close()

if __name__ == "__main__":
    main()
