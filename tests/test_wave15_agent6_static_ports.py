# SPDX-License-Identifier: AGPL-3.0-only
"""Fail-closed transformation, source fidelity, ownership and serving contracts."""
from __future__ import annotations
import hashlib
import json
import re
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen
import pytest
from backend.catalog_runtime.gsap.adapter import get_ports,get_preview_html
from tools.wave15_nonshader_port.pipeline import compile_motion,Unsupported,exclusions
from tools.wave15_nonshader_port.serve import Handler

ROOT=Path(__file__).resolve().parents[1]

def manifest():return json.loads((ROOT/'tools/wave15_nonshader_port/nonshader_manifest.json').read_text(encoding='utf-8'))

def test_exact_169_owned_rows_and_independent_proof_classes():
    report=manifest();rows=report['rows'];ids={r['id'] for r in rows}
    assert len(rows)==len(ids)==169
    assert not ids & exclusions(ROOT)
    assert not ids & {'creator-hud','glitch-transition'}
    assert all(r['wave14_source_hash_matches'] and len(r['source_sha256'])==64 for r in rows)
    assert all(r['source_files'] for r in rows)
    assert all(not r['runtime_ready'] and not r['motion_edit_verified'] for r in rows)
    assert report['status']=='PARTIAL/BLOCKED'
    assert report['counts']['source_ported']==sum(r['source_ported'] for r in rows)
    assert len(get_ports())==10

def test_upstream_taxonomy_is_cited_and_missing_rows_remain_missing():
    rows=manifest()['rows'];by_id={r['id']:r for r in rows}
    tax=by_id['lt-clean-bar']['taxonomy']
    assert (tax['category_id'],tax['category'],tax['subcategory'])==('text-captions','Text & captions','Lower Thirds')
    assert tax['evidence']==['docs/snippets/catalog-gallery-data.mdx']
    assert by_id['snow']['taxonomy']['category'] is None
    assert by_id['snow']['taxonomy']['status']=='SOURCE_CATEGORY_MISSING'
    assert by_id['lt-neon-border']['taxonomy']['subcategory']=='Motion Primitives'

@pytest.mark.parametrize('port',get_ports(),ids=lambda p:p['id'])
def test_actual_local_port_integrity_and_original_motion_schedule(port):
    path=ROOT/port['path'];evidence=json.loads((path/'port-evidence.json').read_text(encoding='utf-8'))
    html=(path/(port['id']+'.html')).read_text(encoding='utf-8')
    assert hashlib.sha256(html.encode()).hexdigest()==evidence['output_html_sha256']
    assert 'gsap.' not in html and 'cdn.jsdelivr' not in html
    assert 'function mount' in html and 'HyperFramesNative.mount' in html
    timeline=evidence['compiled_timeline']
    assert timeline['duration']==4.8
    assert any(op['start']>=4.25 and op['duration']>0 for op in timeline['operations'])
    assert timeline['operations'][-1]['values']=={'visibility':'hidden'}
    assert evidence['source_scripts_executed'] is False
    assert evidence['rights']['gsap']=='REMOVED_NOT_REDISTRIBUTED'
    assert (path/'LICENSE.txt').read_text(encoding='utf-8').startswith('                                 Apache License')
    assert 'Modified' in (path/'NOTICE.txt').read_text(encoding='utf-8')
    assert port['public_ready'] is False

def simple_source(extra=''):
    return '<script>window.__timelines = window.__timelines || {}; var tl = gsap.timeline({ paused: true }); var el = document.getElementById("name"); gsap.set(el, { opacity: 0 }); tl.to(el, { opacity: 1, duration: 0.5, ease: "power3.out" }, 0.1); '+extra+' window.__timelines["sample"] = tl;</script>'

@pytest.mark.parametrize('code',[
    'fetch("https://tracking.invalid");',
    'eval("alert(1)");',
    'tl.to(el, { opacity: 0, onUpdate: function(){fetch("x")} }, 1);',
    'tl.to(el, { opacity: 0, ease: "custom()", duration: 1 }, 1);',
    'tl.to(el, { filter: "blur(3px)", duration: 1 }, 1);',
    'tl.to(el, { opacity: 0, repeat: 3, duration: 1 }, 1);',
    'tl.to(other, { opacity: 0, duration: 1 }, 1);',
    'tl.to(el, { opacity: 0, duration: 1 }, 9);',
    'tl.to(el, { opacity: 0, duration: 1 }, "<");',
])
def test_unknown_javascript_and_animation_dependencies_are_rejected(code):
    with pytest.raises(Unsupported):compile_motion(simple_source(code),'sample',4.8)

def test_literal_source_compiles_without_evaluation():
    config=compile_motion(simple_source(),'sample',4.8)
    assert config['operations'][0]=={'targets':['name'],'values':{'opacity':1.0},'start':.1,'duration':.5,'ease':'power3.out'}

def test_text_controls_are_safe_and_explicit_extensions():
    attack='</script><script>fetch("https://example.invalid")</script>'
    html=get_preview_html('lt-clean-bar',variables={'name':attack})
    assert attack not in html
    assert '\\u003c/script\\u003e' in html
    assert 'connect-src \'none\'' in html
    assert 'worker-src \'none\'' in html
    specs=json.loads((ROOT/'backend/catalog/shipped_blocks/lt-clean-bar/registry-item.json').read_text(encoding='utf-8'))['variables']
    assert all(s['origin']=='PORT_EXTENSION_EXPLICIT' for s in specs)
    with pytest.raises(ValueError):get_preview_html('lt-clean-bar',variables={'unknown':'x'})
    with pytest.raises(ValueError):get_preview_html('lt-clean-bar',variables={'name':{'danger':'x'}})
    with pytest.raises(ValueError):get_preview_html('../aurora')
    with pytest.raises(KeyError):get_preview_html('aurora')
    with pytest.raises(KeyError):get_preview_html('creator-hud')

def test_native_16_9_is_contained_in_vertical_stage():
    html=get_preview_html('lt-clean-bar','9:16',width=360,height=640)
    assert 'left:0.0px;top:218.75px;width:1920px;height:1080px;transform:scale(0.1875)' in html
    assert 'transform-origin:0 0' in html
    assert 'width:360px!important;height:640px!important' in html

def test_isolated_backend_blocks_unowned_shader_unknown_and_arbitrary_paths():
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        origin=f'http://127.0.0.1:{server.server_port}'
        assert urlopen(origin+'/preview/lt-clean-bar').status==200
        for suffix in ['/preview/aurora','/preview/lt-neon-border','/preview/not-a-block','/../../viralmint.db','/preview/lt-clean-bar?variables=%7B%22unknown%22%3A1%7D']:
            with pytest.raises(HTTPError) as exc:urlopen(origin+suffix)
            assert exc.value.code==403
    finally:server.shutdown();server.server_close()

def test_agent1_registration_actionable_contract_pending():
    """Core owner must call adapter for preview and route native timeline seeks.

    This xfail is deliberate: a local port must not fabricate runtime-ready
    while the canonical registry/CAS integration is missing in the exact base.
    """
    core=ROOT/'backend/catalog_runtime/core/registry_engine.py'
    if not core.exists():pytest.xfail('AGENT1_RUNTIME_REGISTRATION_PENDING: import get_ports/get_preview_html and route independent native_static_timeline adapter; preserve rights/7-stage evidence and canonical CAS')
    assert 'catalog_runtime.gsap' in core.read_text(encoding='utf-8'), 'Agent1 must register gsap.adapter compiled native ports, preserving public_ready=False until all acceptance classes pass'
