import hashlib
import json
import time
import logging
from uuid import uuid4
from pathlib import Path
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from rq import Queue
from .config import DATA, ROOT, redis_connection
from .contracts import FNOL, Feedback
from .guardrails import inspect
from .jobs import analyze, save
from .telemetry import setup, INDEX, FRESH, INGEST
from .telemetry import carry,HTTP_REQUESTS
from opentelemetry import trace

setup()
app=FastAPI(title='Motor Insurance FNOL Triage',version='1.0.0',description='Advisory only. Human handlers decide claims.')

def get_redis(): return redis_connection()

@app.exception_handler(RequestValidationError)
async def invalid(request,exc):
    errors=json.loads(json.dumps(exc.errors(),default=str))
    for error in errors:
        error.pop('input',None)
    qid=str(uuid4())
    # Restricted diagnostic storage. Do not persist rejected raw free text / credentials.
    try:
        get_redis().set('quarantine:'+qid,json.dumps({'errors':errors,'time':time.time()}),ex=86400)
    except Exception:
        return JSONResponse(status_code=503,content={'detail':'Quarantine unavailable; no run created'})
    return JSONResponse(status_code=422,content={'quarantine_id':qid,'errors':errors,'agent_started':False})

@app.middleware('http')
async def correlation(request,call_next):
    request.state.correlation_id=str(uuid4())
    try:
        with trace.get_tracer('triage').start_as_current_span('http.'+request.method) as span:
            span.set_attribute('http.route',request.url.path)
            span.set_attribute('correlation_id',request.state.correlation_id)
            response=await call_next(request)
            span.set_attribute('http.status_code',response.status_code)
    except Exception as exc:
        logging.getLogger('triage').exception('request_failed correlation_id=%s',request.state.correlation_id)
        response=JSONResponse(status_code=503,content={'detail':'Service dependency unavailable','correlation_id':request.state.correlation_id})
    route=getattr(request.scope.get('route'),'path','unknown')
    HTTP_REQUESTS.labels(request.method,route,str(response.status_code)).inc()
    response.headers['X-Correlation-ID']=request.state.correlation_id
    return response

RATE_SCRIPT='''local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],60) end; return n'''

@app.get('/',include_in_schema=False)
def home():
    return {'service':'Motor Insurance Claim Research Agent',
            'primary_interface':'python -m app.cli chat',
            'api_docs':'/docs','optional_client':'/client',
            'advisory_only':True}

@app.get('/client',include_in_schema=False)
def optional_client():
    return FileResponse(ROOT/'client'/'index.html')

@app.get('/health')
def health():
    import os
    get_redis().ping()
    if not (DATA/'index'/'metadata.json').exists():
        raise HTTPException(503,'Corpus index missing')
    return {'ok':True,'planner_mode':os.getenv('MODEL_MODE','stub'),
            'semantic_required':os.getenv('SAFETY_REQUIRED','true').lower()=='true'}

@app.get('/metrics',include_in_schema=False)
def metrics():
    path=DATA/'index'/'metadata.json'
    if path.exists():
        metadata=json.loads(path.read_text())
        INDEX.set(metadata['chunks']);FRESH.set(metadata['built_at']);INGEST.set(metadata['chunks_per_second'])
    return Response(generate_latest(),media_type=CONTENT_TYPE_LATEST)

@app.post('/runs',status_code=202)
def submit(fnol:FNOL,request:Request):
    import os
    connection=get_redis()
    # Client address is trustworthy only without an untrusted proxy. See security notes.
    client=hashlib.sha256(request.client.host.encode()).hexdigest()[:20]
    count=connection.eval(RATE_SCRIPT,1,'rate:'+client)
    if count>int(os.getenv('RATE_LIMIT_PER_MINUTE','30')):
        raise HTTPException(429,'Client rate limit; retry next minute')
    f=fnol.model_dump(mode='json')
    issue=inspect(f)
    if issue:
        qid=str(uuid4())
        connection.set('quarantine:'+qid,json.dumps({'guardrail':issue,'time':time.time()}),ex=86400)
        raise HTTPException(503 if issue=='safety_unavailable' else 422,{'quarantine_id':qid,'reason':issue,'agent_started':False})
    run_id=str(uuid4());now=time.time()
    state={'run_id':run_id,'fnol':f,'submitted_at':now,'deadline':now+float(os.getenv('RUN_TIMEOUT_SECONDS','45')),
           'events':[],'passages':[],'tool_calls':0,'steps':0,'correlation_id':request.state.correlation_id}
    carry(state)
    trace.get_current_span().set_attribute('run_id',run_id)
    # Atomic submission pipeline: persist state and enqueue under one Redis transaction.
    q=Queue('analysis',connection=connection)
    with connection.pipeline() as pipe:
        pipe.multi()
        pipe.set('run:'+run_id,json.dumps({'status':'queued','state':state}),ex=86400)
        q.enqueue_call(analyze,args=(state,),timeout=max(1,int(state['deadline']-now)+5),pipeline=pipe)
        pipe.execute()
    return {'run_id':run_id,'status':'queued','poll_path':'/runs/'+run_id}

@app.get('/runs/{run_id}')
def status(run_id:str):
    connection=get_redis()
    raw=connection.get('run:'+run_id)
    if not raw: raise HTTPException(404,'Run not found or retention expired')
    item=json.loads(raw)
    if item['status'] not in ('completed','escalated') and time.time()>item['state']['deadline']:
        from .agents import escalate
        from .jobs import terminal
        state=escalate(item['state'],'worker_or_queue_timeout')
        terminal(connection,state)
        item={'status':'escalated','state':state}
    state=item['state']
    return {'run_id':run_id,'status':item['status'],'result':state.get('proposed'),
            'trace_path':'/runs/'+run_id+'/trace','elapsed_seconds':state.get('completed_at',time.time())-state['submitted_at']}

@app.get('/runs/{run_id}/trace')
def run_trace(run_id:str):
    raw=get_redis().get('run:'+run_id)
    if not raw: raise HTTPException(404,'Unknown run')
    state=json.loads(raw)['state']
    return {'run_id':run_id,'events':state['events'],'retrieved_passages':state.get('passages',[]),
            'verified':state.get('verified',False),'cost_usd':state.get('cost_usd',0),
            'trace_id':state.get('trace_id'),'semantic_report':state.get('semantic_report'),
            'quality':state.get('quality')}

@app.post('/runs/{run_id}/feedback',status_code=201)
def feedback(run_id:str,body:Feedback):
    connection=get_redis()
    if not connection.exists('run:'+run_id): raise HTTPException(404,'Unknown run')
    if inspect(body.model_dump()): raise HTTPException(422,'Feedback guardrail')
    connection.rpush('feedback',json.dumps({'run_id':run_id,**body.model_dump(),'time':time.time()}))
    return {'persisted':True}

@app.get('/quality')
def quality():
    connection=get_redis()
    feedback=[json.loads(x) for x in connection.lrange('feedback',-1000,-1)]
    points=[]
    for rid in connection.zrange('quality:runs',-100,-1):
        raw=connection.get(b'run:'+rid)
        if raw:
            state=json.loads(raw)['state']
            points.append({'time':state['completed_at'],'verified':int(state.get('verified',False)),
                           'cost_usd':state.get('cost_usd',0),'quality':state.get('quality')})
    return {'feedback_count':len(feedback),'satisfactory':sum(x['satisfactory'] for x in feedback),'points':points,
            'note':'Sampled reference-free NLI and semantic relevance scores; not ground-truth claim accuracy.'}
