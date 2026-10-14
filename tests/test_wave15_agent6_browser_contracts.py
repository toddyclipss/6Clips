# SPDX-License-Identifier: AGPL-3.0-only
"""Real Edge autoplay and hostile variable/network sandbox checks."""
from __future__ import annotations
import io
import threading
from http.server import ThreadingHTTPServer
from urllib.parse import urlencode
from PIL import Image,ImageChops,ImageStat
from playwright.sync_api import sync_playwright
import pytest
from backend.catalog_runtime.gsap.adapter import get_ports
from tools.wave15_nonshader_port.serve import Handler

@pytest.fixture(scope='module')
def live_browser():
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True,args=['--disable-gpu','--disable-background-networking','--disable-component-update','--disable-sync','--no-first-run'])
        yield browser,f'http://127.0.0.1:{server.server_port}'
        browser.close()
    server.shutdown();server.server_close()

@pytest.mark.parametrize('ident',[p['id'] for p in get_ports()])
def test_actual_autoplay_with_opaque_sandbox_and_no_egress(live_browser,ident):
    browser,origin=live_browser;context=browser.new_context(viewport={'width':640,'height':360});requests=[];errors=[]
    def route(r):
        requests.append(r.request.url)
        if r.request.url.startswith(origin+'/'):r.continue_()
        else:r.abort()
    context.route('**/*',route)
    page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content(f'<body style="margin:0;background:#242933"><iframe sandbox="allow-scripts" style="width:640px;height:360px;border:0" src="{origin}/preview/{ident}"></iframe>')
    frame=page.frames[1];frame.wait_for_function('window.__wave15Native !== undefined')
    frame.evaluate('window.__wave15Native.pause();window.__wave15Native.seek(0)')
    first=Image.open(io.BytesIO(page.screenshot())).convert('RGB')
    frame.evaluate('window.__wave15Native.play()');page.wait_for_timeout(1100)
    after=Image.open(io.BytesIO(page.screenshot())).convert('RGB')
    assert sum(ImageStat.Stat(ImageChops.difference(first,after)).mean)/3>.05
    assert errors==[]
    assert all(url.startswith(origin+'/') for url in requests)
    # Host access is denied because allow-same-origin is deliberately absent.
    assert frame.evaluate('()=>{try{return parent.document.body!==null}catch(e){return false}}') is False
    context.close()

def test_hostile_text_does_not_execute_and_fetch_is_denied(live_browser):
    import json
    browser,origin=live_browser;context=browser.new_context(viewport={'width':640,'height':360});seen=[]
    def route(r):
        seen.append(r.request.url)
        if r.request.url.startswith(origin+'/'):r.continue_()
        else:r.abort()
    context.route('**/*',route);page=context.new_page()
    attack='</script><script>window.portInjection=true</script>'
    query=urlencode({'variables':json.dumps({'name':attack})})
    page.set_content(f'<iframe sandbox="allow-scripts" src="{origin}/preview/lt-clean-bar?{query}"></iframe>')
    frame=page.frames[1];frame.wait_for_function('window.__wave15Native !== undefined')
    assert frame.locator('#lt-name').text_content()==attack
    assert frame.evaluate('window.portInjection===true') is False
    assert frame.evaluate('async()=>{try{await fetch("https://example.invalid/forbidden");return false}catch(e){return true}}') is True
    assert all(url.startswith(origin+'/') for url in seen)
    context.close()
