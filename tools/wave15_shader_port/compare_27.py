import json
import os
import hashlib
from pathlib import Path

DONOR_BLOCKS = Path(r"C:\Users\toddy\Desktop\hyperframes\registry\blocks")
DONOR_REGISTRY_JSON = Path(r"C:\Users\toddy\Desktop\hyperframes\registry\registry.json")
SHIPPED_BLOCKS = Path(r"C:\Users\toddy\Desktop\ViralMint-wave15-03-shaders\backend\catalog\shipped_blocks")

EXISTING_10 = [
    "aurora", "data-chart", "flowing-gradient", "holographic",
    "instagram-follow", "plasma", "stripes", "tiktok-follow",
    "weight-wave", "yt-lower-third"
]

ELIGIBLE_17 = [
    "blob", "fractal-noise", "frost", "godrays", "goo", "lens-flare", "liquid-metal",
    "marble", "mesh-gradient", "nebula", "prism", "sine-wave", "strands", "swirl",
    "voronoi", "water", "waveform"
]

ALL_27 = EXISTING_10 + ELIGIBLE_17

def compute_hash(p: Path) -> str:
    if not p.exists():
        return "MISSING"
    h = hashlib.sha256()
    for f in sorted(p.rglob("*")):
        if f.is_file():
            h.update(f.relative_to(p).as_posix().encode("utf-8"))
            try:
                h.update(f.read_bytes())
            except Exception:
                pass
    return h.hexdigest()

def run_audit():
    # Load upstream registry.json
    reg_items = {}
    if DONOR_REGISTRY_JSON.exists():
        with open(DONOR_REGISTRY_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
            for it in data.get("items", []):
                if it.get("name"):
                    reg_items[it["name"]] = it

    audit_records = {}

    for slug in ALL_27:
        donor_dir = DONOR_BLOCKS / slug
        shipped_dir = SHIPPED_BLOCKS / slug

        d_hash = compute_hash(donor_dir)
        s_hash = compute_hash(shipped_dir)

        donor_item = {}
        if (donor_dir / "registry-item.json").exists():
            with open(donor_dir / "registry-item.json", "r", encoding="utf-8") as f:
                donor_item = json.load(f)

        shipped_item = {}
        if (shipped_dir / "registry-item.json").exists():
            with open(shipped_dir / "registry-item.json", "r", encoding="utf-8") as f:
                shipped_item = json.load(f)

        reg_item = reg_items.get(slug, {})

        # Check native category / subcategory
        # Upstream registry.json has type="hyperframes:block", tags=[...]
        # Upstream registry-item.json has category, tags
        raw_cat = donor_item.get("category") or reg_item.get("category")
        tags = donor_item.get("tags") or reg_item.get("tags") or []

        # In HyperFrames original taxonomy:
        # If no explicit category in registry-item.json, category is derived from tags
        # e.g., 'webgpu-shader' / 'background' -> 'backgrounds' / 'shaders'
        # 'social' / 'youtube' -> 'social' / 'call-to-action'
        # 'chart' -> 'charts'
        # 'typography' -> 'typography'
        derived_category = raw_cat
        if not derived_category:
            if "webgpu-shader" in tags or "shader" in tags:
                derived_category = "backgrounds/shaders"
            elif "social" in tags or "overlay" in tags:
                derived_category = "social/call-to-action"
            elif "chart" in tags or "data" in tags:
                derived_category = "charts/data"
            elif "typography" in tags:
                derived_category = "typography/kinetic"
            else:
                derived_category = "general"

        audit_records[slug] = {
            "slug": slug,
            "is_existing_10": slug in EXISTING_10,
            "donor_hash": d_hash,
            "shipped_hash": s_hash,
            "title": donor_item.get("title") or slug.replace("-", " ").title(),
            "raw_category": raw_cat,
            "derived_category": derived_category,
            "tags": tags,
            "license": donor_item.get("license") or "Apache-2.0",
            "dimensions": donor_item.get("dimensions") or {"width": 1920, "height": 1080},
            "duration": donor_item.get("duration") or 5.0,
            "donor_files": [f.name for f in donor_dir.iterdir()] if donor_dir.exists() else [],
            "shipped_files": [f.name for f in shipped_dir.iterdir()] if shipped_dir.exists() else [],
        }

    out_file = Path("tools/wave15_shader_port/audit_27_results.json")
    out_file.write_text(json.dumps(audit_records, indent=2), encoding="utf-8")
    print(f"Audit completed for {len(audit_records)} blocks. Written to {out_file}")

if __name__ == "__main__":
    run_audit()
