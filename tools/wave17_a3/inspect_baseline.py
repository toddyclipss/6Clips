import os
import json
from pathlib import Path

def inspect_baseline():
    repo_root = Path(__file__).resolve().parent.parent.parent
    print(f"Repo root: {repo_root}")
    
    shipped_dir = repo_root / "backend" / "catalog" / "shipped_blocks"
    catalog_runtime_dir = repo_root / "backend" / "catalog_runtime"
    donor_dir = Path(r"C:\Users\toddy\Desktop\hyperframes")
    
    print(f"Shipped blocks dir exists: {shipped_dir.exists()}")
    print(f"Donor dir exists: {donor_dir.exists()}")
    
    # Check donor blocks
    donor_blocks = []
    if donor_dir.exists():
        src_blocks = donor_dir / "src" / "blocks"
        if src_blocks.exists():
            donor_blocks = [d.name for d in src_blocks.iterdir() if d.is_dir() and not d.name.startswith(".")]
        print(f"Total donor blocks in hyperframes/src/blocks: {len(donor_blocks)}")
    
    # Check shipped blocks
    shipped_blocks = []
    if shipped_dir.exists():
        shipped_blocks = [d.name for d in shipped_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
        print(f"Total shipped blocks: {len(shipped_blocks)}")
        
    # Check catalog_runtime files
    if catalog_runtime_dir.exists():
        runtime_files = list(catalog_runtime_dir.rglob("*.py")) + list(catalog_runtime_dir.rglob("*.json"))
        print(f"Total catalog_runtime files: {len(runtime_files)}")
        for rf in runtime_files:
            print(f" - {rf.relative_to(repo_root)}")

    # Let's see if there is an existing registry or census
    census_files = list((repo_root / "backend").rglob("*census*.json")) + list((repo_root / "backend").rglob("*registry*.json"))
    for cf in census_files:
        print(f"Found census/registry json: {cf.relative_to(repo_root)}")

if __name__ == "__main__":
    inspect_baseline()
