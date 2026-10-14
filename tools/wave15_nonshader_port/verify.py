# SPDX-License-Identifier: AGPL-3.0-only
"""Sequential Edge + FFmpeg physical evidence runner; all media in TEMP.

Captures complete source duration at 12fps, 640x360 / 360x640, then encodes
1920x1080 / 1080x1920. Reduced capture resolution is recorded, never hidden.
Uses an opaque iframe sandbox and denies all non-loopback network requests.
Does not claim canonical Motion/CAS or reference visual parity verification.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode
from PIL import Image,ImageChops,ImageStat
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from backend.catalog_runtime.gsap.adapter import get_ports
from tools.wave15_nonshader_port.serve import Handler

def hash_file(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def command(args):
    p=subprocess.run(args,capture_output=True,text=True,timeout=180)
    if p.returncode:raise RuntimeError('Command failed: '+args[0]+': '+p.stderr[-1500:])
    return p.stdout
def pixel_delta(a,b):return sum(ImageStat.Stat(ImageChops.difference(a.convert('RGB'),b.convert('RGB'))).mean)/3

def verify(output: Path, ids: list[str]|None=None) -> dict:
    ffmpeg=shutil.which('ffmpeg');ffprobe=shutil.which('ffprobe')
    if not ffmpeg or not ffprobe:raise RuntimeError('FFmpeg/ffprobe missing')
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    origin=f'http://127.0.0.1:{server.server_port}'
    artifacts=Path(tempfile.mkdtemp(prefix='wave15-agent6-physical-'))
    results=[]
    try:
      with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True,args=['--disable-gpu','--disable-background-networking','--disable-component-update','--disable-sync','--no-first-run','--disable-features=OptimizationHints,MediaRouter'])
        ports=get_ports()
        for port in ports:
          if ids and port['id'] not in ids:continue
          ident=port['id'];row={'id':ident,'started_at':datetime.now(timezone.utc).isoformat(),'source_html_sha256':port['output_html_sha256'],'aspects':[],'status':'FAIL','canonical_motion_cas':'NOT_VERIFIED','reference_visual_parity':'NOT_VERIFIED'}
          try:
            for aspect,w,h,ow,oh in [('16:9',640,360,1920,1080),('9:16',360,640,1080,1920)]:
              errors=[];denied=[];local_status=[];context=browser.new_context(viewport={'width':w,'height':h},device_scale_factor=1)
              def route(r):
                if r.request.url.startswith(origin+'/'):r.continue_()
                else:denied.append(r.request.url);r.abort()
              context.route('**/*',route)
              page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)));page.on('response',lambda response:local_status.append(response.status))
              url=origin+'/preview/'+ident+'?'+urlencode({'aspect':aspect,'width':w,'height':h})
              # Host styles never touch the source composition; opacity/checker
              # background makes transparent lower thirds readable for capture.
              page.set_content(f'<html><style>html,body{{margin:0;background:#242933}}iframe{{border:0;width:{w}px;height:{h}px}}</style><iframe sandbox="allow-scripts" src="{url}"></iframe></html>')
              frame=page.frames[1];frame.wait_for_function('window.__wave15Native !== undefined',timeout=15000)
              frame.evaluate('window.__wave15Native.pause()')
              captures=[];images=[];states=[];frames_dir=artifacts/ident/aspect.replace(':','x');frames_dir.mkdir(parents=True)
              for t in [0,.25,.5,1,4.5,4.79]:
                frame.evaluate('(t)=>window.__wave15Native.seek(t)',t);frame.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');data=page.screenshot();path=frames_dir/f'preview-{t}.png';path.write_bytes(data)
                states.append(frame.evaluate('()=>({timeline:window.__wave15Native.stateAt(1),dom:window.__wave15Native.config.targets.map(id=>{const e=document.getElementById(id),c=getComputedStyle(e),r=e.getBoundingClientRect();return {id,transform:c.transform,opacity:c.opacity,visibility:c.visibility,clipPath:c.clipPath,rect:[r.x,r.y,r.width,r.height]}})})'))
                captures.append({'time':t,'path':str(path),'sha256':hash_file(path)});images.append(Image.open(io.BytesIO(data)).copy())
              delta=pixel_delta(images[0],images[3]);exit_delta=pixel_delta(images[3],images[-1])
              if delta<.05 or exit_delta<.05:raise AssertionError('Static/invisible animation')
              # Reverse seek must restore every transformed/style property.
              frame.evaluate('window.__wave15Native.seek(1)');frame.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');replay=page.screenshot()
              (frames_dir/'preview-1-replay.png').write_bytes(replay)
              reverse_delta=pixel_delta(Image.open(io.BytesIO(replay)),images[3])
              reverse_state=frame.evaluate('()=>({timeline:window.__wave15Native.stateAt(1),dom:window.__wave15Native.config.targets.map(id=>{const e=document.getElementById(id),c=getComputedStyle(e),r=e.getBoundingClientRect();return {id,transform:c.transform,opacity:c.opacity,visibility:c.visibility,clipPath:c.clipPath,rect:[r.x,r.y,r.width,r.height]}})})')
              if reverse_state!=states[3]:raise AssertionError('Non-deterministic reverse seek DOM state')
              if reverse_delta>.25:raise AssertionError('Reverse raster difference exceeds 0.25/255 mean: '+str(reverse_delta))
              before=replay
              # Save/reload of the adapter variables is independent of canonical
              # CAS. Record local reload evidence without calling it Motion saved.
              changed=origin+'/preview/'+ident+'?'+urlencode({'aspect':aspect,'width':w,'height':h,'variables':json.dumps({'name':'Wave15 Evidence Name'})})
              frame.goto(changed);frame.wait_for_function('window.__wave15Native !== undefined');frame.evaluate('window.__wave15Native.pause();window.__wave15Native.seek(1)')
              variable_image=page.screenshot();name=frame.locator('#lt-name').text_content()
              if name!='Wave15 Evidence Name' or variable_image==before:raise AssertionError('Variable did not affect rendered content')
              frame.goto(changed);frame.wait_for_function('window.__wave15Native !== undefined');frame.evaluate('window.__wave15Native.pause();window.__wave15Native.seek(1)')
              reload_delta=pixel_delta(Image.open(io.BytesIO(page.screenshot())),Image.open(io.BytesIO(variable_image)))
              if reload_delta>.25:raise AssertionError('Variable reload differs delta='+str(reload_delta))
              frame.goto(url);frame.wait_for_function('window.__wave15Native !== undefined');frame.evaluate('window.__wave15Native.pause()')
              frame_count=math.ceil(port['duration']*12)
              for index in range(frame_count):
                frame.evaluate('(t)=>window.__wave15Native.seek(t)',index/12)
                frame.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
                page.screenshot(path=str(frames_dir/f'{index:04d}.png'))
              video=frames_dir/'original-port.mp4'
              encode=[ffmpeg,'-hide_banner','-loglevel','error','-y','-framerate','12','-i',str(frames_dir/'%04d.png'),'-vf',f'scale={ow}:{oh}:flags=lanczos','-c:v','libx264','-threads','2','-preset','fast','-crf','20','-pix_fmt','yuv420p',str(video)]
              command(encode)
              probe=json.loads(command([ffprobe,'-v','error','-show_streams','-show_format','-of','json',str(video)]))
              stream=probe['streams'][0]
              if (stream['width'],stream['height'])!=(ow,oh) or stream['codec_name']!='h264':raise AssertionError('Unexpected physical stream')
              decode=command([ffmpeg,'-hide_banner','-loglevel','error','-xerror','-i',str(video),'-f','null','-'])
              framehash=command([ffmpeg,'-hide_banner','-loglevel','error','-i',str(video),'-vf','scale=64:64','-f','framemd5','-'])
              hashes=[line.rsplit(',',1)[-1].strip() for line in framehash.splitlines() if line and not line.startswith('#')]
              if len(set(hashes))<5:raise AssertionError('Export static')
              if errors or denied or any(s>=400 for s in local_status):raise AssertionError('Browser errors/network/resource failures')
              row['aspects'].append({'aspect':aspect,'status':'PASS','capture_dimensions':[w,h],'export_dimensions':[ow,oh],'framing':'contain','frames':captures,'pixel_mean_delta':delta,'exit_pixel_mean_delta':exit_delta,'reverse_seek_dom_exact':True,'reverse_seek_pixel_mean_delta':reverse_delta,'pixel_raster_tolerance_mean_0_to_255':.25,'variable_reload_pixel_mean_delta':reload_delta,'variable_visual_change_and_local_reload':True,'canonical_project_save':'NOT_TESTED','browser_errors':errors,'external_requests':denied,'mp4_path':str(video),'mp4_sha256':hash_file(video),'ffprobe':probe,'full_decode':'PASS','decoded_frame_count':len(hashes),'unique_decoded_frame_hashes':len(set(hashes)),'encode_command':encode,'full_decode_stdout':decode})
              context.close()
            row['status']='PASS'
          except Exception as exc:row['error']=str(exc)
          row['finished_at']=datetime.now(timezone.utc).isoformat();results.append(row)
          print(json.dumps({'id':ident,'status':row['status'],'error':row.get('error')}),flush=True)
        browser.close()
    finally:server.shutdown();server.server_close()
    report={'schema_version':1,'timestamp':datetime.now(timezone.utc).isoformat(),'browser':'Microsoft Edge via Playwright','backend':'Agent6 isolated loopback backend, no database','resource_policy':'one browser / one block / one aspect / two encoder threads','artifact_root':str(artifacts),'rows':results,'counts':{'pass':sum(r['status']=='PASS' for r in results),'fail':sum(r['status']!='PASS' for r in results)},'overall':'PARTIAL/BLOCKED','limitations':['Canonical ProjectRevision CAS and public Catalog registration pending Agent1','Authorized original GSAP visual baseline comparison unavailable','Reduced-resolution capture explicitly recorded; MP4 output dimensions validated']}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--ids',nargs='*');args=parser.parse_args();result=verify(args.output,args.ids);print(json.dumps(result['counts']));sys.exit(1 if result['counts']['fail'] else 0)
