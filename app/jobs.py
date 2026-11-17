"""Durable RQ handoff: analysis worker -> verification worker -> terminal state."""
import json
import time
from rq import Queue, Retry
from .config import redis_connection
from .agents import analysis_graph, verification_graph, escalate
from .provider import Gateway
from .telemetry import RUN_LATENCY,run_span,carry,TASKS

def save(connection,state,status):
    from redis.exceptions import WatchError
    while True:
        with connection.pipeline() as pipe:
            try:
                pipe.watch('run:'+state['run_id'])
                existing=pipe.get('run:'+state['run_id'])
                if existing and json.loads(existing)['status'] in ('completed','escalated') and status not in ('completed','escalated'):
                    return False
                pipe.multi();pipe.set('run:'+state['run_id'],json.dumps({'status':status,'state':state}),ex=86400)
                pipe.execute();return True
            except WatchError:continue

def terminal(connection,state):
    if state.get('verified') and time.time()>state['deadline']:
        state=escalate(state,'run_deadline_exceeded')
    state['completed_at']=time.time()
    state['cost_usd']=sum(e.get('cost_usd',0) for e in state['events'])
    state['quality']={'pending':True}
    # First terminal writer wins; polling and a late worker must not overwrite each other.
    from redis.exceptions import WatchError
    while True:
        with connection.pipeline() as pipe:
            try:
                pipe.watch('run:'+state['run_id'])
                existing=pipe.get('run:'+state['run_id'])
                if existing and json.loads(existing)['status'] in ('completed','escalated'):
                    return
                pipe.multi()
                pipe.set('run:'+state['run_id'],json.dumps({'status':'completed' if state.get('verified') else 'escalated','state':state}),ex=86400)
                pipe.zadd('quality:runs',{state['run_id']:time.time()})
                pipe.execute();break
            except WatchError:continue
    RUN_LATENCY.observe(state['completed_at'] - state.get('submitted_at', time.time()))
    try:
        Queue('verification', connection=connection).enqueue(score_job, state['run_id'], job_timeout=40)
    except Exception:
        pass

def score_job(run_id):
    from .quality import sample_score
    connection=redis_connection();raw=connection.get('run:'+run_id)
    if not raw:return
    item=json.loads(raw);state=item['state']
    with run_span(state,'quality'):
        state['quality']=sample_score(state)
    save(connection,state,item['status'])

def analyze(state):
    with run_span(state,'analysis'):
        return _analyze(state)

def _analyze(state):
    connection=redis_connection()
    is_inline=bool(state.get('inline'))
    if not save(connection,state,'analyzing'):return
    try:
        if time.time()>state['deadline']:
            raise TimeoutError('queue deadline exhausted')
        state=analysis_graph(gateway=Gateway(connection)).invoke(state)
        if is_inline:
            state['inline']=True
        carry(state)
        TASKS.labels('analysis','escalated' if state.get('failure') else 'success').inc()
        if not save(connection,state,'verifying'):return
        if is_inline:
            return _verify_job(state)
        Queue('verification',connection=connection).enqueue(verify_job,state,job_timeout=max(1,int(state['deadline']-time.time())+5),
            retry=Retry(max=1,interval=[2]))
    except Exception as exc:
        TASKS.labels('analysis','error').inc()
        terminal(connection,escalate(state,type(exc).__name__+': '+str(exc)[:100]))

def verify_job(state):
    with run_span(state,'verification'):
        return _verify_job(state)

def _verify_job(state):
    connection=redis_connection()
    is_inline=bool(state.get('inline'))
    try:
        state=verification_graph().invoke(state)
        if is_inline:
            state['inline']=True
        carry(state)
        TASKS.labels('verification','success' if state.get('verified') else 'refused').inc()
        if not state.get('verified') and not state.get('failure') and not state.get('retried'):
            state['retried']=True
            state['retry_searches']=state.get('searches',0)
            if is_inline:
                save(connection,state,'retrying')
                return _analyze(state)
            Queue('analysis',connection=connection).enqueue(analyze,state,job_timeout=max(1,int(state['deadline']-time.time())+5),
                retry=Retry(max=1,interval=[2]))
            save(connection,state,'retrying')
            return
        if not state.get('verified'):
            state=escalate(state,state.get('failure','verification_failed'))
        terminal(connection,state)
        return state
    except Exception as exc:
        TASKS.labels('verification','error').inc()
        state=escalate(state,'verification_worker_error: '+type(exc).__name__)
        terminal(connection,state)
        return state
