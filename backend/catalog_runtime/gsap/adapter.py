# SPDX-License-Identifier: AGPL-3.0-only
"""Agent 6's isolated port adapter; canonical catalog/CAS registration is external.

Source ports are not automatically public or runtime-ready. Evidence classes
remain independent; a verified local video is not a saved Motion revision.
"""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
MANIFEST='tools/wave15_nonshader_port/nonshader_manifest.json'

def get_ports(repo_root: Path = ROOT) -> list[dict]:
    report=json.loads((repo_root/MANIFEST).read_text(encoding='utf-8'))
    result=[]
    for row in report['rows']:
        if not row['source_ported']:continue
        path=(repo_root/row['local_implementation']).resolve()
        if not path.is_relative_to((repo_root/'backend/catalog/shipped_blocks').resolve()):raise ValueError('Unsafe port path')
        evidence=json.loads((path/'port-evidence.json').read_text(encoding='utf-8'))
        source=path/(row['id']+'.html')
        if hashlib.sha256(source.read_bytes()).hexdigest()!=evidence['output_html_sha256']:raise ValueError('Port integrity mismatch')
        result.append({'id':row['id'],'path':row['local_implementation'],'taxonomy':row['taxonomy'],'dimensions':row['dimensions'],'duration':row['duration'],'source_sha256':row['source_sha256'],'output_html_sha256':evidence['output_html_sha256'],'rights_status':row['rights_status'],'source_ported':True,'runtime_ready':row['runtime_ready'],'browser_preview_verified':row['browser_preview_verified'],'motion_edit_verified':row['motion_edit_verified'],'render_artifact_verified':row['render_artifact_verified'],'public_ready':False,'blockers':row['blockers']})
    return result

def get_preview_html(block_id: str, aspect_ratio: str='16:9', variables: dict|None=None, width: int|None=None, height: int|None=None, repo_root: Path=ROOT) -> str:
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',block_id):raise ValueError('Invalid block ID')
    ports={r['id']:r for r in get_ports(repo_root)}
    if block_id not in ports:raise KeyError('Block is not an audited compiled port')
    if aspect_ratio not in {'9:16','16:9'}:raise ValueError('Unsupported target aspect')
    default=(1080,1920) if aspect_ratio=='9:16' else (1920,1080)
    width,height=width or default[0],height or default[1]
    if not all(isinstance(n,int) and 64<=n<=4096 for n in (width,height)):raise ValueError('Invalid viewport')
    port=ports[block_id];path=repo_root/port['path']
    metadata=json.loads((path/'registry-item.json').read_text(encoding='utf-8'))
    specs={s['id']:s for s in metadata['variables']}
    variables=variables or {}
    if not isinstance(variables,dict) or set(variables)-set(specs):raise ValueError('Unknown port variables')
    if any(not isinstance(v,str) or len(v)>160 for v in variables.values()):raise ValueError('Port text variables must be strings of at most 160 characters')
    values={k:variables.get(k,s['default']) for k,s in specs.items()}
    raw=(path/(block_id+'.html')).read_text(encoding='utf-8')
    payload=json.dumps(values,ensure_ascii=True).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    bridge='<script>window.__hyperframes={getVariables:()=>('+payload+')};</script>'
    # An opaque-origin sandbox is required by consuming pages; CSP also blocks
    # networking, navigation, media fetches, workers, plugins, and dynamic eval.
    csp="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; font-src 'none'; connect-src 'none'; media-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; worker-src 'none'"
    raw=raw.replace('<head>','<head><meta http-equiv="Content-Security-Policy" content="'+csp+'">'+bridge,1)
    nw,nh=port['dimensions']['width'],port['dimensions']['height']
    scale=min(width/nw,height/nh);left=(width-nw*scale)/2;top=(height-nh*scale)/2
    raw=raw.replace('<body>',f'<body><div id="wave15-native-stage" style="position:absolute;left:{left}px;top:{top}px;width:{nw}px;height:{nh}px;transform:scale({scale});transform-origin:0 0">',1)
    raw=raw.replace('</body>','</div><script>window.__wave15Native.play();</script></body>',1)
    override=f'<style>html,body{{width:{width}px!important;height:{height}px!important;overflow:hidden!important;margin:0!important;background:transparent!important}}</style>'
    return raw.replace('</head>',override+'</head>',1)
