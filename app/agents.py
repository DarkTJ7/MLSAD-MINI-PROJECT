import json
import os
import re
import time
from typing import TypedDict, Any
from langgraph.graph import StateGraph, END
from .contracts import FNOL, Recommendation
from .guardrails import inspect, output_safe
from .provider import Gateway
from .retrieval import Corpus, get_corpus
from .telemetry import step

class State(TypedDict, total=False):
    run_id: str
    fnol: dict
    deadline: float
    events: list
    passages: list
    tool_calls: int
    steps: int
    stage: str
    action: str
    classification: str
    risk: list
    proposed: dict
    verified: bool
    failure: str
    verification_reason: str
    submitted_at: float
    completed_at: float
    correlation_id: str
    retried: bool
    semantic_report: dict
    trace_carrier: dict
    trace_id: str
    quality: dict
    decision: dict
    research_history: list
    observation: dict
    searches: int
    retry_searches: int
    narrative_audit: dict
    research_prompt_version: str
    inline: bool

def classify(f):
    text=f['description'].lower()
    if any(x in text for x in ['stolen','theft','burglary']):
        return 'theft'
    if f['estimated_repair']>.75*f['idv']:
        return 'total_loss'
    if f['third_party_involved']:
        return 'third_party'
    return 'own_damage'

def risks(f):
    text=f['description'].lower()
    found=[]
    if f['vehicle_use'] in ('delivery','hire_reward') or re.search(r'food delivery|delivery run|uber|taxi|paid deliveries|delivering (food|parcels)',text):
        found.append('restricted_use')
    if f['driver_licensed'] is False or 'without a licen' in text:
        found.append('licence')
    if f['intoxicated'] is True or re.search(r'drunk|intoxicated|under the influence',text):
        found.append('intoxication')
    if re.search(r'wear and tear|wear & tear|mechanical breakdown|electrical breakdown',text):
        found.append('breakdown')
    if f['country'].lower()!='india':
        found.append('geography')
    if not f['policy_start']<=f['loss_date']<=f['policy_end']:
        found.append('period')
    return found

def out_of_scope(f):
    return f['insurer'].lower()!='hdfc ergo' or f['product']!='private_car_package' or bool(re.search(
        r'health insurance|hospital bill|crop|marine|travel insurance|battery degradation|engine protect|zero depreciation|\badd.on\b',f['description'],re.I))

def escalate(state,reason):
    state['verified']=False
    state['failure']=reason
    state['proposed']={'recommendation_only':True,'classification':state.get('classification',classify(state['fnol'])),
        'coverage_position':'insufficient_evidence','queue':'investigation',
        'reason':'Human claims review required: '+reason+'. No claim determination is made.',
        'requires_human':True,'escalation':'Claims handler: obtain the policy schedule, endorsements and missing evidence.',
        'citations':[],'verified':False,'prompt_version':state.get('research_prompt_version',state['fnol']['retrieval_version']),
        'limitations':['Advisory only. No approval, rejection or settlement calculation.']}
    return state

def analysis_graph(corpus=None,gateway=None):
    """Current agent only: model-chosen read-only tools, then bounded drafting."""
    from .research_agent import plan_research,use_tool
    corpus=corpus or get_corpus()
    gateway=gateway or Gateway()

    def plan(state):
        return plan_research(state,corpus,gateway)

    def tools(state):
        return use_tool(state,corpus,gateway)

    def draft(state):
        with step(state,'analysis','draft'):
            state['proposed']=make_recommendation(state)
        return state

    def route(state):
        if state.get('failure'):return END
        return 'draft' if state.get('action')=='finish' else 'tools'

    graph=StateGraph(State)
    graph.add_node('plan',plan)
    graph.add_node('tools',tools)
    graph.add_node('draft',draft)
    graph.set_entry_point('plan')
    graph.add_conditional_edges('plan',route,{'tools':'tools','draft':'draft',END:END})
    graph.add_conditional_edges('tools',lambda state:END if state.get('failure') else 'plan',{'plan':'plan',END:END})
    graph.add_edge('draft',END)
    return graph.compile().with_config(recursion_limit=40)

PATTERNS={
 'base':r'accidental external means|burglary housebreaking|loss or damage to the vehicle',
 'third_party':r'legally liable|liability to third parties',
 'total_loss':r'exceeds 75%',
 'restriction':r'usage on hire|limitations as to use',
 'exclusion':r'consequential loss|intoxicating liquor|geographical area',
 'procedure':r'claim process|repair estimate|claims documents',
 'use_clause':r'limitations as to use',
 'intoxication_clause':r'under the influence of intoxicating',
 'breakdown_clause':r'mechanical or electrical breakdown',
 'licence_clause':r'without a valid licen',
}

def evidence(state,concept):
    pattern=re.compile(PATTERNS[concept],re.I)
    preference={'base':2,'third_party':2,'total_loss':2,'restriction':1,'exclusion':3,'procedure':1,
                'use_clause':3,'intoxication_clause':2,'breakdown_clause':2,'licence_clause':1}
    rows=sorted(state.get('passages',[]),key=lambda p:(p['page']!=preference[concept],p['clause_id']))
    for p in rows:
        match=pattern.search(p['text'])
        if match:
            # Exact source substring; page and chunk resolve without fabricated numbering.
            return {'clause_id':p['clause_id'],'document':p['document'],'page':p['page'],
                    'quote':p['text']}
    return None

def make_recommendation(state):
    f=state['fnol']
    kind=state.get('classification') or classify(f)
    risk=state.get('risk') if 'risk' in state else risks(f)
    concepts=['third_party' if kind=='third_party' else 'base','exclusion','procedure']
    if kind=='total_loss': concepts.append('total_loss')
    if 'restricted_use' in risk: concepts+=['restriction','use_clause']
    for item in ('intoxication','breakdown','licence'):
        if item in risk:concepts.append(item+'_clause')
    citations=[evidence(state,c) for c in concepts]
    if any(c is None for c in citations):
        escalate(state,'required_clause_missing')
        return state['proposed']
    unique={c['clause_id']:c for c in citations}
    position='potentially_covered'
    reason='A listed cover may apply, subject to exclusions, the schedule and human verification.'
    queue='fast-track' if kind=='own_damage' and f['network_garage'] and f['estimated_repair']<=float(os.getenv('FAST_TRACK_THRESHOLD','20000')) else 'surveyor assignment'
    escalation='A human handler must verify the schedule, facts and applicable endorsements.'
    if risk:
        position='coverage_concern'; queue='investigation'
        reason='Review required for '+', '.join(risk)+'. Retrieved cover is subject to restrictions; this is not a claim determination.'
    if f['driver_licensed'] is None or f['intoxicated'] is None or f['vehicle_use']=='unknown':
        position='insufficient_evidence';queue='investigation'
        reason='Driver eligibility or vehicle-use facts are missing; obtain them before recommending a coverage position.'
    return {'recommendation_only':True,'classification':kind,'coverage_position':position,'queue':queue,
            'reason':reason,'requires_human':True,'escalation':escalation,'citations':list(unique.values()),
            'verified':False,'prompt_version':state.get('research_prompt_version',f['retrieval_version']),
            'limitations':['Policy schedule and activated endorsements are not in this public corpus.',
                          'Fast-track threshold is an operational demo assumption, not a policy entitlement.',
                          'Local lexical embeddings and rule-based drafting have limited language understanding.']}

def verify(state,corpus=None):
    corpus=corpus or get_corpus()
    details={}
    with step(state,'verification','verify',details):
        proposal=state.get('proposed',{})
        if state.get('failure'):
            return state
        passed=bool(proposal.get('citations')) and output_safe(proposal.get('reason',''))
        details['initial_checks']=bool(passed)
        retrieved={p['clause_id']:p for p in state.get('passages',[])}
        for citation in proposal.get('citations',[]):
            source=retrieved.get(citation['clause_id'])
            canonical=corpus.lookup(citation['clause_id'])
            passed=passed and bool(source and citation['quote'] in source['text'] and
                canonical and source['text']==canonical['text'] and
                citation['page']==source['page'] and citation['document']==source['document'])
        # Drafts are constrained templates. Refuse novel or tampered narrative/decisions,
        # even when the attached quote itself is a valid source substring.
        import copy
        expected=make_recommendation(copy.deepcopy(state))
        details['template_mismatches']=[k for k in ('classification','coverage_position','queue','reason','requires_human','recommendation_only') if proposal.get(k)!=expected.get(k)]
        passed=passed and all(proposal.get(k)==expected.get(k) for k in
            ('classification','coverage_position','queue','reason','requires_human','recommendation_only'))
        # Independent checks against FNOL and full retrieved text catch a missed modifier.
        text=' '.join(c['quote'] for c in proposal.get('citations',[])).lower()
        if 'restricted_use' in risks(state['fnol']):
            passed=passed and bool(re.search(PATTERNS['restriction'],text,re.I)) and proposal.get('coverage_position')=='coverage_concern'
        if risks(state['fnol']) and proposal.get('coverage_position')=='potentially_covered':
            passed=False
        if time.time()>state['deadline']:
            passed=False
            details['deadline_exceeded']=True
        try:
            Recommendation.model_validate(proposal)
        except Exception as exc:
            passed=False
            details['schema_error']=str(exc)[:250]
        if passed:
            from .semantic import verify_claims
            try:state['semantic_report']=verify_claims(state)
            except Exception:state['semantic_report']={'passed':False,'reason':'semantic_service_unavailable'}
            details['semantic']=state['semantic_report']
            passed=bool(state['semantic_report']['passed'])
        state['verified']=bool(passed)
        state['proposed']['verified']=bool(passed)
        details['verified']=bool(passed)
        details['citations_checked']=len(proposal.get('citations',[]))
        if not passed:
            state['verification_reason']='unsupported_or_incomplete_evidence'
            if state['fnol']['retrieval_version']=='v5':
                state['verification_reason']=json.dumps({
                    'request':'Search again using a different query; supply canonical clauses for these unsupported propositions or escalate.',
                    'template_mismatches':details.get('template_mismatches',[]),
                    'unsupported_propositions':[c.get('hypothesis') for c in state.get('semantic_report',{}).get('claims',[]) if not c.get('supported')],
                    'citations_checked':details['citations_checked'],
                    'reason':state.get('semantic_report',{}).get('reason','source_or_evidence_check_failed')})
    return state

def verification_graph(corpus=None):
    graph=StateGraph(State)
    graph.add_node('verify',lambda state:verify(state,corpus))
    graph.set_entry_point('verify');graph.add_edge('verify',END)
    return graph.compile()

def run_local(fnol,run_id='local',gateway=None,corpus=None):
    """Same agent graphs, inline handoff for offline evaluation only."""
    corpus=corpus or get_corpus()
    state={'run_id':run_id,'fnol':FNOL.model_validate(fnol).model_dump(mode='json'),
           'deadline':time.time()+float(os.getenv('RUN_TIMEOUT_SECONDS','45')),'events':[],'passages':[],'tool_calls':0,'steps':0}
    try:
        state=analysis_graph(corpus,gateway).invoke(state)
        state=verification_graph(corpus).invoke(state)
        if not state.get('verified') and not state.get('failure'):
            state['retry_searches']=state.get('searches',0)
            # A verifier refusal requires a different research search before retrying.
            state=analysis_graph(corpus,gateway).invoke(state)
            state=verification_graph(corpus).invoke(state)
        if not state.get('verified'):
            state=escalate(state,state.get('failure','verification_failed'))
    except Exception as exc:
        state=escalate(state,type(exc).__name__+': '+str(exc)[:100])
    return state
