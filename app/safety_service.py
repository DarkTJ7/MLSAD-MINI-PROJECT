import time
from fastapi import FastAPI,Response,HTTPException
from pydantic import BaseModel,Field
from prometheus_client import Counter,Histogram,generate_latest,CONTENT_TYPE_LATEST
from .safety_models import screen,entail,classifier,encoder,relevance
from .telemetry import setup
from opentelemetry import trace
from opentelemetry.propagate import extract

setup()
app=FastAPI(title='Independent safety and entailment service')
@app.middleware('http')
async def tracing(request,call_next):
    with trace.get_tracer('triage').start_as_current_span('safety.'+request.url.path,context=extract(dict(request.headers)),kind=trace.SpanKind.SERVER):
        return await call_next(request)
CALLS=Counter('triage_safety_calls_total','Safety inference calls',['kind','outcome'])
SECONDS=Histogram('triage_safety_seconds','Safety inference latency',['kind'])
class Scan(BaseModel):text:str=Field(max_length=16000)
class Entailment(BaseModel):
    premise:str=Field(min_length=1,max_length=16000)
    hypothesis:str=Field(min_length=1,max_length=1000)
class Relevance(BaseModel):
    query:str=Field(min_length=1,max_length=4000)
    passages:list[str]=Field(max_length=30)
def invoke(kind,func):
    started=time.monotonic()
    try:
        result=func();CALLS.labels(kind,'success').inc();return result
    except Exception:
        CALLS.labels(kind,'error').inc();raise HTTPException(503,'Safety model unavailable')
    finally:SECONDS.labels(kind).observe(time.monotonic()-started)
@app.get('/health')
def health():
    for kind in ('nli','injection','toxicity'):classifier(kind)
    encoder()
    return {'ok':True,'models':4}
@app.get('/metrics')
def metrics():return Response(generate_latest(),media_type=CONTENT_TYPE_LATEST)
@app.post('/screen')
def scan(body:Scan):return invoke('screen',lambda:screen(body.text))
@app.post('/entail')
def nli(body:Entailment):return invoke('entail',lambda:entail(body.premise,body.hypothesis))
@app.post('/relevance')
def context_relevance(body:Relevance):return invoke('relevance',lambda:relevance(body.query,body.passages))
