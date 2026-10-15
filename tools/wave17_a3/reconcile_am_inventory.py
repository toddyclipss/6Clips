import json
import sys
from pathlib import Path

def reconcile():
    repo_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(repo_root))
    inv_file = repo_root / "backend" / "catalog_inventory" / "hyperframes_196_inventory.json"
    ledger_file = repo_root / "backend" / "catalog_inventory" / "wave16_196_per_id_ledger.json"
    shipped_dir = repo_root / "backend" / "catalog" / "shipped_blocks"
    donor_dir = Path(r"C:\Users\toddy\Desktop\hyperframes")
    
    with open(inv_file, "r", encoding="utf-8") as f:
        inv_data = json.load(f)
    
    blocks = inv_data.get("blocks", [])
    all_donor_ids = sorted([b["id"] for b in blocks if "id" in b])
    print(f"Total blocks in hyperframes_196_inventory.json: {len(all_donor_ids)}")
    
    # Filter A-M
    def is_am(bid: str) -> bool:
        first_letter = bid[0].lower()
        return 'a' <= first_letter <= 'm'
        
    am_ids = [bid for bid in all_donor_ids if is_am(bid)]
    nz_ids = [bid for bid in all_donor_ids if not is_am(bid)]
    print(f"Total A-M donor IDs: {len(am_ids)}")
    print(f"Total N-Z donor IDs: {len(nz_ids)}")
    
    # Check shipped_blocks directory
    shipped_dirs = sorted([d.name for d in shipped_dir.iterdir() if d.is_dir() and not d.name.startswith(".")])
    shipped_am = [bid for bid in shipped_dirs if is_am(bid)]
    shipped_nz = [bid for bid in shipped_dirs if not is_am(bid)]
    print(f"Total shipped dirs on disk: {len(shipped_dirs)} (A-M: {len(shipped_am)}, N-Z: {len(shipped_nz)})")
    
    # Check Wave 16 37 operable blocks
    from backend.catalog_runtime.core.taxonomy import THIRTYSEVEN_DONOR_OPERABLE_BLOCKS
    active_am = [bid for bid in THIRTYSEVEN_DONOR_OPERABLE_BLOCKS if is_am(bid)]
    active_nz = [bid for bid in THIRTYSEVEN_DONOR_OPERABLE_BLOCKS if not is_am(bid)]
    print(f"Wave 16 37 operable blocks (A-M: {len(active_am)}, N-Z: {len(active_nz)})")
    print(f"Active A-M blocks: {active_am}")
    
    # Check wave16_196_per_id_ledger if exists
    if ledger_file.exists():
        with open(ledger_file, "r", encoding="utf-8") as f:
            ledger_data = json.load(f)
        print(f"Ledger entries: {len(ledger_data)}")
        # breakdown of ledger statuses for A-M
        statuses = {}
        for bid in am_ids:
            st = ledger_data.get(bid, {}).get("status", "UNKNOWN")
            statuses[st] = statuses.get(st, 0) + 1
        print(f"Wave 16 Ledger status breakdown for A-M: {statuses}")
        
    # Unshipped A-M blocks
    unshipped_am = [bid for bid in am_ids if bid not in shipped_dirs]
    print(f"Unshipped A-M blocks ({len(unshipped_am)}): {unshipped_am}")
    
    # Shipped but inactive A-M blocks
    staged_am = [bid for bid in shipped_am if bid not in THIRTYSEVEN_DONOR_OPERABLE_BLOCKS]
    print(f"Shipped but not in 37 operable (A-M) ({len(staged_am)}):")
    for s in staged_am:
        print(f"  - {s}")
        
    # Check donor blocks existence on donor path
    if donor_dir.exists():
        donor_src = donor_dir / "registry" / "blocks"
        missing_in_donor = [bid for bid in am_ids if not (donor_src / bid).exists()]
        if missing_in_donor:
            print(f"WARNING: IDs in am_ids not found in donor registry/blocks: {missing_in_donor}")
        else:
            print(f"All {len(am_ids)} A-M donor IDs confirmed present in donor reference at {donor_src}")

if __name__ == "__main__":
    reconcile()
