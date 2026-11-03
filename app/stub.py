"""Delayed deterministic planner for system tests; never presented as an LLM."""
import asyncio
import os
from fastapi import FastAPI, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from .telemetry import setup
from opentelemetry import trace
from opentelemetry.propagate import extract

setup()
app=FastAPI(title='Fixed-response model stub')
@app.middleware('http')
async def tracing(request,call_next):
    with trace.get_tracer('triage').start_as_current_span('stub.'+request.url.path,context=extract(dict(request.headers)),kind=trace.SpanKind.SERVER) as span:
        for key in ('run_id','correlation_id'):
            value=request.headers.get('X-'+key.replace('_','-'))
            if value:span.set_attribute(key,value)
        return await call_next(request)
@app.get('/health')
def health(): return {'ok':True,'mode':'stub'}
@app.get('/metrics')
def metrics(): return Response(generate_latest(),media_type=CONTENT_TYPE_LATEST)
@app.post('/v1/chat/completions')
async def complete(payload:dict):
    await asyncio.sleep(float(os.getenv('STUB_DELAY_SECONDS','0.35')))
    if os.getenv('STUB_FAIL','false').lower()=='true':
        return Response(status_code=503)
    stage=payload['stage'];version=payload['context']['version']
    if version=='v5':
        context=payload['context'];history=context.get('history',[])
        searches=sum(x['action']=='corpus_search' for x in history)
        if not history:action,argument='request_fields','*'
        elif not searches:action,argument='corpus_search','SECTION I accidental external means loss damage vehicle'
        elif searches==1:action,argument='corpus_search','general exceptions limitations as to use hire reward claims documents repair estimate'
        elif not any(x['action']=='clause_lookup' for x in history):
            action,argument='clause_lookup',context['evidence'][0]['clause_id']
        else:action,argument='finish',''
        return {'action':action,'argument':argument,'purpose':'Deterministic system-test action; no AI reasoning.',
                'usage':{'prompt_tokens':0,'completion_tokens':0},'mode':'stub'}
    action={'initial':'request_fields','fields_read':'corpus_search','base_read':'corpus_search' if version in ('v2','v3','v4') else 'finish',
            'modifiers_read':'clause_lookup','clause_read':'finish','retry_read':'finish'}.get(stage,'escalate')
    return {'action':action,'usage':{'prompt_tokens':0,'completion_tokens':0},'mode':'stub'}
