"""Trusted operator fault injection; not exposed by the public REST interface."""
import copy,json,os,time
from uuid import uuid4
from rq import Queue
from opentelemetry import trace
from app.config import ROOT,redis_connection
from app.jobs import verify_job,save
from app.telemetry import setup,carry
from app.http_client import client

def run():
    setup();connection=redis_connection()
    evidence=json.loads((ROOT/'results/live_http_demo.json').read_text())
    source=next(x['status']['run_id'] for x in evidence['checks'] if x['case']=='valid')
    state=copy.deepcopy(json.loads(connection.get('run:'+source))['state'])
    rid=str(uuid4());now=time.time()
    for key in ('failure','semantic_report','quality','completed_at','cost_usd','trace_carrier'):state.pop(key,None)
    state.update(run_id=rid,correlation_id=rid,submitted_at=now,deadline=now+180,
                 events=[],steps=0,tool_calls=0,verified=False,retried=False)
    state['proposed']['verified']=False
    state['proposed']['citations'][0]['quote']='Fabricated coverage provision for the controlled verifier test.'
    with trace.get_tracer('triage.demo').start_as_current_span('controlled_unsupported_quote') as span:
        span.set_attribute('run_id',rid);carry(state)
        save(connection,state,'verifying')
        Queue('verification',connection=connection).enqueue(verify_job,state,job_timeout=190)
    base=os.environ['DEMO_BASE_URL'].rstrip('/')
    while time.time()-now<185:
        status=client().get(base+'/runs/'+rid,timeout=15).json()
        if status['status'] in ('completed','escalated'):break
        time.sleep(.25)
    audit=client().get(base+'/runs/'+rid+'/trace',timeout=15).json()
    checks=[e for e in audit['events'] if e.get('step')=='verify']
    caught=bool(checks and checks[0].get('details',{}).get('verified') is False)
    searched_again=any(e.get('details',{}).get('tool')=='corpus_search' for e in audit['events'])
    report={'run_id':rid,'source_run_id':source,'controlled_operator_fault':True,'unsupported_quote_caught':caught,
            'searched_again':searched_again,'terminal':status,'trace':audit,
            'passed':caught and (searched_again or status['status']=='escalated')}
    (ROOT/'results/verifier_live_demo.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('terminal','trace')}))
    if not report['passed']:raise SystemExit(1)
if __name__=='__main__':run()
