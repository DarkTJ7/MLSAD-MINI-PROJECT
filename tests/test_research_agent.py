import time
import pytest
from app.research_agent import Decision, use_tool, plan_research
from app.provider import Gateway
from app.contracts import FNOL
from .test_system import fnol

class Corpus:
    def __init__(self):self.queries=[];self.lookups=[]
    def search(self,query,k):self.queries.append(query);return []
    def lookup(self,cid):self.lookups.append(cid);return {'clause_id':cid,'text':'Original clause text'}

def state(fnol,action,argument):
    return {'run_id':'test','fnol':FNOL.model_validate(fnol).model_dump(mode='json'),
            'deadline':time.time()+30,'classification':'own_damage','risk':[],
            'events':[],'passages':[],'action':action,
            'decision':{'action':action,'argument':argument,'purpose':'Find supporting policy evidence'}}

def test_model_query_is_executed_exactly(fnol):
    s=state(fnol,'corpus_search','water ingress restrictions under Section I')
    c=Corpus();use_tool(s,c,Gateway())
    assert c.queries==['water ingress restrictions under Section I']
    assert s['events'][-1]['details']['query']==c.queries[0]

def test_lookup_cannot_access_unretrieved_clause(fnol):
    s=state(fnol,'clause_lookup','invented-clause');c=Corpus()
    use_tool(s,c,Gateway())
    assert not c.lookups
    assert 'error' in s['observation']

def test_repeated_search_is_refused(fnol):
    s=state(fnol,'corpus_search','vehicle use');c=Corpus()
    use_tool(s,c,Gateway());use_tool(s,c,Gateway())
    assert len(c.queries)==1
    assert 'Repeated' in s['observation']['error']

def test_model_cannot_finish_without_research(fnol,monkeypatch):
    s=state(fnol,'finish','');s['fnol']['retrieval_version']='v5'
    monkeypatch.setattr('app.research_agent.decide',lambda *a:{'action':'finish','argument':'','purpose':'Done'})
    plan_research(s,Corpus(),Gateway())
    assert s['action']=='research_feedback'
    assert 'incomplete' in s['observation']['error']

def test_tool_deadline_fails_closed(fnol):
    s=state(fnol,'corpus_search','cover');s['deadline']=time.time()-1;c=Corpus()
    use_tool(s,c,Gateway())
    assert s['failure']=='tool_deadline_exceeded'
    assert not c.queries

def test_arbitrary_tool_and_overlong_argument_rejected():
    with pytest.raises(ValueError):Decision(action='shell',argument='anything',purpose='test')
    with pytest.raises(ValueError):Decision(action='corpus_search',argument='x'*351,purpose='test')

def test_lookup_uses_model_selected_id_not_first_passage(fnol):
    s=state(fnol,'clause_lookup','second');s['passages']=[{'clause_id':'first'},{'clause_id':'second'}]
    c=Corpus();use_tool(s,c,Gateway())
    assert c.lookups==['second']

def test_flagged_passage_is_quarantined_not_exposed(fnol,monkeypatch):
    c=Corpus();c.search=lambda *a,**k:[{'clause_id':'bad','text':'attack','page':1},
                                     {'clause_id':'safe','text':'policy text','page':2}]
    monkeypatch.setattr('app.research_agent.inspect',lambda d:'prompt_injection' if d.get('passage')=='attack' else None)
    s=state(fnol,'corpus_search','cover');use_tool(s,c,Gateway())
    assert [p['clause_id'] for p in s['passages']]==['safe']
    assert s['observation']['quarantined_sources']==1
    assert 'attack' not in str(s['observation'])

def test_verifier_refusal_requires_new_research_before_finish(fnol,monkeypatch):
    from app.research_agent import decide
    s=state(fnol,'finish','');s.update(searches=2,retry_searches=2,
        verification_reason='Missing support for a policy restriction',
        research_history=[{'action':'clause_lookup','argument':'source','ok':True}])
    monkeypatch.setattr('app.research_agent.missing_evidence',lambda s:[])
    class Capture:
        def call(self,state,agent,payload):
            available=payload['response_format']['json_schema']['schema']['properties']['action']['enum']
            assert 'finish' not in available
            return {'action':'corpus_search','argument':'vehicle use restrictions','purpose':'Address verifier feedback'}
    assert decide(s,Capture())['action']=='corpus_search'

def test_cli_calls_refusal_a_refusal():
    from app.cli import event_line
    e={'agent':'analysis','step':'tool','details':{'tool':'corpus_search','observation':{'error':'Repeated call refused.'}}}
    assert 'tool refused' in event_line(e)

def test_cli_does_not_label_abstention_verified(capsys):
    from app.cli import show_result
    show_result({'run_id':'test','result':{'verified':False,'citations':[]}}, {})
    output=capsys.readouterr().out
    assert 'HUMAN REVIEW REQUIRED' in output
    assert 'VERIFIED ADVICE' not in output
