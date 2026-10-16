"""Independent evidence-claim verification. Unavailable service fails closed."""
import os
import httpx
from .http_client import post
from functools import lru_cache

def safety_url():return os.getenv('SAFETY_URL','').rstrip('/')
def scan_text(text):
    if not safety_url():
        if os.getenv('SAFETY_REQUIRED','true').lower()=='true':raise RuntimeError('Safety service required')
        return {'blocked':False,'method':'lexical-only-development-mode'}
    return _scan(safety_url(),text)

@lru_cache(maxsize=512)
def _scan(url,text):
    response=post(url+'/screen',json={'text':text},timeout=float(os.getenv('SAFETY_TIMEOUT_SECONDS','15')))
    response.raise_for_status();return response.json()

def verify_claims(state):
    if not safety_url():
        if os.getenv('SAFETY_REQUIRED','true').lower()=='true':return {'passed':False,'reason':'semantic_service_missing'}
        return {'passed':True,'method':'development-exact-checks-only','claims':[]}
    result=state['proposed'];citations=result['citations']
    premise=' '.join(c['quote'] for c in citations)
    kind=result['classification']
    hypotheses=[{'own_damage':'The policy covers accidental damage to the insured vehicle.',
                 'theft':'The policy covers theft of the insured vehicle.',
                 'third_party':'The policy covers legal liability for injury to third parties.',
                 'total_loss':'A vehicle is a constructive total loss when repair costs exceed 75% of its IDV.'}[kind]]
    if 'restricted_use' in state.get('risk',[]):hypotheses.append('The policy contains restrictions on the use of the insured vehicle.')
    if 'intoxication' in state.get('risk',[]):hypotheses.append('Damage while the driver is under the influence of alcohol is excluded.')
    if 'breakdown' in state.get('risk',[]):hypotheses.append('Mechanical breakdown is excluded.')
    reports=[]
    for hypothesis in hypotheses:
        chosen=premise
        # Evaluate against the relevant clause, not an arbitrary concatenation of
        # covers, exclusions and claims procedures with unrelated modifiers.
        import re
        if hypothesis==hypotheses[0]:
            pattern={'own_damage':r'accidental external means','theft':r'by burglary housebreaking or theft',
                     'third_party':r'legally liable','total_loss':r'exceeds 75%'}[kind]
            matching=[c['quote'] for c in citations if re.search(pattern,c['quote'],re.I)]
            if matching:chosen=' '.join(matching)
        if hypothesis=='The policy contains restrictions on the use of the insured vehicle.':
            chosen=' '.join(c['quote'] for c in citations if 'limitations as to use' in c['quote'].lower())
        elif 'alcohol is excluded' in hypothesis:
            chosen=' '.join(c['quote'] for c in citations if 'intoxicating' in c['quote'].lower())
        elif hypothesis=='Mechanical breakdown is excluded.':
            chosen=' '.join(c['quote'] for c in citations if 'mechanical or electrical breakdown' in c['quote'].lower())
        response=post(safety_url()+'/entail',json={'premise':chosen,'hypothesis':hypothesis},
                            timeout=float(os.getenv('SAFETY_TIMEOUT_SECONDS','15')))
        response.raise_for_status()
        reports.append({'hypothesis':hypothesis,**response.json()})
    return {'passed':all(x['supported'] for x in reports),'claims':reports,'method':'independent-nli'}
