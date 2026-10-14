# SPDX-License-Identifier: AGPL-3.0-only
"""Verify the delivery and record reproducible QA without shipping media."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime,timezone
from pathlib import Path

def finalize(repo: Path, proof: Path):
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
    start=datetime.now(timezone.utc).isoformat()
    args=['python','-m','pytest','-q','-p','no:cacheprovider','tests/test_wave15_agent6_static_ports.py','tests/test_wave15_agent6_browser_contracts.py']
    result=subprocess.run(args,cwd=repo,env=env,text=True,capture_output=True,timeout=180)
    print(result.stdout,flush=True)
    if result.returncode:raise RuntimeError(result.stdout+'\n'+result.stderr)
    manifest=json.loads((repo/'tools/wave15_nonshader_port/nonshader_manifest.json').read_text(encoding='utf-8'))
    physical=json.loads((repo/'tools/wave15_nonshader_port/physical_evidence.json').read_text(encoding='utf-8'))
    assert len(manifest['rows'])==169
    assert len(physical['rows'])==10 and all(r['status']=='PASS' for r in physical['rows'])
    ports=[r for r in manifest['rows'] if r['source_ported']]
    assert all(r['browser_preview_verified'] and r['render_artifact_verified'] and r['rights_cleared'] for r in ports)
    assert all(not r['runtime_ready'] and not r['motion_edit_verified'] for r in manifest['rows'])
    for row in manifest['rows']:
        assert set(['source_inventoried','source_ported','runtime_ready','browser_preview_verified','motion_edit_verified','render_artifact_verified','rights_cleared'])<=set(row)
        if row['source_ported']:
            evidence=json.loads((repo/row['local_implementation']/'port-evidence.json').read_text(encoding='utf-8'))
            source=(repo/row['local_implementation']/(row['id']+'.html')).read_bytes()
            assert hashlib.sha256(source).hexdigest()==evidence['output_html_sha256']
    qa={'schema_version':1,'base_sha':manifest['base_sha'],'started_at':start,'finished_at':datetime.now(timezone.utc).isoformat(),'command':args,'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr,'expected_pending_test':'AGENT1_RUNTIME_REGISTRATION_PENDING, canonical native adapter bridge/CAS integration','proof_file_sha256':hashlib.sha256(proof.read_bytes()).hexdigest(),'physical_command':['python','tools/wave15_nonshader_port/verify.py','--output','%TEMP%/wave15-agent6-all-physical.json'],'physical_status_output_reconstructed_from_verified_report':'\n'.join(json.dumps({'id':r['id'],'status':r['status'],'error':r.get('error')}) for r in physical['rows'])+'\n'+json.dumps({'pass':sum(r['status']=='PASS' for r in physical['rows']),'fail':sum(r['status']!='PASS' for r in physical['rows'])}),'counts':manifest['counts'],'delivery_status':'PARTIAL/BLOCKED','outstanding':['159 source IDs not ported: explicit per-ID dependency/rights/adapter blockers in manifest','9 SOURCE_CATEGORY_MISSING IDs in manifest','Agent1 native_static_timeline registration and canonical ProjectRevision CAS','Agent5 integrated rights/taxonomy reconciliation','Agent4 final integrated-SHA live evidence','Authorized original visual baseline comparison'],'new_physically_working_per_family':{'Lower Thirds':10}}
    (repo/'tools/wave15_nonshader_port/qa_results.json').write_text(json.dumps(qa,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':'PARTIAL/BLOCKED','counts':manifest['counts']}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--repo',type=Path,required=True);parser.add_argument('--proof',type=Path,required=True);args=parser.parse_args();finalize(args.repo,args.proof)
