# SPDX-License-Identifier: AGPL-3.0-only
"""Import physical evidence after checking artifacts and current package hashes.

Only explicit successful evidence is promoted. No runtime/CAS/public readiness
is inferred from screenshots. Committed records have relative generated paths.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def reconcile(repo: Path, proof: Path) -> dict:
    manifest_path=repo/'tools/wave15_nonshader_port/nonshader_manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    report=json.loads(proof.read_text(encoding='utf-8'));by_id={r['id']:r for r in report['rows']};media_root=Path(report['artifact_root'])
    summaries=[]
    for row in manifest['rows']:
        evidence=by_id.get(row['id']);row['browser_preview_verified']=False;row['render_artifact_verified']=False
        if not evidence:continue
        package=repo/row['local_implementation']/(row['id']+'.html')
        if sha(package)!=evidence['source_html_sha256']:raise ValueError('Evidence is stale for '+row['id'])
        summary={'id':row['id'],'status':evidence['status'],'source_html_sha256':evidence['source_html_sha256'],'started_at':evidence['started_at'],'finished_at':evidence['finished_at'],'canonical_motion_cas':evidence['canonical_motion_cas'],'reference_visual_parity':evidence['reference_visual_parity'],'error':evidence.get('error'),'aspects':[]}
        for aspect in evidence['aspects']:
            if aspect['status']!='PASS':continue
            video=Path(aspect['mp4_path'])
            if not video.is_relative_to(media_root) or sha(video)!=aspect['mp4_sha256']:raise ValueError('Missing or changed physical video')
            frames=[]
            for frame in aspect['frames']:
                path=Path(frame['path'])
                if not path.is_relative_to(media_root) or sha(path)!=frame['sha256']:raise ValueError('Missing or changed physical frame')
                frames.append({'time':frame['time'],'path':path.relative_to(media_root).as_posix(),'sha256':frame['sha256']})
            summary['aspects'].append({k:v for k,v in aspect.items() if k not in {'frames','mp4_path','encode_command','ffprobe'}}|{'frames':frames,'mp4_path':video.relative_to(media_root).as_posix(),'ffprobe_stream':{k:aspect['ffprobe']['streams'][0][k] for k in ['codec_name','width','height','pix_fmt','duration','nb_frames']}})
        verified=evidence['status']=='PASS' and {a['aspect'] for a in summary['aspects']}=={'9:16','16:9'}
        row['browser_preview_verified']=verified
        row['render_artifact_verified']=verified and all(a['full_decode']=='PASS' and a['unique_decoded_frame_hashes']>=5 for a in summary['aspects'])
        row['preview_frames_status']='PASS_BOTH_ASPECTS' if verified else 'FAILED_OR_INCOMPLETE'
        row['mp4_status']='PASS_BOTH_ASPECTS_FULL_DECODE' if row['render_artifact_verified'] else 'FAILED_OR_INCOMPLETE'
        row['physical_evidence_ref']='tools/wave15_nonshader_port/physical_evidence.json#'+row['id']
        row['status']='LOCAL_PORT_VERIFIED_INTEGRATION_BLOCKED' if verified else 'LOCAL_PORT_FAILED'
        summaries.append(summary)
    manifest['counts'].update(browser_preview_verified=sum(r['browser_preview_verified'] for r in manifest['rows']),render_artifact_verified=sum(r['render_artifact_verified'] for r in manifest['rows']))
    output={'schema_version':1,'status':'PARTIAL/BLOCKED','timestamp':report['timestamp'],'browser':report['browser'],'backend':report['backend'],'artifact_directory_name':media_root.name,'resource_policy':report['resource_policy'],'rows':summaries,'limitations':report['limitations'],'physical_proof_file_sha256':sha(proof)}
    (repo/'tools/wave15_nonshader_port/physical_evidence.json').write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
    manifest_path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return manifest['counts']

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--repo',type=Path,required=True);parser.add_argument('--proof',type=Path,required=True);args=parser.parse_args();print(json.dumps(reconcile(args.repo,args.proof),indent=2))
