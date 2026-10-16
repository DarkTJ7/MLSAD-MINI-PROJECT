"""Reference-free quality scoring of a reproducible sample of live runs."""
import hashlib
import os
import httpx
from .http_client import post
from .semantic import safety_url
from .telemetry import QUALITY

def sample_score(state):
    rate=float(os.getenv('QUALITY_SAMPLE_RATE','.25'))
    selected=int(hashlib.sha256(state['run_id'].encode()).hexdigest()[:8],16)/0xffffffff<rate
    if not selected:return {'sampled':False}
    report={'sampled':True,'method':'reference-free-nli-and-embedding-v1'}
    claims=state.get('semantic_report',{}).get('claims',[])
    if claims:
        entailments=[c.get('scores',{}).get('entailment',0) for c in claims]
        report.update(groundedness=sum(entailments)/len(claims),
                      faithfulness=sum(c['supported'] for c in claims)/len(claims),
                      hallucination_rate=sum(not c['supported'] for c in claims)/len(claims))
    else:
        report.update(groundedness=None,faithfulness=None,hallucination_rate=None)
    report['context_relevance']=None
    if safety_url() and state.get('passages'):
        try:
            response=post(safety_url()+'/relevance',json={'query':state['fnol']['description'],
                'passages':[p['text'] for p in state['passages']]},timeout=15)
            response.raise_for_status();report['context_relevance']=response.json()['mean_cosine']
        except Exception:report['error']='relevance_service_unavailable'
    for metric in ('groundedness','faithfulness','hallucination_rate','context_relevance'):
        if report[metric] is not None:QUALITY.labels(metric).observe(report[metric])
    return report
