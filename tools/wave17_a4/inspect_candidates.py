from pathlib import Path

donor_dir = Path(r"C:\Users\toddy\Desktop\hyperframes\registry\blocks")

candidates = [
    "orbit-card",
    "share-sheet-carousel",
    "snow",
    "starfield",
    "swirl-vortex",
    "transitions-3d",
    "transitions-blur",
    "transitions-cover",
    "transitions-destruction",
    "transitions-distortion",
    "transitions-grid",
    "transitions-light",
    "transitions-mechanical",
    "transitions-other",
    "transitions-scale",
    "ui-3d-reveal",
    "vfx-magnetic",
    "vfx-text-cursor"
]

for slug in candidates:
    sdir = donor_dir / slug
    htmls = list(sdir.glob("*.html"))
    print(f"\n=== {slug} ===")
    for h in htmls:
        print(f"File: {h.name} (size: {h.stat().st_size} bytes)")
        content = h.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()
        script_tags = [l.strip() for l in lines if "<script" in l]
        print(f"Scripts: {script_tags}")
        # print first 15 lines
        preview = "\n".join(lines[:10])
        # check if it uses custom CSS or GSAP
        uses_gsap = "gsap" in content.lower()
        print(f"Uses gsap: {uses_gsap}")
