# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Diagnostic script to inspect the physical files in storage/music."""
import json
import subprocess
from pathlib import Path

music_dir = Path("storage/music")
files = sorted(list(music_dir.glob("*")))
print(f"Total files in {music_dir}: {len(files)}")
for f in files:
    print("-----------------------------------------")
    print(f"File: {f.name} (size: {f.stat().st_size} bytes)")
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", str(f)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        data = json.loads(res.stdout)
        fmt = data.get("format", {})
        streams = data.get("streams", [{}])
        s0 = streams[0] if streams else {}
        print(f"  Format: {fmt.get('format_name')}, duration: {fmt.get('duration')}s, bit_rate: {fmt.get('bit_rate')}")
        print(f"  Stream 0: codec={s0.get('codec_name')}, channels={s0.get('channels')}, sample_rate={s0.get('sample_rate')}")
    else:
        print("  ffprobe failed!")

    cmd2 = [
        "ffmpeg", "-i", str(f), "-af", "volumedetect", "-f", "null", "-"
    ]
    res2 = subprocess.run(cmd2, capture_output=True, text=True)
    output = res2.stderr
    mean_vol = [line.strip() for line in output.splitlines() if "mean_volume" in line]
    max_vol = [line.strip() for line in output.splitlines() if "max_volume" in line]
    print(f"  Volume: {mean_vol[0] if mean_vol else 'N/A'} | {max_vol[0] if max_vol else 'N/A'}")
