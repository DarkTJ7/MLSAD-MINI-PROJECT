"""Bounded provider gateway. Stub is reproducible; live mode uses runtime URL/model."""
import json
import os
import time
import httpx
from .http_client import post
from .config import required
from .telemetry import COST, RETRIES

class ProviderUnavailable(RuntimeError):
    pass

class Gateway:
    def __init__(self, connection=None):
        self.connection=connection
        self.failures=0
        self.open_until=0

    def call(self, state, agent, payload):
        key='provider:circuit'
        open_until=float(self.connection.get(key) or 0) if self.connection else self.open_until
        if open_until>time.time():
            raise ProviderUnavailable('circuit_open')
        response=None
        started=time.monotonic()
        errors=[]
        attempts=0
        for attempt in range(3):
            attempts+=1
            if time.time()>state['deadline']:
                raise ProviderUnavailable('run_deadline')
            try:
                remaining=max(.01,min(float(os.getenv('MODEL_TIMEOUT_SECONDS','8')),state['deadline']-time.time()))
                api_key=os.getenv('MODEL_API_KEY','')
                headers={'Authorization':'Bearer '+api_key} if api_key else {}
                wire=payload
                if os.getenv('MODEL_MODE','stub')!='stub':
                    wire={k:v for k,v in payload.items() if k in ('model','messages','temperature','max_tokens','response_format')}
                response=post(required('MODEL_URL'), json=wire, timeout=remaining,headers=headers)
                response.raise_for_status()
                response=response.json()
                if self.connection:
                    self.connection.delete('provider:failures',key)
                self.failures=0
                break
            except (httpx.HTTPError, ValueError) as exc:
                errors.append(type(exc).__name__)
                if attempt<2:
                    RETRIES.labels(agent).inc()
                    time.sleep(min(.1*2**attempt,max(0,state['deadline']-time.time())))
        event={'agent':agent,'step':'provider','seconds':time.monotonic()-started,
               'attempts':attempts,'errors':errors,'prompt_tokens':0,'completion_tokens':0,
               'cost_usd':0.0,'usage_source':'stub' if os.getenv('MODEL_MODE','stub')=='stub' else 'provider',
               'prompt_version':payload.get('prompt_version',state['fnol']['retrieval_version'])}
        if response is None or not isinstance(response,dict):
            failures=int(self.connection.incr('provider:failures')) if self.connection else self.failures+1
            self.failures=failures
            if failures>=int(os.getenv('CIRCUIT_FAILURE_THRESHOLD','2')):
                until=time.time()+float(os.getenv('CIRCUIT_COOLDOWN_SECONDS','20'))
                if self.connection:
                    self.connection.set(key,until,ex=60)
                self.open_until=until
            state.setdefault('events',[]).append(event)
            raise ProviderUnavailable('provider_unavailable')
        usage=response.get('usage',{})
        event['prompt_tokens']=int(usage.get('prompt_tokens',0))
        event['completion_tokens']=int(usage.get('completion_tokens',0))
        if os.getenv('MODEL_MODE','stub')!='stub':
            if not usage or 'INPUT_USD_PER_MILLION' not in os.environ or 'OUTPUT_USD_PER_MILLION' not in os.environ:
                raise ProviderUnavailable('live usage or runtime prices unavailable')
            event['cost_usd']=(event['prompt_tokens']*float(os.environ['INPUT_USD_PER_MILLION'])+
                              event['completion_tokens']*float(os.environ['OUTPUT_USD_PER_MILLION']))/1000000
        COST.labels(agent).inc(event['cost_usd'])
        state.setdefault('events',[]).append(event)
        return response
