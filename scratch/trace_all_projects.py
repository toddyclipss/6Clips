import sqlite3
from pathlib import Path

DB_PATH = Path("c:/Users/toddy/Desktop/ViralMint/viralmint.db")
conn = sqlite3.connect(f"file:{DB_PATH.resolve()}?mode=ro", uri=True)
cur = conn.cursor()

cur.execute("SELECT id, name, revision, created_at FROM projects ORDER BY created_at ASC")
all_projects = cur.fetchall()

print(f"Total projects fetched: {len(all_projects)}")

# Find index of project 71b0dfcd-934a-4c16-bdd4-9b3bfaee87fb
idx_71b = None
for i, p in enumerate(all_projects):
    if p[0] == '71b0dfcd-934a-4c16-bdd4-9b3bfaee87fb':
        idx_71b = i
        break

print(f"Project '71b0dfcd-934a-4c16-bdd4-9b3bfaee87fb' 1-based index: {idx_71b + 1 if idx_71b is not None else 'NOT FOUND'}")

# Print projects around 325
start_idx = max(0, idx_71b - 5)
end_idx = min(len(all_projects), idx_71b + 6)
print("\nProjects around index 325:")
for i in range(start_idx, end_idx):
    p = all_projects[i]
    print(f"  #{i+1:3d} | ID={p[0]} | Name={p[1]} | Rev={p[2]} | Created={p[3]}")

# Print the final projects 325 to 342
print(f"\nProjects from 325 to 342 (total {len(all_projects)}):")
for i in range(idx_71b, len(all_projects)):
    p = all_projects[i]
    print(f"  #{i+1:3d} | ID={p[0]} | Name={p[1]} | Rev={p[2]} | Created={p[3]}")

conn.close()
