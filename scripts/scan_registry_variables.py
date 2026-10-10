import json, os, glob

items = glob.glob('motion_registry_cache/*/registry-item.json')
types = set()
for p in items:
    try:
        data = json.load(open(p, encoding='utf-8'))
        bid = data.get("id") or os.path.basename(os.path.dirname(p))
        print(f"=== {bid} ({p}) ===")
        for v in data.get("variables", []):
            vtype = v.get("type")
            types.add(vtype)
            print(f"   var: id={v.get('id')} type={vtype} default={v.get('default')} options={v.get('options')}")
    except Exception as e:
        print(f"Error {p}: {e}")

print("\nALL VARIABLE TYPES FOUND ACROSS REGISTRY:", types)
