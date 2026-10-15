import os
from pathlib import Path
import sys

phrases = ["Load Test Fixture", "Preview with Isolated Test Fixture", "Trigger Worker Tick"]
frontend_src = Path("frontend/src")

for root, dirs, files in os.walk(frontend_src):
    for f in files:
        if f.endswith((".jsx", ".js", ".tsx", ".ts")):
            p = Path(root) / f
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore")
                for ph in phrases:
                    if ph in txt:
                        print(f"FOUND: '{ph}' in {p}")
            except Exception:
                pass
print("Done scanning frontend/src")
