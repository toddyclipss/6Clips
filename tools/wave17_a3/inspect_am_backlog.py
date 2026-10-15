import json
from pathlib import Path

def analyze_backlog():
    p = Path(__file__).resolve().parent.parent / "wave16_agent3_port" / "am_backlog_analysis.json"
    if not p.exists():
        print(f"File not found: {p}")
        return
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"Total entries in am_backlog_analysis.json: {len(data)}")
    
    # Check statuses
    by_status = {}
    if isinstance(data, dict):
        for bid, info in data.items():
            st = info.get("status") if isinstance(info, dict) else str(info)
            by_status.setdefault(st, []).append(bid)
    elif isinstance(data, list):
        for item in data:
            st = item.get("status") if isinstance(item, dict) else str(item)
            by_status.setdefault(st, []).append(item.get("id") if isinstance(item, dict) else item)
    
    for st, ids in by_status.items():
        print(f"Status '{st}': count={len(ids)}")
        print(f"  IDs: {ids}")

if __name__ == "__main__":
    analyze_backlog()
