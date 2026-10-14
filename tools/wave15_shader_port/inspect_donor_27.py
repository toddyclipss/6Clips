import os
import json
import hashlib
from pathlib import Path

DONOR_BLOCKS = Path(r"C:\Users\toddy\Desktop\hyperframes\registry\blocks")
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
    h = hashlib.sha256()
    for f in sorted(p.rglob("*")):
        if f.is_file():
            h.update(f.relative_to(p).as_posix().encode("utf-8"))
            try:
                h.update(f.read_bytes())
            except Exception:
                pass
    return h.hexdigest()

def inspect_all():
    print(f"Total blocks to audit: {len(ALL_27)}")
    for slug in ALL_27:
        donor_dir = DONOR_BLOCKS / slug
        shipped_dir = SHIPPED_BLOCKS / slug
        donor_exists = donor_dir.exists()
        shipped_exists = shipped_dir.exists()

        d_hash = compute_hash(donor_dir) if donor_exists else "MISSING"
        s_hash = compute_hash(shipped_dir) if shipped_exists else "NOT_YET_SHIPPED"

        # Read donor registry-item.json
        reg_item = {}
        if (donor_dir / "registry-item.json").exists():
            with open(donor_dir / "registry-item.json", "r", encoding="utf-8") as f:
                reg_item = json.load(f)

        files = [f.name for f in donor_dir.iterdir()] if donor_exists else []

        print(f"[{slug}]")
        print(f"  donor_hash:   {d_hash[:16]}...")
        print(f"  shipped_hash: {s_hash[:16] if s_hash != 'NOT_YET_SHIPPED' else s_hash}")
        print(f"  title:        {reg_item.get('title')}")
        print(f"  category:     {reg_item.get('category')}")
        print(f"  tags:         {reg_item.get('tags')}")
        print(f"  license:      {reg_item.get('license')}")
        print(f"  dims:         {reg_item.get('dimensions')}")
        print(f"  duration:     {reg_item.get('duration')}")
        print(f"  donor_files:  {files}")
        if (donor_dir / "lib").exists():
            print(f"  lib_files:    {[f.name for f in (donor_dir / 'lib').iterdir()]}")

if __name__ == "__main__":
    inspect_all()
