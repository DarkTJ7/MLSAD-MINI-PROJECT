"""Transparent deterministic metric proxies; no fabricated LLM judge scores."""
import argparse
import json
import time
import os
from pathlib import Path
from app.agents import run_local, evidence
from app.retrieval import Corpus, index_corpus
from app.config import ROOT
from app.quality import sample_score

def score(state,case):
    result=state['proposed'];citations=result['citations']
    by_id={p['clause_id']:p for p in state.get('passages',[])}
    supported=sum(bool(c['clause_id'] in by_id and c['quote'] in by_id[c['clause_id']]['text']) for c in citations)
    faithful=int(all(result.get(k)==v for k,v in case['expected'].items()))
    expected={p['clause_id'] for p in case.get('support_passages',[])}
    retrieved=set(by_id)
    return {'groundedness':supported/len(citations) if citations else None,
            'context_relevance':len(expected & retrieved)/len(retrieved) if retrieved and expected else None,
            'faithfulness':faithful,
            'hallucination_rate':1-supported/len(citations) if citations else None,
            'reference_recall':len(expected & retrieved)/len(expected) if expected else None,
            'verified':int(result['verified'])}

def evaluate():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='results/evaluation_v5.json')
    parser.add_argument('--prompt-variant',choices=('v5a','v5b'),default='v5b')
    parser.add_argument('--case-id',action='append',dest='case_ids',help='Repeat to select matched scenarios')
    args=parser.parse_args()
    os.environ['RESEARCH_PROMPT_VARIANT']=args.prompt_variant
    index_corpus();corpus=Corpus()
    cases=[json.loads(x) for x in (ROOT/'evaluation/scenarios.jsonl').read_text().splitlines()]
    if args.case_ids:
        unknown=set(args.case_ids)-{case['id'] for case in cases}
        if unknown:parser.error('Unknown case ID(s): '+', '.join(sorted(unknown)))
        cases=[case for case in cases if case['id'] in set(args.case_ids)]
    results=[]
    for case in cases:
        fnol=dict(case['fnol'],retrieval_version='v5')
        started=time.monotonic();state=run_local(fnol,case['id'],corpus=corpus)
        previous=os.environ.get('QUALITY_SAMPLE_RATE')
        os.environ['QUALITY_SAMPLE_RATE']='1'
        quality=sample_score(state)
        if previous is None:os.environ.pop('QUALITY_SAMPLE_RATE',None)
        else:os.environ['QUALITY_SAMPLE_RATE']=previous
        results.append({'id':case['id'],'metrics':score(state,case),'seconds':time.monotonic()-started,
                        'result':state['proposed'],'events':state['events'],
                        'semantic_quality':quality,
                        'cost_usd':sum(e.get('cost_usd',0) for e in state['events'])})
    keys=['groundedness','context_relevance','faithfulness','hallucination_rate','reference_recall','verified']
    summary={}
    counts={}
    for key in keys:
        values=[r['metrics'][key] for r in results if r['metrics'][key] is not None]
        summary[key]=sum(values)/len(values) if values else None
        counts[key]=len(values)
    summary['cost_per_100_runs_usd']=sum(r['cost_usd'] for r in results)/len(results)*100
    semantic_summary={}
    for key in ('groundedness','context_relevance','faithfulness','hallucination_rate'):
        values=[r['semantic_quality'].get(key) for r in results if r['semantic_quality'].get(key) is not None]
        semantic_summary[key]={'mean':sum(values)/len(values) if values else None,'n':len(values)}
    output={'version':'v5','prompt_variant':args.prompt_variant,
            'case_ids':[case['id'] for case in cases], 'mode':os.getenv('MODEL_MODE','stub'),
            'model_id':os.getenv('MODEL_ID',''),
            'safety_required':os.getenv('SAFETY_REQUIRED','false'),'metric_kind':'structured references and citation proxies; semantic evidence in each event',
            'summary':summary,'semantic_summary':semantic_summary,'metric_denominators':counts,'runs':results}
    path=ROOT/args.output;path.parent.mkdir(exist_ok=True,parents=True)
    path.write_text(json.dumps(output,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__=='__main__': evaluate()
