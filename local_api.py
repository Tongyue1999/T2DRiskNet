"""Loopback-only development integration API; no hospital connection is implied."""
import os,json,hmac,hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from data_intake import convert_tables
import pandas as pd
from engine import infer

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass  # Do not log patient payloads or identifiers.
    def reply(self,status,value):
        content=json.dumps(value,ensure_ascii=False,allow_nan=False).encode('utf-8')
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(content)
    def do_POST(self):
        expected=os.environ.get('T2D_LOCAL_API_TOKEN','')
        auth=self.headers.get('Authorization','')
        supplied=auth[7:] if auth.startswith('Bearer ') else ''
        if not expected or not hmac.compare_digest(supplied,expected):return self.reply(401,{'error':'Authentication required'})
        if self.path not in ['/v1/convert','/v1/predict']:return self.reply(404,{'error':'Unknown endpoint'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length<=0 or length>10_000_000:return self.reply(413,{'error':'Payload must be 1–10000000 bytes'})
            data=json.loads(self.rfile.read(length))
            if self.path=='/v1/convert':
                tables=[(t['name'],pd.DataFrame(t['rows'])) for t in data['tables']]
                records,audit=convert_tables(tables,mappings=data.get('field_mapping'),code_mapping=data.get('code_mapping'),gender_mapping=data.get('gender_mapping'))
                return self.reply(200,{'records':records,'audit':audit,'ready_for_inference':False,'next_step':'Confirm field semantics, units and codes before /v1/predict'})
            if data.get('mapping_confirmed') is not True:return self.reply(422,{'error':'mapping_confirmed=true required after verification'})
            records,_=convert_tables([],patients=data['records']);assessment=data['assessment_date']
            # Reuse the same code/unit checks as the UI without a second inference path.
            from simple_ui import check_model_mapping
            check_model_mapping(records)
            f,ex,m=infer(records,'current',assessment)
            return self.reply(200,{'predictions':f.to_dict('records'),'exclusions':ex.to_dict('records'),'manifest':m,'followup_date':None,'clinical_use':'research_only; clinician review required'})
        except Exception:
            # Raw model exceptions can contain source identifiers; retain them locally only.
            return self.reply(422,{'error':'Input validation failed; check dates, demographics, code/unit mapping and eligibility in the local UI.'})

def serve():
    if len(os.environ.get('T2D_LOCAL_API_TOKEN',''))<32:raise SystemExit('Set T2D_LOCAL_API_TOKEN to a random secret of at least 32 characters. Do not commit it.')
    port=int(os.environ.get('T2D_LOCAL_API_PORT','8504'))
    print('Development API listening on 127.0.0.1:'+str(port),flush=True)
    ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()

if __name__=='__main__':serve()
