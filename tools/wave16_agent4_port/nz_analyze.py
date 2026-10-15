# SPDX-License-Identifier: AGPL-3.0-only
import json
from pathlib import Path

report_path = Path("tools/wave16_agent4_port/nz_census_report.json")
data = json.loads(report_path.read_text(encoding="utf-8"))

pending_items = [i for i in data["items"] if i["status"] == "PENDING"]
print(f"Total pending: {len(pending_items)}")

categories = {}
tech_groups = {
    "gsap_html_text": [],
    "threejs_webgl": [],
    "shader_transition": [],
    "trademark_blocked": [],
    "map_geo": [],
    "other": [],
}

for item in pending_items:
    cat = item.get("category") or "unknown"
    categories[cat] = categories.get(cat, 0) + 1
    
    bid = item["id"]
    if item["trademark"]:
        tech_groups["trademark_blocked"].append(bid)
    elif "transitions-" in bid or "transition" in cat.lower() or item["has_shader"]:
        tech_groups["shader_transition"].append(bid)
    elif "map" in bid or "flight" in bid:
        tech_groups["map_geo"].append(bid)
    elif item["has_three"]:
        tech_groups["threejs_webgl"].append(bid)
    elif item["has_gsap"] or item["has_canvas"] or item["has_svg"] or "text" in cat.lower() or "card" in bid:
        tech_groups["gsap_html_text"].append(bid)
    else:
        tech_groups["other"].append(bid)

print("\nCategories in pending:")
for cat, count in sorted(categories.items()):
    print(f"  {cat}: {count}")

print("\nTech / Legal Grouping:")
for grp, ids in tech_groups.items():
    print(f"\n{grp} ({len(ids)}):")
    for i in ids:
        print(f"  - {i}")
