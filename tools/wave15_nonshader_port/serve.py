# SPDX-License-Identifier: AGPL-3.0-only
"""Isolated loopback preview backend. No owner database, inference or publisher."""
from __future__ import annotations
import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs,urlsplit

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from backend.catalog_runtime.gsap.adapter import get_preview_html,get_ports

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        url=urlsplit(self.path);query=parse_qs(url.query)
        try:
            if url.path=='/ports':payload=json.dumps(get_ports()).encode();content_type='application/json'
            elif url.path.startswith('/preview/'):
                payload=get_preview_html(url.path.rsplit('/',1)[1],query.get('aspect',['16:9'])[0],json.loads(query.get('variables',['{}'])[0]),int(query.get('width',['640'])[0]),int(query.get('height',['360'])[0])).encode();content_type='text/html; charset=utf-8'
            else:self.send_error(403);return
        except (ValueError,KeyError):self.send_error(403);return
        self.send_response(200);self.send_header('Content-Type',content_type);self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(payload)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=0);args=parser.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print(json.dumps({'listen_host':'127.0.0.1','port':server.server_port,'database':'NONE','source':'agent6_isolated_backend'}),flush=True)
    server.serve_forever()
