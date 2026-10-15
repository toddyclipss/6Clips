import json
from pathlib import Path

def inspect_17():
    repo_root = Path(__file__).resolve().parent.parent.parent
    donor_dir = Path(r"C:\Users\toddy\Desktop\hyperframes\registry\blocks")
    
    unshipped_17 = [
        'apple-money-count', 'blue-sweater-intro-video', 'canopy-part-title', 
        'chatgpt-exchange', 'claude-exchange', 'code-snippet-apple-terminal-pro', 
        'exploded-stack', 'extruded-logo', 'glass-hero', 'glass-shard-title', 
        'heygen-avatar-promo-card', 'ios26-liquid-glass', 'liquid-glass-notification', 
        'liquid-glass-widgets', 'lottie-character-walk', 'macos-notification', 
        'macos-tahoe-liquid-glass'
    ]
    
    print("=== INSPECTING 17 UNSHIPPED BLOCKS IN DONOR ===")
    for bid in unshipped_17:
        bpath = donor_dir / bid
        if not bpath.exists():
            print(f"MISSING IN DONOR: {bid}")
            continue
        files = [f.name for f in bpath.iterdir()]
        meta = {}
        for cand in ["registry-item.json", "package.json", "metadata.json"]:
            if (bpath / cand).exists():
                try:
                    meta = json.loads((bpath / cand).read_text(encoding="utf-8"))
                    break
                except:
                    pass
        print(f"\n--- {bid} ---")
        print(f"Files: {files}")
        if meta:
            print(f"Title: {meta.get('title')}, Tags: {meta.get('tags')}, Category: {meta.get('category')}")
        # check html/tsx/js
        htmls = list(bpath.glob("*.html"))
        tsxs = list(bpath.glob("*.tsx")) + list(bpath.glob("*.jsx"))
        scripts = []
        for h in htmls:
            content = h.read_text(encoding="utf-8", errors="ignore")
            import re
            scripts.extend(re.findall(r'<script[^>]+src=[\'"]([^\'"]+)[\'"]', content))
        print(f"HTML entrypoints: {[h.name for h in htmls]}")
        print(f"TSX/JSX files: {[t.name for t in tsxs]}")
        print(f"External scripts: {scripts[:5]}")

if __name__ == "__main__":
    inspect_17()
