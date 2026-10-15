import json
import os
from pathlib import Path

def main():
    inv_path = Path("backend/catalog_inventory/hyperframes_196_inventory.json")
    if not inv_path.exists():
        print("Inventory not found!")
        return

    with open(inv_path, "r", encoding="utf-8") as f:
        inv = json.load(f)

    blocks = inv.get("blocks", [])
    print(f"Total items in inventory: {len(blocks)}")

    donor_dir = Path(r"C:\Users\toddy\Desktop\hyperframes")
    donor_exists = donor_dir.exists()
    print(f"Donor dir exists: {donor_exists}")

    shipped_dir = Path("backend/catalog/shipped_blocks")
    shipped = set(d.name for d in shipped_dir.iterdir() if d.is_dir()) if shipped_dir.exists() else set()

    nz_items = []
    for item in blocks:
        slug = item["id"]
        first_char = slug[0].lower()
        if ("n" <= first_char <= "z") or first_char.isdigit():
            nz_items.append(item)

    print(f"Total N-Z/0-9 items in inventory: {len(nz_items)}")
    
    nz_shipped = [it for it in nz_items if it["id"] in shipped]
    nz_unshipped = [it for it in nz_items if it["id"] not in shipped]

    print(f"N-Z in shipped_blocks ({len(nz_shipped)}):")
    for it in nz_shipped:
        p = shipped_dir / it["id"]
        files = [f.name for f in p.glob("*")]
        print(f"  [SHIPPED_DIR] {it['id']} | files={len(files)} | cat={it.get('taxonomy', {}).get('category_id')}")

    print(f"\nN-Z NOT in shipped_blocks ({len(nz_unshipped)}):")
    for it in nz_unshipped:
        rel = it.get("relative_source_path", "")
        donor_file = donor_dir / rel if donor_exists else None
        donor_found = donor_file.exists() if donor_file else False
        print(f"  [NO_SHIPPED_DIR] {it['id']} | cat={it.get('taxonomy', {}).get('category_id')} | donor_found={donor_found} | rel={rel}")

if __name__ == "__main__":
    main()
