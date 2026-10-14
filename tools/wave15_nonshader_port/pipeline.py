# SPDX-License-Identifier: AGPL-3.0-only
"""Offline read-only donor census and fail-closed static motion compiler.

Never imports, evaluates, builds, or executes donor code. Output is limited to
Agent 6's paths. Unhandled scripts remain quarantined, never silently stripped.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

BASE_SHA = 'e110d2923638eb32bc293dd96dcd464fab835fa5'
GSAP_LICENSE = 'https://gsap.com/community/standard-license/'
GSAP_CDN = 'https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js'
PROPERTIES = {'x', 'y', 'scale', 'scaleX', 'scaleY', 'opacity', 'visibility', 'clipPath', 'transformOrigin'}
BRANDS = {'apple-money-count','chatgpt-exchange','claude-exchange','code-snippet-apple-terminal-pro','heygen-avatar-promo-card','ios26-liquid-glass','macos-notification','macos-tahoe-liquid-glass','reddit-post','slack-notification-ad','spotify-card','vpn-youtube-spot','vfx-iphone-device','x-post','yt-comment-card','yt-logo-intro'}
UNCLEARED_ASSETS = {'canopy-part-title','glass-shard-title','frost-sequence-camera-orbit','lottie-character-walk','blue-sweater-intro-video'}

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def file_hashes(root: Path) -> dict:
    result = {}
    for p in sorted(root.rglob('*')):
        if p.is_symlink():
            raise ValueError('Donor symlink must be reviewed: '+p.name)
        if p.is_file():
            result[p.relative_to(root).as_posix()] = sha(p.read_bytes())
    return result

def source_hash(root: Path) -> str:
    digest=hashlib.sha256()
    for p in sorted(root.rglob('*')):
        if p.is_file():
            digest.update(p.relative_to(root).as_posix().encode());digest.update(p.read_bytes())
    return digest.hexdigest()

def exclusions(repo: Path) -> set[str]:
    rows=json.loads((repo/'backend/catalog_inventory/hyperframes_196_inventory.json').read_text(encoding='utf-8'))['blocks']
    ids={r['id'] for r in rows if r['integration_status'] in {'INTERNALIZED','ELIGIBLE_NOT_PORTED'}}
    if len(rows)!=196 or len(ids)!=27 or {'creator-hud','glitch-transition'} & ids:
        raise ValueError('Wave14 ownership inventory changed; expected 196 source IDs / 27 exclusions')
    return ids

def taxonomy(donor: Path) -> tuple[dict, dict]:
    source=donor/'docs/snippets/catalog-gallery-data.mdx'
    data=json.loads(source.read_text(encoding='utf-8').split('=',1)[1].strip().rstrip(';'))
    groups={g['id']:g['label'] for g in data['groups']}
    gallery={i['id']:i for i in data['items'] if i.get('kind')=='block'}
    navigation={}
    def walk(value, path=()):
        if isinstance(value,dict):
            path=path+(value['group'],) if 'group' in value else path
            for k,v in value.items():
                if k!='group':walk(v,path)
        elif isinstance(value,list):
            for item in value:walk(item,path)
        elif isinstance(value,str) and value.startswith('catalog/blocks/'):
            navigation[value.rsplit('/',1)[1]]=list(path)
    walk(json.loads((donor/'docs/docs.json').read_text(encoding='utf-8')))
    result={}
    for directory in sorted((donor/'registry/blocks').iterdir()):
        if not directory.is_dir():continue
        ident=directory.name; item=gallery.get(ident); nav=navigation.get(ident)
        doc=donor/'docs/catalog/blocks'/f'{ident}.mdx'
        doc_category=None
        if doc.exists():
            match=re.search(r'"category"\s*:\s*"([^"]+)"',doc.read_text(encoding='utf-8'))
            if match:doc_category=match[1]
        result[ident]={
            'category_id':item.get('group') if item else None,
            'category':groups.get(item.get('group')) if item else None,
            'subcategory':item.get('section') if item else None,
            'navigation_path':nav,'doc_category':doc_category,
            'status':'SOURCE_CATEGORY_VERIFIED' if item else 'SOURCE_CATEGORY_MISSING',
            'proposed_fallback':None,
            'evidence':['docs/snippets/catalog-gallery-data.mdx'] if item else [],
            'conflict': bool(nav and item and nav[-1]!=item.get('section')),
        }
    return result, {'gallery_sha256':sha(source.read_bytes()),'navigation_sha256':sha((donor/'docs/docs.json').read_bytes())}

class MarkupAudit(HTMLParser):
    def __init__(self):
        super().__init__();self.refs=[];self.ids=set();self.text_bindings={};self.failures=[];self.current=None
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if 'id' in attrs:self.ids.add(attrs['id']);self.current=attrs['id']
        for key,value in attrs.items():
            if key.lower().startswith('on') or key=='srcdoc':self.failures.append('active attribute '+key)
            if key in {'src','href','poster'} and value and not value.startswith('#'):self.refs.append(value)
        if tag in {'iframe','object','embed','form','base'}:self.failures.append('active tag '+tag)
    def handle_data(self,data):
        if self.current in {'lt-name','lt-role','lt-tag','lt-kicker'} and data.strip():self.text_bindings[self.current]=data.strip()
    def handle_endtag(self,tag):self.current=None

class Unsupported(ValueError):pass

def split_top(text: str) -> list[str]:
    parts=[];start=0;depth=0;quote=None;escape=False
    for i,c in enumerate(text):
        if quote:
            if escape:escape=False
            elif c=='\\':escape=True
            elif c==quote:quote=None
        elif c in '\"\'':quote=c
        elif c in '({[':depth+=1
        elif c in ')}]':depth-=1
        elif c==',' and depth==0:parts.append(text[start:i].strip());start=i+1
        if depth<0:raise Unsupported('Unbalanced source declaration')
    if quote or depth:raise Unsupported('Unbalanced source declaration')
    if text[start:].strip():parts.append(text[start:].strip())
    return parts

def literal(value: str, constants: dict):
    value=value.strip()
    if value in constants:return constants[value]
    if re.fullmatch(r'-?\d+(?:\.\d+)?',value):
        number=float(value)
        if not math.isfinite(number):raise Unsupported('Non-finite value')
        return number
    if re.fullmatch(r'"[^"\\]*"',value):return json.loads(value)
    raise Unsupported('Non-literal value: '+value[:70])

def object_values(text: str, constants: dict) -> dict:
    if not (text.startswith('{') and text.endswith('}')):raise Unsupported('Expected literal object')
    result={}
    for part in split_top(text[1:-1]):
        match=re.fullmatch(r'(\w+)\s*:\s*(.*)',part,re.S)
        if not match:raise Unsupported('Unsupported object expression')
        if match[1] in result:raise Unsupported('Duplicate property')
        result[match[1]]=literal(match[2],constants)
    return result

def compile_motion(html: str, ident: str, duration: float) -> dict:
    scripts=re.findall(r'<script\b[^>]*>(.*?)</script>',html,re.S|re.I)
    code='\n'.join(scripts)
    # Only full-line comments, never strip arbitrary lexical content.
    code=re.sub(r'^\s*//[^\n]*','',code,flags=re.M).strip()
    code=re.sub(r'window\.__timelines\s*=\s*window\.__timelines\s*\|\|\s*\{\};','',code)
    code=re.sub(r'var tl = gsap\.timeline\(\{ paused: true \}\);','',code)
    code=re.sub(r'window\.__timelines\["'+re.escape(ident)+r'"\] = tl;','',code)
    bindings={};constants={}
    def binding(m):bindings[m[1]]=m[2];return ''
    code=re.sub(r'var (\w+) = document\.getElementById\("([\w-]+)"\);',binding,code)
    def constant(m):constants[m[1]]=float(m[2]);return ''
    code=re.sub(r'var (\w+) = (-?\d+(?:\.\d+)?);',constant,code)
    initial=[];operations=[]
    call=re.compile(r'(gsap\.set|tl\.to|tl\.set)\s*\(')
    while code.strip():
        code=code.lstrip(); match=call.match(code)
        if not match:raise Unsupported('Uncompiled JavaScript: '+code[:85].replace('\n',' '))
        start=match.end();depth=1;quote=None;i=start
        while i<len(code) and depth:
            c=code[i]
            if quote:
                if c==quote:quote=None
                elif c=='\\':raise Unsupported('Escaped JavaScript requires review')
            elif c in '\"\'':quote=c
            elif c=='(':depth+=1
            elif c==')':depth-=1
            i+=1
        if depth or not code[i:].lstrip().startswith(';'):raise Unsupported('Malformed call')
        args=split_top(code[start:i-1]);code=code[i:].lstrip()[1:]
        expected=2 if match[1]=='gsap.set' else 3
        if len(args)!=expected:raise Unsupported('Unsupported call arity')
        targets=split_top(args[0][1:-1]) if args[0].startswith('[') and args[0].endswith(']') else [args[0]]
        if not all(t in bindings for t in targets):raise Unsupported('Unknown target')
        targets=[bindings[t] for t in targets];values=object_values(args[1],constants)
        length=values.pop('duration',0);easing=values.pop('ease','none')
        if not set(values)<=PROPERTIES:raise Unsupported('Unsupported properties: '+','.join(sorted(set(values)-PROPERTIES)))
        if not re.fullmatch(r'none|power[1-4]\.(?:in|out|inOut)|back\.out\([0-9.]+\)',str(easing)):raise Unsupported('Unsupported ease')
        if not isinstance(length,(int,float)) or length<0:raise Unsupported('Invalid duration')
        for key,v in values.items():
            if key in {'x','y','scale','scaleX','scaleY','opacity'} and not isinstance(v,(int,float)):raise Unsupported('Non-numeric transform')
            if key=='clipPath' and not re.fullmatch(r'inset\((?:-?\d+(?:\.\d+)?%?\s*){4}\)',str(v)):raise Unsupported('Unsupported clipPath')
        op={'targets':targets,'values':values}
        if match[1]=='gsap.set':initial.append(op)
        else:
            time=literal(args[2],constants)
            if not isinstance(time,(int,float)) or time<0 or time+length>duration+.001:raise Unsupported('Invalid timeline boundary')
            op.update(start=time,duration=length if match[1]=='tl.to' else 0,ease=easing);operations.append(op)
    if not operations or not initial:raise Unsupported('No verified motion declarations')
    return {'id':ident,'duration':duration,'targets':sorted(set(bindings.values())),'initial':initial,'operations':operations,'textBindings':{}}

def port(directory: Path, repo: Path, row: dict, runtime: str, license_text: str):
    ident=directory.name
    if directory.is_symlink():raise Unsupported('Donor directory symlink rejected')
    if not row['wave14_source_hash_matches']:raise Unsupported('SOURCE_CHANGED_REVIEW_REQUIRED')
    if ident in exclusions(repo):raise ValueError('Agent 3 ownership conflict')
    htmls=list(directory.glob('*.html'))
    if len(htmls)!=1:raise Unsupported('Expected single source HTML')
    html=htmls[0].read_text(encoding='utf-8');audit=MarkupAudit();audit.feed(html)
    if audit.failures:raise Unsupported('; '.join(audit.failures))
    if sorted(set(audit.refs))!=[GSAP_CDN]:raise Unsupported('Unvetted dependencies/assets: '+', '.join(sorted(set(audit.refs))))
    # Only these ten sources have received manual HTML/style/script review.
    if not re.fullmatch(r'lt-(accent-underline|bold-block|clean-bar|color-block|dark-card|kicker-name|mask-reveal|side-rule|soft-pill|stack-bars)',ident):
        raise Unsupported('Source family requires additional static compiler adapter and manual review')
    config=compile_motion(html,ident,float(row['duration']))
    config['textBindings']={key:target for key,target in {'name':'lt-name','role':'lt-role','tag':'lt-tag','kicker':'lt-kicker'}.items() if target in audit.ids}
    controls=[{'id':key,'type':'string','label':key.title(),'default':audit.text_bindings.get(target,''),'origin':'PORT_EXTENSION_EXPLICIT'} for key,target in config['textBindings'].items()]
    sanitized=re.sub(r'<script\b[^>]*>.*?</script>','<!-- Original motion script statically compiled; no donor JavaScript executed. -->',html,flags=re.S|re.I)
    if re.search(r'https?://|@import|url\s*\(|javascript:|expression\s*\(',sanitized,re.I):raise Unsupported('Unvetted stylesheet/resource expression')
    notice='<!-- Modified by ViralMint Wave15: original markup/styles retained; timeline statically compiled to independent local player. -->\n'
    packed=notice+sanitized.replace('</body>','<script>'+runtime+'</script>\n<script>HyperFramesNative.mount('+json.dumps(config,ensure_ascii=True,separators=(',',':'))+');</script>\n</body>')
    output=repo/'backend/catalog/shipped_blocks'/ident
    output.mkdir(parents=True,exist_ok=True)
    (output/'.gitattributes').write_text('* text eol=lf\n',encoding='utf-8',newline='\n')
    (output/htmls[0].name).write_text(packed,encoding='utf-8',newline='\n')
    metadata=json.loads((directory/'registry-item.json').read_text(encoding='utf-8'));metadata.pop('preview',None)
    metadata['variables']=controls
    metadata['wave15_port']={'source_category':row['taxonomy'],'runtime':'independent-static-timeline-v1','fidelity':'ORIGINAL_MARKUP_STYLES_TIMING_EASING_RETAINED; VISUAL_BASELINE_REVIEW_PENDING','variables_origin':'PORT_EXTENSION_EXPLICIT','native_aspect_policy':'contain','public_ready':False}
    (output/'registry-item.json').write_text(json.dumps(metadata,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    (output/'LICENSE.txt').write_text(license_text,encoding='utf-8')
    (output/'RUNTIME-LICENSE.txt').write_text((repo/'LICENSE').read_text(encoding='utf-8'),encoding='utf-8')
    (output/'NOTICE.txt').write_text('HyperFrames original composition: Apache-2.0; source registry/blocks/'+ident+'\nSource repository: https://github.com/heygen-com/hyperframes\nModified: removed GSAP CDN and executable donor scripts; statically compiled original motion declarations.\nIndependent native player: AGPL-3.0-only, ViralMint Contributors.\nNo GSAP product/code is redistributed. Named fonts were not supplied by source; original system fallbacks retained.\n',encoding='utf-8')
    evidence={'schema_version':1,'id':ident,'source_files':row['source_files'],'source_sha256':row['source_sha256'],'compiled_timeline':config,'source_html_sha256':sha(html.encode()),'output_html_sha256':sha(packed.encode()),'runtime_sha256':sha(runtime.encode()),'source_scripts_executed':False,'rights':{'composition':'Apache-2.0','runtime':'AGPL-3.0-only','gsap':'REMOVED_NOT_REDISTRIBUTED','assets':'NONE','trademark':'NONE_IDENTIFIED'},'fidelity_limits':['Visual comparison against an authorized original GSAP renderer not yet performed','Original fonts absent upstream; exact glyph metrics depend on system font fallback','Additional text controls are explicitly port extensions']}
    (output/'port-evidence.json').write_text(json.dumps(evidence,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    row.update(local_implementation=output.relative_to(repo).as_posix(),source_ported=True,rights_status='CLEARED_COMPOSITION_AND_INDEPENDENT_RUNTIME',rights_cleared=True,source_fidelity=evidence['fidelity_limits'],blockers=['AGENT1_RUNTIME_REGISTRATION_PENDING','CANONICAL_PROJECT_REVISION_CAS_NOT_VERIFIED','ORIGINAL_VISUAL_BASELINE_REVIEW_PENDING'])

def run(donor: Path, repo: Path, output: Path, do_port: bool) -> dict:
    if donor.resolve()==repo.resolve() or donor.resolve() in repo.resolve().parents:raise ValueError('Donor must stay read-only')
    excluded=exclusions(repo);taxonomy_map,taxonomy_evidence=taxonomy(donor)
    inventory=json.loads((repo/'backend/catalog_inventory/hyperframes_196_inventory.json').read_text(encoding='utf-8'))
    inventory_by_id={r['id']:r for r in inventory['blocks']}
    directories=sorted(d for d in (donor/'registry/blocks').iterdir() if d.is_dir())
    if {d.name for d in directories}!=set(inventory_by_id):raise ValueError('Donor directory IDs differ from exact Wave14 inventory')
    runtime=(repo/'backend/catalog_runtime/gsap/native_timeline.js').read_text(encoding='utf-8')
    rows=[]
    for d in directories:
        if d.name in excluded:continue
        metadata=json.loads((d/'registry-item.json').read_text(encoding='utf-8'));hashes=file_hashes(d)
        sources=[p for p in d.rglob('*') if p.is_file() and p.suffix in {'.html','.js','.mjs','.css'}]
        text='\n'.join(p.read_text(encoding='utf-8', errors='replace') for p in sources)
        urls=sorted(set(re.findall(r'https?://[^\s\"\'<>`\\)]+',text)))
        fonts=sorted(set(re.findall(r'font-family\s*:\s*([^;}{]+)',text)))
        scripts=sorted(set(re.findall(r'<script\b[^>]*\bsrc=[\"\']([^\"\']+)',text,re.I)))
        has_gsap=bool(re.search(r'\bgsap\b',text,re.I))
        blockers=[]
        if has_gsap:blockers.append('GSAP_VISUAL_BUILDER_PERMISSION_REQUIRED_OR_STATIC_ADAPTER_NEEDED')
        if urls:blockers.append('REMOTE_REFERENCE_REVIEW_REQUIRED')
        if d.name in BRANDS:blockers.append('BRAND_OWNER_CLEARANCE_REVIEW_REQUIRED')
        if d.name in UNCLEARED_ASSETS:blockers.append('ASSET_AUTHOR_PROVENANCE_REQUIRED')
        if taxonomy_map[d.name]['status']=='SOURCE_CATEGORY_MISSING':blockers.append('SOURCE_CATEGORY_MISSING')
        row={'id':d.name,'title':metadata['title'],'taxonomy':taxonomy_map[d.name],'dimensions':metadata['dimensions'],'duration':metadata['duration'],'native_aspect_policy':'contain; no stretching','variables':metadata.get('variables',metadata.get('params',[])),'dependency_inventory':{'script_sources':scripts,'remote_references':urls,'font_stacks':fonts,'gsap':has_gsap,'three':bool(re.search(r'\bTHREE\b|three(?:\.min)?\.js|three\.module',text)),'license_files':[p for p in hashes if re.search(r'license|notice|ofl',p,re.I)]},'license_inventory':{'composition':metadata.get('license','Apache-2.0 (root LICENSE and CREDITS.md; third-party rights separate)'),'gsap':{'license':'GSAP Standard License, not OSI','owner':'Webflow','evidence_url':GSAP_LICENSE,'permission_needed':'Written consent if visual editor falls within Prohibited Uses'} if has_gsap else None,'asset_or_brand_permission_owner':'original asset author / respective trademark owner' if d.name in BRANDS|UNCLEARED_ASSETS else 'not individually cleared outside compiled reviewed family'},'source_files':hashes,'source_sha256':source_hash(d),'wave14_source_hash_matches':source_hash(d)==inventory_by_id[d.name]['source_sha256'],'source_inventoried':True,'source_ported':False,'runtime_ready':False,'browser_preview_verified':False,'motion_edit_verified':False,'render_artifact_verified':False,'rights_cleared':False,'rights_status':'PENDING_ITEM_REVIEW','local_implementation':None,'source_fidelity':'NOT_PORTED','preview_frames_status':'NOT_RUN','mp4_status':'NOT_RUN','status':'BLOCKED','blockers':blockers}
        if do_port:
            try:port(d,repo,row,runtime,(donor/'LICENSE').read_text(encoding='utf-8'))
            except Unsupported as exc:row['blockers'].append(str(exc))
        rows.append(row)
    if len(rows)!=169 or len({r['id'] for r in rows})!=169:raise ValueError('Expected strictly 169 owned source IDs')
    report={'schema_version':1,'agent':6,'base_sha':BASE_SHA,'status':'PARTIAL/BLOCKED','excluded_agent3_ids':sorted(excluded),'taxonomy_evidence':taxonomy_evidence,'rows':rows,'counts':{'source_inventoried':len(rows),'source_ported':sum(r['source_ported'] for r in rows),'runtime_ready':0,'browser_preview_verified':0,'motion_edit_verified':0,'render_artifact_verified':0,'rights_cleared':sum(r['rights_cleared'] for r in rows)},'integration_contract':{'loader_module':'backend.catalog_runtime.gsap.adapter','get_ports':'get_ports(repo_root)','preview':'get_preview_html(block_id, aspect_ratio, variables, width, height)','seek':'window.__timelines[block_id].seek(seconds)','glue_needed':'Agent 1 must register only truthfully gated paths; Agent 5 applies rights/taxonomy evidence; CAS remains core responsibility'},'families':dict(Counter(r['taxonomy']['subcategory'] or 'SOURCE_CATEGORY_MISSING' for r in rows))}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--donor',type=Path,required=True);parser.add_argument('--repo',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--port',action='store_true');args=parser.parse_args()
    result=run(args.donor,args.repo,args.output,args.port);print(json.dumps({'status':result['status'],'counts':result['counts']},indent=2))
