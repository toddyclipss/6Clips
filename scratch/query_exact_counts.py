import sqlite3
from pathlib import Path

DB_PATH = Path("c:/Users/toddy/Desktop/ViralMint/viralmint.db")
conn = sqlite3.connect(f"file:{DB_PATH.resolve()}?mode=ro", uri=True)
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM projects")
total_projects = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM project_revisions")
total_revisions = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM chat_sessions")
total_sessions = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM chat_messages")
total_messages = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM user_settings")
total_settings = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM user_behavior")
total_behavior = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM jobs")
total_jobs = cursor.fetchone()[0]

print("=== VIRALMINT.DB STATS ===")
print(f"Total projects: {total_projects}")
print(f"Total project_revisions: {total_revisions}")
print(f"Total chat_sessions: {total_sessions}")
print(f"Total chat_messages: {total_messages}")
print(f"Total user_settings: {total_settings}")
print(f"Total user_behavior: {total_behavior}")
print(f"Total jobs: {total_jobs}")

# Find project 71b0dfcd-934a-4c16-bdd4-9b3bfaee87fb
cursor.execute("SELECT id, name, revision, created_at, updated_at FROM projects WHERE id='71b0dfcd-934a-4c16-bdd4-9b3bfaee87fb'")
target_proj = cursor.fetchone()
print(f"\nTarget project 71b0dfcd-934a-4c16-bdd4-9b3bfaee87fb: {target_proj}")

cursor.execute("SELECT id, project_id, revision, operation_type, author, created_at FROM project_revisions WHERE project_id='71b0dfcd-934a-4c16-bdd4-9b3bfaee87fb'")
target_revs = cursor.fetchall()
print(f"Target project revisions: {target_revs}")

# Show newest 10 projects
cursor.execute("SELECT id, name, revision, created_at FROM projects ORDER BY created_at DESC LIMIT 10")
newest_projs = cursor.fetchall()
print("\nNewest 10 projects:")
for p in newest_projs:
    print(f"  {p[0]} | {p[1]} | rev {p[2]} | {p[3]}")

# Show oldest 5 projects
cursor.execute("SELECT id, name, revision, created_at FROM projects ORDER BY created_at ASC LIMIT 5")
oldest_projs = cursor.fetchall()
print("\nOldest 5 projects:")
for p in oldest_projs:
    print(f"  {p[0]} | {p[1]} | rev {p[2]} | {p[3]}")

conn.close()
