import json
from pathlib import Path

with open("tools/wave15_shader_port/audit_27_results.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for slug in ['aurora', 'data-chart', 'flowing-gradient', 'holographic', 'instagram-follow', 'plasma', 'stripes', 'tiktok-follow', 'weight-wave', 'yt-lower-third']:
    rec = data[slug]
    match = (rec["donor_hash"] == rec["shipped_hash"])
    print(f"{slug}: match={match}")
    print(f"  donor_files:   {rec['donor_files']}")
    print(f"  shipped_files: {rec['shipped_files']}")
    print(f"  donor_hash:    {rec['donor_hash']}")
    print(f"  shipped_hash:  {rec['shipped_hash']}")
