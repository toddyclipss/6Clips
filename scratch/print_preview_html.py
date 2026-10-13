import os, sys, asyncio
sys.path.insert(0, '.')
os.environ['VIRALMINT_DATA_DIR'] = 'c:/Users/toddy/Desktop/ViralMint/tmp_isolated_test'
from backend.services.hyperframes_adapter import HyperFramesAdapter
from pathlib import Path

res = asyncio.run(HyperFramesAdapter.sync_project_to_studio('6169c61a-9805-43fa-9230-7806f4ed922b', 5))
html = Path(res['html_path']).read_text(encoding='utf-8')
s = html.find('id="stage"')
e = html.find('</div>\n  <script id="vm-custom-code">', s)
print(html[s:e+6])
