from pathlib import Path

d_root = Path(r"C:\Users\toddy\Desktop\hyperframes\registry\blocks")
s_root = Path("backend/catalog/shipped_blocks")

slugs = [
    'aurora', 'data-chart', 'flowing-gradient', 'holographic', 'instagram-follow',
    'plasma', 'stripes', 'tiktok-follow', 'weight-wave', 'yt-lower-third'
]

for slug in slugs:
    d = d_root / slug
    s = s_root / slug
    all_files = sorted(set(
        [f.relative_to(d).as_posix() for f in d.rglob('*') if f.is_file()] +
        [f.relative_to(s).as_posix() for f in s.rglob('*') if f.is_file()]
    ))
    diffs = []
    for rel in all_files:
        df = d / rel
        sf = s / rel
        if not df.exists():
            diffs.append(f"+shipped_only:{rel}")
        elif not sf.exists():
            diffs.append(f"-donor_only:{rel}")
        else:
            db = df.read_bytes().replace(b'\r\n', b'\n')
            sb = sf.read_bytes().replace(b'\r\n', b'\n')
            if db != sb:
                diffs.append(f"~modified:{rel}")
    res = diffs if diffs else "EXACT_SOURCE_MATCH"
    print(f"{slug}: {res}")
