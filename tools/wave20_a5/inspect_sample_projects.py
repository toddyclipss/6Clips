# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
import sqlite3
import json
from pathlib import Path

PROD_DB = Path(r"C:\Users\toddy\Desktop\ViralMint\viralmint.db")

def main():
    conn = sqlite3.connect(f"file:{PROD_DB.as_posix()}?mode=ro", uri=True)
    cur = conn.cursor()
    rows = cur.execute("SELECT id, name, revision, document_json FROM projects WHERE document_json LIKE '%block_id%' LIMIT 3").fetchall()
    for pid, name, rev, doc_json in rows:
        print(f"=== PROJECT {pid}: {name} (rev {rev}) ===")
        doc = json.loads(doc_json)
        timeline = doc.get("timeline", {})
        tracks = timeline.get("tracks", [])
        for track in tracks:
            print(f"Track: id={track.get('id')}, type={track.get('type')}, name={track.get('name')}, clips={len(track.get('clips', []))}")
            for clip in track.get("clips", []):
                if "block_id" in clip:
                    print(f"  BLOCK CLIP {clip.get('id')}: block_id={clip.get('block_id')}, start={clip.get('start_seconds')}, dur={clip.get('duration_seconds')}, vars={clip.get('variables')}")
                else:
                    print(f"  REGULAR CLIP {clip.get('id')}: type={clip.get('type')}, dur={clip.get('duration_seconds')}, asset={clip.get('asset_file')}")
    conn.close()

if __name__ == "__main__":
    main()
