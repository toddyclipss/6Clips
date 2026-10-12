import os
import sqlite3

def audit():
    print("=== TEST DATABASE & FILESYSTEM RESIDUE AUDIT ===")
    mv = "motion/studio/test_moving_video.mp4"
    print(f"File {mv}: exists={os.path.exists(mv)}")
    if os.path.exists(mv):
        print(f"  size: {os.path.getsize(mv)} bytes")

    p1 = "viralmint.db"
    print(f"\nDatabase {p1}: exists={os.path.exists(p1)}")
    if os.path.exists(p1):
        conn = sqlite3.connect(p1)
        cur = conn.cursor()
        cur.execute("SELECT id, title, video_path FROM downloaded_videos WHERE id = 'test-moving-vid-1'")
        row = cur.fetchone()
        print(f"  test-moving-vid-1 record: {row}")
        cur.execute("SELECT COUNT(*) FROM downloaded_videos")
        count = cur.fetchone()[0]
        print(f"  total downloaded_videos: {count}")
        conn.close()

    p2 = "storage/viralmint.db"
    print(f"\nDatabase {p2}: exists={os.path.exists(p2)}")

if __name__ == "__main__":
    audit()
