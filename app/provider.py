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

    def choose(self,state,available,context):
        from .config import ROOT
        if len(available)==1 and os.getenv('MODEL_MODE','stub')!='stub':
            # A single compulsory field read has no model decision to evaluate.
            return available[0]
        version=state['fnol']['retrieval_version']
        from .guardrails import inspect
        if inspect(context['fnol']) or any(inspect({'passage':p['text']}) for p in context.get('passages',[])):
            raise ProviderUnavailable('untrusted_context_guardrail')
        system=(ROOT/'prompts'/f'analysis_{version}.txt').read_text()
        payload={'agent':'analysis','stage':context['stage'],'available':available,
                 'context':context,'model':os.getenv('MODEL_ID',''),
                 'messages':[{'role':'system','content':system},
                             {'role':'user','content':json.dumps(context)}]}
        if os.getenv('MODEL_MODE','stub')!='stub':
            # Bounded evidence view; full source is retained in the audit state.
            view={'stage':context['stage'],'description':context['fnol']['description'],
                  'risk':context['risk'],'passages':[p['text'][:140] for p in context.get('passages',[])[:3]]}
            view['available_actions']=available
            if version=='v4':
                view['passages']=[{'id':p['clause_id'],'text':p['text'][:140]} for p in context.get('passages',[])[:3]]
                view['tool_catalog']={'corpus_search':'Find cover or modifying clauses.',
                    'clause_lookup':'Inspect an already retrieved source; identifier supplied automatically.',
                    'finish':'Research complete: hand off draft for independent verification.',
                    'escalate':'Research tools failed; not a coverage decision.'}
                view['objective']={'fields_read':'Find a policy provision applying to the reported event.',
                    'base_read':'Find the exceptions or use limitations modifying the apparent cover.',
                    'modifiers_read':'Inspect an original source passage before handing off the research.',
                    'clause_read':'Hand the researched clauses to the independent verifier.'}.get(context['stage'],'Read the request fields.')
            payload['messages'][-1]['content']=json.dumps(view)
            payload.update(temperature=0,max_tokens=100,response_format={'type':'json_schema','json_schema':{
                'name':'planner_action','strict':True,'schema':{'type':'object','properties':{
                    'action':{'type':'string','enum':available}},'required':['action'],'additionalProperties':False}}})
        raw=self.call(state,'analysis',payload)
        if 'choices' in raw:
            raw=json.loads(raw['choices'][0]['message']['content'])
        action=raw.get('action')
        if action not in available:
            raise ProviderUnavailable('invalid provider action')
        return action
