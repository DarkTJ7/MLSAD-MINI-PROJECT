"""Model-authored tool calls, bounded execution and observable research memory."""
import json
import os
import time
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from .provider import ProviderUnavailable
from .telemetry import step, TOOLS
from .guardrails import inspect

class Decision(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    action: Literal['request_fields','corpus_search','clause_lookup','finish','escalate']
    argument: str = Field(max_length=160)
    purpose: str = Field(min_length=1,max_length=100)

class NarrativeUse(BaseModel):
    """Conservative, source-quoted interpretation of the incident narrative."""
    model_config=ConfigDict(extra='forbid',strict=True)
    narrative_use: Literal['delivery','hire_reward','private_or_business','unknown']
    evidence_phrase: str = Field(max_length=160)

RESEARCH_PROMPTS={'v5a':'analysis_v5.txt','v5b':'analysis_v5b.txt'}

def research_prompt():
    from .config import ROOT
    variant=os.getenv('RESEARCH_PROMPT_VARIANT','v5b').strip().lower()
    if variant not in RESEARCH_PROMPTS:
        raise ValueError('RESEARCH_PROMPT_VARIANT must be v5a or v5b')
    return variant,(ROOT/'prompts'/RESEARCH_PROMPTS[variant]).read_text(encoding='utf-8')

def audit_narrative(state,gateway):
    """Ask the model once about vehicle use; never erase deterministic risk flags."""
    if 'narrative_audit' in state:
        return
    from .config import ROOT
    description=state['fnol']['description']
    audit={'narrative_use':'unknown','evidence_phrase':'','source':'stub'}
    if os.getenv('MODEL_MODE','stub')!='stub':
        payload={'model':os.getenv('MODEL_ID',''),
            'agent':'intake','stage':'narrative_use','prompt_version':'intake_audit_v1',
            'messages':[{'role':'system','content':(ROOT/'prompts/intake_audit_v1.txt').read_text()},
                        {'role':'user','content':json.dumps({'incident_description':description})}],
            'temperature':0,'max_tokens':100,
            'response_format':{'type':'json_schema','json_schema':{
                'name':'narrative_use_audit','strict':True,'schema':NarrativeUse.model_json_schema()}}}
        raw=gateway.call(state,'intake',payload)
        if 'choices' in raw:
            raw=json.loads(raw['choices'][0]['message']['content'])
        audit=NarrativeUse.model_validate(raw).model_dump()
        phrase=audit['evidence_phrase'].strip()
        # The model may flag a concern only when it quotes the claimant's own words.
        if audit['narrative_use'] in ('delivery','hire_reward'):
            if len(phrase)<4 or phrase.casefold() not in description.casefold():
                audit={'narrative_use':'unknown','evidence_phrase':'',
                       'source':'model','status':'unverified_phrase'}
            else:
                audit['source']='model';audit['status']='quoted_signal'
        else:
            audit={'narrative_use':audit['narrative_use'],'evidence_phrase':'',
                   'source':'model','status':'no_commercial_signal'}
    structured=state['fnol']['vehicle_use']
    audit['structured_vehicle_use']=structured
    audit['field_conflict']=audit['narrative_use'] in ('delivery','hire_reward') and structured in ('personal','commute','business')
    state['narrative_audit']=audit
    if audit['narrative_use'] in ('delivery','hire_reward') and 'restricted_use' not in state['risk']:
        state['risk'].append('restricted_use')

def checkpoint(state,gateway):
    if getattr(gateway,'connection',None) is not None:
        from .jobs import save
        save(gateway.connection,state,'analyzing')

def missing_evidence(state):
    from .agents import evidence
    concepts=['third_party' if state['classification']=='third_party' else 'base','exclusion','procedure']
    if state['classification']=='total_loss':concepts.append('total_loss')
    if 'restricted_use' in state['risk']:concepts+=['restriction','use_clause']
    for risk in ('intoxication','breakdown','licence'):
        if risk in state['risk']:concepts.append(risk+'_clause')
    return [c for c in concepts if evidence(state,c) is None]

def modifier_search_complete(state):
    if 'restricted_use' not in state.get('risk',[]):
        return True
    return any(h['action']=='corpus_search' and
        any(word in h['argument'].casefold() for word in ('use','hire','reward','limitation','commercial','delivery'))
        for h in state.get('research_history',[]))

def decide(state,gateway):
    from .config import ROOT
    variant,system_prompt=research_prompt()
    state['research_prompt_version']=variant
    schema=Decision.model_json_schema()
    history=state.get('research_history',[])
    revision_due=bool(state.get('verification_reason')) and state.get('searches',0)<=state.get('retry_searches',-1)
    available=['corpus_search']
    # Preserve an attempt to investigate a modifier before voluntary abstention.
    # Safety, scope, time and tool-budget failures still escalate immediately.
    if (state.get('searches',0)>=3 and modifier_search_complete(state)) or state.get('tool_calls',0)>=6:
        available.append('escalate')
    if not any(h['action']=='request_fields' for h in history):available.append('request_fields')
    if state.get('passages'):available.append('clause_lookup')
    if not revision_due and state.get('searches',0)>=2 and not missing_evidence(state) and modifier_search_complete(state) and any(h['action']=='clause_lookup' and h.get('ok') for h in history):available.append('finish')
    schema['properties']['action']['enum']=available
    missing=missing_evidence(state)
    meanings={'base':'accidental loss or damage cover','exclusion':'general policy exclusions',
        'procedure':'claim procedure and required documents','restriction':'hire/reward use restrictions',
        'use_clause':'limitations as to use','third_party':'third party legal liability',
        'total_loss':'constructive total loss definition','intoxication_clause':'alcohol exclusion',
        'breakdown_clause':'mechanical breakdown exclusion','licence_clause':'driving licence condition'}
    if revision_due:objective='The independent verifier refused the draft. Make a DIFFERENT search addressing verifier_feedback before finishing, or escalate.'
    elif missing:objective='Research this evidence gap with a short targeted query: '+meanings.get(missing[0],missing[0])+'. Defer the other topics until the next turn.'
    elif not modifier_search_complete(state):objective='Search specifically for private-car limitations as to use or hire/reward restrictions before finishing.'
    elif state.get('searches',0)<2:objective='Cover was found. Make a DIFFERENT targeted search for modifying exceptions, vehicle-use restrictions or conditions.'
    elif not any(h['action']=='clause_lookup' and h.get('ok') for h in history):objective='Evidence topics are present. Use clause_lookup to inspect one exact clause_id from the evidence.'
    else:objective='Evidence is ready. Use finish to hand off to the independent verifier, unless a new specific gap needs research.'
    context={'claim':state['fnol'],'risk_flags':state['risk'],
        'narrative_audit':state.get('narrative_audit'),
        'history':state.get('research_history',[]),'last_observation':state.get('observation',{}),
        'research_objective':objective,'missing_evidence':[meanings.get(k,k) for k in missing],
        'verifier_feedback':state.get('verification_reason'),
        'available_tools':available,
        'remaining_tool_calls':10-state.get('tool_calls',0),
        'evidence':[{'clause_id':p['clause_id'],'text':p['text'][:450]} for p in state.get('passages',[])[-12:]]}
    raw=gateway.call(state,'analysis',{'model':os.getenv('MODEL_ID',''),
        'agent':'analysis','stage':'research','context':{'version':'v5',**context},
        'prompt_version':variant,
        'messages':[{'role':'system','content':system_prompt},
                    {'role':'user','content':json.dumps(context)+'\nNEXT RESEARCH OBJECTIVE: '+objective}],
        'temperature':0,'max_tokens':150,'response_format':{'type':'json_schema','json_schema':{
            'name':'research_tool_call','strict':True,'schema':schema}}})
    if 'choices' in raw:raw=json.loads(raw['choices'][0]['message']['content'])
    else:raw={k:raw[k] for k in ('action','argument','purpose') if k in raw}
    result=Decision.model_validate(raw).model_dump()
    if result['action'] not in available:raise ProviderUnavailable('unavailable_tool')
    if result['action']=='finish':
        # The final explanation comes from verified policy evidence, never from
        # a planner's free-text purpose or accidental echoed policy fragment.
        result['argument']=''
        result['purpose']='Hand gathered evidence to the independent verifier'
    return result

def plan_research(state,corpus,gateway):
    from .agents import classify,risks,escalate,out_of_scope
    state['steps']=state.get('steps',0)+1
    if time.time()>state['deadline'] or state['steps']>14 or state.get('tool_calls',0)>=10:
        return escalate(state,'research_budget_exhausted')
    if inspect(state['fnol']):return escalate(state,'input_guardrail')
    if out_of_scope(state['fnol']):return escalate(state,'outside_corpus')
    state['classification']=classify(state['fnol'])
    state['risk']=risks(state['fnol'])
    if 'narrative_audit' not in state:
        details={}
        with step(state,'intake','narrative_audit',details):
            audit_narrative(state,gateway)
            details.update(state['narrative_audit'])
    elif state['narrative_audit'].get('narrative_use') in ('delivery','hire_reward') and 'restricted_use' not in state['risk']:
        state['risk'].append('restricted_use')
    details={}
    with step(state,'analysis','decision',details):
        decision=decide(state,gateway)
        # Only the argument reaches a tool. A flagged display-purpose is
        # replaced, while an unsafe argument or unavailable guard stays fatal.
        argument_issue=inspect({'tool_argument':decision['argument']})
        if argument_issue:raise ProviderUnavailable('tool_argument_guardrail: '+argument_issue)
        purpose_issue=inspect({'purpose':decision['purpose']})
        if purpose_issue=='safety_unavailable':raise ProviderUnavailable('purpose_guardrail_unavailable')
        if purpose_issue:decision['purpose']='Inspect policy evidence'
        state['decision']=decision;state['action']=decision['action'];details.update(decision)
        if decision['action']=='escalate':
            return escalate(state,'research_agent_escalated: '+decision['argument'])
        if decision['action']=='finish':
            history=state.get('research_history',[])
            if state.get('searches',0)<2 or not modifier_search_complete(state) or not any(h['action']=='clause_lookup' and h.get('ok') for h in history):
                state['observation']={'error':'Research incomplete. Search cover and modifiers explicitly, then inspect an evidence clause.'}
                state['action']='research_feedback'
            elif missing_evidence(state):
                state['observation']={'error':'Required evidence missing. Search these concepts or escalate.','missing':missing_evidence(state)}
                state['action']='research_feedback'
    checkpoint(state,gateway)
    return state

def use_tool(state,corpus,gateway):
    from .agents import escalate
    if state['action']=='research_feedback':return state
    decision=state['decision'];name=decision['action'];arg=decision['argument'].strip()
    state['tool_calls']=state.get('tool_calls',0)+1
    TOOLS.labels('analysis',name).inc()
    details={'tool':name,'argument':arg,'purpose':decision['purpose']}
    history=state.setdefault('research_history',[])
    with step(state,'analysis','tool',details):
        if time.time()>state['deadline']:return escalate(state,'tool_deadline_exceeded')
        if any(h['action']==name and h['argument']==arg for h in history):
            observation={'error':'Repeated call refused. Choose a different query or a different tool.'}
        elif name=='request_fields':
            keys=list(state['fnol']) if arg=='*' else [s.strip().removeprefix('claim.') for s in arg.split(',')]
            observation={'fields':{k:state['fnol'][k] for k in keys if k in state['fnol']},
                         'unknown_fields':[k for k in keys if k not in state['fnol']],
                         'available_fields':list(state['fnol'])}
        elif name=='corpus_search':
            if not arg:observation={'error':'A nonempty search query is required.'}
            else:
                candidates=corpus.search(arg,k=6);state['searches']=state.get('searches',0)+1
                rows=[];quarantined=[]
                for row in candidates:
                    issue=inspect({'passage':row['text']})
                    if issue=='safety_unavailable':return escalate(state,'safety_unavailable')
                    if issue:quarantined.append({'clause_id':row['clause_id'],'reason':issue})
                    else:rows.append(row)
                by_id={p['clause_id']:p for p in state.get('passages',[])+rows}
                state['passages']=list(by_id.values())
                observation={'passages':[{'clause_id':r['clause_id'],'text':r['text'][:450]} for r in rows],
                             'missing_evidence':missing_evidence(state),'quarantined_sources':len(quarantined)}
                details['query']=arg;details['passages']=rows
                details['quarantined_sources']=quarantined
        elif name=='clause_lookup':
            allowed={p['clause_id'] for p in state.get('passages',[])}
            row=corpus.lookup(arg) if arg in allowed else None
            if row and inspect({'passage':row['text']}):return escalate(state,'retrieved_passage_guardrail')
            observation={'clause':row} if row else {'error':'Choose an exact clause_id from retrieved evidence.'}
            details['clause_id']=arg;details['result']=row
        else:observation={'error':'Tool is not allowed.'}
        if time.time()>state['deadline']:return escalate(state,'tool_deadline_exceeded')
        state['observation']=observation;details['observation']=observation
        history.append({'action':name,'argument':arg,'ok':'error' not in observation})
    checkpoint(state,gateway)
    return state
