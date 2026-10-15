import json
import sys
from pathlib import Path

def inspect_104():
    repo_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(repo_root))
    
    shipped_dir = repo_root / "backend" / "catalog" / "shipped_blocks"
    desc_file = repo_root / "backend" / "catalog_runtime" / "ports" / "wave16_agent3" / "descriptors.json"
    
    if not desc_file.exists():
        print("Descriptors file not found!")
        return
        
    with open(desc_file, "r", encoding="utf-8") as f:
        desc = json.load(f)
        
    blocks = desc.get("blocks", [])
    print(f"Total blocks in descriptors: {len(blocks)}")
    
    by_readiness = {}
    for b in blocks:
        r = b.get("runtime_readiness")
        by_readiness.setdefault(r, []).append(b["id"])
        
    for r, ids in by_readiness.items():
        print(f"Readiness '{r}': {len(ids)}")
        if r != "RUNTIME_READY":
            print(f"  {r}: {ids}")

    # Inspect the 104 runtime ready blocks in shipped_dir
    rr_ids = by_readiness.get("RUNTIME_READY", [])
    print(f"\nChecking physical files for {len(rr_ids)} RUNTIME_READY blocks...")
    missing_html = []
    missing_reg = []
    missing_gsap = []
    for bid in rr_ids:
        bdir = shipped_dir / bid
        if not bdir.exists():
            print(f"MISSING DIR: {bid}")
            continue
        if not (bdir / f"{bid}.html").exists():
            missing_html.append(bid)
        if not (bdir / "registry-item.json").exists():
            missing_reg.append(bid)
        if not (bdir / "lib" / "gsap.min.js").exists():
            missing_gsap.append(bid)
            
    print(f"Missing HTML: {len(missing_html)}")
    print(f"Missing registry-item.json: {len(missing_reg)}")
    print(f"Missing vendored gsap: {len(missing_gsap)}")

if __name__ == "__main__":
    inspect_104()
