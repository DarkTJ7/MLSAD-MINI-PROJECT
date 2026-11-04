"""Record actual HTTP demonstration evidence against an already running service."""
import os,time,json
from pathlib import Path
import httpx
from app.config import ROOT

def run():
    base=os.environ['DEMO_BASE_URL'].rstrip('/')
    evidence={'environment':os.getenv('DEMO_ENVIRONMENT','configured API deployment'),
              'planner_mode':os.getenv('MODEL_MODE','unknown'),'base_url':base,'checks':[]}
    with httpx.Client(base_url=base,timeout=30,trust_env=False) as client:
        for _ in range(90):
            try:
                if client.get('/health').status_code==200:break
            except httpx.HTTPError:pass
            time.sleep(1)
        else:raise RuntimeError('API did not become healthy')
        for name,code in [('malformed',422),('injection',422)]:
            response=client.post('/runs',json=json.loads((ROOT/'examples'/f'{name}.json').read_text()))
            evidence['checks'].append({'case':name,'status_code':response.status_code,'passed':response.status_code==code,'body':response.json()})
        for name in ('valid','food_delivery','surveyor','outside_corpus'):
            started=time.perf_counter()
            body=json.loads((ROOT/'examples'/f'{name if name in ("valid","food_delivery") else "valid"}.json').read_text())
            if name=='surveyor':body['estimated_repair']=65000
            if name=='outside_corpus':body['insurer']='Other Insurer'
            response=client.post('/runs',json=body)
            response.raise_for_status();rid=response.json()['run_id']
            while time.perf_counter()-started<float(os.getenv('DEMO_TIMEOUT_SECONDS','420')):
                body=client.get('/runs/'+rid).json()
                if body['status'] in ('completed','escalated'):break
                time.sleep(.2)
            trace=client.get('/runs/'+rid+'/trace').json()
            feedback=client.post('/runs/'+rid+'/feedback',json={'satisfactory':body['status']=='completed','reason':'Automated live demonstration evidence collected.'})
            for _ in range(30):
                trace=client.get('/runs/'+rid+'/trace').json()
                if not (trace.get('quality') or {}).get('pending'):break
                time.sleep(.2)
            expected='escalated' if name=='outside_corpus' else 'completed'
            evidence['checks'].append({'case':name,'status':body,'trace':trace,'seconds':time.perf_counter()-started,
                                       'feedback_code':feedback.status_code,'passed':body['status']==expected and feedback.status_code==201})
        evidence['quality']=client.get('/quality').json()
    target=ROOT/'results/live_http_demo.json';target.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print(json.dumps([{'case':x['case'],'passed':x['passed']} for x in evidence['checks']]))
    if not all(x['passed'] for x in evidence['checks']):raise SystemExit(1)
if __name__=='__main__':run()
