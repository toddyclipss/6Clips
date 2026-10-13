import subprocess
import json
from pathlib import Path

def probe(p):
    cmd = ['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(p)]
    return json.loads(subprocess.check_output(cmd))

p1 = Path('tmp_isolated_test/storage/downloads/technical_gaming_fixture.mp4')
p2 = Path('tmp_isolated_test/storage/generated/render_6169c61a-9805-43fa-9230-7806f4ed922b_rev5_f9b0a3d2.mp4')

if p1.exists():
    f1 = probe(p1)
    print("=== FIXTURE ===")
    print("Duration:", f1['format'].get('duration'))
    print("Size:", f1['format'].get('size'))
    for s in f1['streams']:
        print(" Stream:", s['codec_type'], s.get('codec_name'), s.get('width'), s.get('height'), s.get('r_frame_rate'))

if p2.exists():
    f2 = probe(p2)
    print("=== RENDER ===")
    print("Duration:", f2['format'].get('duration'))
    print("Size:", f2['format'].get('size'))
    for s in f2['streams']:
        print(" Stream:", s['codec_type'], s.get('codec_name'), s.get('width'), s.get('height'), s.get('r_frame_rate'))
