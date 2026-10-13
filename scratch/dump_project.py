import sqlite3
import json

conn = sqlite3.connect('tmp_isolated_test/viralmint.db')
c = conn.cursor()
row = c.execute("SELECT document_json FROM projects WHERE id='6169c61a-9805-43fa-9230-7806f4ed922b'").fetchone()

if row:
    doc = json.loads(row[0])
    print(json.dumps(doc.get("timeline", {}).get("tracks", []), indent=2))
